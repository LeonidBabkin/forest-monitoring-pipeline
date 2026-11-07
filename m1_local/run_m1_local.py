"""Оркестратор одной сцены Sentinel-2: SCS+C.""" 
import yaml
import numpy as np
import rasterio
import pandas as pd
from pathlib import Path
from scipy.ndimage import binary_dilation
from rasterio.warp import Resampling, transform_geom
from rasterio.mask import mask as rio_mask
from shapely.geometry import box, mapping

from m1_scsc_local import (
    reproject_to_target_grid, compute_slope_aspect,
    compute_cos_i, calibrate_c, apply_scsc, gate_pearson,
)
from parse_metadata import parse_sun_angles


def load_config(path: str = 'config.yaml') -> dict:
    with open(path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)


def crop_to_aoi(src_path: Path, cfg: dict) -> tuple[np.ndarray, dict]:
    """Мастер-сетка по B04 (обрезает по AOI)."""
    a = cfg['aoi']
    wgs84_geom = box(a['lon_min'], a['lat_min'], a['lon_max'], a['lat_max'])
    with rasterio.open(src_path) as src:
        projected_geom = transform_geom('EPSG:4326', src.crs, mapping(wgs84_geom))
        out_image, out_transform = rio_mask(src, [projected_geom], crop=True, filled=True)
        profile = src.profile.copy()
        profile.update({
            'height': out_image.shape[1],
            'width': out_image.shape[2],
            'transform': out_transform,
            'crs': src.crs,
        })
    return out_image[0].astype(np.float32), profile


def process_scene(scene_id: str, cfg: dict) -> dict:
    raw = Path(cfg['paths']['raw_dir'])
    out = Path(cfg['paths']['output_dir'])
    out.mkdir(parents=True, exist_ok=True)

    # 1. Мастер-геометрия по B04
    b4, prof = crop_to_aoi(raw / f"{scene_id}_B04.tif", cfg)

    # 2. Все каналы приводим к мастер-сетке B04 (устраняет half-pixel shift)
    b8 = reproject_to_target_grid(str(raw / f"{scene_id}_B08.tif"), prof, Resampling.bilinear)
    b12 = reproject_to_target_grid(str(raw / f"{scene_id}_B12.tif"), prof, Resampling.bilinear)
    scl = reproject_to_target_grid(str(raw / f"{scene_id}_SCL.tif"), prof, Resampling.nearest)
    dem = reproject_to_target_grid(cfg['paths']['dem_path'], prof, Resampling.bilinear)

    # 3. Морфометрия и углы Солнца
    slope, aspect = compute_slope_aspect(dem, prof['transform'])
    sun_zenith, sun_azimuth = parse_sun_angles(raw / f"{scene_id}_MTD_TL.xml")

    # 4. Маски дефектов (SCL) + дилатация
    bad_mask = np.isin(scl.astype(int), [0, 1, 3, 8, 9, 10, 11])
    dilation_px = cfg['scsc'].get('cloud_dilation_pixels', 0)
    if dilation_px > 0:
        size = 2 * dilation_px + 1
        bad_mask = binary_dilation(bad_mask, structure=np.ones((size, size)))
    cloud_free_mask = ~bad_mask

    # 5. NoData
    nodata_mask = (b4 <= 0) | (b8 <= 0) | (b12 <= 0)
    valid_data_mask = ~nodata_mask

    # 6. NDVI
    denom = b8 + b4
    safe_denom = np.where(denom == 0, 1e-6, denom)
    ndvi = (b8 - b4) / safe_denom
    slope_deg = np.rad2deg(slope)

    # 7. Маска леса
    cos_i = compute_cos_i(sun_zenith, sun_azimuth, slope, aspect)
    forest_mask = (ndvi > cfg['scsc']['ndvi_threshold']) & \
                  (slope_deg > cfg['scsc']['slope_threshold_deg']) & \
                  cloud_free_mask & valid_data_mask & (cos_i > 0.4)

    if cfg['scsc'].get('use_b4_filter', False):
        forest_mask &= (b4 < cfg['scsc']['b4_filter_max'])


    # 8. SCS+C по каналам
    results = {'scene_id': scene_id}
    all_valid = 1
    for band_name, dn in zip(['B04', 'B08', 'B12'], [b4, b8, b12]):
        print(f"DEBUG в цикле [{band_name}]: forest_mask sum = {np.sum(forest_mask)}, cos_i max = {np.nanmax(cos_i)}")
        C, _, _, has = calibrate_c(dn, cos_i, forest_mask, cfg['scsc'])
        corrected = apply_scsc(dn, cos_i, sun_zenith, slope, C, forest_mask)
        corrected[nodata_mask] = 0.0
        r, p = gate_pearson(corrected, cos_i, forest_mask)

        results[f'scsc_C_{band_name}'] = C
        results[f'scsc_r_{band_name}'] = r
        results[f'scsc_p_{band_name}'] = p
        results[f'scsc_gate_ran_{band_name}'] = has
        all_valid = all_valid and has

        out_path = out / f"{scene_id}_{band_name}_corr.tif"
        prof.update(dtype='float32', count=1, compress='lzw', nodata=0.0)
        with rasterio.open(out_path, 'w', **prof) as dst:
            dst.write(corrected.astype(np.float32), 1)

    results['scsc_processed'] = int(all_valid)
    return results


if __name__ == '__main__':
    cfg = load_config()
    scene_ids = ['T31UGR_20210601T104021']
    rows = [process_scene(sid, cfg) for sid in scene_ids]
    pd.DataFrame(rows).to_csv('m1_calibration_audit.csv', index=False)
    print(pd.DataFrame(rows).T)