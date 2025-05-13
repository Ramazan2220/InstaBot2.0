import logging
from logging.handlers import RotatingFileHandler
import os

from config import LOG_LEVEL, LOG_FORMAT, LOG_FILE, LOGS_DIR

def setup_logger(name):
    """Настройка логгера"""
    # Создаем директорию для логов, если её нет
    os.makedirs(LOGS_DIR, exist_ok=True)

    # Создаем логгер
    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, LOG_LEVEL))

    # Создаем обработчик для записи в файл с ротацией
    file_handler = RotatingFileHandler(
        LOG_FILE,
        maxBytes=10*1024*1024,  # 10 МБ
        backupCount=5
    )
    file_handler.setFormatter(logging.Formatter(LOG_FORMAT))

    # Создаем обработчик для вывода в консоль
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(logging.Formatter(LOG_FORMAT))

    # Добавляем обработчики к логгеру
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    return logger