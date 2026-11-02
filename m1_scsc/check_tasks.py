import ee

# Ваш ID проекта
ee.Initialize(project='ee-learning-trier')

# Получаем список всех ваших задач (Tasks)
tasks = ee.batch.Task.list()

print("=" * 60)
print("СТАТУС ПОСЛЕДНИХ 15 ЗАДАЧ В GOOGLE EARTH ENGINE:")
print("=" * 60)

# Выводим последние 15 задач (чтобы не засорять экран)
for task in tasks[-15:]:
    status = task.status()
    state = status.get('state')
    description = status.get('description')
    error_message = status.get('error_message', '')
    
    # Если задача упала, выводим текст ошибки
    if state == 'FAILED':
        print(f"❌ FAILED: {description}")
        print(f"   Причина: {error_message}")
    elif state == 'COMPLETED':
        print(f"✅ COMPLETED: {description}")
    elif state in ['RUNNING', 'READY']:
        print(f"⏳ {state}: {description}")
    else:
        print(f"❓ {state}: {description}")

print("=" * 60)