"""
Модуль M1 (personal project): посценовая поканальная топокоррекция SCS+C.
Математическое ядро фильтрации облачности и расчёта геометрии углов солнца.
"""
import ee
import math


def mask_clouds(image: ee.Image) -> ee.Image:
    """
    Облачная маска: объединяет стандартный канал QA60 и маску вероятности s2cloudless.
    """
    # 1. Извлекаем заводской технический канал флагов облачности QA60
    qa = image.select('QA60')
    
    # Биты 10 и 11 в этом канале отвечают за плотные облака и перистые (cirrus)
    cloud_bit = 1 << 10
    cirrus_bit = 1 << 11
    
    # Проверяем, чтобы оба бита были равны 0 (то есть пиксель чист от облаков)
    mask = qa.bitwiseAnd(cloud_bit).eq(0).And(qa.bitwiseAnd(cirrus_bit).eq(0))
    
    # 2. Дополнительно используем современную карту вероятности облаков MSK_CLDPRB.
    # Мы оставляем только те пиксели, где вероятность облака строго МЕНЬШЕ 40%.
    cloud_prob = ee.Image(image.select('MSK_CLDPRB')).lt(40)
    
    # Накладываем обе маски на снимок. Пиксели с облаками полностью исчезают из расчётов.
    return image.updateMask(mask).updateMask(cloud_prob)


def get_sun_angles(image: ee.Image) -> ee.Image:
    """
    Извлекает углы положения солнца из метаданных снимка и переводит их в радианы.
    """
    # Спутник присылает углы азимута и зенита в привычных градусах (от 0 до 360)
    sun_az = ee.Number(image.get('MEAN_SOLAR_AZIMUTH_ANGLE')).multiply(math.pi / 180)
    sun_zn = ee.Number(image.get('MEAN_SOLAR_ZENITH_ANGLE')).multiply(math.pi / 180)
    
    # Записываем эти значения обратно в свойства снимка, но уже в радианах
    return image.set({'sun_azimuth_rad': sun_az, 'sun_zenith_rad': sun_zn})

# """
# RU: Модуль M1 (personal project): посценовая поканальная топокоррекция SCS+C.
#     Математическое ядро фильтрации облачности и расчёта геометрии углов солнца.
# EN: Module M1 (personal project): scene-by-scene, band-specific SCS+C topographic correction.
#     Mathematical core for cloud masking and solar angle geometry calculation.
# DE: Modul M1 (persönliches Projekt): Szenenweise und kanalspezifische SCS+C Topographiekorrektur.
#     Mathematischer Kern für Wolkenmaskierung und Berechnung der Sonnenwinkelgeometrie.
# """
# import ee
# import math


# def mask_clouds(image: ee.Image) -> ee.Image:
#     """
#     RU: Облачная маска: объединяет стандартный канал QA60 и маску вероятности s2cloudless.
#     EN: Cloud mask: combines standard QA60 band and s2cloudless probability mask.
#     DE: Wolkenmaske: kombiniert das standardmäßige QA60-Band und die s2cloudless-Wahrscheinlichkeitsmaske.
#     """
#     # 1. RU: Извлекаем заводской технический канал флагов облачности QA60
#     #    EN: Extract the factory technical cloud flag band QA60
#     #    DE: Extrahiere das werkseitige technische Wolkenflag-Band QA60
#     qa = image.select('QA60')
    
#     # RU: Биты 10 и 11 в этом канале отвечают за плотные облака и перистые (cirrus)
#     # EN: Bits 10 and 11 in this band represent opaque clouds and cirrus
#     # DE: Die Bits 10 und 11 in diesem Band stehen für dichte Wolken und Schleierwolken (Cirrus)
#     cloud_bit = 1 << 10
#     cirrus_bit = 1 << 11
    
#     # RU: Проверяем, чтобы оба бита были равны 0 (то есть пиксель чист от облаков)
#     # EN: Check that both bits are 0 (meaning the pixel is cloud-free)
#     # DE: Überprüfe, ob beide Bits 0 sind (das bedeutet, der Pixel ist wolkenfrei)
#     mask = qa.bitwiseAnd(cloud_bit).eq(0).And(qa.bitwiseAnd(cirrus_bit).eq(0))
    
#     # 2. RU: Дополнительно используем современную карту вероятности облаков MSK_CLDPRB.
#     #    RU: Мы оставляем только те пиксели, где вероятность облака строго МЕНЬШЕ 40%.
#     #    EN: Additionally use the modern cloud probability map MSK_CLDPRB.
#     #    EN: We keep only pixels where cloud probability is strictly LESS than 40%.
#     #    DE: Verwende zusätzlich die moderne Wolkenwahrscheinlichkeitskarte MSK_CLDPRB.
#     #    DE: Wir behalten nur Pixel, deren Wolkenwahrscheinlichkeit строго UNTER 40% liegt.
#     cloud_prob = ee.Image(image.select('MSK_CLDPRB')).lt(40)
    
#     # RU: Накладываем обе маски на снимок. Пиксели с облаками полностью исчезают из расчётов.
#     # EN: Apply both masks to the image. Cloud-affected pixels are completely masked out from calculations.
#     # DE: Wende beide Masken auf das Bild an. Wolkenpixel werden vollständig aus den Berechnungen ausgeblendet.
#     return image.updateMask(mask).updateMask(cloud_prob)


# def get_sun_angles(image: ee.Image) -> ee.Image:
#     """
#     RU: Извлекает углы положения солнца из метаданных снимка и переводит их в радианы.
#     EN: Extracts solar position angles from image metadata and converts them to radians.
#     DE: Extrahiert Sonnenpositionswinkel aus den Bildmetadaten und rechnet sie in Bogenmaß (Radanten) um.
#     """
#     # RU: Спутник присылает углы азимута и зенита в привычных градусах (от 0 до 360)
#     # EN: The satellite provides azimuth and zenith angles in standard degrees (0 to 360)
#     # DE: Der Satellit liefert Azimut- und Zenitwinkel in üblichen Gradzahlen (0 bis 360)
#     sun_az = ee.Number(image.get('MEAN_SOLAR_AZIMUTH_ANGLE')).multiply(math.pi / 180)
#     sun_zn = ee.Number(image.get('MEAN_SOLAR_ZENITH_ANGLE')).multiply(math.pi / 180)
    
#     # RU: Записываем эти значения обратно в свойства снимка, но уже в радианах
#     # EN: Write these values back to the image properties, but in radians
#     # DE: Schreibe diese Werte zurück in die Bildeigenschaften, jedoch im Bogenmaß
#     return image.set({'sun_azimuth_rad': sun_az, 'sun_zenith_rad': sun_zn})
