# update_schema.py
import sqlite3
import os
from config import DATABASE_URL  # Импортируйте путь к вашей базе данных

def update_schema():
    """Обновляет схему базы данных, добавляя новые поля в таблицу instagram_accounts"""

    # Определяем путь к базе данных
    db_path = DATABASE_URL.replace('sqlite:///', '')

    # Проверяем, существует ли файл базы данных
    if not os.path.exists(db_path):
        print(f"Файл базы данных не найден: {db_path}")
        return

    # Подключаемся к базе данных
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    try:
        # Проверяем, существуют ли уже колонки email и email_password
        cursor.execute("PRAGMA table_info(instagram_accounts)")
        columns = cursor.fetchall()
        column_names = [column[1] for column in columns]

        # Добавляем колонку email, если она не существует
        if 'email' not in column_names:
            print("Добавление колонки 'email' в таблицу instagram_accounts...")
            cursor.execute("ALTER TABLE instagram_accounts ADD COLUMN email TEXT")

        # Добавляем колонку email_password, если она не существует
        if 'email_password' not in column_names:
            print("Добавление колонки 'email_password' в таблицу instagram_accounts...")
            cursor.execute("ALTER TABLE instagram_accounts ADD COLUMN email_password TEXT")

        # Сохраняем изменения
        conn.commit()
        print("Схема базы данных успешно обновлена!")

    except Exception as e:
        print(f"Ошибка при обновлении схемы базы данных: {str(e)}")
        conn.rollback()

    finally:
        # Закрываем соединение
        conn.close()

if __name__ == "__main__":
    update_schema()