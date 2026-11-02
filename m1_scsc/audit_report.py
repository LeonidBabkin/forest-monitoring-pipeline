import pandas as pd

# Загружаем объединенный файл
# df = pd.read_csv('m1_calibration_audit.csv')
# df = pd.read_csv('M1_Audit_All_Years.csv')
df = pd.read_csv('m1_calibration_audit.csv')

# Приводим колонки к числам (на случай, если есть строки)
for col in ['scsc_processed', 'scsc_C_B4', 'scsc_C_B8', 'scsc_C_B12']:
    if col in df.columns:
        df[col] = pd.to_numeric(df[col], errors='coerce')

print("=" * 50)
print("📊 ОТЧЕТ ПО АУДИТУ M1 (SCS+C)")
print("=" * 50)
print(f"Всего обработано сцен: {len(df)}\n")

# 1. Проверка флага scsc_processed
if 'scsc_processed' in df.columns:
    success_count = (df['scsc_processed'] == 1).sum()
    percent = (success_count / len(df)) * 100
    print(f"✅ Сцен с успешной калибровкой (scsc_processed=1): {success_count} ({percent:.1f}%)")
    print(f"⚠️ Сцен со сбоем калибровки (scsc_processed=0): {len(df) - success_count}\n")

# 2. Проверка выбросов C по каналам
for band in ['B4', 'B8', 'B12']:
    c_col = f'scsc_C_{band}'
    if c_col in df.columns:
        c_vals = df[c_col].dropna()
        in_range = ((c_vals > 0) & (c_vals < 5)).sum()
        out_of_range = len(c_vals) - in_range
        
        print(f"Канал {band}:")
        print(f"  - Среднее C: {c_vals.mean():.3f}")
        print(f"  - Мин / Макс: {c_vals.min():.3f} / {c_vals.max():.3f}")
        print(f"  - В диапазоне (0, 5): {in_range} ({in_range/len(df)*100:.1f}%)")
        print(f"  - Выбросов: {out_of_range}")
print("=" * 50)