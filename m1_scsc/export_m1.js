// 1. Задаем AOI и параметры
var aoi = ee.Geometry.Rectangle([6.5, 49.7, 6.7, 49.8]);
var startYear = 2018;
var endYear = 2026;

// 2. Загружаем SRTM (как мы делали в Python)
var srtm = ee.Image('CGIAR/SRTM90_V4').select('elevation');
var slope = ee.Terrain.slope(srtm).multiply(Math.PI / 180.0);
var aspect = ee.Terrain.aspect(srtm).multiply(Math.PI / 180.0);

// 3. Функция обработки одной сцены (аналог вашей apply_production_scsc)
var processScene = function(image) {
  // Облачная маска
  var qa = image.select('QA60');
  var mask = qa.bitwiseAnd(1 << 10).eq(0).and(qa.bitwiseAnd(1 << 11).eq(0));
  var cloudProb = image.select('MSK_CLDPRB').lt(40);
  image = image.updateMask(mask).updateMask(cloudProb);

  // Солнечные углы
  var sunAz = ee.Number(image.get('MEAN_SOLAR_AZIMUTH_ANGLE')).multiply(Math.PI / 180);
  var sunZn = ee.Number(image.get('MEAN_SOLAR_ZENITH_ANGLE')).multiply(Math.PI / 180);
  
  var sunZnImg = ee.Image.constant(sunZn);
  var sunAzImg = ee.Image.constant(sunAz);

  // cos(i)
  var cosI = sunZnImg.cos().multiply(slope.cos())
    .add(sunZnImg.sin().multiply(slope.sin()).multiply(sunAzImg.subtract(aspect).cos()))
    .rename('cosI');

  // Маска леса
  var ndvi = image.normalizedDifference(['B8', 'B4']).rename('NDVI');
  var slopeDeg = slope.multiply(180.0 / Math.PI);
  var forestMask = ndvi.gt(0.35).and(slopeDeg.gt(5.0));

  var bands = ['B4', 'B8', 'B12'];
  var allValid = ee.Number(1);
  var metadata = ee.Dictionary({});

  bands.forEach(function(band) {
    var bandImg = image.select(band);
    var validMask = forestMask.and(bandImg.mask()).and(bandImg.gt(0));

    // Считаем пиксели
    var count = validMask.reduceRegion({
      reducer: ee.Reducer.count(), geometry: aoi, scale: 90, maxPixels: 1e8
    }).get(band);
    
    var hasPixels = ee.Number(count).gt(100);
    
    // Регрессия
    var regImg = ee.Image.constant(1).addBands(cosI);
    var regResult = ee.Dictionary(ee.Algorithms.If(
      hasPixels,
      regImg.addBands(bandImg).updateMask(validMask).reduceRegion({
        reducer: ee.Reducer.linearRegression(2, 1), geometry: aoi, scale: 90, maxPixels: 1e8, tileScale: 4
      }),
      {coefficients: ee.Array([[0], [0.0001]])}
    ));

    var coeffs = ee.Array(regResult.get('coefficients'));
    var b = ee.Number(coeffs.get([0, 0]));
    var a = ee.Number(coeffs.get([1, 0]));
    var safeA = ee.Number(ee.Algorithms.If(a.abs().gt(0.0001), a, 0.0001));
    var cCalc = b.divide(safeA);
    
    var bandValid = hasPixels.and(cCalc.gt(0)).and(cCalc.lt(5));
    allValid = allValid.and(bandValid);
    
    var cValue = ee.Number(ee.Algorithms.If(bandValid, cCalc, 0.5));
    
    metadata = metadata.set('scsc_C_' + band, cValue);
  });

  return image.set(metadata).set('scsc_processed', allValid);
};

// 4. Обрабатываем коллекцию
var collection = ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED')
  .filterBounds(aoi)
  .filterDate(startYear + '-05-01', endYear + '-09-30')
  .filter(ee.Filter.lt('CLOUDY_PIXEL_PERCENTAGE', 40))
  .map(processScene);

// 5. Превращаем в таблицу для экспорта
var features = collection.map(function(img) {
  return ee.Feature(null, {
    'system:index': img.get('system:index'),
    'year': ee.Date(img.get('system:time_start')).get('year'),
    'scsc_processed': img.get('scsc_processed'),
    'scsc_C_B4': img.get('scsc_C_B4'),
    'scsc_C_B8': img.get('scsc_C_B8'),
    'scsc_C_B12': img.get('scsc_C_B12')
  });
});

// 6. Экспорт в Google Диск (ОДИН ФАЙЛ НА ВСЁ)
Export.table.toDrive({
  collection: features,
  description: 'M1_Audit_All_Years',
  folder: 'm1_audit_js',
  fileFormat: 'CSV'
});