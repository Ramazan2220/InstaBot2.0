import json
import os
import time
import shutil
import logging
import asyncio
import concurrent.futures
from datetime import datetime  
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, ParseMode
from telegram.ext import ConversationHandler, CommandHandler, MessageHandler, Filters

from config import ACCOUNTS_DIR, ADMIN_USER_IDS, MEDIA_DIR
from database.db_manager import get_session, get_instagram_accounts, bulk_add_instagram_accounts, delete_instagram_account, get_instagram_account
from database.models import InstagramAccount, PublishTask
from instagrapi import Client
from instagrapi.exceptions import LoginRequired, BadPassword, ChallengeRequired
from instagram.client import check_login_challenge, submit_challenge_code
from instagram.email_utils import test_email_connection
import random
from database.models import Proxy
from utils.proxy_manager import assign_proxy_to_account
from instagram.client import check_login_challenge, submit_challenge_code, test_instagram_login_with_proxy

logger = logging.getLogger(__name__)

# Глобальный словарь для хранения обработчиков запросов на подтверждение
challenge_handlers = {}

# Состояния для добавления аккаунта
ENTER_USERNAME, ENTER_PASSWORD, ENTER_EMAIL, ENTER_EMAIL_PASSWORD, CONFIRM_ACCOUNT, ENTER_VERIFICATION_CODE = range(6)

# Состояние для ожидания файла с аккаунтами
WAITING_ACCOUNTS_FILE = 10

def save_account_from_telegram(update, context):
    """Добавляет аккаунт Instagram в базу данных из Telegram-бота"""
    user_data = context.user_data

    username = user_data.get('instagram_username')
    password = user_data.get('instagram_password')
    email = user_data.get('email')
    email_password = user_data.get('email_password')

    # Проверяем наличие всех необходимых данных
    if not all([username, password, email, email_password]):
        missing_fields = []
        if not username: missing_fields.append("имя пользователя")
        if not password: missing_fields.append("пароль")
        if not email: missing_fields.append("email")
        if not email_password: missing_fields.append("пароль от email")

        update.message.reply_text(
            f"❌ Отсутствуют необходимые данные: {', '.join(missing_fields)}.\n"
            f"Пожалуйста, начните процесс добавления аккаунта заново."
        )
        user_data.clear()
        return ConversationHandler.END

    try:
        # Добавляем аккаунт в базу данных
        from database.db_manager import add_instagram_account

        # Добавляем аккаунт в базу данных напрямую
        success, result = add_instagram_account(username, password, email, email_password)

        if success:
            # Если аккаунт успешно добавлен, result содержит ID аккаунта
            account_id = result
            
            # Назначаем прокси для аккаунта
            from utils.proxy_manager import assign_proxy_to_account
            proxy_success, proxy_message = assign_proxy_to_account(account_id)

            update.message.reply_text(
                f"✅ Аккаунт {username} успешно добавлен!\n"
                f"{'📡' if proxy_success else '⚠️'} {proxy_message}\n\n"
                f"Теперь вы можете использовать его для публикации контента."
            )
        else:
            # Если произошла ошибка, result содержит сообщение об ошибке
            update.message.reply_text(f"❌ Ошибка при добавлении аккаунта {username}: {result}")

        # Очищаем данные пользователя
        user_data.clear()
        return ConversationHandler.END

    except Exception as e:
        logger.error(f"Ошибка при добавлении аккаунта: {str(e)}")
        update.message.reply_text(f"❌ Произошла ошибка при добавлении аккаунта: {str(e)}")
        user_data.clear()  # Очищаем данные даже при ошибке
        return ConversationHandler.END

def is_admin(user_id):
    return user_id in ADMIN_USER_IDS

