import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import CallbackContext, ConversationHandler

from database.db_manager import get_instagram_account, update_instagram_account
from instagram.profile_manager import ProfileManager
from profile_setup import EDIT_USERNAME

logger = logging.getLogger(__name__)

def edit_profile_username(update: Update, context: CallbackContext) -> int:
    """Запрашивает новое имя пользователя"""
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

    query.edit_message_text(
        f"Текущее имя пользователя: *{account.username}*\n\nВведите новое имя пользователя:",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 Отмена", callback_data=f"profile_account_{account_id}")]
        ])
    )

    return EDIT_USERNAME

def save_profile_username(update: Update, context: CallbackContext) -> int:
    """Сохраняет новое имя пользователя"""
    new_username = update.message.text
    account_id = context.user_data.get('current_account_id')

    # Отправляем сообщение о начале процесса
    message = update.message.reply_text("⏳ Обновление имени пользователя...")

    try:
        # Создаем менеджер профиля и обновляем имя пользователя
        profile_manager = ProfileManager(account_id)
        success, result = profile_manager.update_username(new_username)

        if success:
            # Обновляем имя пользователя в базе данных
            update_instagram_account(account_id, username=new_username)

            # Отправляем сообщение об успехе
            update.message.reply_text(
                f"✅ Имя пользователя успешно изменено на *{new_username}*!",
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔙 Назад к настройкам профиля", callback_data=f"profile_account_{account_id}")],
                    [InlineKeyboardButton("🏠 Главное меню", callback_data="back_to_main")]
                ])
            )
        else:
            # Отправляем сообщение об ошибке
            update.message.reply_text(
                f"❌ Ошибка при изменении имени пользователя: {result}",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔙 Назад к настройкам профиля", callback_data=f"profile_account_{account_id}")],
                    [InlineKeyboardButton("🏠 Главное меню", callback_data="back_to_main")]
                ])
            )
    except Exception as e:
        logger.error(f"Ошибка при обновлении имени пользователя: {e}")
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