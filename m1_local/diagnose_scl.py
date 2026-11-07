"""Диагностика риска класса 2 (Dark Area) в forest_mask."""
from pathlib import Path
import numpy as np
from rasterio.warp import Resampling
from run_m1_local import load_config, crop_to_aoi, reproject_to_target_grid


def diagnose(scene_id: str, cfg: dict) -> None:
    raw = Path(cfg['paths']['raw_dir'])
    b4, prof = crop_to_aoi(raw / f"{scene_id}_B04.tif", cfg)
    b8 = reproject_to_target_grid(str(raw / f"{scene_id}_B08.tif"), prof, Resampling.bilinear)
    scl = reproject_to_target_grid(str(raw / f"{scene_id}_SCL.tif"), prof, Resampling.nearest)

    denom = b8 + b4
    safe_denom = np.where(denom == 0, 1e-6, denom)
    ndvi = (b8 - b4) / safe_denom
    forest = ndvi > cfg['scsc']['ndvi_threshold']

    total = int(forest.sum())
    c2 = int((forest & (scl.astype(int) == 2)).sum())
    share = c2 / max(total, 1)

    print(f"Сцена: {scene_id}")
    print(f"Лесных пикселей: {total}")
    print(f"Класс 2 (Dark Area): {c2} ({share*100:.2f}%)")
    if share > 0.05:
        print("⚠️ РИСК >5%. Включите use_b4_filter: true в config.yaml.")
    else:
        print("✅ Риск <5%. C защищен.")


if __name__ == '__main__':
    cfg = load_config()
    diagnose('T32ULA_20210601T104021', cfg)