def accounts_handler(update, context):
    keyboard = [
        [InlineKeyboardButton("➕ Добавить аккаунт", callback_data='add_account')],
        [InlineKeyboardButton("📋 Список аккаунтов", callback_data='list_accounts')],
        [InlineKeyboardButton("📤 Загрузить аккаунты", callback_data='upload_accounts')],
        [InlineKeyboardButton("📤 Асинхронная загрузка аккаунтов", callback_data='async_upload_accounts')],
        [InlineKeyboardButton("⚙️ Настройка профиля", callback_data='profile_setup')],
        [InlineKeyboardButton("🔙 Назад", callback_data='back_to_main')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    update.message.reply_text(
        "🔧 *Меню управления аккаунтами*\n\n"
        "Выберите действие из списка ниже:",
        reply_markup=reply_markup,
        parse_mode=ParseMode.MARKDOWN
    )

def add_account(update, context):
    if update.callback_query:
        query = update.callback_query
        query.answer()

        # Проверяем наличие прокси перед добавлением аккаунта
        session = get_session()
        proxies_count = session.query(Proxy).filter_by(is_active=True).count()
        session.close()

        if proxies_count == 0:
            keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data='menu_accounts')]]
            reply_markup = InlineKeyboardMarkup(keyboard)

            query.edit_message_text(
                "⚠️ В системе нет доступных прокси!\n\n"
                "Для корректной работы с Instagram необходимо добавить хотя бы один рабочий прокси.\n"
                "Используйте команду /add_proxy для добавления прокси.",
                reply_markup=reply_markup
            )
            return ConversationHandler.END

        keyboard = [
            [InlineKeyboardButton("🔙 Назад", callback_data='menu_accounts')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        query.edit_message_text(
            "Пожалуйста, введите имя пользователя (логин) аккаунта Instagram:\n\n"
            "Или введите все данные сразу в формате:\n"
            "`логин:пароль:email:пароль_email`\n\n"
            "Пример: `username:password123:user@example.com:emailpass456`\n\n"
            "Или нажмите 'Назад' для возврата в меню аккаунтов.",
            reply_markup=reply_markup,
            parse_mode=ParseMode.MARKDOWN
        )
        return ENTER_USERNAME
    else:
        # Проверяем наличие прокси перед добавлением аккаунта
        session = get_session()
        proxies_count = session.query(Proxy).filter_by(is_active=True).count()
        session.close()

        if proxies_count == 0:
            keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data='menu_accounts')]]
            reply_markup = InlineKeyboardMarkup(keyboard)

            update.message.reply_text(
                "⚠️ В системе нет доступных прокси!\n\n"
                "Для корректной работы с Instagram необходимо добавить хотя бы один рабочий прокси.\n"
                "Используйте команду /add_proxy для добавления прокси.",
                reply_markup=reply_markup
            )
            return ConversationHandler.END

        keyboard = [
            [InlineKeyboardButton("🔙 Назад", callback_data='menu_accounts')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        update.message.reply_text(
            "Пожалуйста, введите имя пользователя (логин) аккаунта Instagram:\n\n"
            "Или введите все данные сразу в формате:\n"
            "`логин:пароль:email:пароль_email`\n\n"
            "Пример: `username:password123:user@example.com:emailpass456`\n\n"
            "Или нажмите 'Назад' для возврата в меню аккаунтов.",
            reply_markup=reply_markup,
            parse_mode=ParseMode.MARKDOWN
        )
        return ENTER_USERNAME

def enter_username(update, context):
    text = update.message.text.strip()

    # Проверяем, содержит ли ввод все данные сразу в формате login:password:email:email_password
    parts = text.split(':')

    if len(parts) == 4:
        # Полный формат login:password:email:email_password
        username, password, email, email_password = parts

        # Проверяем, существует ли уже аккаунт с таким именем
        session = get_session()
        existing_account = session.query(InstagramAccount).filter_by(username=username).first()
        session.close()

        if existing_account:
            keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data='menu_accounts')]]
            reply_markup = InlineKeyboardMarkup(keyboard)

            update.message.reply_text(
                f"Аккаунт с именем пользователя '{username}' уже существует. "
                f"Пожалуйста, используйте другое имя пользователя или вернитесь в меню аккаунтов.",
                reply_markup=reply_markup
            )
            return ConversationHandler.END

        # Сообщаем пользователю, что данные получены
        update.message.reply_text(f"Получены все данные для аккаунта {username}. Начинаем процесс добавления...")

        # Сначала добавляем аккаунт в базу данных без проверки входа
        try:
            from database.db_manager import add_instagram_account_without_login

            # Добавляем аккаунт без проверки входа
            account = add_instagram_account_without_login(
                username=username,
                password=password,
                email=email,
                email_password=email_password
            )

            if not account:
                update.message.reply_text("❌ Не удалось добавить аккаунт в базу данных.")
                return ConversationHandler.END

            update.message.reply_text("✅ Аккаунт добавлен в базу данных. Назначаем прокси...")

            # Назначаем прокси для аккаунта
            from utils.proxy_manager import assign_proxy_to_account
            proxy_success, proxy_message = assign_proxy_to_account(account.id)

            if not proxy_success:
                update.message.reply_text(f"⚠️ {proxy_message}\n\nПродолжаем без прокси...")
            else:
                update.message.reply_text(f"✅ {proxy_message}")

            # Теперь проверяем подключение к почте
            update.message.reply_text("🔄 Проверяем подключение к почте...")
            print(f"[DEBUG] Проверка подключения к почте {email}")

            from instagram.email_utils import test_email_connection
            success, message = test_email_connection(email, email_password)

            if not success:
                update.message.reply_text(f"❌ Ошибка подключения к почте: {message}\n\nПожалуйста, проверьте пароль и попробуйте снова.")
                return ConversationHandler.END

            update.message.reply_text("✅ Подключение к почте успешно установлено.")

            # Теперь пытаемся войти в Instagram с использованием прокси
            update.message.reply_text("🔄 Пытаемся войти в Instagram...")

            from instagram.client import test_instagram_login_with_proxy
            login_success = test_instagram_login_with_proxy(
                account_id=account.id,
                username=username,
                password=password,
                email=email,
                email_password=email_password
            )

            if login_success:
                # Если вход успешен, активируем аккаунт
                from database.db_manager import activate_instagram_account
                activate_instagram_account(account.id)

                update.message.reply_text(
                    f"✅ Аккаунт {username} успешно добавлен и активирован!\n\n"
                    f"Теперь вы можете использовать его для публикации контента."
                )
            else:
                update.message.reply_text(
                    f"⚠️ Аккаунт {username} добавлен, но не удалось войти в Instagram.\n\n"
                    f"Вы можете попробовать войти позже через меню управления аккаунтами."
                )

            # Очищаем данные пользователя
            context.user_data.clear()
            return ConversationHandler.END

        except Exception as e:
            update.message.reply_text(f"❌ Произошла ошибка: {str(e)}")
            logger.error(f"Ошибка при добавлении аккаунта: {str(e)}")
            return ConversationHandler.END

    # Если это не полный формат, продолжаем стандартную логику
    username = text

    session = get_session()
    existing_account = session.query(InstagramAccount).filter_by(username=username).first()
    session.close()

    if existing_account:
        keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data='menu_accounts')]]
        reply_markup = InlineKeyboardMarkup(keyboard)

        update.message.reply_text(
            f"Аккаунт с именем пользователя '{username}' уже существует. "
            f"Пожалуйста, используйте другое имя пользователя или вернитесь в меню аккаунтов.",
            reply_markup=reply_markup
        )
        return ConversationHandler.END

    context.user_data['instagram_username'] = username

    keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data='menu_accounts')]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    update.message.reply_text(
        "Теперь введите пароль для этого аккаунта Instagram.\n\n"
        "⚠️ *Важно*: Ваш пароль будет храниться в зашифрованном виде и использоваться только для авторизации в Instagram.",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=reply_markup
    )
    return ENTER_PASSWORD

def enter_password(update, context):
    password = update.message.text.strip()

    context.user_data['instagram_password'] = password

    keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data='menu_accounts')]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    update.message.reply_text(
        "Теперь введите адрес электронной почты, привязанный к этому аккаунту Instagram.\n\n"
        "Этот адрес будет использоваться для получения кодов подтверждения.",
        reply_markup=reply_markup
    )

    # Удаляем сообщение с паролем для безопасности
    update.message.delete()

    return ENTER_EMAIL

def enter_email(update, context):
    """Обработчик ввода адреса электронной почты"""
    user_data = context.user_data
    email = update.message.text.strip()

    # Сохраняем адрес электронной почты
    user_data['email'] = email

    update.message.reply_text(
        "Теперь введите пароль от электронной почты.\n\n"
        "⚠️ Важно: Пароль будет храниться в зашифрованном виде и использоваться только для получения кодов подтверждения."
    )

    return ENTER_EMAIL_PASSWORD

