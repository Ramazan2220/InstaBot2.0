import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import CallbackContext, ConversationHandler

from database.db_manager import get_instagram_account, get_instagram_accounts as get_all_instagram_accounts

logger = logging.getLogger(__name__)

def profile_setup_menu(update: Update, context: CallbackContext) -> None:
    """Показывает меню настройки профиля"""
    query = update.callback_query
    if query:
        query.answer()

    accounts = get_all_instagram_accounts()

    if not accounts:
        if query:
            query.edit_message_text(
                "У вас нет добавленных аккаунтов Instagram. Сначала добавьте аккаунт.",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🏠 Главное меню", callback_data="back_to_main")]
                ])
            )
        else:
            update.message.reply_text(
                "У вас нет добавленных аккаунтов Instagram. Сначала добавьте аккаунт.",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🏠 Главное меню", callback_data="back_to_main")]
                ])
            )
        return

    keyboard = []
    for account in accounts:
        keyboard.append([InlineKeyboardButton(f"{account.username}", callback_data=f"profile_account_{account.id}")])

    keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data="back_to_main")])

    if query:
        query.edit_message_text(
            "Выберите аккаунт для настройки профиля:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    else:
        update.message.reply_text(
            "Выберите аккаунт для настройки профиля:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

def profile_account_menu(update: Update, context: CallbackContext) -> None:
    """Показывает меню настройки конкретного аккаунта"""
    query = update.callback_query
    query.answer()

    # Получаем ID аккаунта из callback_data
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
        return

    keyboard = [
        [InlineKeyboardButton("👤 Изменить имя", callback_data="profile_edit_name")],
        [InlineKeyboardButton("🔤 Изменить имя пользователя", callback_data="profile_edit_username")],
        [InlineKeyboardButton("📝 Изменить описание профиля", callback_data="profile_edit_bio")],
        [InlineKeyboardButton("🔗 Добавить/изменить ссылки", callback_data="profile_edit_links")],
        [InlineKeyboardButton("🖼️ Добавить фото профиля", callback_data=f"add_profile_photo_{account_id}")],
        [InlineKeyboardButton("🖼️ Добавить пост", callback_data="profile_add_post")],
        [InlineKeyboardButton("🗑️ Удалить все посты", callback_data="profile_delete_posts")],
        [InlineKeyboardButton("🧹 Очистить описание профиля", callback_data="profile_delete_bio")],
        [InlineKeyboardButton("🔙 Назад к списку аккаунтов", callback_data="profile_setup")]
    ]

    query.edit_message_text(
        f"Настройка профиля для аккаунта: *{account.username}*\n\nВыберите действие:",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )

def cancel(update: Update, context: CallbackContext) -> int:
    """Отменяет текущую операцию"""
    query = update.callback_query
    query.answer()

    account_id = context.user_data.get('current_account_id')

    if account_id:
        return profile_account_menu(update, context)
    else:
        return profile_setup_menu(update, context)