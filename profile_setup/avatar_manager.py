import os
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import CallbackContext, ConversationHandler

from database.db_manager import get_instagram_account
from instagram.profile_manager import ProfileManager
from profile_setup import ADD_PHOTO

logger = logging.getLogger(__name__)

def add_profile_photo(update: Update, context: CallbackContext) -> int:
    """Запрашивает фото профиля"""
    query = update.callback_query
    query.answer()

    # Извлекаем ID аккаунта из callback_data
    account_id = int(query.data.split('_')[-1])
    context.user_data['current_account_id'] = account_id

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
        f"Отправьте фото для установки в качестве фото профиля для аккаунта *{account.username}*:",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 Отмена", callback_data=f"profile_account_{account_id}")]
        ])
    )

    return ADD_PHOTO

def save_profile_photo(update: Update, context: CallbackContext) -> int:
    """Сохраняет новое фото профиля"""
    account_id = context.user_data.get('current_account_id')

    # Отправляем сообщение о начале процесса
    message = update.message.reply_text("⏳ Обновление фото профиля...")

    try:
        # Получаем фото
        photo_file = update.message.photo[-1].get_file()
        photo_path = f"temp_profile_photo_{account_id}.jpg"
        photo_file.download(photo_path)

        # Создаем менеджер профиля и обновляем фото
        profile_manager = ProfileManager(account_id)
        success, result = profile_manager.update_profile_picture(photo_path)

        # Удаляем временный файл
        if os.path.exists(photo_path):
            os.remove(photo_path)

        if success:
            # Отправляем сообщение об успехе
            update.message.reply_text(
                "✅ Фото профиля успешно обновлено!",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔙 Назад к настройкам профиля", callback_data=f"profile_account_{account_id}")],
                    [InlineKeyboardButton("🏠 Главное меню", callback_data="back_to_main")]
                ])
            )
        else:
            # Отправляем сообщение об ошибке
            update.message.reply_text(
                f"❌ Ошибка при обновлении фото профиля: {result}",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔙 Назад к настройкам профиля", callback_data=f"profile_account_{account_id}")],
                    [InlineKeyboardButton("🏠 Главное меню", callback_data="back_to_main")]
                ])
            )
    except Exception as e:
        logger.error(f"Ошибка при обновлении фото профиля: {e}")
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

def delete_profile_photo(update: Update, context: CallbackContext) -> None:
    """Удаляет фото профиля"""
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
        f"⏳ Удаление фото профиля для аккаунта {account.username}..."
    )

    try:
        # Создаем менеджер профиля и удаляем фото
        profile_manager = ProfileManager(account_id)
        success, result = profile_manager.remove_profile_picture()

        if success:
            # Отправляем сообщение об успехе
            query.edit_message_text(
                "✅ Фото профиля успешно удалено!",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔙 Назад к настройкам профиля", callback_data=f"profile_account_{account_id}")],
                    [InlineKeyboardButton("🏠 Главное меню", callback_data="back_to_main")]
                ])
            )
        else:
            # Отправляем сообщение об ошибке
            query.edit_message_text(
                f"❌ Ошибка при удалении фото профиля: {result}",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔙 Назад к настройкам профиля", callback_data=f"profile_account_{account_id}")],
                    [InlineKeyboardButton("🏠 Главное меню", callback_data="back_to_main")]
                ])
            )
    except Exception as e:
        logger.error(f"Ошибка при удалении фото профиля: {e}")
        query.edit_message_text(
            "❌ Произошла ошибка при обработке вашего запроса. Пожалуйста, попробуйте еще раз.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 Назад к настройкам профиля", callback_data=f"profile_account_{account_id}")],
                [InlineKeyboardButton("🏠 Главное меню", callback_data="back_to_main")]
            ])
        )