def enter_email_password(update, context):
    """
    Обрабатывает ввод пароля от электронной почты
    """
    user_id = update.effective_user.id
    email_password = update.message.text

    # Сохраняем пароль от почты
    context.user_data['email_password'] = email_password

    # Получаем данные для входа
    email = context.user_data.get('email')
    instagram_username = context.user_data.get('instagram_username')
    instagram_password = context.user_data.get('instagram_password')

    if not email:
        update.message.reply_text("❌ Ошибка: адрес электронной почты не указан.")
        return ConversationHandler.END

    if not instagram_username or not instagram_password:
        update.message.reply_text("❌ Ошибка: данные для входа в Instagram не указаны.")
        return ConversationHandler.END

    # Сначала добавляем аккаунт в базу данных без проверки входа
    try:
        from database.db_manager import add_instagram_account_without_login

        # Добавляем аккаунт без проверки входа
        account = add_instagram_account_without_login(
            username=instagram_username,
            password=instagram_password,
            email=email,
            email_password=email_password
        )

        if not account:
            update.message.reply_text("❌ Не удалось добавить аккаунт в базу данных.")
            return ConversationHandler.END

        update.message.reply_text("✅ Аккаунт добавлен в базу данных. Назначаем прокси...")

        # Назначаем прокси для аккаунта
        from utils.proxy_manager import assign_proxy_to_account
        proxy_success, proxy_message = assign_proxy_to_account(account.id)

        if not proxy_success:
            update.message.reply_text(f"⚠️ {proxy_message}\n\nПродолжаем без прокси...")
        else:
            update.message.reply_text(f"✅ {proxy_message}")

        # Теперь проверяем подключение к почте
        update.message.reply_text("🔄 Проверяем подключение к почте...")
        print(f"[DEBUG] Проверка подключения к почте {email}")

        from instagram.email_utils import test_email_connection
        success, message = test_email_connection(email, email_password)

        if not success:
            update.message.reply_text(f"❌ Ошибка подключения к почте: {message}\n\nПожалуйста, проверьте пароль и попробуйте снова.")
            return ENTER_EMAIL_PASSWORD

        update.message.reply_text("✅ Подключение к почте успешно установлено.")

        # Теперь пытаемся войти в Instagram с использованием прокси
        update.message.reply_text("🔄 Пытаемся войти в Instagram...")

        from instagram.client import test_instagram_login_with_proxy
        login_success = test_instagram_login_with_proxy(
            account_id=account.id,
            username=instagram_username,
            password=instagram_password,
            email=email,
            email_password=email_password
        )

        if login_success:
            # Если вход успешен, активируем аккаунт
            from database.db_manager import activate_instagram_account
            activate_instagram_account(account.id)

            update.message.reply_text(
                f"✅ Аккаунт {instagram_username} успешно добавлен и активирован!\n\n"
                f"Теперь вы можете использовать его для публикации контента."
            )
        else:
            update.message.reply_text(
                f"⚠️ Аккаунт {instagram_username} добавлен, но не удалось войти в Instagram.\n\n"
                f"Вы можете попробовать войти позже через меню управления аккаунтами."
            )

        # Очищаем данные пользователя
        context.user_data.clear()
        return ConversationHandler.END

    except Exception as e:
        update.message.reply_text(f"❌ Произошла ошибка: {str(e)}")
        logger.error(f"Ошибка при обработке пароля от почты: {str(e)}")
        return ConversationHandler.END

def confirm_add_account(update, context):
    """Подтверждение добавления аккаунта"""
    query = update.callback_query
    query.answer()

    user_id = update.effective_user.id
    username = context.user_data.get('instagram_username')
    password = context.user_data.get('instagram_password')
    email = context.user_data.get('instagram_email')
    email_password = context.user_data.get('instagram_email_password')

    print(f"[DEBUG] confirm_add_account вызван для {username}")

    query.edit_message_text(
        text=f"🔄 Выполняется вход в аккаунт {username}...\n\n"
        f"Это может занять некоторое время. Пожалуйста, подождите."
    )

    try:
        # Проверяем, требуется ли код подтверждения
        challenge_required, challenge_info = check_login_challenge(username, password, email, email_password)

        if not challenge_required:
            # Если вход успешен, добавляем аккаунт
            success, result = add_instagram_account(username, password, email, email_password)

            if success:
                print(f"[DEBUG] Аккаунт {username} успешно добавлен")
                query.edit_message_text(
                    text=f"✅ Аккаунт {username} успешно добавлен!"
                )
                return ConversationHandler.END
            else:
                print(f"[DEBUG] Ошибка при добавлении аккаунта {username}: {result}")
                query.edit_message_text(
                    text=f"❌ Не удалось добавить аккаунт {username}.\n\n"
                    f"Ошибка: {result}\n\n"
                    f"Пожалуйста, попробуйте снова или используйте другой аккаунт."
                )
                return ConversationHandler.END
        else:
            # Если требуется код подтверждения
            print(f"[DEBUG] Требуется код подтверждения для {username}")

            # Сохраняем информацию о запросе
            context.user_data['challenge_info'] = challenge_info

            # Отправляем сообщение с запросом кода
            query.edit_message_text(
                text=f"📱 Требуется подтверждение для аккаунта *{username}*\n\n"
                f"Instagram запрашивает код подтверждения, отправленный на электронную почту.\n\n"
                f"Пожалуйста, введите код подтверждения (6 цифр):",
                parse_mode='Markdown'
            )

            return ENTER_VERIFICATION_CODE

    except Exception as e:
        print(f"[DEBUG] Ошибка в confirm_add_account для {username}: {str(e)}")
        logger.error(f"Ошибка в confirm_add_account для {username}: {str(e)}")

        query.edit_message_text(
            text=f"❌ Произошла ошибка при входе в аккаунт {username}.\n\n"
            f"Ошибка: {str(e)}\n\n"
            f"Пожалуйста, попробуйте снова или используйте другой аккаунт."
        )
        return ConversationHandler.END

def enter_verification_code(update, context):
    """Обработчик ввода кода подтверждения"""
    user_data = context.user_data
    verification_code = update.message.text.strip()

    print(f"[DEBUG] enter_verification_code вызван с кодом {verification_code}")

    username = user_data.get('instagram_username')  # Исправлено
    password = user_data.get('instagram_password')  # Исправлено
    challenge_info = user_data.get('challenge_info')

    print(f"[DEBUG] Данные для {username}: challenge_info={bool(challenge_info)}")

    if not challenge_info:
        update.message.reply_text("❌ Ошибка: данные о запросе на подтверждение отсутствуют.")
        return ConversationHandler.END

    # Отправляем код подтверждения
    from instagram.client import submit_challenge_code

    print(f"[DEBUG] Вызываем submit_challenge_code для {username} с кодом {verification_code}")
    success, result = submit_challenge_code(username, password, verification_code, challenge_info)

    print(f"[DEBUG] Результат submit_challenge_code: success={success}, result={result}")

    if not success:
        update.message.reply_text(f"❌ Ошибка при проверке кода: {result}\n\nПожалуйста, проверьте код и попробуйте снова.")
        return ENTER_VERIFICATION_CODE

    # Код подтверждения принят, добавляем аккаунт
    return save_account_from_telegram(update, context)

def verification_code_handler(update, context):
    """Обработчик для ввода кода подтверждения"""
    user_id = update.effective_user.id
    code = update.message.text.strip()

    print(f"[VERIFICATION_HANDLER] Получен код подтверждения: {code} от пользователя {user_id}")

    # Проверяем формат кода (6 цифр)
    if not code.isdigit() or len(code) != 6:
        print(f"[VERIFICATION_HANDLER] Некорректный формат кода: {code}")
        update.message.reply_text("Пожалуйста, введите корректный код подтверждения (6 цифр).")
        return

    # Используем статический метод для установки кода
    from instagram.auth_manager import TelegramChallengeHandler
    if TelegramChallengeHandler.set_code(user_id, code):
        update.message.reply_text("✅ Код подтверждения принят. Выполняется вход...")
    else:
        update.message.reply_text("В данный момент код подтверждения не запрашивается.")

