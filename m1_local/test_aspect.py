"""Unit-тест: склон на север → aspect ≈ 0°."""
import numpy as np
import rasterio
from rasterio.transform import from_origin
from m1_scsc_local import compute_slope_aspect


def test_aspect_north():
    width = height = 5
    dem = np.zeros((height, width), dtype=np.float32)
    for r in range(height):
        dem[r, :] = r * 10.0  # высоты растут к югу → склон на север
    transform = from_origin(500000, 5500000, 10, 10)
    slope, aspect = compute_slope_aspect(dem, transform)
    center_deg = np.rad2deg(aspect[2, 2])
    assert abs(center_deg) < 1.0 or abs(center_deg - 360) < 1.0, \
        f"Ожидался 0°/360° (Север), получено {center_deg}°"
    print(f"✅ PASSED: aspect = {center_deg:.1f}°")


if __name__ == '__main__':
    test_aspect_north()