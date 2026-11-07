import numpy as np
import rasterio
from pathlib import Path
from rasterio.warp import reproject, Resampling

raw = Path('data/raw')
scene_id = 'T31UGR_20210601T104021'

# Читаем B04 как эталон
with rasterio.open(raw / f"{scene_id}_B04.tif") as src:
    b4 = src.read(1).astype(np.float32)
    prof = src.profile.copy()

# Читаем B08 и B12 (с приведением к сетке B04)
def read_band(band_name):
    with rasterio.open(raw / f"{scene_id}_{band_name}.tif") as src:
        arr = src.read(1).astype(np.float32)
        p = src.profile.copy()
        if arr.shape != b4.shape:
            dst = np.empty_like(b4)
            reproject(source=arr, destination=dst,
                      src_transform=p['transform'], src_crs=p['crs'],
                      dst_transform=prof['transform'], dst_crs=prof['crs'],
                      resampling=Resampling.bilinear)
            return dst
        return arr

b8 = read_band('B08')
b12 = read_band('B12')

print("=== ПРОВЕРКА ЗНАЧЕНИЙ В КАНАЛАХ ===")
for name, arr in [('B04', b4), ('B08', b8), ('B12', b12)]:
    print(f"\nКанал {name}:")
    print(f"  Мин / Макс: {np.nanmin(arr):.4f} / {np.nanmax(arr):.4f}")
    print(f"  Среднее: {np.nanmean(arr):.4f}")
    
    # Считаем количество "плохих" пикселей
    n_nan = np.sum(np.isnan(arr))
    n_zero = np.sum(arr == 0)
    n_neg = np.sum(arr < 0)
    n_total = arr.size
    
    print(f"  NaN: {n_nan} ({n_nan/n_total*100:.1f}%)")
    print(f"  Ровно 0: {n_zero} ({n_zero/n_total*100:.1f}%)")
    print(f"  Отрицательные: {n_neg} ({n_neg/n_total*100:.1f}%)")