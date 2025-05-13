import os
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import CallbackContext, ConversationHandler, CommandHandler, CallbackQueryHandler, MessageHandler, Filters

from database.db_manager import get_instagram_account, get_instagram_accounts as get_all_instagram_accounts, update_instagram_account
from instagram.profile_manager import ProfileManager
from telegram_bot.keyboards import get_main_menu_keyboard
from telegram_bot.states import ProfileStates

logger = logging.getLogger(__name__)

# Состояния для ConversationHandler
EDIT_NAME, EDIT_USERNAME, EDIT_BIO, EDIT_LINKS, ADD_PHOTO, ADD_POST = range(6)

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
            account = get_instagram_account(account_id)
            if hasattr(account, 'full_name'):
                account.full_name = new_name
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
            account = get_instagram_account(account_id)
            account.username = new_username
            update_instagram_account(account)

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
            # Вместо передачи объекта account, передаем account_id и biography
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
            if hasattr(account, 'biography'):
                account.biography = ""
                update_instagram_account(account)

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

def cancel(update: Update, context: CallbackContext) -> int:
    """Отменяет текущую операцию"""
    query = update.callback_query
    query.answer()

    account_id = context.user_data.get('current_account_id')

    if account_id:
        return profile_account_menu(update, context)
    else:
        return profile_setup_menu(update, context)

def get_profile_handlers():
    """Возвращает обработчики для управления профилем"""
    profile_conv_handler = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(edit_profile_name, pattern='^profile_edit_name$'),
            CallbackQueryHandler(edit_profile_username, pattern='^profile_edit_username$'),
            CallbackQueryHandler(edit_profile_bio, pattern='^profile_edit_bio$'),
            CallbackQueryHandler(edit_profile_links, pattern='^profile_edit_links$'),
            CallbackQueryHandler(add_profile_photo, pattern='^profile_add_photo$'),
            CallbackQueryHandler(add_post, pattern='^profile_add_post$'),
        ],
        states={
            EDIT_NAME: [MessageHandler(Filters.text & ~Filters.command, save_profile_name)],
            EDIT_USERNAME: [MessageHandler(Filters.text & ~Filters.command, save_profile_username)],
            EDIT_BIO: [MessageHandler(Filters.text & ~Filters.command, save_profile_bio)],
            EDIT_LINKS: [MessageHandler(Filters.text & ~Filters.command, save_profile_links)],
            ADD_PHOTO: [MessageHandler(Filters.photo, save_profile_photo)],
            ADD_POST: [
                MessageHandler(Filters.photo | Filters.video, save_post),
            ],
        },
        fallbacks=[
            CallbackQueryHandler(cancel, pattern='^profile_account_'),
            CallbackQueryHandler(cancel, pattern='^profile_setup$'),
        ],
        name="profile_conversation",
        persistent=False,
    )

    handlers = [
        CommandHandler('profile', profile_setup_menu),
        CallbackQueryHandler(profile_setup_menu, pattern='^profile_setup$'),
        CallbackQueryHandler(profile_account_menu, pattern='^profile_account_'),
        CallbackQueryHandler(delete_profile_photo, pattern='^profile_delete_photo$'),
        CallbackQueryHandler(add_profile_photo, pattern='^add_profile_photo_\d+$'),  
        CallbackQueryHandler(delete_all_posts, pattern='^profile_delete_posts$'),
        CallbackQueryHandler(delete_bio, pattern='^profile_delete_bio$'),
        profile_conv_handler,
    ]

    return handlers