def cancel_add_account(update, context):
    """Обработчик отмены добавления аккаунта"""
    query = update.callback_query
    query.answer()

    # Очищаем данные
    if 'instagram_username' in context.user_data:
        del context.user_data['instagram_username']
    if 'instagram_password' in context.user_data:
        del context.user_data['instagram_password']
    if 'instagram_client' in context.user_data:
        del context.user_data['instagram_client']
    if 'challenge_handler' in context.user_data:
        del context.user_data['challenge_handler']

    keyboard = [[InlineKeyboardButton("🔙 К меню аккаунтов", callback_data='menu_accounts')]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    query.edit_message_text(
        "❌ Добавление аккаунта отменено.",
        reply_markup=reply_markup
    )

    return ConversationHandler.END

def list_accounts_handler(update, context):
    session = get_session()
    accounts = session.query(InstagramAccount).all()
    session.close()

    if update.callback_query:
        query = update.callback_query
        query.answer()

        if not accounts:
            keyboard = [
                [InlineKeyboardButton("➕ Добавить аккаунт", callback_data='add_account')],
                [InlineKeyboardButton("🔙 К меню аккаунтов", callback_data='menu_accounts')]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)

            query.edit_message_text(
                "У вас пока нет добавленных аккаунтов Instagram.",
                reply_markup=reply_markup
            )
            return

        accounts_text = "📋 *Список ваших аккаунтов Instagram:*\n\n"
        keyboard = []

        for account in accounts:
            status = "✅ Активен" if account.is_active else "❌ Неактивен"
            accounts_text += f"👤 *{account.username}*\n"
            accounts_text += f"🆔 ID: `{account.id}`\n"
            accounts_text += f"📅 Добавлен: {account.created_at.strftime('%d.%m.%Y %H:%M')}\n"
            accounts_text += f"📊 Статус: {status}\n\n"

            # Добавляем кнопку удаления для каждого аккаунта
            keyboard.append([InlineKeyboardButton(f"🗑️ Удалить {account.username}", callback_data=f'delete_account_{account.id}')])

        # Добавляем кнопку для удаления всех аккаунтов
        if accounts:
            keyboard.append([InlineKeyboardButton("🗑️ Удалить все аккаунты", callback_data='delete_all_accounts')])

        keyboard.append([InlineKeyboardButton("🔄 Проверить валидность", callback_data='check_accounts_validity')])
        keyboard.append([InlineKeyboardButton("🔙 К меню аккаунтов", callback_data='menu_accounts')])

        reply_markup = InlineKeyboardMarkup(keyboard)

        query.edit_message_text(
            accounts_text,
            reply_markup=reply_markup,
            parse_mode=ParseMode.MARKDOWN
        )
    else:
        if not accounts:
            keyboard = [
                [InlineKeyboardButton("➕ Добавить аккаунт", callback_data='add_account')],
                [InlineKeyboardButton("🔙 К меню аккаунтов", callback_data='menu_accounts')]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)

            update.message.reply_text(
                "У вас пока нет добавленных аккаунтов Instagram.",
                reply_markup=reply_markup
            )
            return

        accounts_text = "📋 *Список ваших аккаунтов Instagram:*\n\n"
        keyboard = []

        for account in accounts:
            status = "✅ Активен" if account.is_active else "❌ Неактивен"
            accounts_text += f"👤 *{account.username}*\n"
            accounts_text += f"🆔 ID: `{account.id}`\n"
            accounts_text += f"📅 Добавлен: {account.created_at.strftime('%d.%m.%Y %H:%M')}\n"
            accounts_text += f"📊 Статус: {status}\n\n"

            # Добавляем кнопку удаления для каждого аккаунта
            keyboard.append([InlineKeyboardButton(f"🗑️ Удалить {account.username}", callback_data=f'delete_account_{account.id}')])

        # Добавляем кнопку для удаления всех аккаунтов
        if accounts:
            keyboard.append([InlineKeyboardButton("🗑️ Удалить все аккаунты", callback_data='delete_all_accounts')])

        keyboard.append([InlineKeyboardButton("🔄 Проверить валидность", callback_data='check_accounts_validity')])
        keyboard.append([InlineKeyboardButton("🔙 К меню аккаунтов", callback_data='menu_accounts')])

        reply_markup = InlineKeyboardMarkup(keyboard)

        update.message.reply_text(
            accounts_text,
            reply_markup=reply_markup,
            parse_mode=ParseMode.MARKDOWN
        )

def delete_account_handler(update, context):
    """Обработчик для удаления аккаунта"""
    query = update.callback_query
    query.answer()

    # Получаем ID аккаунта из callback_data
    account_id = int(query.data.split('_')[2])

    # Получаем информацию об аккаунте
    account = get_instagram_account(account_id)

    if not account:
        keyboard = [[InlineKeyboardButton("🔙 К списку аккаунтов", callback_data='list_accounts')]]
        reply_markup = InlineKeyboardMarkup(keyboard)

        query.edit_message_text(
            "Аккаунт не найден.",
            reply_markup=reply_markup
        )
        return

    try:
        session = get_session()

        # Сначала удаляем связанные задачи
        session.query(PublishTask).filter_by(account_id=account_id).delete()

        # Затем удаляем аккаунт
        account = session.query(InstagramAccount).filter_by(id=account_id).first()
        if account:
            session.delete(account)
            session.commit()

            # Удаляем файл сессии, если он существует
            session_dir = os.path.join(ACCOUNTS_DIR, str(account_id))
            if os.path.exists(session_dir):
                shutil.rmtree(session_dir)

            keyboard = [[InlineKeyboardButton("🔙 К списку аккаунтов", callback_data='list_accounts')]]
            reply_markup = InlineKeyboardMarkup(keyboard)

            query.edit_message_text(
                f"✅ Аккаунт {account.username} успешно удален.",
                reply_markup=reply_markup
            )
        else:
            keyboard = [[InlineKeyboardButton("🔙 К списку аккаунтов", callback_data='list_accounts')]]
            reply_markup = InlineKeyboardMarkup(keyboard)

            query.edit_message_text(
                "Аккаунт не найден.",
                reply_markup=reply_markup
            )
    except Exception as e:
        session.rollback()

        keyboard = [[InlineKeyboardButton("🔙 К списку аккаунтов", callback_data='list_accounts')]]
        reply_markup = InlineKeyboardMarkup(keyboard)

        query.edit_message_text(
            f"❌ Ошибка при удалении аккаунта: {str(e)}",
            reply_markup=reply_markup
        )
    finally:
        session.close()

def delete_all_accounts_handler(update, context):
    query = update.callback_query
    query.answer()

    keyboard = [
        [
            InlineKeyboardButton("✅ Да, удалить все", callback_data='confirm_delete_all_accounts'),
            InlineKeyboardButton("❌ Нет, отмена", callback_data='list_accounts')
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    query.edit_message_text(
        "⚠️ Вы уверены, что хотите удалить ВСЕ аккаунты?\n\n"
        "Это действие нельзя отменить. Все данные аккаунтов будут удалены.",
        reply_markup=reply_markup
    )

def confirm_delete_all_accounts_handler(update, context):
    query = update.callback_query
    query.answer()

    try:
        session = get_session()
        accounts = session.query(InstagramAccount).all()
        session.close()

        # Удаляем каждый аккаунт с помощью нашей новой функции
        from instagram.client import remove_instagram_account
        success_count = 0
        failed_count = 0

        for account in accounts:
            try:
                if remove_instagram_account(account.id):
                    success_count += 1
                else:
                    failed_count += 1
            except Exception as e:
                logger.error(f"Ошибка при удалении аккаунта {account.username}: {e}")
                failed_count += 1

        keyboard = [[InlineKeyboardButton("🔙 К меню аккаунтов", callback_data='menu_accounts')]]
        reply_markup = InlineKeyboardMarkup(keyboard)

        if failed_count == 0:
            query.edit_message_text(
                f"✅ Все аккаунты успешно удалены ({success_count}).",
                reply_markup=reply_markup
            )
        else:
            query.edit_message_text(
                f"⚠️ Удалено {success_count} аккаунтов, не удалось удалить {failed_count} аккаунтов.",
                reply_markup=reply_markup
            )
    except Exception as e:
        keyboard = [[InlineKeyboardButton("🔙 К списку аккаунтов", callback_data='list_accounts')]]
        reply_markup = InlineKeyboardMarkup(keyboard)

        query.edit_message_text(
            f"❌ Ошибка при удалении аккаунтов: {str(e)}",
            reply_markup=reply_markup
        )

def check_accounts_validity_handler(update, context):
    query = update.callback_query
    query.answer()

    query.edit_message_text("🔄 Проверка валидности аккаунтов... Это может занять некоторое время.")

    session = get_session()
    accounts = session.query(InstagramAccount).all()

    if not accounts:
        keyboard = [[InlineKeyboardButton("🔙 К меню аккаунтов", callback_data='menu_accounts')]]
        reply_markup = InlineKeyboardMarkup(keyboard)

        query.edit_message_text(
            "У вас нет добавленных аккаунтов для проверки.",
            reply_markup=reply_markup
        )
        session.close()
        return

    results = []

    for account in accounts:
        try:
            client = Client()

            # Проверяем наличие сессии
            session_file = os.path.join(ACCOUNTS_DIR, str(account.id), 'session.json')
            if os.path.exists(session_file):
                try:
                    with open(session_file, 'r') as f:
                        session_data = json.load(f)

                    if 'settings' in session_data:
                        client.set_settings(session_data['settings'])

                    # Проверяем валидность сессии
                    try:
                        client.get_timeline_feed()
                        results.append((account.username, True, "Сессия валидна"))
                        continue
                    except:
                        # Если сессия невалидна, пробуем войти с логином и паролем
                        pass
                except:
                    pass

            # Пробуем войти с логином и паролем
            try:
                client.login(account.username, account.password)

                # Сохраняем обновленную сессию
                os.makedirs(os.path.join(ACCOUNTS_DIR, str(account.id)), exist_ok=True)
                session_data = {
                    'username': account.username,
                    'account_id': account.id,
                    'updated_at': time.strftime('%Y-%m-%d %H:%M:%S'),
                    'settings': client.get_settings()
                }
                with open(session_file, 'w') as f:
                    json.dump(session_data, f)

                results.append((account.username, True, "Успешный вход"))
            except Exception as e:
                results.append((account.username, False, str(e)))
        except Exception as e:
            results.append((account.username, False, str(e)))

    session.close()

    # Формируем отчет
    report = "📊 *Результаты проверки аккаунтов:*\n\n"

    for username, is_valid, message in results:
        status = "✅ Валиден" if is_valid else "❌ Невалиден"
        report += f"👤 *{username}*: {status}\n"
        if not is_valid:
            report += f"📝 Причина: {message}\n"
        report += "\n"

    keyboard = [[InlineKeyboardButton("🔙 К списку аккаунтов", callback_data='list_accounts')]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    query.edit_message_text(
        report,
        reply_markup=reply_markup,
        parse_mode=ParseMode.MARKDOWN
    )

def bulk_upload_accounts_command(update, context):
    if update.callback_query:
        query = update.callback_query
        query.answer()

        keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data='menu_accounts')]]
        reply_markup = InlineKeyboardMarkup(keyboard)

        query.edit_message_text(
            "Отправьте TXT файл с аккаунтами Instagram.\n\n"
            "Формат файла:\n"
            "username:password\n"
            "username:password\n"
            "...\n\n"
            "Каждый аккаунт должен быть на новой строке в формате username:password",
            reply_markup=reply_markup
        )
    else:
        keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data='menu_accounts')]]
        reply_markup = InlineKeyboardMarkup(keyboard)

        update.message.reply_text(
            "Отправьте TXT файл с аккаунтами Instagram.\n\n"
            "Формат файла:\n"
            "username:password\n"
            "username:password\n"
            "...\n\n"
            "Каждый аккаунт должен быть на новой строке в формате username:password",
            reply_markup=reply_markup
        )

    # Устанавливаем состояние для ожидания файла
    context.user_data['waiting_for_accounts_file'] = True
    return WAITING_ACCOUNTS_FILE

