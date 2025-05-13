import os
import tempfile
import json
import logging
import threading
from datetime import datetime

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, ParseMode
from telegram.ext import ConversationHandler

from database.db_manager import get_instagram_account, get_instagram_accounts, create_publish_task
from instagram_api.publisher import publish_video
from database.models import TaskType, TaskStatus
from instagram.reels_manager import publish_reels_in_parallel
from utils.task_queue import add_task_to_queue, get_task_status

logger = logging.getLogger(__name__)

# Состояния для публикации видео
CHOOSE_ACCOUNT, ENTER_CAPTION, CONFIRM_PUBLISH, CHOOSE_SCHEDULE, CHOOSE_HIDE_FROM_FEED = range(10, 15)

def is_admin(user_id):
    from telegram_bot.bot import is_admin
    return is_admin(user_id)

def publish_now_handler(update, context):
    """Обработчик команды публикации контента"""
    user_id = update.effective_user.id

    if not is_admin(user_id):
        update.message.reply_text("У вас нет прав для выполнения этой команды.")
        return ConversationHandler.END

    # Получаем список аккаунтов
    accounts = get_instagram_accounts()

    if not accounts:
        keyboard = [[InlineKeyboardButton("➕ Добавить аккаунт", callback_data='add_account')]]
        reply_markup = InlineKeyboardMarkup(keyboard)

        update.message.reply_text(
            "У вас нет добавленных аккаунтов Instagram. Сначала добавьте аккаунт.",
            reply_markup=reply_markup
        )
        return ConversationHandler.END

    # Создаем клавиатуру с аккаунтами
    keyboard = []
    for account in accounts:
        if account.is_active:
            keyboard.append([InlineKeyboardButton(f"👤 {account.username}", callback_data=f"publish_account_{account.id}")])

    # Добавляем кнопку "Выбрать все аккаунты"
    keyboard.append([InlineKeyboardButton("✅ Выбрать все аккаунты", callback_data='publish_all_accounts')])
    keyboard.append([InlineKeyboardButton("🔙 Отмена", callback_data='cancel_publish')])
    reply_markup = InlineKeyboardMarkup(keyboard)

    if update.callback_query:
        query = update.callback_query
        query.answer()
        query.edit_message_text(
            "Выберите аккаунт для публикации:",
            reply_markup=reply_markup
        )
    else:
        update.message.reply_text(
            "Выберите аккаунт для публикации:",
            reply_markup=reply_markup
        )

    return CHOOSE_ACCOUNT

def choose_account_callback(update, context):
    """Обработчик выбора аккаунта для публикации"""
    query = update.callback_query
    query.answer()

    # Получаем ID аккаунта из callback_data
    account_id = int(query.data.split('_')[-1])
    context.user_data['publish_account_id'] = account_id

    # Добавляем аккаунт в список выбранных (для совместимости)
    if 'selected_accounts' not in context.user_data:
        context.user_data['selected_accounts'] = []
    context.user_data['selected_accounts'].append(account_id)

    # Получаем аккаунт
    account = get_instagram_account(account_id)
    context.user_data['publish_account_username'] = account.username

    # Проверяем, есть ли уже медиафайл
    if 'publish_media_path' in context.user_data:
        # Если медиафайл уже загружен, переходим к вводу подписи
        query.edit_message_text(
            f"Выбран аккаунт: *{account.username}*\n\n"
            f"Теперь введите подпись к публикации (или отправьте /skip для публикации без подписи):",
            parse_mode=ParseMode.MARKDOWN
        )
        return ENTER_CAPTION
    else:
        # Если медиафайла нет, просим загрузить
        query.edit_message_text(
            f"Выбран аккаунт: *{account.username}*\n\n"
            f"Теперь отправьте видео для публикации:",
            parse_mode=ParseMode.MARKDOWN
        )
        return ConversationHandler.END

