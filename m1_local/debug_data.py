import numpy as np
import rasterio
from pathlib import Path
from m1_scsc_local import compute_slope_aspect
from parse_metadata import parse_sun_angles
from rasterio.warp import reproject, Resampling

raw = Path('data/raw')
scene_id = 'T31UGR_20210601T104021'

# 1. Читаем B04 и B08
with rasterio.open(raw / f"{scene_id}_B04.tif") as src:
    b4 = src.read(1).astype(np.float32)
    prof = src.profile.copy()

with rasterio.open(raw / f"{scene_id}_B08.tif") as src:
    b8_src = src.read(1).astype(np.float32)
    prof8 = src.profile.copy()

# Проверяем, совпадают ли размеры. Если нет — перепроецируем B08
if b8_src.shape != b4.shape:
    b8 = np.empty_like(b4)
    reproject(source=b8_src, destination=b8,
              src_transform=prof8['transform'], src_crs=prof8['crs'],
              dst_transform=prof['transform'], dst_crs=prof['crs'],
              resampling=Resampling.bilinear)
else:
    b8 = b8_src

# 2. Считаем NDVI
denom = b8 + b4
safe_denom = np.where(denom == 0, 1e-6, denom)
ndvi = (b8 - b4) / safe_denom

print(f"=== ДИАГНОСТИКА ДАННЫХ ===")
print(f"NDVI max: {np.nanmax(ndvi):.3f} (должно быть > 0.35)")
print(f"NDVI mean: {np.nanmean(ndvi):.3f}")

# 3. Читаем DEM и считаем Slope
dem_path = Path('data/dem/dgm10_trier.tif')
with rasterio.open(dem_path) as src:
    dem_src = src.read(1).astype(np.float32)
    prof_dem = src.profile.copy()

dem = np.empty_like(b4)
reproject(source=dem_src, destination=dem,
          src_transform=prof_dem['transform'], src_crs=prof_dem['crs'],
          dst_transform=prof['transform'], dst_crs=prof['crs'],
          resampling=Resampling.bilinear)

slope_rad, aspect_rad = compute_slope_aspect(dem, prof['transform'])
slope_deg = np.rad2deg(slope_rad)

print(f"\nSlope max: {np.nanmax(slope_deg):.3f} (должно быть > 5.0)")
print(f"Slope mean: {np.nanmean(slope_deg):.3f}")

# 4. Проверяем маску леса (NDVI > 0.35 и slope > 5)
forest_mask = (ndvi > 0.35) & (slope_deg > 5.0)
print(f"\nПикселей с NDVI > 0.35: {np.sum(ndvi > 0.35)}")
print(f"Пикселей с slope > 5.0: {np.sum(slope_deg > 5.0)}")
print(f"Пикселей в forest_mask: {np.sum(forest_mask)}")