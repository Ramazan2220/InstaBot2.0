import logging
import threading
import time
import sys
from datetime import datetime
from telegram.ext import Updater
from instagram.monkey_patch import *

# Импортируем наши модули
from config import (
    TELEGRAM_TOKEN, LOG_LEVEL, LOG_FORMAT, LOG_FILE,
    TELEGRAM_READ_TIMEOUT, TELEGRAM_CONNECT_TIMEOUT,
    TELEGRAM_ERROR_LOG
)
from database.db_manager import init_db
from telegram_bot.bot import setup_bot
from utils.scheduler import start_scheduler
from utils.task_queue import start_task_queue  # Добавляем импорт

print(f"Python version: {sys.version}")
print(f"Python executable: {sys.executable}")
print(f"Python path: {sys.path}")

# Настраиваем логирование
logging.basicConfig(
    format=LOG_FORMAT,
    level=getattr(logging, LOG_LEVEL),
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

def error_callback(update, context):
    """Логирование ошибок Telegram"""
    logger.error(f'Update "{update}" caused error "{context.error}"')

    # Записываем ошибку в отдельный файл
    with open(TELEGRAM_ERROR_LOG, 'a') as f:
        f.write(f'{datetime.now()} - Update: {update} - Error: {context.error}\n')

def main():
    # Инициализируем базу данных
    logger.info("Инициализация базы данных...")
    init_db()

    # Запускаем планировщик задач в отдельном потоке
    logger.info("Запуск планировщика задач...")
    scheduler_thread = threading.Thread(target=start_scheduler, daemon=True)
    scheduler_thread.start()

    # Запускаем обработчик очереди задач
    logger.info("Запуск обработчика очереди задач...")
    start_task_queue()  # Добавляем запуск очереди задач

    # Запускаем Telegram бота
    logger.info("Запуск Telegram бота...")
    updater = Updater(TELEGRAM_TOKEN, request_kwargs={
        'read_timeout': TELEGRAM_READ_TIMEOUT,
        'connect_timeout': TELEGRAM_CONNECT_TIMEOUT
    })

    # Добавляем обработчик ошибок
    updater.dispatcher.add_error_handler(error_callback)

    # Настраиваем бота
    setup_bot(updater)

    # Запускаем бота и ждем сигналов для завершения
    updater.start_polling()
    logger.info("Бот запущен и готов к работе!")
    updater.idle()

if __name__ == '__main__':
    main()