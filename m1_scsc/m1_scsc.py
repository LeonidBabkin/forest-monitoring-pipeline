"""
Модуль M1 (production): посценовая поканальная топокоррекция SCS+C.
Версия 9.8.0 — Архитектурно исправленная.
"""
import ee
import math


def mask_clouds(image: ee.Image) -> ee.Image:
    """Облачная маска QA60 + s2cloudless (порог 40%)."""
    qa = image.select('QA60')
    cloud_bit = 1 << 10
    cirrus_bit = 1 << 11
    mask = qa.bitwiseAnd(cloud_bit).eq(0).And(qa.bitwiseAnd(cirrus_bit).eq(0))
    cloud_prob = ee.Image(image.select('MSK_CLDPRB')).lt(40)
    return image.updateMask(mask).updateMask(cloud_prob)


def get_sun_angles(image: ee.Image) -> ee.Image:
    """Извлечь солнечные углы из метаданных сцены и перевести в радианы."""
    sun_az = ee.Number(image.get('MEAN_SOLAR_AZIMUTH_ANGLE')).multiply(math.pi / 180)
    sun_zn = ee.Number(image.get('MEAN_SOLAR_ZENITH_ANGLE')).multiply(math.pi / 180)
    return image.set({'sun_azimuth_rad': sun_az, 'sun_zenith_rad': sun_zn})


def apply_production_scsc(
    image: ee.Image,
    slope: ee.Image,
    aspect: ee.Image,
    aoi: ee.Geometry,
    params: dict = None,
) -> ee.Image:
    """
    Посценовая поканальная топокоррекция SCS+C с гейтом приёмки.
    """
    if params is None:
        params = {}

    target_bands = params.get('target_bands', ['B4', 'B8', 'B12'])
    ndvi_thr = params.get('ndvi_threshold', 0.35)
    slope_thr_deg = params.get('slope_threshold_deg', 5.0)
    min_valid = params.get('min_valid_pixels', 100)
    c_default = params.get('c_default', 0.5)
    c_min = params.get('c_min', 0.0)
    c_max = params.get('c_max', 5.0)
    n_accept = params.get('acceptance_samples', 100)
    seed = params.get('acceptance_seed', 42)

    sun_az = ee.Number(image.get('sun_azimuth_rad'))
    sun_zn = ee.Number(image.get('sun_zenith_rad'))

    sun_zn_img = ee.Image.constant(sun_zn)
    sun_az_img = ee.Image.constant(sun_az)

    # 1. Считаем cos(i) на основе рельефа
    cos_i = (
        sun_zn_img.cos().multiply(slope.cos())
        .add(sun_zn_img.sin().multiply(slope.sin())
             .multiply(sun_az_img.subtract(aspect).cos()))
    ).rename('cosI')

    # 2. Считаем NDVI на родном разрешении 10 метров
    ndvi = image.normalizedDifference(['B8', 'B4']).rename('NDVI')
    slope_deg = slope.multiply(180.0 / math.pi)
    
    # 3. Создаем базовую маску леса и склонов (не привязанную к конкретному каналу)
    base_forest_slope_mask = ndvi.gt(ndvi_thr).And(slope_deg.gt(slope_thr_deg))

    # Геометрия для расчетов (просто AOI)
    scene_aoi = aoi 
    regression_image = ee.Image.constant(1).addBands(cos_i)

    calibration_metadata = ee.Dictionary({})
    output_image = image
    all_bands_valid = ee.Number(1)

    for band in target_bands:
        band_image = image.select(band)

        # 4. Итоговая маска = (лес+склон) И (есть данные в этом канале)
        valid_pixels_mask = base_forest_slope_mask.And(band_image.mask())

        # 5. Гейт: достаточно ли валидных пикселей
        pixel_count_check = valid_pixels_mask.reduceRegion(
            reducer=ee.Reducer.count(),
            geometry=scene_aoi,
            scale=params.get('regression_scale_m', 10),
            maxPixels=100000000,
        )
        has_pixels = ee.Number(pixel_count_check.values().get(0)).gt(min_valid)

        # 6. Регрессия
        reg_result = ee.Dictionary(ee.Algorithms.If(
            has_pixels,
            regression_image.addBands(band_image).updateMask(valid_pixels_mask).reduceRegion(
                reducer=ee.Reducer.linearRegression(numX=2, numY=1),
                geometry=scene_aoi,
                scale=params.get('regression_scale_m', 10),
                maxPixels=params.get('regression_max_pixels', 100000000),
                tileScale=4,
            ),
            ee.Dictionary({'coefficients': ee.Array([[0.0], [0.0001]])}),
        ))

        coefficients = ee.Array(reg_result.get('coefficients'))
        b = ee.Number(coefficients.get([0, 0]))
        a = ee.Number(coefficients.get([1, 0]))

        safe_a = ee.Number(ee.Algorithms.If(a.abs().gt(0.0001), a, 0.0001))
        c_calculated = b.divide(safe_a)

        # 7. Валидация C
        band_valid = has_pixels.And(c_calculated.gt(c_min)).And(c_calculated.lt(c_max))
        all_bands_valid = all_bands_valid.And(band_valid)

        c_value = ee.Number(ee.Algorithms.If(band_valid, c_calculated, c_default))

        # 8. Формула SCS+C
        numerator = sun_zn_img.cos().multiply(slope.cos()).add(c_value)
        denominator = cos_i.add(c_value)
        corrected_band = band_image.multiply(numerator.divide(denominator)).rename(f'{band}_corr')

        # 9. Гейт Пирсона
        test_samples = (
            corrected_band.addBands(cos_i)
            .updateMask(valid_pixels_mask)
            .sample(
                region=scene_aoi,
                scale=params.get('acceptance_scale_m', 10),
                numPixels=n_accept,
                seed=seed,
                tileScale=2,
            )
        )

        pearson_stats = ee.Dictionary(ee.Algorithms.If(
            has_pixels,
            test_samples.reduceColumns(
                reducer=ee.Reducer.pearsonsCorrelation(),
                selectors=[f'{band}_corr', 'cosI'],
            ),
            ee.Dictionary({'correlation': -999.0, 'p-value': -999.0}),
        ))

        r_value = ee.Number(pearson_stats.get('correlation'))
        p_value = ee.Number(pearson_stats.get('p-value'))

        calibration_metadata = calibration_metadata.combine(ee.Dictionary({
            f'scsc_C_{band}': c_value,
            f'scsc_r_{band}': r_value,
            f'scsc_p_{band}': p_value,
            f'scsc_gate_ran_{band}': ee.Number(ee.Algorithms.If(has_pixels, 1, 0)),
        }))

        output_image = output_image.addBands(corrected_band, None, True)

    calibration_metadata = calibration_metadata.set('scsc_processed', all_bands_valid)
    return output_image.set(calibration_metadata)