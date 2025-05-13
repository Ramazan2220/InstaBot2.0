import os
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import CallbackContext, ConversationHandler

from database.db_manager import get_instagram_account
from instagram.profile_manager import ProfileManager
from profile_setup import ADD_POST

logger = logging.getLogger(__name__)

def add_post(update: Update, context: CallbackContext) -> int:
    """Запрашивает фото или видео для поста"""
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
        f"Отправьте фото или видео для публикации в профиле *{account.username}*.\n\nПосле отправки медиафайла вам будет предложено ввести подпись к посту.",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 Отмена", callback_data=f"profile_account_{account_id}")]
        ])
    )

    return ADD_POST

def save_post(update: Update, context: CallbackContext) -> int:
    """Сохраняет новый пост"""
    account_id = context.user_data.get('current_account_id')

    # Отправляем сообщение о начале процесса
    message = update.message.reply_text("⏳ Публикация поста...")

    try:
        # Определяем тип медиа (фото или видео)
        if update.message.photo:
            # Получаем фото
            media_file = update.message.photo[-1].get_file()
            media_path = f"temp_post_{account_id}.jpg"
            media_file.download(media_path)

            # Создаем менеджер профиля и публикуем фото
            profile_manager = ProfileManager(account_id)
            caption = update.message.caption or ""
            success, result = profile_manager.upload_photo(media_path, caption)
        elif update.message.video:
            # Получаем видео
            media_file = update.message.video.get_file()
            media_path = f"temp_post_{account_id}.mp4"
            media_file.download(media_path)

            # Создаем менеджер профиля и публикуем видео
            profile_manager = ProfileManager(account_id)
            caption = update.message.caption or ""
            success, result = profile_manager.upload_video(media_path, caption)
        else:
            update.message.reply_text(
                "❌ Пожалуйста, отправьте фото или видео для публикации.",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔙 Назад к настройкам профиля", callback_data=f"profile_account_{account_id}")],
                    [InlineKeyboardButton("🏠 Главное меню", callback_data="back_to_main")]
                ])
            )
            message.delete()
            return ConversationHandler.END

        # Удаляем временный файл
        if os.path.exists(media_path):
            os.remove(media_path)

        if success:
            # Отправляем сообщение об успехе
            update.message.reply_text(
                "✅ Пост успешно опубликован!",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔙 Назад к настройкам профиля", callback_data=f"profile_account_{account_id}")],
                    [InlineKeyboardButton("🏠 Главное меню", callback_data="back_to_main")]
                ])
            )
        else:
            # Отправляем сообщение об ошибке
            update.message.reply_text(
                f"❌ Ошибка при публикации поста: {result}",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔙 Назад к настройкам профиля", callback_data=f"profile_account_{account_id}")],
                    [InlineKeyboardButton("🏠 Главное меню", callback_data="back_to_main")]
                ])
            )
    except Exception as e:
        logger.error(f"Ошибка при публикации поста: {e}")
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