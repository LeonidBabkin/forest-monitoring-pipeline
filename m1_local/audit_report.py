import pandas as pd

df = pd.read_csv('m1_calibration_audit.csv')
for col in df.columns:
    if col.startswith('scsc_') and col != 'scene_id':
        df[col] = pd.to_numeric(df[col], errors='coerce')

print("=" * 50)
print("📊 ОТЧЕТ ПО АУДИТУ M1 (SCS+C, v3.4)")
print("=" * 50)
print(f"Всего сцен: {len(df)}\n")
ok = (df['scsc_processed'] == 1).sum()
print(f"✅ scsc_processed=1: {ok} ({ok/len(df)*100:.1f}%)")
for band in ['B04', 'B08', 'B12']:
    c = df[f'scsc_C_{band}'].dropna()
    if not c.empty:
        print(f"{band}: mean={c.mean():.3f}, min={c.min():.3f}, max={c.max():.3f}")