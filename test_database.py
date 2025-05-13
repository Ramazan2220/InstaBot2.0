"""
Тест для проверки работы базы данных проекта
"""
try:
    # Импортируем модели
    from database.models import Base, InstagramAccount, Proxy, PublishTask
    print("Модели базы данных успешно импортированы.")

    # Импортируем функции управления базой данных
    from database.db_manager import init_database, Session
    print("Функции управления базой данных успешно импортированы.")

    # Инициализируем базу данных
    init_database()
    print("База данных успешно инициализирована.")

    # Создаем тестовую сессию
    session = Session()

    # Проверяем соединение с базой данных
    try:
        from sqlalchemy import text
session.execute(text("SELECT 1"))
        print("Соединение с базой данных работает корректно.")
    except Exception as e:
        print(f"Ошибка при соединении с базой данных: {e}")

    print("Тестирование базы данных завершено.")
except ImportError as e:
    print(f"Ошибка импорта: {e}")
except Exception as e:
    print(f"Ошибка при тестировании базы данных: {e}")