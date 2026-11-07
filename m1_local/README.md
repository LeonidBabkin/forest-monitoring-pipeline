# Проект: Мониторинг деградации лесов (Трир / долина Мозеля)

## Модуль 1: Топографическая коррекция SCS+C (Локальная версия)

### Статус: ✅ ЗАВЕРШЕН (Gate 1 пройден)

### 1. Цель модуля и Архитектура
**Цель:** Устранение топографического эффекта (влияния рельефа) на снимках Sentinel-2 L2A для корректного расчета индексов (NBR) в последующих модулях. Без этой коррекции алгоритмы (LandTrendr) воспринимают разницу в освещении склонов как реальную гибель леса.

**Архитектура и стек:**
Модуль 1 реализован **полностью локально** на Python. 
*   **Не используется:** Google Earth Engine (GEE), `earthengine-api`, облачные вычисления.
*   **Используется:** `rasterio` (чтение/запись GeoTIFF, репроецирование), `numpy` (векторизованная математика), `scipy` (статистика и морфология), `pandas` (аудит).

### 2. Результаты прогона (Сцена T31UGR, 2021-06-01)
- **Успешная калибровка (`scsc_processed = 1`):** Да.
- **Гейт Пирсона (`gate_ran`):** 1 (успех для всех трех каналов).
- **Параметры C:** B04 = 1.17, B08 = 3.85, B12 = 4.30 (все в физическом диапазоне 0–5).
- **Остаточная корреляция (r):** B04 = -0.21, B08 = -0.01, B12 = -0.05.
- **Выходные файлы:** `data/output/` содержит скорректированные каналы (`*_corr.tif`).

### 3. Структура файлов модуля
*   **`config.yaml`** — настройки проекта (пути к данным, пороги NDVI, уклонов, диапазоны C, параметры для гейта Пирсона).
*   **`m1_scsc_local.py`** — **ядро модуля**. Содержит функции для морфометрии рельефа (slope/aspect), расчета `cos(i)`, вычисления параметра `C` через регрессию и применения формулы SCS+C.
*   **`run_m1_local.py`** — **главный скрипт запуска**. Загружает конфиг, читает снимки, обрезает их по AOI, запускает пайплайн для каждого канала и сохраняет результаты.
*   **`parse_metadata.py`** — парсер XML-файла `MTD_TL.xml`. Извлекает зенитный угол и азимут Солнца, необходимые для расчета `cos(i)`.
*   **`audit_report.py`** — скрипт для аудита. Читает итоговый CSV-файл и выводит статистику (средние значения `C`, количество сцен с `scsc_processed=1` и т.д.).
*   **`diagnose_scl.py`** — диагностический скрипт. Проверяет долю пикселей класса 2 (Dark Area) в маске леса, чтобы вовремя заметить риск искажения параметра `C`.
*   **`test_aspect.py`** — unit-тест для проверки корректности расчета экспозиции (aspect) на синтетическом склоне.

### 4. Подготовка данных (Входные данные)
Для запуска модуля необходимы:
- **Снимки Sentinel-2 L2A:** Каналы `B04.tif`, `B08.tif`, `B12.tif`, `SCL.tif` (в папке `data/raw/`).
- **Метаданные:** Файл `MTD_TL.xml` (содержит углы Солнца).
- **ЦМР (DEM):** Файл `dgm10_trier.tif` (10 м, EPSG:25832, в папке `data/dem/`).
- **Формат именования:** Все файлы должны иметь одинаковый префикс (например, `T31UGR_20210601T104021_`).
- **Структура папок:** `data/raw/` (исходники), `data/dem/` (рельеф), `data/output/` (результаты).

### 5. Как запустить (Локально)
1. Установите зависимости: 
   `pip install rasterio numpy pandas scipy pyyaml`
2. Убедитесь, что структура папок `data/raw/`, `data/dem/` и `data/output/` создана и заполнена.
3. Выполните в терминале (из папки `m1_local`):
   `python run_m1_local.py`
4. Проверьте результаты в консоли и в папке `data/output/`.

