import numpy as np
import rasterio
from pathlib import Path
from rasterio.warp import reproject, Resampling
from run_m1_local import load_config, crop_to_aoi
from m1_scsc_local import reproject_to_target_grid, compute_slope_aspect, compute_cos_i
from parse_metadata import parse_sun_angles

def check():
    cfg = load_config()
    raw = Path(cfg['paths']['raw_dir'])
    scene_id = 'T31UGR_20210601T104021'

    b4, prof = crop_to_aoi(raw / f"{scene_id}_B04.tif", cfg)
    b8 = reproject_to_target_grid(str(raw / f"{scene_id}_B08.tif"), prof, Resampling.bilinear)
    scl = reproject_to_target_grid(str(raw / f"{scene_id}_SCL.tif"), prof, Resampling.nearest)
    dem = reproject_to_target_grid(cfg['paths']['dem_path'], prof, Resampling.bilinear)

    slope, aspect = compute_slope_aspect(dem, prof['transform'])
    sun_zenith, sun_azimuth = parse_sun_angles(raw / f"{scene_id}_MTD_TL.xml")
    cos_i = compute_cos_i(sun_zenith, sun_azimuth, slope, aspect)

    denom = b8 + b4
    safe_denom = np.where(denom == 0, 1e-6, denom)
    ndvi = (b8 - b4) / safe_denom
    slope_deg = np.rad2deg(slope)

    # Маска леса
    mask = (ndvi > cfg['scsc']['ndvi_threshold']) & \
           (slope_deg > cfg['scsc']['slope_threshold_deg']) & \
           (cos_i > 0.4)

    # Смотрим распределение значений B04 в маске
    dn_in_mask = b4[mask]
    print(f"Пикселей в маске: {len(dn_in_mask)}")
    print(f"B04 в маске: min={np.min(dn_in_mask)}, max={np.max(dn_in_mask)}, mean={np.mean(dn_in_mask)}")
    print(f"  99-й перцентиль: {np.percentile(dn_in_mask, 99)}")
    print(f"  1-й перцентиль: {np.percentile(dn_in_mask, 1)}")

    # Смотрим, что за классы SCL попали в маску
    scl_in_mask = scl[mask]
    unique, counts = np.unique(scl_in_mask, return_counts=True)
    print("\nКлассы SCL в маске:")
    for u, c in zip(unique, counts):
        print(f"  Класс {int(u)}: {c} пикселей ({c/len(dn_in_mask)*100:.1f}%)")

if __name__ == '__main__':
    check()