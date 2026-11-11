"""
Альтернативная инициализация данных для Модуля 1 через STAC (Planetary Computer).
Скачивает снимки Sentinel-2 L2A за июнь–август 2019–2020, обрезает по AOI (6.5–6.7 E, 49.7–49.8 N), 
перепроецирует в EPSG:25832,  передаёт углы солнца из STAC напрямую в process_scene (без MTD_TL.xml).
"""

import pystac_client
import planetary_computer
import rioxarray
import numpy as np
import rasterio
from rasterio.warp import transform_geom
from rasterio.enums import Resampling
from shapely.geometry import box, mapping
from pathlib import Path
from typing import Optional

from run_m1_local import load_config, process_scene


def fetch_data_stac_year(
    cfg: dict,
    year: int,
    max_cloud: float = 20.0,
    max_scenes_per_year: int = 10,
    months: Optional[list[int]] = None,
    target_epsg: int = 25832,
) -> list[dict]:
    """
    Ищет снимки Sentinel-2 L2A за указанный год, перепроецирует в target_epsg,
    обрезает по AOI, выполняет SCS+C через process_scene.
    Возвращает только сцены с scsc_processed=1.
    """
    aoi_cfg = cfg['aoi']
    aoi_wgs84 = box(
        aoi_cfg['lon_min'], aoi_cfg['lat_min'],
        aoi_cfg['lon_max'], aoi_cfg['lat_max']
    )

    months = months or [6, 7, 8]
    date_range = f"{year}-01-01/{year}-12-31"

    catalog = pystac_client.Client.open(
        "https://planetarycomputer.microsoft.com/api/stac/v1",
        modifier=planetary_computer.sign_inplace,
    )

    search = catalog.search(
        collections=["sentinel-2-l2a"],
        bbox=list(aoi_wgs84.bounds),
        datetime=date_range,
        query={"eo:cloud_cover": {"lt": max_cloud}},
        max_items=max_scenes_per_year * 20,
    )

    items = list(search.items())
    items = [it for it in items if it.datetime.month in months]
    print(f"[{year}] STAC найдено летних сцен (cloud < {max_cloud}%): {len(items)}")

    results = []
    raw_dir = Path(cfg['paths']['raw_dir'])
    raw_dir.mkdir(parents=True, exist_ok=True)

    for item in items:
        if len(results) >= max_scenes_per_year:
            break

        scene_id = item.id
        print(f"  Обработка: {scene_id} ({item.datetime.strftime('%Y-%m-%d')})")

        try:
            if "s2:mean_solar_zenith" not in item.properties or \
               "s2:mean_solar_azimuth" not in item.properties:
                print("    ⚠️ Пропуск: нет углов солнца в STAC Item")
                continue

            sun_zenith_rad = np.deg2rad(item.properties["s2:mean_solar_zenith"])
            sun_azimuth_rad = np.deg2rad(item.properties["s2:mean_solar_azimuth"])

            # Извлекаем BOA_ADD_OFFSET из метаданных STAC
            # Теория: Planetary Computer хранит поправку в свойстве 's2:boa_add_offset'.
            # Если его нет (старые сцены), используем 0. Приводим к float.
            boa_offset = float(item.properties.get("s2:boa_add_offset", 0))

            # --- 1. Загрузка B04 (10 м) ---
            b04_da = rioxarray.open_rasterio(
                item.assets["B04"].href, chunks=True
            ).squeeze("band", drop=True)

            # --- 2. Обрезка по AOI В РОДНОЙ ПРОЕКЦИИ СНИМКА (UTM) ---
            # Переводим координаты AOI в систему координат снимка
            aoi_native = transform_geom(
                'EPSG:4326', b04_da.rio.crs, mapping(aoi_wgs84)
            )
            coords = aoi_native['coordinates'][0]
            bounds = (
                min(c[0] for c in coords), min(c[1] for c in coords),
                max(c[0] for c in coords), max(c[1] for c in coords),
            )


            # Обрезаем! Теперь Dask знает, что нужно скачать только этот кусочек.
            b04_crop = b04_da.rio.clip_box(*bounds)
            print(f"DEBUG CRS снимка: {b04_da.rio.crs}")


            # --- 3. РЕПРОЕЦИРОВАНИЕ (уже обрезанного кусочка!) в EPSG:25832 ---
            b04_crop = b04_crop.rio.reproject(f"EPSG:{target_epsg}")


            # --- 4. То же самое для B08, B12, SCL ---
            channels = {}
            for band in ["B08", "B12", "SCL"]:
                da = rioxarray.open_rasterio(
                    item.assets[band].href, chunks=True
                ).squeeze("band", drop=True)
                
                # Сначала обрезаем в родной проекции
                da_crop = da.rio.clip_box(*bounds)
                
                # Потом репроецируем обрезанный кусочек
                da_crop = da_crop.rio.reproject(f"EPSG:{target_epsg}")
                
                # Выравниваем сетку по B04
                resampling = (
                    Resampling.nearest
                    if band == "SCL"
                    else Resampling.bilinear
                )
                channels[band] = da_crop.rio.reproject_match(
                    b04_crop, resampling=resampling
                )

            # --- 4. Сохранение во временные файлы ---
            profile = {
                'height': b04_crop.shape[0],
                'width': b04_crop.shape[1],
                'count': 1,
                'crs': b04_crop.rio.crs,
                'transform': b04_crop.rio.transform(),
                'nodata': 0.0,
            }

            for name, arr, dtype in [
                ("B04", b04_crop.values.astype(np.float32), 'float32'),
                ("B08", channels["B08"].values.astype(np.float32), 'float32'),
                ("B12", channels["B12"].values.astype(np.float32), 'float32'),
                ("SCL", channels["SCL"].values.astype(np.int16), 'int16'),
            ]:
                p = profile.copy()
                p['dtype'] = dtype
                p['nodata'] = 0
                with rasterio.open(raw_dir / f"{scene_id}_{name}.tif", 'w', **p) as dst:
                    dst.write(arr, 1)

            # --- 5. SCS+C через process_scene с углами из STAC ---
            result = process_scene(
                scene_id, cfg,
                sun_angles=(sun_zenith_rad, sun_azimuth_rad),
                boa_offset=boa_offset, # <--- ДОБАВЛЕНО
            )

            # --- Очистка памяти Dask ---
            b04_da.close()
            for ch in channels.values():
                ch.close()
            b04_crop.close() # Если у crop остался открытый файл-дескриптор

            if result.get('scsc_processed') == 1:
                print(f"    ✅ SCS+C OK (C_B04={result.get('scsc_C_B04', 'N/A')})")
                results.append(result)
            else:
                print("    ⚠️ SCS+C не прошёл (scsc_processed=0)")

            # Удаляем файлы этой сцены, так как она не прошла калибровку
            for f in raw_dir.glob(f"{scene_id}_*.tif"):
                f.unlink()
            for f in Path(cfg['paths']['output_dir']).glob(f"{scene_id}_*.tif"):
                f.unlink()

        except Exception as e:
            print(f"    ❌ Ошибка: {e}")
            continue

    print(f"[{year}] Итого: {len(results)}/{max_scenes_per_year} сцен прошли SCS+C")
    return results


