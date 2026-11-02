import pandas as pd
import glob

# Путь к папке, куда вы скачали файлы (проверьте, нет ли там подпапки m1_audit)
# files = glob.glob(r'C:\Users\Trier\OneDrive\Documents\curriculum\Project module 1\cscvfilesm1_calibration_*.csv') 
files = glob.glob('m1_calibration_*.csv')


if not files:
    print("Файлы не найдены. Проверьте путь к папке.")
else:
    df_list = [pd.read_csv(f) for f in files]
    df_all = pd.concat(df_list, ignore_index=True)
    df_all.to_csv('m1_calibration_audit.csv', index=False)
    print(f"Успешно объединено {len(files)} файлов. Всего сцен: {len(df_all)}")