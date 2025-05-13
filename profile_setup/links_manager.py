import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import CallbackContext, ConversationHandler

from database.db_manager import get_instagram_account
from instagram.profile_manager import ProfileManager
from profile_setup import EDIT_LINKS

logger = logging.getLogger(__name__)

def edit_profile_links(update: Update, context: CallbackContext) -> int:
    """Запрашивает новые ссылки профиля"""
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

    # Отправляем сообщение о загрузке
    loading_message = query.message.reply_text("⏳ Подключение к Instagram... Пожалуйста, подождите.")

    # Получаем текущие ссылки профиля
    try:
        profile_manager = ProfileManager(account_id)
        current_link = profile_manager.get_profile_links()

        # Удаляем сообщение о загрузке
        loading_message.delete()

        current_link_text = "Не указана" if not current_link else current_link

        query.message.reply_text(
            f"Текущая ссылка в профиле: {current_link_text}\n\n"
            "Введите новую ссылку для профиля Instagram (например, example.com):",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 Отмена", callback_data=f"profile_account_{account_id}")]
            ])
        )

        return EDIT_LINKS
    except Exception as e:
        logger.error(f"Ошибка при получении ссылок профиля: {e}")

        # Удаляем сообщение о загрузке
        loading_message.delete()

        query.message.reply_text(
            "❌ Произошла ошибка при получении ссылок профиля. Пожалуйста, попробуйте еще раз.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 Назад к настройкам профиля", callback_data=f"profile_account_{account_id}")],
                [InlineKeyboardButton("🏠 Главное меню", callback_data="back_to_main")]
            ])
        )
        return ConversationHandler.END

def save_profile_links(update: Update, context: CallbackContext) -> int:
    """Сохраняет новые ссылки профиля"""
    links_text = update.message.text
    account_id = context.user_data.get('current_account_id')

    # Отправляем сообщение о начале процесса
    message = update.message.reply_text("⏳ Обновление ссылок профиля...")

    try:
        # Берем только первую ссылку, так как Instagram поддерживает только одну
        link = links_text.strip()
        if '|' in link:
            _, url = link.split('|', 1)
            link = url.strip()

        # Создаем менеджер профиля и обновляем ссылку
        profile_manager = ProfileManager(account_id)
        success, result = profile_manager.update_profile_links(link)

        if success:
            # Отправляем сообщение об успехе
            update.message.reply_text(
                "✅ Ссылка профиля успешно обновлена!",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔙 Назад к настройкам профиля", callback_data=f"profile_account_{account_id}")],
                    [InlineKeyboardButton("🏠 Главное меню", callback_data="back_to_main")]
                ])
            )
        else:
            # Отправляем сообщение об ошибке
            update.message.reply_text(
                f"❌ Ошибка при обновлении ссылки профиля: {result}",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔙 Назад к настройкам профиля", callback_data=f"profile_account_{account_id}")],
                    [InlineKeyboardButton("🏠 Главное меню", callback_data="back_to_main")]
                ])
            )
    except Exception as e:
        logger.error(f"Ошибка при обновлении ссылки профиля: {e}")
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