def fetch_data_stac(
    cfg: dict,
    years: Optional[list[int]] = None,
    max_cloud: float = 20.0,
    max_scenes_per_year: int = 10,
    months: Optional[list[int]] = None,
    target_epsg: int = 25832,
) -> list[dict]:
    """
    Обёртка: цикл по годам, перепроецирование в target_epsg.
    По умолчанию: 2019–2020, июнь–август, EPSG:25832.
    """
    years = years or [2019, 2020]
    months = months or [6, 7, 8]

    all_results = []
    for year in years:
        print(f"\n{'='*60}\nГод {year} (месяцы {months}, EPSG:{target_epsg})\n{'='*60}")
        results = fetch_data_stac_year(
            cfg, year,
            max_cloud=max_cloud,
            max_scenes_per_year=max_scenes_per_year,
            months=months,
            target_epsg=target_epsg,
        )
        all_results.extend(results)

    print(f"\n📊 ВСЕГО за {len(years)} лет: {len(all_results)} сцен прошли SCS+C")
    return all_results


if __name__ == "__main__":
    cfg = load_config("config.yaml")

    # === ПАРАМЕТРЫ ПОИСКА ===
    results = fetch_data_stac(
        cfg,
        years=[2019, 2020],              # только 2019–2020
        max_cloud=15.0,                   # облачность сцены, %
        max_scenes_per_year=5,            # сколько успешных сцен на каждый год
        months=[6, 7, 8],                 # июнь, июль, август
        target_epsg=25832,                # перепроецирование в EPSG:25832
    )

    import pandas as pd
    if results:
        df = pd.DataFrame(results)
        df.to_csv("m1_stac_audit.csv", index=False)
        print("\nАудит сохранён: m1_stac_audit.csv")
        print(df[['scene_id', 'scsc_C_B04', 'scsc_C_B08', 'scsc_C_B12']])