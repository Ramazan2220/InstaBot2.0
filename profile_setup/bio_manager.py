import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import CallbackContext, ConversationHandler

from database.db_manager import get_instagram_account, update_instagram_account
from instagram.profile_manager import ProfileManager
from profile_setup import EDIT_BIO

logger = logging.getLogger(__name__)

def edit_profile_bio(update: Update, context: CallbackContext) -> int:
    """Запрашивает новое описание профиля"""
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

    # Получаем текущее описание профиля
    current_bio = account.biography if hasattr(account, 'biography') and account.biography else "Не указано"

    query.edit_message_text(
        f"Текущее описание профиля:\n\n{current_bio}\n\nВведите новое описание профиля (до 150 символов):",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 Отмена", callback_data=f"profile_account_{account_id}")]
        ])
    )

    return EDIT_BIO

def save_profile_bio(update: Update, context: CallbackContext) -> int:
    """Сохраняет новое описание профиля"""
    new_bio = update.message.text
    account_id = context.user_data.get('current_account_id')

    # Отправляем сообщение о начале процесса
    message = update.message.reply_text("⏳ Обновление описания профиля...")

    try:
        # Создаем менеджер профиля и обновляем описание
        profile_manager = ProfileManager(account_id)
        success, result = profile_manager.update_biography(new_bio)

        if success:
            # Обновляем описание в базе данных
            update_instagram_account(account_id, biography=new_bio)

            # Отправляем сообщение об успехе
            update.message.reply_text(
                "✅ Описание профиля успешно обновлено!",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔙 Назад к настройкам профиля", callback_data=f"profile_account_{account_id}")],
                    [InlineKeyboardButton("🏠 Главное меню", callback_data="back_to_main")]
                ])
            )
        else:
            # Отправляем сообщение об ошибке
            update.message.reply_text(
                f"❌ Ошибка при обновлении описания профиля: {result}",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔙 Назад к настройкам профиля", callback_data=f"profile_account_{account_id}")],
                    [InlineKeyboardButton("🏠 Главное меню", callback_data="back_to_main")]
                ])
            )
    except Exception as e:
        logger.error(f"Ошибка при обновлении описания профиля: {e}")
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

def delete_bio(update: Update, context: CallbackContext) -> None:
    """Очищает описание профиля"""
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
        f"⏳ Очистка описания профиля для аккаунта {account.username}..."
    )

    try:
        # Создаем менеджер профиля и очищаем описание
        profile_manager = ProfileManager(account_id)
        success, result = profile_manager.update_biography("")

        if success:
            # Обновляем описание в базе данных
            update_instagram_account(account_id, biography="")

            # Отправляем сообщение об успехе
            query.edit_message_text(
                "✅ Описание профиля успешно очищено!",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔙 Назад к настройкам профиля", callback_data=f"profile_account_{account_id}")],
                    [InlineKeyboardButton("🏠 Главное меню", callback_data="back_to_main")]
                ])
            )
        else:
            # Отправляем сообщение об ошибке
            query.edit_message_text(
                f"❌ Ошибка при очистке описания профиля: {result}",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔙 Назад к настройкам профиля", callback_data=f"profile_account_{account_id}")],
                    [InlineKeyboardButton("🏠 Главное меню", callback_data="back_to_main")]
                ])
            )
    except Exception as e:
        logger.error(f"Ошибка при очистке описания профиля: {e}")
        query.edit_message_text(
            "❌ Произошла ошибка при обработке вашего запроса. Пожалуйста, попробуйте еще раз.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 Назад к настройкам профиля", callback_data=f"profile_account_{account_id}")],
                [InlineKeyboardButton("🏠 Главное меню", callback_data="back_to_main")]
            ])
        )