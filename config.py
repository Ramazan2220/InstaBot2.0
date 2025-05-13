import os
from pathlib import Path

# Загружаем переменные окружения из файла .env
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # Если python-dotenv не установлен, продолжаем без него

# Базовые пути
BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / 'data'
ACCOUNTS_DIR = DATA_DIR / 'accounts'
MEDIA_DIR = DATA_DIR / 'media'
LOGS_DIR = DATA_DIR / 'logs'

# Создаем директории, если они не существуют
os.makedirs(ACCOUNTS_DIR, exist_ok=True)
os.makedirs(MEDIA_DIR, exist_ok=True)
os.makedirs(LOGS_DIR, exist_ok=True)

# Настройки Telegram бота
# Пытаемся получить токен из переменных окружения, иначе используем значение по умолчанию
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", '7799643879:AAHIjhm13baBFsPYuGK7CaBjB0YbQco5skY')
ADMIN_USER_IDS = [6499246016]  # Замените на ваш Telegram ID

# Настройки базы данных
DATABASE_URL = f'sqlite:///{DATA_DIR}/database.sqlite'

# Настройки многопоточности
MAX_WORKERS = 3  # Максимальное количество одновременных потоков

# Настройки логирования
LOG_LEVEL = 'INFO'
LOG_FORMAT = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
LOG_FILE = LOGS_DIR / 'bot.log'

# Настройки Instagram
INSTAGRAM_LOGIN_ATTEMPTS = 3  # Количество попыток входа
INSTAGRAM_DELAY_BETWEEN_REQUESTS = 5  # Задержка между запросами (в секундах)

# Настройки таймаутов для Telegram API
TELEGRAM_READ_TIMEOUT = 60  # Таймаут чтения в секундах
TELEGRAM_CONNECT_TIMEOUT = 60  # Таймаут соединения в секундах

# Настройки бота верификации
VERIFICATION_BOT_TOKEN = "7709908636:AAHB9bH74-w565IApIggZ7L1XwdOufXSnu0"  # Токен бота верификации
VERIFICATION_BOT_ADMIN_ID = 6499246016  # Ваш ID в Telegram

# Добавьте в config.py
TELEGRAM_ERROR_LOG = LOGS_DIR / 'telegram_errors.log'