"""Парсинг углов Солнца из MTD_TL.xml (GRANULE)."""
import xml.etree.ElementTree as ET
import numpy as np
from pathlib import Path


def parse_sun_angles(mtd_tl_path: Path) -> tuple[float, float]:
    tree = ET.parse(mtd_tl_path)
    root = tree.getroot()
    mean_sun = root.find('.//Mean_Sun_Angle')
    if mean_sun is None:
        raise ValueError(f"Mean_Sun_Angle не найден в {mtd_tl_path}")
    zen_el = mean_sun.find('./ZENITH_ANGLE')
    azi_el = mean_sun.find('./AZIMUTH_ANGLE')
    if zen_el is None or azi_el is None:
        raise ValueError(f"ZENITH_ANGLE или AZIMUTH_ANGLE не найдены в {mtd_tl_path}")
    zenith_rad = np.deg2rad(float(zen_el.text))
    azimuth_rad = np.deg2rad(float(azi_el.text))
    return float(zenith_rad), float(azimuth_rad)