"""
Тест для проверки работы instagrapi
"""
try:
    import instagrapi
    from instagrapi import Client

    print(f"instagrapi успешно импортирован. Версия: {instagrapi.__version__}")

    # Создаем клиент (без авторизации)
    client = Client()

    print("instagrapi работает корректно!")
except ImportError as e:
    print(f"Ошибка импорта: {e}")
except Exception as e:
    print(f"Ошибка при тестировании instagrapi: {e}")