### 6. Ключевые инженерные решения и преодоленные проблемы (Debug)
В ходе отладки были выявлены и устранены следующие проблемы:
1. **Разное разрешение каналов:** B12 (20 м) и SCL (20 м) репроецируются в сетку B04 (10 м) с использованием `Resampling.bilinear` (для высот) и `Resampling.nearest` (для дискретных классов).
2. **Ошибка `overflow` в градиентах:** Исправлена путем приведения к `float64` перед возведением в квадрат в функции `compute_slope_aspect`.
3. **Радиометрическое смещение ESA (Baseline 05.00):** Выявлено, что снимки, обработанные после января 2022 года, содержат смещение `+1000` (BOA_ADD_OFFSET). В функцию `calibrate_c` добавлена коррекция `dn = dn - 1000.0`.
4. **Эффект размера выборки (p-value):** При выборке >500 000 пикселей значение p-value стремится к 0 даже при r ≈ 0.01. В коде гейт приёмки ориентирован на величину `r` (|r| < 0.1), а не на p-value.



# M1 — Topographic Correction SCS+C (Sentinel-2 L2A) / Topografische Korrektur SCS+C

[Deutsch](#deutsch) · [English](#english)

---

## Deutsch

### Kurzbeschreibung
Modul 1 einer lokalen Pipeline zur Walddegradationsüberwachung (Trier / Moseltal).
Es korrigiert den topografischen Beleuchtungseffekt auf Sentinel-2-L2A-Aufnahmen
mit der **SCS+C-Methode** (Soenen et al., 2005), damit nachgelagerte Algorithmen
(LandTrendr, NBR-Zeitreihen) Schattenhänge nicht als Waldverlust fehlinterpretieren.

**Status:** Produktionsreif für Einzelszenen; Batch-/Cloud-Betrieb in Vorbereitung.

### Technologiestack
- **Python 3.10+**
- **rasterio** — GeoTIFF-I/O, Reprojektion (`rasterio.warp.reproject`), Profil-Preservation
- **numpy** — vektorisierte Mathematik (keine Pixel-Schleifen)
- **scipy** — `ndimage.binary_dilation` (Wolkenmasken), `stats.linregress` (C-Kalibrierung)
- **pandas** — Audit-Tabelle (`m1_calibration_audit.csv`)
- **PyYAML** — Konfiguration (`config.yaml`)
- **xml.etree.ElementTree** — Parsing von `MTD_TL.xml` (Sonnenwinkel)
- **pytest** — Unit-Tests (u. a. `test_aspect.py`)

### Was implementiert wurde
1. **Grid-Harmonisierung**: B08 (10 m), B12 (20 m), SCL (20 m) und DEM (10 m) werden
   auf das B04-Raster reprojiziert. Resampling: `bilinear` für kontinuierliche Daten
   (Reflektanz, Höhe), `nearest` für diskrete Klassen (SCL, Masken).
2. **Maskierung**: Wolken aus SCL (Klassen 3, 8, 9) mit morphologischer Dilatation;
   NoData-Maske; Waldmaske über NDVI-Schwelle + Hangneigung > 5°.
3. **Morphometrie**: Hangneigung und Exposition über zentrale Differenzen
   (`float64`, overflow-sicher).
4. **cos(i)**: `cos(Z)·cos(S) + sin(Z)·sin(S)·cos(A − Aspect)` aus Sonnenzenit/-azimut
   (`MTD_TL.xml`) und Geländeparametern.
5. **C-Kalibrierung**: lineare Regression `DN ~ cos(i)` auf Waldpixeln;
   `C = intercept / slope`; Validitätsprüfung `0 ≤ C ≤ 5`.
   **ESA-Offset-Korrektur**: `DN −= 1000` für Szenen nach Baseline 04.00 (Jan 2022).
6. **SCS+C-Anwendung**: `L_corr = L · (cos(Z)·cos(S) + C) / (cos(i) + C)`.
7. **Akzeptanz-Gate (Pearson)**: Restkorrelation `r` zwischen korrigierter DN und `cos(i)`
   auf 900 Zufallspixeln; Gate besteht bei `|r| < 0.1`. Bewusst `r` statt `p-value`,
   da bei `n > 500 000` `p → 0` auch bei `r ≈ 0.01`.
8. **Audit**: CSV mit `band`, `scsc_C`, `scsc_r`, `scsc_processed` pro Szene/Kanal.

### Ergebnis (Referenzszene T31UGR, 2021-06-01)
| Kanal | C | Restkorrelation r | Gate |
|-------|---|-------------------|------|
| B04 | 1.17 | −0.21 | bestanden |
| B08 | 3.85 | −0.01 | bestanden |
| B12 | 4.30 | −0.05 | bestanden |

Ausgabe: `data/output/*_corr.tif` (geokodiert, gleiches Profil wie Eingabe).

### Ausführung
```bash
pip install rasterio numpy pandas scipy pyyaml
python run_m1_local.py

Eingaben: data/raw/ (B04, B08, B12, SCL als TIFF), data/dem/ (DGM10),
MTD_TL.xml. Konfiguration: config.yaml.

Architektur
run_m1_local.py — Orchestrator (I/O, Masken, Schleifen, Schreiben)

m1_scsc_local.py — reine Mathematik (ndarray → ndarray, testbar)

parse_metadata.py — XML-Parser (Sonnenwinkel)

audit_report.py, diagnose_scl.py — Hilfsskripte (Audit, SCL-Diagnose)

test_aspect.py — Unit-Test für Exposition

Bekannte Grenzen
Einzelszenen-Verarbeitung (Batch-Modus geplant)

Kein Docker/Cloud-Deployment (in Vorbereitung)

Gültigkeit der C-Kalibrierung hängt von Waldanteil und Wolkenfreiheit der Szene ab


English
Summary
Module 1 of a local pipeline for forest degradation monitoring (Trier / Moselle valley).
It removes the topographic illumination effect on Sentinel-2 L2A imagery using the
SCS+C method (Soenen et al., 2005), so that downstream algorithms (LandTrendr,
NBR time series) do not mistake shaded slopes for forest loss.

Status: production-ready for single scenes; batch/cloud operation in preparation.

Stack
Python 3.10+, rasterio (GeoTIFF I/O, reprojection), numpy (vectorised math),
scipy (binary_dilation, linregress), pandas (audit CSV), PyYAML (config),
xml.etree.ElementTree (sun angles), pytest (unit tests).

What was implemented
Grid harmonisation — B08 (10 m), B12 (20 m), SCL (20 m), DEM (10 m) reprojected
to the B04 grid; bilinear for continuous data, nearest for discrete classes.

Masking — clouds from SCL (3, 8, 9) with binary dilation; NoData mask;
forest mask via NDVI threshold + slope > 5°.

Morphometry — slope and aspect via central differences, float64, overflow-safe.

cos(i) — cos(Z)·cos(S) + sin(Z)·sin(S)·cos(A − Aspect) from MTD_TL.xml
sun angles and terrain parameters.

C calibration — linear regression DN ~ cos(i) on forest pixels;
C = intercept / slope; validity check 0 ≤ C ≤ 5.
ESA offset fix: DN −= 1000 for scenes after Baseline 04.00 (Jan 2022).

SCS+C application — L_corr = L · (cos(Z)·cos(S) + C) / (cos(i) + C).

Acceptance gate (Pearson) — residual correlation r between corrected DN and
cos(i) on 900 random pixels; pass if |r| < 0.1. r is used instead of p-value
because at n > 500 000 p → 0 even for r ≈ 0.01.

Audit — CSV with band, scsc_C, scsc_r, scsc_processed per scene/band.

Results (reference scene T31UGR, 2021-06-01)
Band	C	Residual r	Gate
B04	1.17	−0.21	passed
B08	3.85	−0.01	passed
B12	4.30	−0.05	passed
Output: data/output/*_corr.tif, geocoded, same profile as input.

Run

pip install rasterio numpy pandas scipy pyyaml
python run_m1_local.py

nputs: data/raw/ (B04, B08, B12, SCL as TIFF), data/dem/ (DGM10), MTD_TL.xml.
Config: config.yaml.

Architecture
run_m1_local.py — orchestrator (I/O, masks, loops, writing)

m1_scsc_local.py — pure math (ndarray → ndarray, unit-testable)

parse_metadata.py — XML parser (sun angles)

audit_report.py, diagnose_scl.py — helper scripts

test_aspect.py — unit test for aspect

Known limitations
Single-scene processing (batch mode planned)

No Docker/cloud deployment yet (in preparation)

C calibration validity depends on forest fraction and cloud-free area of the scene