def bulk_upload_accounts_file(update, context):
    # Сбрасываем флаг ожидания файла
    context.user_data['waiting_for_accounts_file'] = False

    file = update.message.document

    if not file.file_name.endswith('.txt'):
        keyboard = [[InlineKeyboardButton("🔙 К меню аккаунтов", callback_data='menu_accounts')]]
        reply_markup = InlineKeyboardMarkup(keyboard)

        update.message.reply_text(
            "❌ Пожалуйста, отправьте файл в формате .txt",
            reply_markup=reply_markup
        )
        return ConversationHandler.END

    # Скачиваем файл
    file_path = os.path.join(MEDIA_DIR, file.file_name)
    file_obj = context.bot.get_file(file.file_id)
    file_obj.download(file_path)

    # Читаем файл
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()

        accounts = []
        for line in lines:
            line = line.strip()
            if not line or ':' not in line:
                continue

            parts = line.split(':', 1)
            if len(parts) != 2:
                continue

            username, password = parts
            accounts.append((username.strip(), password.strip()))

        if not accounts:
            keyboard = [[InlineKeyboardButton("🔙 К меню аккаунтов", callback_data='menu_accounts')]]
            reply_markup = InlineKeyboardMarkup(keyboard)

            update.message.reply_text(
                "❌ В файле не найдено аккаунтов в правильном формате.",
                reply_markup=reply_markup
            )
            return ConversationHandler.END

        # Добавляем аккаунты в базу данных
        added, skipped, errors = bulk_add_instagram_accounts(accounts)

        # Формируем отчет
        report = f"📊 *Результаты загрузки аккаунтов:*\n\n"
        report += f"✅ Успешно добавлено: {added}\n"
        report += f"⚠️ Пропущено (уже существуют): {skipped}\n"
        report += f"❌ Ошибки: {len(errors)}\n\n"

        if errors:
            report += "*Ошибки при добавлении:*\n"
            for username, error in errors:
                report += f"👤 *{username}*: {error}\n"

        keyboard = [[InlineKeyboardButton("🔙 К списку аккаунтов", callback_data='list_accounts')]]
        reply_markup = InlineKeyboardMarkup(keyboard)

        update.message.reply_text(
            report,
            reply_markup=reply_markup,
            parse_mode=ParseMode.MARKDOWN
        )

    except Exception as e:
        keyboard = [[InlineKeyboardButton("🔙 К меню аккаунтов", callback_data='menu_accounts')]]
        reply_markup = InlineKeyboardMarkup(keyboard)

        update.message.reply_text(
            f"❌ Произошла ошибка при обработке файла: {str(e)}",
            reply_markup=reply_markup
        )

    # Удаляем временный файл
    try:
        os.remove(file_path)
    except:
        pass

    return ConversationHandler.END

