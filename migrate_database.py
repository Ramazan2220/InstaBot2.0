# migrate_database.py
from sqlalchemy import create_engine, inspect
from config import DATABASE_URL
import logging
import sqlite3

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def add_columns_sqlite():
    """Добавляет новые колонки в таблицу instagram_accounts для SQLite"""
    conn = sqlite3.connect(DATABASE_URL.replace('sqlite:///', ''))
    cursor = conn.cursor()

    try:
        # Проверяем, существует ли колонка full_name
        cursor.execute("PRAGMA table_info(instagram_accounts)")
        columns = [column[1] for column in cursor.fetchall()]

        if 'full_name' not in columns:
            logger.info("Добавление колонки full_name...")
            cursor.execute('ALTER TABLE instagram_accounts ADD COLUMN full_name TEXT')

        if 'biography' not in columns:
            logger.info("Добавление колонки biography...")
            cursor.execute('ALTER TABLE instagram_accounts ADD COLUMN biography TEXT')

        conn.commit()
        logger.info("Миграция завершена успешно!")
    except Exception as e:
        logger.error(f"Ошибка при выполнении миграции: {e}")
    finally:
        conn.close()

def add_columns_postgres():
    """Добавляет новые колонки в таблицу instagram_accounts для PostgreSQL"""
    engine = create_engine(DATABASE_URL)

    try:
        # Добавляем колонку full_name
        logger.info("Добавление колонки full_name...")
        engine.execute('ALTER TABLE instagram_accounts ADD COLUMN IF NOT EXISTS full_name VARCHAR(255)')

        # Добавляем колонку biography
        logger.info("Добавление колонки biography...")
        engine.execute('ALTER TABLE instagram_accounts ADD COLUMN IF NOT EXISTS biography TEXT')

        logger.info("Миграция завершена успешно!")
    except Exception as e:
        logger.error(f"Ошибка при выполнении миграции: {e}")

if __name__ == "__main__":
    if DATABASE_URL.startswith('sqlite'):
        add_columns_sqlite()
    else:
        add_columns_postgres()