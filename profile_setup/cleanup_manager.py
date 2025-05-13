import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import CallbackContext

from database.db_manager import get_instagram_account
from instagram.profile_manager import ProfileManager

logger = logging.getLogger(__name__)

def delete_all_posts(update: Update, context: CallbackContext) -> None:
    """Удаляет все посты"""
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
        return

    # Отправляем сообщение о начале процесса
    query.edit_message_text(
        f"⏳ Удаление всех постов для аккаунта {account.username}...\n\nЭто может занять некоторое время."
    )

    try:
        # Создаем менеджер профиля и удаляем все посты
        profile_manager = ProfileManager(account_id)
        success, result = profile_manager.delete_all_posts()

        if success:
            # Отправляем сообщение об успехе
            query.edit_message_text(
                f"✅ {result}",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔙 Назад к настройкам профиля", callback_data=f"profile_account_{account_id}")],
                    [InlineKeyboardButton("🏠 Главное меню", callback_data="back_to_main")]
                ])
            )
        else:
            # Отправляем сообщение об ошибке
            query.edit_message_text(
                f"❌ Ошибка при удалении постов: {result}",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔙 Назад к настройкам профиля", callback_data=f"profile_account_{account_id}")],
                    [InlineKeyboardButton("🏠 Главное меню", callback_data="back_to_main")]
                ])
            )
    except Exception as e:
        logger.error(f"Ошибка при удалении постов: {e}")
        query.edit_message_text(
            "❌ Произошла ошибка при обработке вашего запроса. Пожалуйста, попробуйте еще раз.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 Назад к настройкам профиля", callback_data=f"profile_account_{account_id}")],
                [InlineKeyboardButton("🏠 Главное меню", callback_data="back_to_main")]
            ])
        )