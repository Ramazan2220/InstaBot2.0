import logging
   from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
   from telegram.ext import CallbackContext, ConversationHandler

   from config import ADMIN_USER_IDS
   from database.db_manager import add_instagram_account
   from telegram.keyboards import get_accounts_menu_keyboard
   from instagram.client import Client

   logger = logging.getLogger(__name__)

   # Состояния для ConversationHandler
   WAITING_COOKIES_FILE = 11  # Ожидание файла с куки

   def upload_cookies_handler(update: Update, context: CallbackContext):
       """Обработчик для загрузки аккаунтов по куки"""
       user_id = update.effective_user.id

       if user_id not in ADMIN_USER_IDS:
           return

       if update.callback_query:
           query = update.callback_query
           query.answer()

           query.edit_message_text(
               "Отправьте файл с куки для аккаунтов Instagram.\n\n"
               "Формат файла JSON:\n"
               "{\n"
               '  "username1": {"cookies": "...", "user_agent": "...", ...},\n'
               '  "username2": {"cookies": "...", "user_agent": "...", ...}\n'
               "}\n\n"
               "Или отправьте ZIP-архив с отдельными JSON-файлами для каждого аккаунта.",
               reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Назад", callback_data='menu_accounts')]])
           )
       else:
           update.message.reply_text(
               "Отправьте файл с куки для аккаунтов Instagram.\n\n"
               "Формат файла JSON:\n"
               "{\n"
               '  "username1": {"cookies": "...", "user_agent": "...", ...},\n'
               '  "username2": {"cookies": "...", "user_agent": "...", ...}\n'
               "}\n\n"
               "Или отправьте ZIP-архив с отдельными JSON-файлами для каждого аккаунта.",
               reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Назад", callback_data='menu_accounts')]])
           )

       return WAITING_COOKIES_FILE

   def handle_cookies_file(update: Update, context: CallbackContext):
       """Обработчик для файла с куки"""
       user_id = update.effective_user.id

       # Проверяем, что пользователь отправил файл
       if not update.message.document:
           update.message.reply_text(
               "Пожалуйста, отправьте файл с куки.",
               reply_markup=get_accounts_menu_keyboard()
           )
           return WAITING_COOKIES_FILE

       file = update.message.document.get_file()
       file_name = update.message.document.file_name

       # Создаем временную директорию для файлов
       temp_dir = os.path.join(os.path.dirname(__file__), "temp")
       os.makedirs(temp_dir, exist_ok=True)

       file_path = os.path.join(temp_dir, file_name)
       file.download(file_path)

       # Обрабатываем файл в зависимости от его типа
       if file_name.endswith('.json'):
           # Обрабатываем JSON-файл
           try:
               with open(file_path, 'r') as f:
                   cookies_data = json.load(f)

               results = []

               for username, settings in cookies_data.items():
                   # Сохраняем сессию
                   session_dir = os.path.join(os.path.dirname(__file__), "sessions")
                   os.makedirs(session_dir, exist_ok=True)
                   session_file = os.path.join(session_dir, f"{username}.json")

                   with open(session_file, 'w') as f:
                       json.dump(settings, f)

                   # Проверяем, работает ли сессия
                   client = Client()
                   client.set_settings(settings)

                   try:
                       client.get_timeline_feed()  # Проверка, что сессия активна

                       # Добавляем аккаунт в базу данных (без пароля)
                       success, result = add_instagram_account(username, "")

                       if success:
                           results.append(f"✅ {username}: Успешно добавлен")
                       else:
                           results.append(f"❌ {username}: Ошибка при добавлении в БД - {result}")

                   except Exception as e:
                       results.append(f"❌ {username}: Ошибка при проверке сессии - {e}")

               # Отправляем результаты
               update.message.reply_text(
                   "Результаты загрузки аккаунтов по куки:\n\n" + "\n".join(results),
                   reply_markup=get_accounts_menu_keyboard()
               )

           except Exception as e:
               update.message.reply_text(
                   f"Ошибка при обработке JSON-файла: {e}",
                   reply_markup=get_accounts_menu_keyboard()
               )

       elif file_name.endswith('.zip'):
           # Обрабатываем ZIP-архив
           import zipfile

           try:
               # Создаем директорию для распаковки
               extract_dir = os.path.join(temp_dir, "extract")
               os.makedirs(extract_dir, exist_ok=True)

               # Распаковываем архив
               with zipfile.ZipFile(file_path, 'r') as zip_ref:
                   zip_ref.extractall(extract_dir)

               # Обрабатываем каждый JSON-файл
               results = []

               for json_file in os.listdir(extract_dir):
                   if json_file.endswith('.json'):
                       username = os.path.splitext(json_file)[0]

                       try:
                           with open(os.path.join(extract_dir, json_file), 'r') as f:
                               settings = json.load(f)

                           # Сохраняем сессию
                           session_dir = os.path.join(os.path.dirname(__file__), "sessions")
                           os.makedirs(session_dir, exist_ok=True)
                           session_file = os.path.join(session_dir, f"{username}.json")

                           with open(session_file, 'w') as f:
                               json.dump(settings, f)

                           # Проверяем, работает ли сессия
                           client = Client()
                           client.set_settings(settings)

                           try:
                               client.get_timeline_feed()  # Проверка, что сессия активна

                               # Добавляем аккаунт в базу данных (без пароля)
                               success, result = add_instagram_account(username, "")

                               if success:
                                   results.append(f"✅ {username}: Успешно добавлен")
                               else:
                                   results.append(f"❌ {username}: Ошибка при добавлении в БД - {result}")

                           except Exception as e:
                               results.append(f"❌ {username}: Ошибка при проверке сессии - {e}")

                       except Exception as e:
                           results.append(f"❌ {username}: Ошибка при обработке файла - {e}")

               # Отправляем результаты
               update.message.reply_text(
                   "Результаты загрузки аккаунтов по куки:\n\n" + "\n".join(results),
                   reply_markup=get_accounts_menu_keyboard()
               )

           except Exception as e:
               update.message.reply_text(
                   f"Ошибка при обработке ZIP-архива: {e}",
                   reply_markup=get_accounts_menu_keyboard()
               )

       else:
           update.message.reply_text(
               "Неподдерживаемый формат файла. Пожалуйста, отправьте JSON-файл или ZIP-архив.",
               reply_markup=get_accounts_menu_keyboard()
           )
           return WAITING_COOKIES_FILE

       # Удаляем временные файлы
       import shutil
       shutil.rmtree(temp_dir, ignore_errors=True)

       return ConversationHandler.END