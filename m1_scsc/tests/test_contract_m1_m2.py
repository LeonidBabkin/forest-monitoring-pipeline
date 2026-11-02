import ee
import math
import pytest
from run_m1 import validate_slope_unit

# ee.Initialize(project='your-gee-project')   # ЗАМЕНИТЕ
ee.Initialize(project='ee-learning-trier')  # ЗАМЕНИТЕ




def test_slope_unit_radians_passthrough():
    slope = ee.Image.constant(0.1)
    cfg = {'dem': {'slope_unit': 'radians'}}
    out = validate_slope_unit(slope, cfg)
    # Безопасное извлечение первого пикселя из изображения
    val = out.reduceRegion(ee.Reducer.first(), ee.Geometry.Point([0,0]), 1).get('constant').getInfo()
    assert val == pytest.approx(0.1)


def test_slope_unit_degrees_converts():
    slope_deg = ee.Image.constant(5.0)
    cfg = {'dem': {'slope_unit': 'degrees'}}
    out = validate_slope_unit(slope_deg, cfg)
    expected = 5.0 * math.pi / 180.0
    val = out.reduceRegion(ee.Reducer.first(), ee.Geometry.Point([0,0]), 1).get('constant').getInfo()
    assert val == pytest.approx(expected, rel=1e-6)


def test_slope_unit_invalid_raises():
    slope = ee.Image.constant(0.1)
    cfg = {'dem': {'slope_unit': 'gradians'}}
    with pytest.raises(ValueError):
        validate_slope_unit(slope, cfg)