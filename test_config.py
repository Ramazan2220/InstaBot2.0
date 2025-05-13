"""
Тест для проверки конфигурации проекта
"""
try:
    import os
    from config import (
        BASE_DIR, DATA_DIR, ACCOUNTS_DIR, MEDIA_DIR, LOGS_DIR,
        TELEGRAM_TOKEN, ADMIN_USER_IDS, DATABASE_URL,
        MAX_WORKERS, LOG_LEVEL, LOG_FORMAT, LOG_FILE
    )

    print("Конфигурация успешно импортирована.")

    # Проверяем существование директорий
    dirs_to_check = [DATA_DIR, ACCOUNTS_DIR, MEDIA_DIR, LOGS_DIR]
    for dir_path in dirs_to_check:
        if os.path.exists(dir_path):
            print(f"Директория {dir_path} существует.")
        else:
            print(f"Директория {dir_path} не существует!")

    # Проверяем токен Telegram
    if TELEGRAM_TOKEN == 'YOUR_TELEGRAM_BOT_TOKEN':
        print("ВНИМАНИЕ: Токен Telegram не настроен!")
    else:
        print("Токен Telegram настроен.")

    # Проверяем ID администраторов
    if not ADMIN_USER_IDS or ADMIN_USER_IDS == [123456789]:
        print("ВНИМАНИЕ: ID администраторов не настроены!")
    else:
        print(f"Настроены ID администраторов: {ADMIN_USER_IDS}")

    print("Тестирование конфигурации завершено.")
except ImportError as e:
    print(f"Ошибка импорта: {e}")
except Exception as e:
    print(f"Ошибка при тестировании конфигурации: {e}")