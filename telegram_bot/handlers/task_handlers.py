import logging
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, ParseMode
from telegram.ext import ConversationHandler

from database.db_manager import get_publish_task, update_publish_task_status
from database.models import TaskStatus

logger = logging.getLogger(__name__)

def tasks_handler(update, context):
    keyboard = [
        [
            InlineKeyboardButton("📤 Опубликовать сейчас", callback_data='publish_now'),
            InlineKeyboardButton("⏰ Запланировать публикацию", callback_data='schedule_publish')
        ],
        [
            InlineKeyboardButton("📊 Статистика публикаций", callback_data='publication_stats'),
            InlineKeyboardButton("🔙 Назад", callback_data='back_to_main')
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    update.message.reply_text(
        "📝 *Меню управления задачами*\n\n"
        "Выберите действие из списка ниже:",
        reply_markup=reply_markup,
        parse_mode=ParseMode.MARKDOWN
    )

def schedule_publish_handler(update, context):
    keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data='menu_tasks')]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    update.message.reply_text(
        "Функция планирования публикации в разработке",
        reply_markup=reply_markup
    )
    return ConversationHandler.END

async def handle_task_error(update, context, task_id, error_message):
    """Обрабатывает ошибки при выполнении задач"""
    # Получаем задачу
    task = get_publish_task(task_id)
    if not task:
        await update.message.reply_text(f"❌ Задача с ID {task_id} не найдена.")
        return

    # Проверяем, связана ли ошибка с прокси и пытаемся заменить прокси
    from utils.proxy_manager import auto_replace_failed_proxy
    success, message = auto_replace_failed_proxy(task.account_id, error_message)

    if success:
        # Если прокси успешно заменен, предлагаем повторить задачу
        keyboard = [
            [InlineKeyboardButton("✅ Повторить задачу", callback_data=f"retry_task_{task_id}")],
            [InlineKeyboardButton("❌ Отмена", callback_data="cancel")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await update.message.reply_text(
            f"⚠️ Ошибка при выполнении задачи: {error_message}\n\n"
            f"✅ {message}\n\n"
            f"Хотите повторить задачу с новым прокси?",
            reply_markup=reply_markup
        )
    else:
        # Если прокси не заменен или ошибка не связана с прокси
        keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data="back_to_main")]]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await update.message.reply_text(
            f"❌ Ошибка при выполнении задачи: {error_message}\n\n"
            f"{message if 'Ошибка' not in message else ''}",
            reply_markup=reply_markup
        )

async def retry_task_callback(update, context):
    """Обрабатывает нажатие кнопки повтора задачи"""
    query = update.callback_query
    await query.answer()

    # Получаем ID задачи из callback_data
    task_id = int(query.data.split('_')[-1])

    # Получаем задачу
    task = get_publish_task(task_id)
    if not task:
        await query.edit_message_text(
            "❌ Задача не найдена.",
            reply_markup=None
        )
        return

    # Обновляем статус задачи на PENDING
    update_publish_task_status(task_id, TaskStatus.PENDING)

    await query.edit_message_text(
        f"✅ Задача #{task_id} поставлена в очередь на повторное выполнение.",
        reply_markup=None
    )

def get_task_handlers():
    """Возвращает обработчики для управления задачами"""
    from telegram.ext import CommandHandler, CallbackQueryHandler

    return [
        CommandHandler("tasks", tasks_handler),
        CommandHandler("schedule_publish", schedule_publish_handler),
        CallbackQueryHandler(retry_task_callback, pattern=r'^retry_task_\d+$')
    ]