def profile_setup_handler(update, context):
    if update.callback_query:
        query = update.callback_query
        query.answer()

        keyboard = [[InlineKeyboardButton("🔙 К меню аккаунтов", callback_data='menu_accounts')]]
        reply_markup = InlineKeyboardMarkup(keyboard)

        query.edit_message_text(
            "⚙️ Функция настройки профиля находится в разработке.\n\n"
            "Пожалуйста, попробуйте позже.",
            reply_markup=reply_markup
        )
    else:
        keyboard = [[InlineKeyboardButton("🔙 К меню аккаунтов", callback_data='menu_accounts')]]
        reply_markup = InlineKeyboardMarkup(keyboard)

        update.message.reply_text(
            "⚙️ Функция настройки профиля находится в разработке.\n\n"
            "Пожалуйста, попробуйте позже.",
            reply_markup=reply_markup
        )

# Новые асинхронные функции для обработки аккаунтов
async def process_account_async(account_data):
    """Асинхронная функция для обработки одного аккаунта"""
    username, password, email, email_password = account_data
    result = {
        "username": username,
        "status": "failed",
        "message": ""
    }
    
    try:
        # Проверяем, существует ли уже аккаунт с таким именем
        session = get_session()
        existing_account = session.query(InstagramAccount).filter_by(username=username).first()
        session.close()

        if existing_account:
            result["status"] = "skipped"
            result["message"] = "Аккаунт уже существует в базе данных"
            return result

        # Добавляем аккаунт в базу данных без проверки входа
        from database.db_manager import add_instagram_account_without_login
        account = add_instagram_account_without_login(
            username=username,
            password=password,
            email=email,
            email_password=email_password
        )

        if not account:
            result["message"] = "Не удалось добавить аккаунт в базу данных"
            return result

        # Назначаем прокси для аккаунта
        from utils.proxy_manager import assign_proxy_to_account
        proxy_success, proxy_message = assign_proxy_to_account(account.id)
        
        # Проверяем подключение к почте
        from instagram.email_utils import test_email_connection
        email_success, email_message = test_email_connection(email, email_password)
        
        if not email_success:
            result["message"] = f"Ошибка подключения к почте: {email_message}"
            return result

        # Пытаемся войти в Instagram с использованием прокси
        from instagram.client import test_instagram_login_with_proxy
        login_success = test_instagram_login_with_proxy(
            account_id=account.id,
            username=username,
            password=password,
            email=email,
            email_password=email_password
        )

        if login_success:
            # Если вход успешен, активируем аккаунт
            from database.db_manager import activate_instagram_account
            activate_instagram_account(account.id)
            result["status"] = "success"
            result["message"] = "Аккаунт успешно добавлен и активирован"
        else:
            result["status"] = "partial"
            result["message"] = "Аккаунт добавлен, но не удалось войти в Instagram"
            
        return result
    except Exception as e:
        result["message"] = str(e)
        logger.error(f"Ошибка при добавлении аккаунта {username}: {str(e)}")
        return result

async def async_bulk_add_accounts(update, context, accounts_data):
    """Асинхронно обрабатывает массовое добавление аккаунтов"""
    update.message.reply_text(f"🔄 Начинаем асинхронное добавление {len(accounts_data)} аккаунтов...")
    
    # Создаем пул задач для обработки аккаунтов
    tasks = []
    for account_data in accounts_data:
        tasks.append(process_account_async(account_data))
    
    # Запускаем все задачи параллельно и ждем их завершения
    results = await asyncio.gather(*tasks)
    
    # Подсчитываем статистику
    success_count = sum(1 for r in results if r["status"] == "success")
    partial_count = sum(1 for r in results if r["status"] == "partial")
    skipped_count = sum(1 for r in results if r["status"] == "skipped")
    failed_count = sum(1 for r in results if r["status"] == "failed")
    
    # Формируем отчет
    report = f"📊 *Результаты асинхронного добавления аккаунтов:*\n\n"
    report += f"✅ Успешно добавлено: {success_count}\n"
    report += f"⚠️ Частично добавлено: {partial_count}\n"
    report += f"⏭️ Пропущено (уже существуют): {skipped_count}\n"
    report += f"❌ Не удалось добавить: {failed_count}\n\n"
    
    # Добавляем детали по неудачным аккаунтам
    failed_accounts = [r for r in results if r["status"] == "failed"]
    if failed_accounts:
        report += "*Ошибки при добавлении:*\n"
        for account in failed_accounts:
            report += f"👤 *{account['username']}*: {account['message']}\n"
    
    keyboard = [[InlineKeyboardButton("🔙 К списку аккаунтов", callback_data='list_accounts')]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    update.message.reply_text(
        report,
        reply_markup=reply_markup,
        parse_mode=ParseMode.MARKDOWN
    )

def async_upload_accounts_command(update, context):
    """Обработчик команды для асинхронной загрузки аккаунтов"""
    if update.callback_query:
        query = update.callback_query
        query.answer()

        keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data='menu_accounts')]]
        reply_markup = InlineKeyboardMarkup(keyboard)

        query.edit_message_text(
            "Отправьте TXT файл с аккаунтами Instagram для асинхронной загрузки.\n\n"
            "Формат файла:\n"
            "username:password:email:email_password\n"
            "username:password:email:email_password\n"
            "...\n\n"
            "Каждый аккаунт должен быть на новой строке в указанном формате.",
            reply_markup=reply_markup
        )
        context.user_data['waiting_for_async_accounts_file'] = True
        return WAITING_ACCOUNTS_FILE
    else:
        keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data='menu_accounts')]]
        reply_markup = InlineKeyboardMarkup(keyboard)

        update.message.reply_text(
            "Отправьте TXT файл с аккаунтами Instagram для асинхронной загрузки.\n\n"
            "Формат файла:\n"
            "username:password:email:email_password\n"
            "username:password:email:email_password\n"
            "...\n\n"
            "Каждый аккаунт должен быть на новой строке в указанном формате.",
            reply_markup=reply_markup
        )
        context.user_data['waiting_for_async_accounts_file'] = True
        return WAITING_ACCOUNTS_FILE

