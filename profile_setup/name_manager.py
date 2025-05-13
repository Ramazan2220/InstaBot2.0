import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import CallbackContext, ConversationHandler

from database.db_manager import get_instagram_account, update_instagram_account
from instagram.profile_manager import ProfileManager
from profile_setup import EDIT_NAME

logger = logging.getLogger(__name__)

def edit_profile_name(update: Update, context: CallbackContext) -> int:
    """Запрашивает новое имя профиля"""
    query = update.callback_query
    query.answer()

    account_id = context.user_data.get('current_account_id')
    account = get_instagram_account(account_id)

    if not account:
        query.edit_message_text(
            "Аккаунт не найден. Возможно, он был удален.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 Назад", callback_data="profile_setup")]
            ])
        )
        return ConversationHandler.END

    # Получаем текущее имя профиля
    current_name = account.full_name if hasattr(account, 'full_name') and account.full_name else "Не указано"

    query.edit_message_text(
        f"Текущее имя профиля: *{current_name}*\n\nВведите новое имя профиля:",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 Отмена", callback_data=f"profile_account_{account_id}")]
        ])
    )

    return EDIT_NAME

def save_profile_name(update: Update, context: CallbackContext) -> int:
    """Сохраняет новое имя профиля"""
    new_name = update.message.text
    account_id = context.user_data.get('current_account_id')

    # Отправляем сообщение о начале процесса
    message = update.message.reply_text("⏳ Обновление имени профиля...")

    try:
        # Создаем менеджер профиля и обновляем имя
        profile_manager = ProfileManager(account_id)
        success, result = profile_manager.update_profile_name(new_name)

        if success:
            # Обновляем имя в базе данных
            update_instagram_account(account_id, full_name=new_name)

            # Отправляем сообщение об успехе
            update.message.reply_text(
                f"✅ Имя профиля успешно изменено на *{new_name}*!",
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔙 Назад к настройкам профиля", callback_data=f"profile_account_{account_id}")],
                    [InlineKeyboardButton("🏠 Главное меню", callback_data="back_to_main")]
                ])
            )
        else:
            # Отправляем сообщение об ошибке
            update.message.reply_text(
                f"❌ Ошибка при изменении имени профиля: {result}",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔙 Назад к настройкам профиля", callback_data=f"profile_account_{account_id}")],
                    [InlineKeyboardButton("🏠 Главное меню", callback_data="back_to_main")]
                ])
            )
    except Exception as e:
        logger.error(f"Ошибка при обновлении имени профиля: {e}")
        update.message.reply_text(
            "❌ Произошла ошибка при обработке вашего запроса. Пожалуйста, попробуйте еще раз.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 Назад к настройкам профиля", callback_data=f"profile_account_{account_id}")],
                [InlineKeyboardButton("🏠 Главное меню", callback_data="back_to_main")]
            ])
        )

    # Удаляем сообщение о процессе
    message.delete()

    return ConversationHandler.END