def choose_all_accounts_callback(update, context):
    """Обработчик выбора всех аккаунтов для публикации"""
    query = update.callback_query
    query.answer()

    # Получаем все активные аккаунты
    accounts = get_instagram_accounts()
    active_accounts = [account for account in accounts if account.is_active]

    if not active_accounts:
        query.edit_message_text("Нет активных аккаунтов для публикации.")
        return ConversationHandler.END

    # Сохраняем список ID всех аккаунтов
    account_ids = [account.id for account in active_accounts]
    context.user_data['publish_account_ids'] = account_ids
    context.user_data['publish_to_all_accounts'] = True

    # Сохраняем имена пользователей для отображения
    account_usernames = [account.username for account in active_accounts]
    context.user_data['publish_account_usernames'] = account_usernames

    # Формируем список имен аккаунтов для отображения
    account_names = [account.username for account in active_accounts]
    accounts_str = ", ".join(account_names)

    # Проверяем, есть ли уже медиафайл
    if 'publish_media_path' in context.user_data:
        # Если медиафайл уже загружен, переходим к вводу подписи
        query.edit_message_text(
            f"Выбраны все аккаунты ({len(active_accounts)}):\n{accounts_str}\n\n"
            f"Теперь введите подпись к публикации (или отправьте /skip для публикации без подписи):"
        )
        return ENTER_CAPTION
    else:
        # Если медиафайла нет, просим загрузить
        query.edit_message_text(
            f"Выбраны все аккаунты ({len(active_accounts)}):\n{accounts_str}\n\n"
            f"Теперь отправьте видео для публикации:"
        )
        return ConversationHandler.END  # Здесь мы завершаем разговор, чтобы пользователь мог загрузить видео

def choose_category_callback(update, context):
    """Обработчик выбора категории аккаунтов (заглушка)"""
    query = update.callback_query
    query.answer()

    query.edit_message_text(
        "🚧 Функция выбора категории находится в разработке.\n\n"
        "Пожалуйста, выберите конкретный аккаунт или все аккаунты."
    )

    # Возвращаемся к выбору аккаунта
    return publish_now_handler(update, context)

def video_upload_handler(update, context):
    """Обработчик загрузки видео"""
    user_id = update.effective_user.id

    if not is_admin(user_id):
        update.message.reply_text("У вас нет прав для выполнения этой команды.")
        return

    # Проверяем, выбран ли аккаунт или аккаунты
    if 'publish_account_id' not in context.user_data and 'publish_account_ids' not in context.user_data:
        # Если аккаунт не выбран, запускаем процесс выбора аккаунта
        # Store the video file information for later use
        context.user_data['pending_video'] = update.message.video or update.message.document
        return publish_now_handler(update, context)

    # Получаем информацию о видео
    video_file = update.message.video or update.message.document
    file_id = video_file.file_id

    # Скачиваем видео
    video = context.bot.get_file(file_id)

    # Создаем временный файл для сохранения видео
    with tempfile.NamedTemporaryFile(delete=False, suffix='.mp4') as temp_file:
        video_path = temp_file.name

    # Скачиваем видео во временный файл
    video.download(video_path)

    # Сохраняем путь к видео и тип медиа (используем перечисление)
    context.user_data['publish_media_path'] = video_path
    context.user_data['publish_media_type'] = TaskType.VIDEO.name  # Используем имя из перечисления

    # Запрашиваем подпись
    update.message.reply_text(
        "Видео успешно загружено!\n\n"
        "Теперь введите подпись к публикации (или отправьте /skip для публикации без подписи):"
    )

    return ENTER_CAPTION