def async_upload_accounts_file(update, context):
    """Обработчик для файла с аккаунтами для асинхронной загрузки"""
    # Сбрасываем флаг ожидания файла
    context.user_data['waiting_for_async_accounts_file'] = False

    file = update.message.document

    if not file.file_name.endswith('.txt'):
        keyboard = [[InlineKeyboardButton("🔙 К меню аккаунтов", callback_data='menu_accounts')]]
        reply_markup = InlineKeyboardMarkup(keyboard)

        update.message.reply_text(
            "❌ Пожалуйста, отправьте файл в формате .txt",
            reply_markup=reply_markup
        )
        return ConversationHandler.END

    # Скачиваем файл
    file_path = os.path.join(MEDIA_DIR, file.file_name)
    file_obj = context.bot.get_file(file.file_id)
    file_obj.download(file_path)

    # Читаем файл
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()

        accounts_data = []
        for line in lines:
            line = line.strip()
            if not line:
                continue

            parts = line.split(':')
            if len(parts) != 4:
                continue

            username, password, email, email_password = parts
            accounts_data.append((username.strip(), password.strip(), email.strip(), email_password.strip()))

        if not accounts_data:
            keyboard = [[InlineKeyboardButton("🔙 К меню аккаунтов", callback_data='menu_accounts')]]
            reply_markup = InlineKeyboardMarkup(keyboard)

            update.message.reply_text(
                "❌ В файле не найдено аккаунтов в правильном формате.",
                reply_markup=reply_markup
            )
            return ConversationHandler.END

        # Запускаем асинхронную обработку аккаунтов
        asyncio.run(async_bulk_add_accounts(update, context, accounts_data))

    except Exception as e:
        keyboard = [[InlineKeyboardButton("🔙 К меню аккаунтов", callback_data='menu_accounts')]]
        reply_markup = InlineKeyboardMarkup(keyboard)

        update.message.reply_text(
            f"❌ Произошла ошибка при обработке файла: {str(e)}",
            reply_markup=reply_markup
        )

    # Удаляем временный файл
    try:
        os.remove(file_path)
    except:
        pass

    return ConversationHandler.END

def get_account_handlers():
    """Возвращает обработчики для управления аккаунтами"""
    from telegram.ext import CommandHandler, CallbackQueryHandler, MessageHandler, Filters

    # Новый ConversationHandler для массовой загрузки аккаунтов
    bulk_upload_conversation = ConversationHandler(
        entry_points=[
            CommandHandler("upload_accounts", bulk_upload_accounts_command),
            CallbackQueryHandler(bulk_upload_accounts_command, pattern='^upload_accounts$')
        ],
        states={
            WAITING_ACCOUNTS_FILE: [
                MessageHandler(Filters.document.file_extension("txt"), bulk_upload_accounts_file),
                CallbackQueryHandler(lambda u, c: ConversationHandler.END, pattern='^menu_accounts$')
            ]
        },
        fallbacks=[CommandHandler("cancel", lambda update, context: ConversationHandler.END)]
    )
    
    # Новый ConversationHandler для асинхронной загрузки аккаунтов
    async_upload_conversation = ConversationHandler(
        entry_points=[
            CommandHandler("async_upload_accounts", async_upload_accounts_command),
            CallbackQueryHandler(async_upload_accounts_command, pattern='^async_upload_accounts$')
        ],
        states={
            WAITING_ACCOUNTS_FILE: [
                MessageHandler(Filters.document.file_extension("txt"), async_upload_accounts_file),
                CallbackQueryHandler(lambda u, c: ConversationHandler.END, pattern='^menu_accounts$')
            ]
        },
        fallbacks=[CommandHandler("cancel", lambda update, context: ConversationHandler.END)]
    )

    return [
        CommandHandler("accounts", accounts_handler),
        # Удаляем account_conversation, так как он теперь регистрируется в bot.py
        bulk_upload_conversation,
        async_upload_conversation,
        CommandHandler("list_accounts", list_accounts_handler),
        CommandHandler("profile_setup", profile_setup_handler),
        CallbackQueryHandler(delete_account_handler, pattern='^delete_account_\\d+$'),
        CallbackQueryHandler(delete_all_accounts_handler, pattern='^delete_all_accounts$'),
        CallbackQueryHandler(confirm_delete_all_accounts_handler, pattern='^confirm_delete_all_accounts$'),
        CallbackQueryHandler(check_accounts_validity_handler, pattern='^check_accounts_validity$')
    ]

