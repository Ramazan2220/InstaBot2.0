from telegram_bot.handlers.account_handlers import get_account_handlers
from telegram_bot.handlers.proxy_handlers import get_proxy_handlers
from telegram_bot.handlers.publish_handlers import get_publish_handlers
from telegram_bot.handlers.task_handlers import get_task_handlers

def get_all_handlers():
    """Возвращает все обработчики"""
    handlers = []
    handlers.extend(get_account_handlers())
    handlers.extend(get_proxy_handlers())
    handlers.extend(get_publish_handlers())
    handlers.extend(get_task_handlers())
    return handlers