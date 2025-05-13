import asyncio
import logging
import re
import os
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import Message
from config import VERIFICATION_BOT_TOKEN, VERIFICATION_BOT_ADMIN_ID

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Путь к файлу для хранения последнего кода
CODE_FILE = "verification_code.txt"

# Глобальный словарь для хранения последнего полученного кода
last_verification_code = None
code_event = asyncio.Event()

# Инициализация бота и диспетчера
bot = Bot(token=VERIFICATION_BOT_TOKEN)
dp = Dispatcher()

@dp.message(Command("start"))
async def cmd_start(message: Message):
    """Обработчик команды /start"""
    if str(message.from_user.id) != str(VERIFICATION_BOT_ADMIN_ID):
        await message.answer("Извините, у вас нет доступа к этому боту.")
        return

    await message.answer(
        "👋 Привет! Я бот для получения кодов подтверждения Instagram.\n\n"
        "Просто перешлите мне письмо с кодом подтверждения, и я автоматически извлеку код."
    )

@dp.message(Command("help"))
async def cmd_help(message: Message):
    """Обработчик команды /help"""
    if str(message.from_user.id) != str(VERIFICATION_BOT_ADMIN_ID):
        return

    await message.answer(
        "📋 Инструкция по использованию:\n\n"
        "1. Перешлите мне письмо с кодом подтверждения от Instagram\n"
        "2. Я автоматически извлеку код из письма\n"
        "3. Если код не найден автоматически, вы можете отправить его вручную\n\n"
        "Команды:\n"
        "/start - Начать работу с ботом\n"
        "/help - Показать эту справку\n"
        "/status - Проверить статус бота"
    )

@dp.message(Command("status"))
async def cmd_status(message: Message):
    """Обработчик команды /status"""
    if str(message.from_user.id) != str(VERIFICATION_BOT_ADMIN_ID):
        return

    global last_verification_code

    if last_verification_code:
        await message.answer(f"✅ Последний полученный код: {last_verification_code}")
    else:
        await message.answer("❌ Код подтверждения еще не получен")

@dp.message()
async def handle_message(message: Message):
    """Обработчик всех сообщений"""
    if str(message.from_user.id) != str(VERIFICATION_BOT_ADMIN_ID):
        return

    global last_verification_code, code_event

    # Получаем текст сообщения
    text = message.text or message.caption or ""

    # Ищем 6-значный код в тексте
    code_match = re.search(r'\b\d{6}\b', text)

    if code_match:
        # Нашли код
        verification_code = code_match.group(0)
        last_verification_code = verification_code
        code_event.set()  # Устанавливаем событие, чтобы уведомить ожидающие функции

        # Сохраняем код в файл
        try:
            with open(CODE_FILE, "w") as f:
                f.write(verification_code)
            logger.info(f"Код {verification_code} сохранен в файл {CODE_FILE}")
        except Exception as e:
            logger.error(f"Ошибка при сохранении кода в файл: {str(e)}")

        await message.answer(f"✅ Получен код подтверждения: {verification_code}")
        logger.info(f"Получен код подтверждения: {verification_code}")
    else:
        # Код не найден, просим пользователя ввести его вручную
        await message.answer(
            "🔍 Не удалось автоматически найти код подтверждения в сообщении.\n"
            "Пожалуйста, отправьте код вручную (6 цифр)."
        )

async def get_verification_code(timeout=300):
    """
    Ожидает получения кода подтверждения

    Args:
        timeout (int): Время ожидания в секундах

    Returns:
        str: Код подтверждения или None, если время ожидания истекло
    """
    global last_verification_code, code_event

    # Сбрасываем предыдущий код и событие
    last_verification_code = None
    code_event.clear()

    try:
        # Ждем, пока событие не будет установлено или не истечет таймаут
        await asyncio.wait_for(code_event.wait(), timeout=timeout)
        return last_verification_code
    except asyncio.TimeoutError:
        logger.warning(f"Время ожидания кода подтверждения истекло ({timeout} секунд)")
        return None

async def main():
    """Основная функция для запуска бота"""
    # Проверяем, настроен ли токен бота
    if not VERIFICATION_BOT_TOKEN:
        logger.error("Ошибка: VERIFICATION_BOT_TOKEN не настроен в config.py")
        return

    # Проверяем, настроен ли ID администратора
    if not VERIFICATION_BOT_ADMIN_ID:
        logger.error("Ошибка: VERIFICATION_BOT_ADMIN_ID не настроен в config.py")
        return

    # Запускаем бота
    logger.info("Запуск бота верификации...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())