def bulk_add_accounts_command(update, context):
    """Обработчик команды /bulk_add_accounts для массового добавления аккаунтов"""
    user_id = update.effective_user.id

    # Проверяем, является ли пользователь администратором
    if not is_admin(user_id):
        update.message.reply_text("У вас нет прав для выполнения этой команды.")
        return

    # Проверяем, есть ли текст после команды
    if not context.args:
        update.message.reply_text(
            "Пожалуйста, укажите аккаунты в формате:\n\n"
            "/bulk_add_accounts\n"
            "username1:password1:email1:email_password1\n"
            "username2:password2:email2:email_password2\n"
            "...\n\n"
            "Каждый аккаунт должен быть на новой строке."
        )
        return

    # Получаем текст после команды
    accounts_text = " ".join(context.args)

    # Разбиваем текст на строки
    accounts_lines = accounts_text.strip().split("\n")

    # Статистика
    total_accounts = len(accounts_lines)
    added_accounts = 0
    failed_accounts = 0
    already_exists = 0
    failed_accounts_list = []

    update.message.reply_text(f"🔄 Начинаем добавление {total_accounts} аккаунтов...")

    # Обрабатываем каждую строку
    for line in accounts_lines:
        line = line.strip()
        if not line:
            continue

        parts = line.split(":")
        if len(parts) != 4:
            update.message.reply_text(f"❌ Неверный формат строки: {line}")
            failed_accounts += 1
            failed_accounts_list.append(f"{line} - неверный формат")
            continue

        username, password, email, email_password = parts

        # Проверяем, существует ли уже аккаунт с таким именем
        session = get_session()
        existing_account = session.query(InstagramAccount).filter_by(username=username).first()
        session.close()

        if existing_account:
            update.message.reply_text(f"⚠️ Аккаунт {username} уже существует в базе данных.")
            already_exists += 1
            continue

        try:
            # Добавляем аккаунт в базу данных без проверки входа
            from database.db_manager import add_instagram_account_without_login

            account = add_instagram_account_without_login(
                username=username,
                password=password,
                email=email,
                email_password=email_password
            )

            if not account:
                update.message.reply_text(f"❌ Не удалось добавить аккаунт {username} в базу данных.")
                failed_accounts += 1
                failed_accounts_list.append(f"{username} - ошибка добавления в БД")
                continue

            # Назначаем прокси для аккаунта
            from utils.proxy_manager import assign_proxy_to_account
            proxy_success, proxy_message = assign_proxy_to_account(account.id)

            if not proxy_success:
                update.message.reply_text(f"⚠️ {username}: {proxy_message}")

            # Проверяем подключение к почте
            from instagram.email_utils import test_email_connection
            email_success, email_message = test_email_connection(email, email_password)

            if not email_success:
                update.message.reply_text(f"⚠️ {username}: Ошибка подключения к почте: {email_message}")
                # Продолжаем, даже если не удалось подключиться к почте

            # Пытаемся войти в Instagram с использованием прокси
            from instagram.client import test_instagram_login_with_proxy
            login_success = test_instagram_login_with_proxy(
                account_id=account.id,
                username=username,
                password=password,
                email=email,
                email_password=email_password
            )

            if login_success:
                # Если вход успешен, активируем аккаунт
                from database.db_manager import activate_instagram_account
                activate_instagram_account(account.id)
                update.message.reply_text(f"✅ Аккаунт {username} успешно добавлен и активирован!")
            else:
                update.message.reply_text(f"⚠️ Аккаунт {username} добавлен, но не удалось войти в Instagram.")

            added_accounts += 1

        except Exception as e:
            update.message.reply_text(f"❌ Ошибка при добавлении аккаунта {username}: {str(e)}")
            logger.error(f"Ошибка при добавлении аккаунта {username}: {str(e)}")
            failed_accounts += 1
            failed_accounts_list.append(f"{username} - {str(e)}")

    # Отправляем итоговую статистику
    summary = (
        f"📊 Итоги добавления аккаунтов:\n"
        f"Всего обработано: {total_accounts}\n"
        f"Успешно добавлено: {added_accounts}\n"
        f"Уже существуют: {already_exists}\n"
        f"Не удалось добавить: {failed_accounts}"
    )

    update.message.reply_text(summary)

    # Если есть неудачные аккаунты, отправляем их список
    if failed_accounts_list:
        failed_list = "❌ Список неудачно добавленных аккаунтов:\n" + "\n".join(failed_accounts_list)
        update.message.reply_text(failed_list)

def bulk_add_accounts_text(update, context):
    """Обработчик текстового сообщения с списком аккаунтов"""
    user_id = update.effective_user.id
    text = update.message.text.strip()

    # Разбиваем текст на строки
    accounts_lines = text.split("\n")

    # Статистика
    total_accounts = len(accounts_lines)
    added_accounts = 0
    failed_accounts = 0
    already_exists = 0
    failed_accounts_list = []

    update.message.reply_text(f"🔄 Начинаем добавление {total_accounts} аккаунтов...")

    # Обрабатываем каждую строку
    for line in accounts_lines:
        line = line.strip()
        if not line:
            continue

        parts = line.split(":")
        if len(parts) != 4:
            update.message.reply_text(f"❌ Неверный формат строки: {line}")
            failed_accounts += 1
            failed_accounts_list.append(f"{line} - неверный формат")
            continue

        username, password, email, email_password = parts

        # Проверяем, существует ли уже аккаунт с таким именем
        session = get_session()
        existing_account = session.query(InstagramAccount).filter_by(username=username).first()
        session.close()

        if existing_account:
            update.message.reply_text(f"⚠️ Аккаунт {username} уже существует в базе данных.")
            already_exists += 1
            continue

        try:
            # Добавляем аккаунт в базу данных без проверки входа
            from database.db_manager import add_instagram_account_without_login

            account = add_instagram_account_without_login(
                username=username,
                password=password,
                email=email,
                email_password=email_password
            )

            if not account:
                update.message.reply_text(f"❌ Не удалось добавить аккаунт {username} в базу данных.")
                failed_accounts += 1
                failed_accounts_list.append(f"{username} - ошибка добавления в БД")
                continue

            # Назначаем прокси для аккаунта
            from utils.proxy_manager import assign_proxy_to_account
            proxy_success, proxy_message = assign_proxy_to_account(account.id)

            if not proxy_success:
                update.message.reply_text(f"⚠️ {username}: {proxy_message}")

            # Проверяем подключение к почте
            from instagram.email_utils import test_email_connection
            email_success, email_message = test_email_connection(email, email_password)

            if not email_success:
                update.message.reply_text(f"⚠️ {username}: Ошибка подключения к почте: {email_message}")
                # Продолжаем, даже если не удалось подключиться к почте

            # Пытаемся войти в Instagram с использованием прокси
            from instagram.client import test_instagram_login_with_proxy
            login_success = test_instagram_login_with_proxy(
                account_id=account.id,
                username=username,
                password=password,
                email=email,
                email_password=email_password
            )

            if login_success:
                # Если вход успешен, активируем аккаунт
                from database.db_manager import activate_instagram_account
                activate_instagram_account(account.id)
                update.message.reply_text(f"✅ Аккаунт {username} успешно добавлен и активирован!")
            else:
                update.message.reply_text(f"⚠️ Аккаунт {username} добавлен, но не удалось войти в Instagram.")

            added_accounts += 1

        except Exception as e:
            update.message.reply_text(f"❌ Ошибка при добавлении аккаунта {username}: {str(e)}")
            logger.error(f"Ошибка при добавлении аккаунта {username}: {str(e)}")
            failed_accounts += 1
            failed_accounts_list.append(f"{username} - {str(e)}")

    # Отправляем итоговую статистику
    summary = (
        f"📊 Итоги добавления аккаунтов:\n"
        f"Всего обработано: {total_accounts}\n"
        f"Успешно добавлено: {added_accounts}\n"
        f"Уже существуют: {already_exists}\n"
        f"Не удалось добавить: {failed_accounts}"
    )

    update.message.reply_text(summary)

    # Если есть неудачные аккаунты, отправляем их список
    if failed_accounts_list:
        failed_list = "❌ Список неудачно добавленных аккаунтов:\n" + "\n".join(failed_accounts_list)
        update.message.reply_text(failed_list)

    # Возвращаем клавиатуру меню аккаунтов
    keyboard = [
        [InlineKeyboardButton("➕ Добавить аккаунт", callback_data='add_account')],
        [InlineKeyboardButton("📋 Список аккаунтов", callback_data='list_accounts')],
        [InlineKeyboardButton("🔙 Назад", callback_data='back_to_main')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    update.message.reply_text("Выберите действие:", reply_markup=reply_markup)

    # Очищаем флаг ожидания списка аккаунтов
    context.user_data['waiting_for_bulk_accounts'] = False

    return ConversationHandler.END