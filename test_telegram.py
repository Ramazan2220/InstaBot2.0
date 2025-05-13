"""
Тест для проверки работы python-telegram-bot
"""
try:
    import telegram
    from telegram.ext import Updater, CommandHandler

    print(f"python-telegram-bot успешно импортирован. Версия: {telegram.__version__}")

    # Проверяем базовую функциональность
    def dummy_function(update, context):
        pass

    # Создаем тестовый обработчик (без запуска)
    handler = CommandHandler("start", dummy_function)

    print("python-telegram-bot работает корректно!")
except ImportError as e:
    print(f"Ошибка импорта: {e}")
except Exception as e:
    print(f"Ошибка при тестировании python-telegram-bot: {e}")