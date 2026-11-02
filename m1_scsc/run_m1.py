import ee
import yaml
import math
from m1_scsc import mask_clouds, get_sun_angles, apply_production_scsc

def load_config(path='config.yaml'):
    with open(path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)

def build_aoi(cfg):
    a = cfg['aoi']
    return ee.Geometry.Rectangle([a['lon_min'], a['lat_min'], a['lon_max'], a['lat_max']])

def run(start_year=2018, end_year=2026):
    # Убедитесь, что ID проекта ваш!
    ee.Initialize(project='ee-learning-trier') 
    cfg = load_config()
    aoi = build_aoi(cfg)

    # Загружаем ваш загруженный растр SRTM 30м из Assets
    # dem = ee.Image('projects/ee-learning-trier/assets/dem_srtm_30m').select(0)
        # Используем встроенную NASADEM (30 метров)
    dem = ee.Image('NASA/NASADEM_HGT/001').select('elevation')
    
    # Считаем уклон и экспозицию (GEE вернет их в градусах)
    slope_deg = ee.Terrain.slope(dem)
    aspect_deg = ee.Terrain.aspect(dem)
    
    # Переводим в радианы для нашего модуля M1
    slope = slope_deg.multiply(math.pi / 180.0)
    aspect = aspect_deg.multiply(math.pi / 180.0)



    scsc_params = cfg['scsc']

    for year in range(start_year, end_year + 1):
        start = ee.Date.fromYMD(year, 5, 1)
        end = ee.Date.fromYMD(year, 9, 30)

        print(f"Обработка {year} года...")

        collection = (
            ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED')
            .filterBounds(aoi)
            .filterDate(start, end)
            .filter(ee.Filter.lt('CLOUDY_PIXEL_PERCENTAGE', 40))
            .map(mask_clouds)
            .map(get_sun_angles)
            .map(lambda img: apply_production_scsc(img, slope, aspect, aoi, scsc_params))
        )

        def extract_props(img):
            img = ee.Image(img)
            return ee.Feature(None, {
                'system:index': img.get('system:index'),
                'scsc_processed': img.get('scsc_processed'),
                'scsc_C_B4': img.get('scsc_C_B4'),
                'scsc_C_B8': img.get('scsc_C_B8'),
                'scsc_C_B12': img.get('scsc_C_B12'),
                'year': year
            })

        fc = ee.FeatureCollection(collection.map(extract_props))

        task = ee.batch.Export.table.toDrive(
            collection=fc,
            description=f'm1_calibration_{year}',
            folder='m1_audit',
            fileFormat='CSV'
        )
        task.start()
        print(f"Задача на экспорт {year} успешно запущена.")

if __name__ == '__main__':
    for year in range(2018, 2027):
        run(start_year=year, end_year=year)