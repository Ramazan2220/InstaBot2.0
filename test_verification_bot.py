import asyncio
import aiohttp
import logging
from config import VERIFICATION_BOT_TOKEN, VERIFICATION_BOT_ADMIN_ID

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_bot():
    """Тестирует работу бота верификации"""
    
    # Проверяем настройки
    if not VERIFICATION_BOT_TOKEN:
        logger.error("VERIFICATION_BOT_TOKEN не настроен")
        return
    
    if not VERIFICATION_BOT_ADMIN_ID:
        logger.error("VERIFICATION_BOT_ADMIN_ID не настроен")
        return
    
    # Отправляем тестовое сообщение
    url = f"https://api.telegram.org/bot{VERIFICATION_BOT_TOKEN}/sendMessage"
    data = {
        "chat_id": VERIFICATION_BOT_ADMIN_ID,
        "text": "Тестовое сообщение от бота верификации"
    }
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, data=data) as response:
                if response.status == 200:
                    logger.info("Тестовое сообщение отправлено успешно")
                else:
                    logger.error(f"Ошибка при отправке тестового сообщения: {response.status}")
                    response_text = await response.text()
                    logger.error(f"Ответ: {response_text}")
    except Exception as e:
        logger.error(f"Ошибка при отправке тестового сообщения: {str(e)}")
    
    # Получаем обновления
    url = f"https://api.telegram.org/bot{VERIFICATION_BOT_TOKEN}/getUpdates"
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                if response.status == 200:
                    data = await response.json()
                    logger.info(f"Получены обновления: {data}")
                    
                    if data["ok"] and data["result"]:
                        for update in data["result"]:
                            logger.info(f"Обновление: {update}")
                    else:
                        logger.warning("Обновления не найдены")
                else:
                    logger.error(f"Ошибка при получении обновлений: {response.status}")
                    response_text = await response.text()
                    logger.error(f"Ответ: {response_text}")
    except Exception as e:
        logger.error(f"Ошибка при получении обновлений: {str(e)}")

if __name__ == "__main__":
    asyncio.run(test_bot())