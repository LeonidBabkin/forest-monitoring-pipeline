import ee
import pytest
from m1_scsc import apply_production_scsc, get_sun_angles

# ee.Initialize(project='your-gee-project')   # ЗАМЕНИТЕ
ee.Initialize(project='ee-learning-trier')  


AOI = ee.Geometry.Rectangle([6.5, 49.7, 6.7, 49.8])
SLOPE = ee.Image.constant(0.1)      # ~5.7°
ASPECT = ee.Image.constant(0.0)


def test_scsc_processed_zero_on_empty_scene():
    """Сцена без валидных пикселей (100% облачность) → scsc_processed=0, C=0.5."""
    empty = (ee.Image.constant([0, 0, 0])
             .rename(['B4', 'B8', 'B12'])
             .updateMask(ee.Image.constant(0))   # всё под маской
             .set({
                 'MEAN_SOLAR_AZIMUTH_ANGLE': 180,
                 'MEAN_SOLAR_ZENITH_ANGLE': 45,
                 'sun_azimuth_rad': 3.14159,
                 'sun_zenith_rad': 0.7854,
             })
             .clip(AOI))
    out = apply_production_scsc(empty, SLOPE, ASPECT, AOI)
    # [FIX 1] было == 1; теперь 0 — соответствует названию теста и Контракту 1
    assert out.get('scsc_processed').getInfo() == 0, \
        "При пустой сцене scsc_processed должен быть 0 (сбой калибровки)"
    # C должен быть дефолтным 0.5
    c = ee.Number(out.get('scsc_C_B4')).getInfo()
    assert c == 0.5, f"При пустой сцене C должен быть 0.5, получено {c}"
    # [FIX 2] sentinel r/p = -999, gate_ran = 0
    r = ee.Number(out.get('scsc_r_B4')).getInfo()
    assert r == -999.0, f"При пустой сцене r должен быть sentinel -999, получено {r}"
    gate = ee.Number(out.get('scsc_gate_ran_B4')).getInfo()
    assert gate == 0, f"gate_ran должен быть 0 при пустой сцене, получено {gate}"


def test_scsc_processed_one_on_valid_scene():
    """На валидной реальной сцене scsc_processed=1 и C в (0,5) для всех каналов."""
    scene = (ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED')
             .filterBounds(AOI)
             .filterDate('2021-06-01', '2021-09-30')
             .filter(ee.Filter.lt('CLOUDY_PIXEL_PERCENTAGE', 20))
             .first())
    if scene is None or scene.getInfo() is None:
        pytest.skip("Нет сцены для теста — пропуск")
    scene = get_sun_angles(scene)
    out = apply_production_scsc(scene, SLOPE, ASPECT, AOI)
    assert out.get('scsc_processed').getInfo() == 1, \
        "На валидной сцене scsc_processed должен быть 1"
    for band in ['B4', 'B8', 'B12']:
        c = ee.Number(out.get(f'scsc_C_{band}')).getInfo()
        assert 0 < c < 5, f"C_{band} вне диапазона (0,5): {c}"
        gate = ee.Number(out.get(f'scsc_gate_ran_{band}')).getInfo()
        assert gate == 1, f"gate_ran_{band} должен быть 1 на валидной сцене"


def test_scsc_c_in_valid_range():
    """Совместимость: C в (0,5) на реальной сцене (дублирует проверку выше)."""
    scene = (ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED')
             .filterBounds(AOI)
             .filterDate('2021-06-01', '2021-09-30')
             .filter(ee.Filter.lt('CLOUDY_PIXEL_PERCENTAGE', 20))
             .first())
    if scene is None or scene.getInfo() is None:
        pytest.skip("Нет сцены для теста — пропуск")
    scene = get_sun_angles(scene)
    out = apply_production_scsc(scene, SLOPE, ASPECT, AOI)
    for band in ['B4', 'B8', 'B12']:
        c = ee.Number(out.get(f'scsc_C_{band}')).getInfo()
        assert 0 < c < 5, f"C_{band} вне диапазона (0,5): {c}"