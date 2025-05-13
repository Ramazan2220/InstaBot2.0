import logging
from telegram.ext import Updater
from config import TELEGRAM_TOKEN

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

def main():
    """Запуск бота"""
    # Создаем Updater с увеличенным таймаутом
    updater = Updater(TELEGRAM_TOKEN, request_kwargs={'read_timeout': 60, 'connect_timeout': 60})
    
    # Получаем информацию о боте
    bot_info = updater.bot.get_me()
    logger.info(f"Бот успешно подключен: {bot_info.first_name} (@{bot_info.username})")
    
    logger.info("Тест завершен успешно!")

if __name__ == '__main__':
    try:
        main()
    except Exception as e:
        logger.error(f"Ошибка при подключении к боту: {e}")