def enter_caption(update, context):
    """Обработчик ввода подписи к публикации"""
    if update.message.text == '/skip':
        context.user_data['publish_caption'] = ""
    else:
        context.user_data['publish_caption'] = update.message.text

    # Если это рилс (видео), спрашиваем о видимости в основной сетке
    if context.user_data.get('publish_media_type') == TaskType.VIDEO.name:
        keyboard = [
            [
                InlineKeyboardButton("✅ Оставить в основной сетке", callback_data='keep_in_feed'),
                InlineKeyboardButton("❌ Удалить из основной сетки", callback_data='hide_from_feed')
            ],
            [InlineKeyboardButton("🔙 Отмена", callback_data='cancel_publish')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        update.message.reply_text(
            "Хотите ли вы удалить рилс из основной сетки профиля?\n"
            "(Рилс останется в разделе Reels, но не будет отображаться в основной сетке фотографий)",
            reply_markup=reply_markup
        )
        return CHOOSE_HIDE_FROM_FEED
    else:
        # Для других типов контента переходим сразу к подтверждению
        return show_publish_confirmation(update, context)

def choose_hide_from_feed(update, context):
    """Обработчик выбора видимости рилса в основной сетке"""
    query = update.callback_query
    query.answer()

    if query.data == 'hide_from_feed':
        context.user_data['hide_from_feed'] = True
        query.edit_message_text("Рилс будет удален из основной сетки профиля.")
    else:  # keep_in_feed
        context.user_data['hide_from_feed'] = False
        query.edit_message_text("Рилс останется в основной сетке профиля.")

    # Показываем подтверждение публикации
    return show_publish_confirmation(update, context, is_callback=True)

def show_publish_confirmation(update, context, is_callback=False):
    """Показывает подтверждение публикации"""
    # Получаем данные для публикации
    media_type = context.user_data.get('publish_media_type')
    caption = context.user_data.get('publish_caption')
    hide_from_feed = context.user_data.get('hide_from_feed', False)

    # Проверяем, публикуем на один аккаунт или на несколько
    if context.user_data.get('publish_to_all_accounts'):
        account_ids = context.user_data.get('publish_account_ids', [])
        accounts = [get_instagram_account(account_id) for account_id in account_ids]
        account_usernames = [account.username for account in accounts]
        account_info = f"👥 *Аккаунты:* {len(account_usernames)} аккаунтов"
    else:
        account_id = context.user_data.get('publish_account_id')
        account_username = context.user_data.get('publish_account_username')
        account_info = f"👤 *Аккаунт:* {account_username}"

    # Создаем клавиатуру для подтверждения
    keyboard = [
        [
            InlineKeyboardButton("✅ Опубликовать сейчас", callback_data='confirm_publish_now'),
            InlineKeyboardButton("⏰ Запланировать", callback_data='schedule_publish')
        ],
        [InlineKeyboardButton("❌ Отмена", callback_data='cancel_publish')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    message_text = (
        f"*Данные для публикации:*\n\n"
        f"{account_info}\n"
        f"📝 *Тип:* {media_type}\n"
        f"✏️ *Подпись:* {caption or '(без подписи)'}\n"
    )

    # Добавляем информацию о видимости в основной сетке для рилсов
    if media_type == TaskType.VIDEO.name:
        message_text += f"🔍 *Видимость:* {'Скрыт из основной сетки' if hide_from_feed else 'В основной сетке'}\n"

    message_text += "\nЧто вы хотите сделать?"

    if is_callback:
        query = update.callback_query
        query.edit_message_text(
            message_text,
            reply_markup=reply_markup,
            parse_mode=ParseMode.MARKDOWN
        )
    else:
        update.message.reply_text(
            message_text,
            reply_markup=reply_markup,
            parse_mode=ParseMode.MARKDOWN
        )

    return CONFIRM_PUBLISH

def confirm_publish_now(update, context):
    """Обработчик подтверждения немедленной публикации"""
    query = update.callback_query
    query.answer()

    # Получаем данные для публикации
    media_path = context.user_data.get('publish_media_path')
    media_type = context.user_data.get('publish_media_type')
    caption = context.user_data.get('publish_caption', '')
    hide_from_feed = context.user_data.get('hide_from_feed', False)
    user_id = query.from_user.id

    # Преобразуем строковый тип в перечисление TaskType
    try:
        task_type = TaskType[media_type]
    except (KeyError, TypeError):
        query.edit_message_text(f"❌ Неподдерживаемый тип медиа: {media_type}")
        return ConversationHandler.END

    # Отправляем сообщение о начале публикации
    status_message = query.edit_message_text(
        f"⏳ Начинаем публикацию... Это может занять некоторое время."
    )

    # Проверяем, публикуем на один аккаунт или на несколько
    if 'publish_account_ids' in context.user_data:
        # Публикация на несколько аккаунтов
        account_ids = context.user_data.get('publish_account_ids')

        # Публикуем видео параллельно на все аккаунты
        if task_type == TaskType.VIDEO:
            # Обновляем статус
            context.bot.edit_message_text(
                f"⏳ Подготовка к публикации видео на {len(account_ids)} аккаунтах...",
                chat_id=status_message.chat_id,
                message_id=status_message.message_id
            )

            # Создаем задачи для каждого аккаунта и добавляем их в очередь
            task_ids = []
            for account_id in account_ids:
                # Подготавливаем дополнительные данные
                additional_data = {
                    'hide_from_feed': hide_from_feed
                }

                # Создаем задачу на публикацию
                success, task_id = create_publish_task(
                    account_id=account_id,
                    task_type=task_type,
                    media_path=media_path,
                    caption=caption,
                    additional_data=json.dumps(additional_data)
                )

                if success:
                    # Добавляем задачу в очередь
                    from utils.task_queue import add_task_to_queue
                    if add_task_to_queue(task_id, user_id, context.bot):
                        account = get_instagram_account(account_id)
                        task_ids.append((task_id, account.username))

            if task_ids:
                # Формируем сообщение о созданных задачах
                message = "✅ Созданы задачи на публикацию:\n\n"
                for task_id, username in task_ids:
                    message += f"• Задача #{task_id} для аккаунта {username}\n"

                message += "\nВы получите уведомления о результатах публикации."

                # Отправляем новое сообщение с результатами вместо редактирования
                context.bot.send_message(
                    chat_id=status_message.chat_id,
                    text=message
                )
            else:
                context.bot.edit_message_text(
                    "❌ Не удалось создать задачи на публикацию.",
                    chat_id=status_message.chat_id,
                    message_id=status_message.message_id
                )
        else:
            context.bot.edit_message_text(
                "❌ Неподдерживаемый тип медиа для множественной публикации",
                chat_id=status_message.chat_id,
                message_id=status_message.message_id
            )
    else:
        # Публикация на один аккаунт
        account_id = context.user_data.get('publish_account_id')

        # Обновляем статус
        context.bot.edit_message_text(
            "⏳ Подготовка к публикации контента...",
            chat_id=status_message.chat_id,
            message_id=status_message.message_id
        )

        # Подготавливаем дополнительные данные
        additional_data = {
            'hide_from_feed': hide_from_feed
        }

        # Создаем задачу на публикацию
        success, task_id = create_publish_task(
            account_id=account_id,
            task_type=task_type,
            media_path=media_path,
            caption=caption,
            additional_data=json.dumps(additional_data)
        )

        if not success:
            context.bot.edit_message_text(
                f"❌ Ошибка при создании задачи: {task_id}",
                chat_id=status_message.chat_id,
                message_id=status_message.message_id
            )
            return ConversationHandler.END

        # Добавляем задачу в очередь
        from utils.task_queue import add_task_to_queue
        if add_task_to_queue(task_id, user_id, context.bot):
            account = get_instagram_account(account_id)
            context.bot.edit_message_text(
                f"✅ Задача #{task_id} на публикацию в аккаунт {account.username} добавлена в очередь.\n"
                f"Вы получите уведомление после завершения публикации.",
                chat_id=status_message.chat_id,
                message_id=status_message.message_id
            )
        else:
            context.bot.edit_message_text(
                f"❌ Ошибка при добавлении задачи в очередь.",
                chat_id=status_message.chat_id,
                message_id=status_message.message_id
            )

    # Очищаем данные пользователя
    if 'publish_account_id' in context.user_data:
        del context.user_data['publish_account_id']
    if 'publish_account_username' in context.user_data:
        del context.user_data['publish_account_username']
    if 'publish_account_ids' in context.user_data:
        del context.user_data['publish_account_ids']
    if 'publish_to_all_accounts' in context.user_data:
        del context.user_data['publish_to_all_accounts']
    if 'publish_media_path' in context.user_data:
        # Не удаляем временный файл, так как он будет использоваться для публикации
        del context.user_data['publish_media_path']
    if 'publish_media_type' in context.user_data:
        del context.user_data['publish_media_type']
    if 'publish_caption' in context.user_data:
        del context.user_data['publish_caption']
    if 'hide_from_feed' in context.user_data:
        del context.user_data['hide_from_feed']

    return ConversationHandler.END

def schedule_publish_callback(update, context):
    """Обработчик запланированной публикации"""
    query = update.callback_query
    query.answer()

    query.edit_message_text(
        "Введите дату и время публикации в формате ДД.ММ.ГГГГ ЧЧ:ММ\n"
        "Например: 25.12.2023 15:30"
    )

    return CHOOSE_SCHEDULE

def choose_schedule(update, context):
    """Обработчик выбора времени для запланированной публикации"""
    try:
        # Парсим дату и время
        scheduled_time = datetime.strptime(update.message.text, "%d.%m.%Y %H:%M")

        # Получаем данные для публикации
        account_id = context.user_data.get('publish_account_id')
        media_path = context.user_data.get('publish_media_path')
        media_type = context.user_data.get('publish_media_type')
        caption = context.user_data.get('publish_caption', '')
        hide_from_feed = context.user_data.get('hide_from_feed', False)
        user_id = update.effective_user.id

        # Преобразуем строковый тип в перечисление TaskType
        try:
            # Если media_type - это строка с именем перечисления (например, 'VIDEO')
            task_type = TaskType[media_type]
        except (KeyError, TypeError):
            # Если не удалось преобразовать, выдаем ошибку
            update.message.reply_text(f"❌ Неподдерживаемый тип медиа: {media_type}")
            return ConversationHandler.END

        # Подготавливаем дополнительные данные
        additional_data = {
            'hide_from_feed': hide_from_feed
        }

        # Создаем задачу на публикацию
        success, task_id = create_publish_task(
            account_id=account_id,
            task_type=task_type,  # Передаем объект перечисления
            media_path=media_path,
            caption=caption,
            scheduled_time=scheduled_time,
            additional_data=json.dumps(additional_data)
        )

        if not success:
            update.message.reply_text(f"❌ Ошибка при создании задачи: {task_id}")
            return ConversationHandler.END

        keyboard = [[InlineKeyboardButton("🔙 К меню задач", callback_data='menu_tasks')]]
        reply_markup = InlineKeyboardMarkup(keyboard)

        update.message.reply_text(
            f"✅ Публикация успешно запланирована на {scheduled_time.strftime('%d.%m.%Y %H:%M')}",
            reply_markup=reply_markup
        )

        # Очищаем данные
        if 'publish_account_id' in context.user_data:
            del context.user_data['publish_account_id']
        if 'publish_account_username' in context.user_data:
            del context.user_data['publish_account_username']
        if 'publish_media_path' in context.user_data:
            del context.user_data['publish_media_path']
        if 'publish_media_type' in context.user_data:
            del context.user_data['publish_media_type']
        if 'publish_caption' in context.user_data:
            del context.user_data['publish_caption']
        if 'hide_from_feed' in context.user_data:
            del context.user_data['hide_from_feed']
        if 'selected_accounts' in context.user_data:
            del context.user_data['selected_accounts']

    except ValueError:
        update.message.reply_text(
            "❌ Неверный формат даты и времени. Пожалуйста, используйте формат ДД.ММ.ГГГГ ЧЧ:ММ\n"
            "Например: 25.12.2023 15:30"
        )
        return CHOOSE_SCHEDULE

    return ConversationHandler.END

def cancel_publish(update, context):
    """Обработчик отмены публикации"""
    query = update.callback_query
    query.answer()

    # Очищаем данные
    if 'publish_account_id' in context.user_data:
        del context.user_data['publish_account_id']
    if 'publish_account_username' in context.user_data:
        del context.user_data['publish_account_username']
    if 'publish_account_ids' in context.user_data:
        del context.user_data['publish_account_ids']
    if 'publish_to_all_accounts' in context.user_data:
        del context.user_data['publish_to_all_accounts']
    if 'selected_accounts' in context.user_data:
        del context.user_data['selected_accounts']
    if 'publish_media_path' in context.user_data:
        # Удаляем временный файл
        try:
            os.remove(context.user_data['publish_media_path'])
        except:
            pass
        del context.user_data['publish_media_path']
    if 'publish_media_type' in context.user_data:
        del context.user_data['publish_media_type']
    if 'publish_caption' in context.user_data:
        del context.user_data['publish_caption']
    if 'hide_from_feed' in context.user_data:
        del context.user_data['hide_from_feed']

    keyboard = [[InlineKeyboardButton("🔙 К меню задач", callback_data='menu_tasks')]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    query.edit_message_text(
        "❌ Публикация отменена.",
        reply_markup=reply_markup
    )

    return ConversationHandler.END

def check_task_status_handler(update, context):
    """Обработчик для проверки статуса задачи"""
    user_id = update.effective_user.id

    if not is_admin(user_id):
        update.message.reply_text("У вас нет прав для выполнения этой команды.")
        return

    # Проверяем, указан ли ID задачи
    if not context.args or not context.args[0].isdigit():
        update.message.reply_text(
            "❌ Пожалуйста, укажите ID задачи. Например: /task_status 123"
        )
        return

    task_id = int(context.args[0])

    # Получаем статус задачи
    status = get_task_status(task_id)

    if not status:
        update.message.reply_text(
            f"❌ Задача с ID {task_id} не найдена."
        )
        return

    # Формируем сообщение о статусе
    if status['success']:
        message = f"✅ Задача #{task_id} успешно выполнена!\n"
        if 'result' in status and status['result']:
            message += f"Результат: {status['result']}\n"
    else:
        message = f"❌ Задача #{task_id} завершилась с ошибкой:\n{status['result']}\n"

    if 'completed_at' in status and status['completed_at']:
        message += f"Время завершения: {status['completed_at'].strftime('%d.%m.%Y %H:%M:%S')}"

    update.message.reply_text(message)

def get_publish_handlers():
    """Возвращает обработчики для публикации контента"""
    from telegram.ext import CommandHandler, CallbackQueryHandler, MessageHandler, Filters

    publish_conversation = ConversationHandler(
        entry_points=[
            CommandHandler("publish_now", publish_now_handler),
            CallbackQueryHandler(publish_now_handler, pattern='^publish_now$')
        ],
        states={
            CHOOSE_ACCOUNT: [
                CallbackQueryHandler(choose_account_callback, pattern='^publish_account_\d+$'),
                CallbackQueryHandler(choose_all_accounts_callback, pattern='^publish_all_accounts$'),
                CallbackQueryHandler(cancel_publish, pattern='^cancel_publish$')
            ],
            ENTER_CAPTION: [
                MessageHandler(Filters.text & ~Filters.command, enter_caption),
                CommandHandler("skip", enter_caption)
            ],
            CHOOSE_HIDE_FROM_FEED: [
                CallbackQueryHandler(choose_hide_from_feed, pattern='^(hide_from_feed|keep_in_feed)$'),
                CallbackQueryHandler(cancel_publish, pattern='^cancel_publish$')
            ],
            CONFIRM_PUBLISH: [
                CallbackQueryHandler(confirm_publish_now, pattern='^confirm_publish_now$'),
                CallbackQueryHandler(schedule_publish_callback, pattern='^schedule_publish$'),
                CallbackQueryHandler(cancel_publish, pattern='^cancel_publish$')
            ],
            CHOOSE_SCHEDULE: [
                MessageHandler(Filters.text & ~Filters.command, choose_schedule)
            ]
        },
        fallbacks=[CommandHandler("cancel", lambda update, context: ConversationHandler.END)]
    )

    video_handler = MessageHandler(Filters.video | Filters.document.video, video_upload_handler)
    task_status_handler = CommandHandler("task_status", check_task_status_handler)

    return [publish_conversation, video_handler, task_status_handler]