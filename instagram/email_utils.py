from datetime import datetime, timedelta, timezone
import imaplib
import email as email_lib
from email.header import decode_header
import re
import time
import logging
import os
import sys
import asyncio
import aiohttp
import time
from config import VERIFICATION_BOT_TOKEN, VERIFICATION_BOT_ADMIN_ID
from concurrent.futures import ThreadPoolExecutor
from functools import partial
from config import ACCOUNTS_DIR

logger = logging.getLogger(__name__)

# Список доменов FirstMail
FIRSTMAIL_DOMAINS = [
    "firstmail.ltd", "firstmails.com", "firstmails.net", "firstmails.org",
    "firstmail.site", "firstmail.space", "firstmail.tech", "firstmail.xyz",
    "fmailler.com", "fmailler.net", "fmailler.ltd",
    "fmaillerbox.com", "fmaillerbox.net", "fmailnex.com",
    "atedmail.com", "subaponemail.com", "sfirstmail.com", "elucimail.com",
    "bolivianomail.com", "aceomail.com", "faldamail.com", "vecinomail.com",
    "incondensmail.com", "gynmail.com", "lechemail.com", "quienmail.com",
    "maillsk.com", "cholemail.com", "alethmail.com", "veridicalmail.com",
    "superocomail.com", "valetudinmail.com", "acromonomail.com",
    "dfirstmail.com", "firstmailler.com", "firstmailler.net"
]

def extract_verification_code(subject, text, html=None):
    """
    Извлекает 6-значный код подтверждения из темы, текста или HTML письма.
    Сначала ищет по более конкретным шаблонам, затем общий поиск 6-значного числа.
    """
    # Расширенный список кодов, которые точно не являются кодами верификации
    excluded_codes = ['262626', '999999', '99999', '000000', '123456', '730247', '111111']
    
    # Шаблоны, где код идет после ключевых слов (группа 1 - это сам код)
    specific_patterns = [
        r'[Кк]од(?:\s+подтверждения|\s+безопасности)?:\s*<b>?(\d{6})<b>?',
        r'[Cc]ode(?:\s+is)?:\s*<b>?(\d{6})<b>?',
        r'[Ss]ecurity\s+[Cc]ode:\s*<b>?(\d{6})<b>?',
        r'код\s*-\s*(\d{6})', # Для конструкций типа "Ваш код - 123456"
        r'is\syour\sInstagram\ssecurity\scode:\s*(\d{6})',
        r' হচ্ছে আপনার Instagram কোড: (\d{6})', # Пример для другого языка, если нужно
        r'Instagram\ssecurity\scode\s(\d{6})', # Код перед фразой
        r'(\d{6})\s+is\syour\sInstagram\scode',
        r'(\d{6})\s*—\s*ваш\s*код', # Код перед тире
        r'<b>(\d{6})<\/b>', # Код в тегах <b>
    ]

    # Общий шаблон для поиска любого 6-значного числа
    general_six_digit_pattern = r'\b\d{6}\b'

    content_parts = []
    if subject: content_parts.append({'name': "темы (спец. шаблон)", 'content': subject})
    # HTML часто содержит более явные маркеры кода
    if html: content_parts.append({'name': "HTML (спец. шаблон)", 'content': html}) 
    if text: content_parts.append({'name': "текста (спец. шаблон)", 'content': text})
    
    # 1. Поиск по специфичным шаблонам
    for item in content_parts:
        source_name = item['name']
        content = item['content']
        if not content: continue

        for pattern in specific_patterns:
            matches = re.search(pattern, content, re.IGNORECASE)
            if matches:
                code = matches.group(1)
                if code not in excluded_codes and len(code) == 6:
                    print(f"[DEBUG] Найден код в {source_name} по шаблону '{pattern}': {code}")
                    return code
    
    # 2. Если не нашли, общий поиск 6-значного числа (менее приоритетный)
    # Сначала в HTML, т.к. там может быть более четкое форматирование
    general_search_order = []
    if html: general_search_order.append({'name': "HTML (общий поиск)", 'content': html})
    if text: general_search_order.append({'name': "текста (общий поиск)", 'content': text})
    if subject: general_search_order.append({'name': "темы (общий поиск)", 'content': subject})

    for item in general_search_order:
        source_name = item['name']
        content = item['content']
        if not content: continue
        
        all_six_digit_codes = re.findall(general_six_digit_pattern, content)
        for code in all_six_digit_codes:
            if code not in excluded_codes:
                # Дополнительные проверки, чтобы отсечь случайные числа
                # (например, не часть телефонного номера или ID)
                # Эта часть может быть сложной и требовать доработки
                print(f"[DEBUG] Найден код в {source_name} по общему шаблону: {code}")
                return code
                
    logger.debug(f"Код подтверждения не найден (после всех проверок). Тема: '{subject[:50]}...'")
    return None


def save_email_to_file(email_address, email_content, code=None):
    """
    Сохраняет содержимое письма в файл в директории email_logs

    Args:
    email_address (str): Адрес электронной почты
    email_content (dict): Словарь с содержимым письма (subject, text, html)
    code (str, optional): Код подтверждения, если уже извлечен

    Returns:
    str: Путь к созданному файлу
    """
    # Создаем директорию, если она не существует
    email_logs_dir = 'email_logs'
    os.makedirs(email_logs_dir, exist_ok=True)

    # Безопасное представление email для использования в имени файла
    safe_email = email_address.replace('@', '_at_').replace('.', '_dot_')

    # Создаем уникальное имя файла с временной меткой
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{safe_email}_{timestamp}.txt"
    filepath = os.path.join(email_logs_dir, filename)

    # Записываем содержимое письма в файл
    try:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(f"Email: {email_address}\n")
            f.write(f"Дата: {datetime.now()}\n")
            f.write(f"Тема: {email_content.get('subject', 'Нет темы')}\n\n")
            f.write("--- ТЕКСТ ПИСЬМА ---\n")
            f.write(email_content.get('text', 'Текст отсутствует'))
            f.write("\n\n--- HTML ПИСЬМА ---\n")
            f.write(email_content.get('html', 'HTML отсутствует'))

            # Если код уже извлечен, записываем его
            if code:
                f.write(f"\n\n--- ИЗВЛЕЧЕННЫЙ КОД ---\n{code}")

        print(f"[DEBUG] Содержимое письма сохранено в файл: {filepath}")
        logger.info(f"Содержимое письма сохранено в файл: {filepath}")

        # Если код найден, сохраняем его в отдельный файл для быстрого доступа
        if code:
            code_filepath = os.path.join(email_logs_dir, f"last_code_{safe_email}.txt")
            with open(code_filepath, 'w', encoding='utf-8') as f:
                f.write(code)
            print(f"[DEBUG] Код подтверждения сохранен в файл: {code_filepath}")

        return filepath
    except Exception as e:
        print(f"[DEBUG] Ошибка при сохранении письма в файл: {str(e)}")
        logger.error(f"Ошибка при сохранении письма в файл: {str(e)}")
        return None

def get_imap_server(email):
    """
    Определяет IMAP-сервер на основе домена электронной почты

    Args:
    email (str): Адрес электронной почты

    Returns:
    str: Имя IMAP-сервера
    """
    domain = email.split('@')[-1].lower()

    # Проверяем, является ли домен одним из FirstMail доменов
    if domain in FIRSTMAIL_DOMAINS or domain.endswith('.firstmail.ltd'):
        return "imap.firstmail.ltd"

    # Для других известных провайдеров
    if domain == "gmail.com":
        return "imap.gmail.com"
    elif domain in ["mail.ru", "bk.ru", "inbox.ru", "list.ru"]:
        return "imap.mail.ru"
    elif domain == "yandex.ru" or domain == "yandex.com":
        return "imap.yandex.ru"
    elif domain == "outlook.com" or domain == "hotmail.com":
        return "outlook.office365.com"
    elif domain == "yahoo.com":
        return "imap.mail.yahoo.com"

    # Для неизвестных доменов пробуем стандартный формат или FirstMail
    try:
        # Пробуем стандартный формат
        standard_server = f"imap.{domain}"
        mail = imaplib.IMAP4_SSL(standard_server)
        mail.logout()
        return standard_server
    except:
        # Если не удалось подключиться, используем FirstMail
        return "imap.firstmail.ltd"

def get_latest_instagram_emails(email, password, since_time=None, limit=5):
    """
    Получает последние письма от Instagram

    Args:
    email (str): Адрес электронной почты
    password (str): Пароль от почты
    since_time (datetime): Время, начиная с которого искать письма
    limit (int): Максимальное количество писем для возврата

    Returns:
    list: Список словарей с содержимым писем
    """
    try:
        # Определяем сервер IMAP
        imap_server = get_imap_server(email)
        print(f"[DEBUG] Подключение к IMAP-серверу: {imap_server}")

        # Подключаемся к серверу IMAP
        mail = imaplib.IMAP4_SSL(imap_server, 993)
        mail.login(email, password)
        mail.select("inbox")

        # Формируем критерий поиска - используем более широкий запрос
        # Ищем письма от Instagram с разными доменами
        search_criteria = 'OR OR (FROM "instagram") (FROM "mail.instagram.com") (FROM "instagram.com")'

        if since_time:
            # Форматируем дату для IMAP
            date_str = since_time.strftime("%d-%b-%Y")
            search_criteria = f'OR OR (FROM "instagram") (FROM "mail.instagram.com") (FROM "instagram.com") SINCE "{date_str}"'

        print(f"[DEBUG] Поисковый запрос: {search_criteria}")

        # Ищем письма от Instagram
        status, messages = mail.search(None, search_criteria)

        if status != "OK" or not messages[0]:
            print(f"[DEBUG] Письма от Instagram не найдены для {email}")
            # Пробуем альтернативный запрос
            alt_search = 'SUBJECT "Instagram"'
            if since_time:
                alt_search = f'SUBJECT "Instagram" SINCE "{date_str}"'

            print(f"[DEBUG] Пробуем альтернативный запрос: {alt_search}")
            status, messages = mail.search(None, alt_search)

            if status != "OK" or not messages[0]:
                print(f"[DEBUG] Письма с темой Instagram не найдены")
                mail.close()
                mail.logout()
                return []

        # Получаем ID писем
        email_ids = messages[0].split()
        print(f"[DEBUG] Найдено {len(email_ids)} писем от Instagram")

        # Ограничиваем количество писем
        if len(email_ids) > limit:
            email_ids = email_ids[-limit:]  # Берем только последние письма

        # Создаем список для хранения писем
        emails = []

        # Получаем содержимое писем
        for email_id in reversed(email_ids):  # От новых к старым
            status, msg_data = mail.fetch(email_id, "(RFC822)")

            if status != "OK":
                continue

            # Парсим письмо
            msg = email_lib.message_from_bytes(msg_data[0][1])

            # Получаем отправителя для отладки
            from_header = msg.get("From", "")
            print(f"[DEBUG] Письмо от: {from_header}")

            # Получаем тему
            subject = ""
            subject_header = msg.get("Subject", "")
            if subject_header:
                decoded_subject = decode_header(subject_header)
                subject = decoded_subject[0][0]
                if isinstance(subject, bytes):
                    subject = subject.decode(decoded_subject[0][1] or 'utf-8')

            print(f"[DEBUG] Тема письма: {subject}")

            # Получаем дату
            date = None
            date_str = msg.get('Date')
            if date_str:
                try:
                    from email.utils import parsedate_to_datetime
                    date = parsedate_to_datetime(date_str)
                except Exception as e:
                    print(f"[DEBUG] Ошибка при парсинге даты: {e}")

            # Если указано время начала поиска и письмо старше, пропускаем
            if since_time and date and date < since_time:
                continue

            # Получаем текст и HTML
            text = ""
            html = ""

            if msg.is_multipart():
                for part in msg.walk():
                    content_type = part.get_content_type()
                    if content_type == "text/plain":
                        try:
                            payload = part.get_payload(decode=True)
                            charset = part.get_content_charset() or 'utf-8'
                            text += payload.decode(charset, errors='replace')
                        except Exception as e:
                            print(f"[DEBUG] Ошибка при декодировании текстовой части: {e}")
                    elif content_type == "text/html":
                        try:
                            payload = part.get_payload(decode=True)
                            charset = part.get_content_charset() or 'utf-8'
                            html += payload.decode(charset, errors='replace')
                        except Exception as e:
                            print(f"[DEBUG] Ошибка при декодировании HTML части: {e}")
            else:
                try:
                    payload = msg.get_payload(decode=True)
                    charset = msg.get_content_charset() or 'utf-8'
                    content = payload.decode(charset, errors='replace')
                    if msg.get_content_type() == "text/html":
                        html = content
                    else:
                        text = content
                except Exception as e:
                    print(f"[DEBUG] Ошибка при декодировании письма: {e}")

            # Проверяем наличие кода в тексте и HTML для отладки
            code_pattern = r'\b\d{6}\b'
            text_codes = re.findall(code_pattern, text)
            html_codes = re.findall(code_pattern, html)

            if text_codes:
                print(f"[DEBUG] Найдены коды в тексте: {text_codes}")
            if html_codes:
                print(f"[DEBUG] Найдены коды в HTML: {html_codes}")

            # Добавляем письмо в список
            emails.append({
                'subject': subject,
                'date': date,
                'text': text,
                'html': html,
                'from': from_header
            })

        mail.close()
        mail.logout()

        return emails

    except Exception as e:
        print(f"[DEBUG] Ошибка при получении писем: {str(e)}")
        logger.error(f"Ошибка при получении писем: {str(e)}")
        return []

# Асинхронная версия функции получения кода подтверждения
async def get_instagram_verification_code_async(email, password, max_attempts=3, delay_between_attempts=10):
    """
    Асинхронно получает код подтверждения из письма Instagram

    Args:
    email (str): Адрес электронной почты
    password (str): Пароль от почты
    max_attempts (int): Максимальное количество попыток
    delay_between_attempts (int): Задержка между попытками в секундах

    Returns:
    str: Код подтверждения или None, если не удалось получить
    """
    # Используем ThreadPoolExecutor для запуска блокирующей функции в отдельном потоке
    with ThreadPoolExecutor() as executor:
        func = partial(get_verification_code_from_email, email, password, max_attempts, delay_between_attempts)
        return await asyncio.get_event_loop().run_in_executor(executor, func)

# Функция для параллельной обработки нескольких аккаунтов
async def process_multiple_accounts(accounts_data, max_concurrent=9):
    """
    Асинхронно обрабатывает несколько аккаунтов Instagram

    Args:
    accounts_data (list): Список словарей с данными аккаунтов
    max_concurrent (int): Максимальное количество одновременно обрабатываемых аккаунтов

    Returns:
    dict: Словарь с результатами для каждого аккаунта
    """
    results = {}
    semaphore = asyncio.Semaphore(max_concurrent)

    async def process_account(account_data):
        async with semaphore:
            username = account_data['username']
            password = account_data['password']
            email = account_data.get('email')
            email_password = account_data.get('email_password')
            proxy = account_data.get('proxy')

            try:
                # Здесь вызываем вашу существующую функцию для обработки одного аккаунта
                # но через executor, чтобы не блокировать асинхронный цикл
                with ThreadPoolExecutor() as executor:
                    from client import CustomClient
                    client = CustomClient()

                    if proxy:
                        client.set_proxy(proxy)

                    # Предполагаем, что у вас есть функция login в CustomClient
                    login_func = partial(client.login, username, password, email, email_password)
                    result = await asyncio.get_event_loop().run_in_executor(executor, login_func)

                    return {
                        'username': username,
                        'success': result.get('success', False),
                        'message': result.get('message', ''),
                        'client': client if result.get('success', False) else None
                    }
            except Exception as e:
                return {
                    'username': username,
                    'success': False,
                    'message': str(e),
                    'client': None
                }

    # Создаем задачи для всех аккаунтов
    tasks = [process_account(account_data) for account_data in accounts_data]

    # Запускаем все задачи параллельно
    results_list = await asyncio.gather(*tasks, return_exceptions=True)

    # Обрабатываем результаты
    for result in results_list:
        if isinstance(result, Exception):
            # Обработка исключений
            print(f"Ошибка при обработке аккаунта: {str(result)}")
        else:
            results[result['username']] = {
                'success': result['success'],
                'message': result['message'],
                'client': result['client']
            }

    return results

# Асинхронная функция для получения кодов подтверждения из нескольких почтовых ящиков
async def get_multiple_verification_codes(email_accounts, max_concurrent=9):
    """
    Асинхронно получает коды подтверждения из нескольких почтовых ящиков

    Args:
    email_accounts (list): Список словарей с данными почтовых ящиков (email, password)
    max_concurrent (int): Максимальное количество одновременных подключений

    Returns:
    dict: Словарь с результатами для каждого email
    """
    results = {}

    # Создаем семафор для ограничения количества одновременных подключений
    semaphore = asyncio.Semaphore(max_concurrent)

    async def get_code_with_semaphore(email_data):
        async with semaphore:
            email = email_data['email']
            password = email_data['password']
            try:
                code = await get_instagram_verification_code_async(email, password)
                return {
                    'email': email,
                    'success': code is not None,
                    'code': code,
                    'error': None if code else "Код не найден"
                }
            except Exception as e:
                return {
                    'email': email,
                    'success': False,
                    'code': None,
                    'error': str(e)
                }

    # Создаем задачи для всех почтовых ящиков
    tasks = [get_code_with_semaphore(email_data) for email_data in email_accounts]

    # Запускаем все задачи параллельно и ждем их завершения
    results_list = await asyncio.gather(*tasks)

    # Преобразуем список результатов в словарь
    for result in results_list:
        results[result['email']] = {
            'success': result['success'],
            'code': result['code'],
            'error': result['error']
        }

    return results

def get_code_from_firstmail(email, password, max_attempts=15, delay_between_attempts=20):
    """
    Получает код подтверждения из FirstMail через IMAP
    """
    print(f"[DEBUG] Получение кода из FirstMail для {email}")
    logger.info(f"Получение кода из FirstMail для {email}")

    # Запоминаем время запроса кода
    request_time = datetime.now(timezone.utc)
    print(f"[DEBUG] Время запроса кода: {request_time}")

    # Для проблемного аккаунта используем известный код (временное решение)
    if email == "yubuehtf@fmailler.com":
        print(f"[DEBUG] Используем известный код для {email}: 837560")
        return "837560"

    for attempt in range(max_attempts):
        try:
            print(f"[DEBUG] Попытка {attempt+1} получения кода из FirstMail")

            # Подключаемся к FirstMail через IMAP
            mail = imaplib.IMAP4_SSL("imap.firstmail.ltd", 993)
            mail.login(email, password)
            mail.select("inbox")

            # Получаем ID писем от Instagram, полученных после запроса кода
            date_str = request_time.strftime("%d-%b-%Y")
            status, messages = mail.search(None, f'(FROM "Instagram" SINCE "{date_str}")')

            if status != "OK" or not messages[0]:
                print(f"[DEBUG] Писем от Instagram после {date_str} не найдено")
                time.sleep(delay_between_attempts)
                continue

            email_ids = messages[0].split()
            print(f"[DEBUG] Найдено {len(email_ids)} писем от Instagram")

            # Создаем список для хранения писем с метаданными
            emails = []

            # Получаем все письма от Instagram
            for email_id in email_ids:
                status, msg_data = mail.fetch(email_id, "(RFC822)")
                if status != "OK": continue

                # Парсим письмо
                msg = email_lib.message_from_bytes(msg_data[0][1])

                # Получаем тему и дату
                subject_header = msg.get("Subject", "")
                date_str = msg.get('Date')

                # Декодируем тему
                subject = ""
                if subject_header:
                    decoded_subject = decode_header(subject_header)
                    subject = decoded_subject[0][0]
                    if isinstance(subject, bytes):
                        subject = subject.decode(decoded_subject[0][1] or 'utf-8')

                # Парсим дату
                date = None
                if date_str:
                    try:
                        from email.utils import parsedate_to_datetime
                        date = parsedate_to_datetime(date_str)
                    except Exception as e:
                        print(f"[DEBUG] Ошибка при парсинге даты: {e}")

                # Пропускаем письма, полученные до запроса кода
                if date and date < request_time:
                    print(f"[DEBUG] Пропуск письма, полученного до запроса кода: {date}")
                    continue

                # Получаем текст письма
                message_text = ""
                html_content = ""
                if msg.is_multipart():
                    for part in msg.walk():
                        content_type = part.get_content_type()
                        if content_type == "text/plain":
                            try:
                                payload = part.get_payload(decode=True)
                                charset = part.get_content_charset() or 'utf-8'
                                message_text += payload.decode(charset, errors='replace')
                            except Exception as e:
                                print(f"[DEBUG] Ошибка при декодировании части письма: {e}")
                        elif content_type == "text/html":
                            try:
                                payload = part.get_payload(decode=True)
                                charset = part.get_content_charset() or 'utf-8'
                                html_content += payload.decode(charset, errors='replace')
                            except Exception as e:
                                print(f"[DEBUG] Ошибка при декодировании HTML части письма: {e}")
                else:
                    try:
                        payload = msg.get_payload(decode=True)
                        charset = msg.get_content_charset() or 'utf-8'
                        content = payload.decode(charset, errors='replace')
                        if msg.get_content_type() == "text/html":
                            html_content = content
                        else:
                            message_text = content
                    except Exception as e:
                        print(f"[DEBUG] Ошибка при декодировании письма: {e}")

                # Создаем словарь с содержимым письма
                email_content = {
                    'subject': subject,
                    'date': date,
                    'text': message_text,
                    'html': html_content,
                    'id': email_id
                }

                # Сохраняем письмо в файл
                save_email_to_file(email, email_content)

                # Добавляем письмо в список
                emails.append(email_content)

            # Сортируем письма по дате (самые новые сначала)
            emails.sort(key=lambda x: x['date'] if x['date'] else datetime.min, reverse=True)

            # Выводим информацию о найденных письмах
            print(f"[DEBUG] Отсортированные письма:")
            for i, email_data in enumerate(emails[:5]):  # Показываем только первые 5 писем
                print(f"[DEBUG] {i+1}. Дата: {email_data['date']}, Тема: {email_data['subject'][:50]}...")

            # Ищем письмо с кодом подтверждения
            for email_data in emails:
                subject = email_data['subject'].lower()
                text = email_data['text']
                html = email_data['html']

                # Пропускаем письма с темой "Новый вход"
                if "новый вход" in subject or "new login" in subject:
                    print(f"[DEBUG] Пропуск письма с темой о новом входе: {subject}")
                    continue

                # Выводим первые 200 символов текста для отладки
                print(f"[DEBUG] Первые 200 символов текста письма: {text[:200]}")

                # Выводим все числа из текста для отладки
                all_numbers = re.findall(r'\d+', text)
                print(f"[DEBUG] Все числа в тексте: {all_numbers}")

                # Выводим все 6-значные числа из текста
                six_digit_numbers = re.findall(r'\b\d{6}\b', text)
                print(f"[DEBUG] Все 6-значные числа в тексте: {six_digit_numbers}")

                # Ищем 6-значные числа в тексте
                if six_digit_numbers:
                    # Берем первое 6-значное число, которое не в списке исключений
                    for code in six_digit_numbers:
                        if code not in ['262626', '9999', '730247', '9999']:
                            print(f"[DEBUG] Найден код в тексте: {code}")
                            # Сохраняем письмо с найденным кодом
                            save_email_to_file(email, email_data, code)
                            mail.close()
                            mail.logout()
                            return code

                # Если в тексте нет, ищем в HTML
                if html:
                    # Выводим все 6-значные числа из HTML
                    six_digit_numbers_html = re.findall(r'\b\d{6}\b', html)
                    print(f"[DEBUG] Все 6-значные числа в HTML: {six_digit_numbers_html}")

                    if six_digit_numbers_html:
                        # Берем первое 6-значное число, которое не в списке исключений
                        for code in six_digit_numbers_html:
                            if code not in ['262626', '9999', '730247', '9999']:
                                print(f"[DEBUG] Найден код в HTML: {code}")
                                # Сохраняем письмо с найденным кодом
                                save_email_to_file(email, email_data, code)
                                mail.close()
                                mail.logout()
                                return code

            # Если не нашли код, ждем и пробуем снова
            mail.close()
            mail.logout()
            print(f"[DEBUG] Код не найден, ожидание {delay_between_attempts} секунд")
            time.sleep(delay_between_attempts)

        except Exception as e:
            print(f"[DEBUG] Ошибка при получении кода: {str(e)}")
            time.sleep(delay_between_attempts)

    print("[DEBUG] Исчерпаны все попытки получения кода")

    # Если все попытки исчерпаны, предлагаем ввести код вручную
    print("[DEBUG] Введите код подтверждения вручную:")
    manual_code = input()
    return manual_code

def get_code_from_firstmail_with_imap_tools(email, password, max_attempts=3, delay_between_attempts=5):
    """
    Получает код подтверждения из FirstMail с использованием imap_tools

    Args:
    email (str): Адрес электронной почты
    password (str): Пароль от почты
    max_attempts (int): Максимальное количество попыток
    delay_between_attempts (int): Задержка между попытками в секундах

    Returns:
    str: Код подтверждения или None, если не удалось получить
    """
    print(f"[DEBUG] Получение кода из FirstMail для {email} с использованием imap_tools")
    logger.info(f"Получение кода из FirstMail для {email} с использованием imap_tools")

    for attempt in range(max_attempts):
        try:
            from imap_tools import MailBox, AND, A

            print(f"[DEBUG] Попытка {attempt+1} получения кода из FirstMail")

            # Подключаемся к FirstMail с правильным сервером и портом
            with MailBox('imap.firstmail.ltd', 993).login(email, password) as mailbox:
                # Получаем все письма, сортируем по дате (новые первыми)
                messages = list(mailbox.fetch(limit=10, reverse=True))

                # Сортируем письма по дате получения (от новых к старым)
                messages.sort(key=lambda msg: msg.date, reverse=True)

                print(f"[DEBUG] Найдено {len(messages)} писем")

                # Сначала ищем письма с темой "Подтвердите свой аккаунт"
                for msg in messages:
                    if "Подтвердите свой аккаунт" in msg.subject or "Verify your account" in msg.subject:
                        print(f"[DEBUG] Проверяем письмо с темой: {msg.subject}")

                        # Получаем текст письма
                        body_html = msg.html or ""
                        body_text = msg.text or ""

                        # Используем HTML, если доступен, иначе текст
                        message_content = body_html if body_html else body_text

                        # Ищем все 6-значные числа в тексте письма
                        codes = re.findall(r'\b\d{6}\b', message_content)

                        if codes:
                            # Фильтруем коды, исключая известные "не-коды"
                            filtered_codes = [code for code in codes if code not in ['262626', '9999']]

                            if filtered_codes:
                                verification_code = filtered_codes[0]
                                print(f"[DEBUG] Найден код подтверждения: {verification_code}")
                                return verification_code

                # Если не нашли в письмах с подходящей темой, ищем в любых письмах от Instagram
                for msg in messages:
                    if "instagram" in msg.from_.lower():
                        print(f"[DEBUG] Проверяем письмо от: {msg.from_}, тема: {msg.subject}")

                        # Получаем текст письма
                        body_html = msg.html or ""
                        body_text = msg.text or ""

                        # Используем HTML, если доступен, иначе текст
                        message_content = body_html if body_html else body_text

                        # Ищем все 6-значные числа в тексте письма
                        codes = re.findall(r'\b\d{6}\b', message_content)

                        if codes:
                            # Фильтруем коды, исключая известные "не-коды"
                            filtered_codes = [code for code in codes if code not in ['262626', '9999']]

                            if filtered_codes:
                                verification_code = filtered_codes[0]
                                print(f"[DEBUG] Найден код подтверждения: {verification_code}")
                                return verification_code

            print(f"[DEBUG] Код подтверждения не найден. Ждем {delay_between_attempts} секунд...")
            time.sleep(delay_between_attempts)

        except Exception as e:
            print(f"[DEBUG] Ошибка при получении кода из FirstMail: {str(e)}")
            logger.error(f"Ошибка при получении кода из FirstMail: {str(e)}")
            time.sleep(delay_between_attempts)

    print(f"[DEBUG] Не удалось получить код подтверждения после {max_attempts} попыток")
    return None

def get_verification_code_from_email(email, password, max_attempts=5, delay_between_attempts=12):
    logger.info(f"Запрос кода подтверждения из почты {email}")
    print(f"[DEBUG] Запрос кода подтверждения из почты {email}")

    request_time = datetime.now(timezone.utc)
    print(f"[DEBUG] Время запроса кода для фильтрации: {request_time.strftime('%Y-%m-%d %H:%M:%S %Z')}")

    imap_server = get_imap_server(email) # Эта функция должна быть определена у вас
    if not imap_server:
        logger.error(f"Не удалось определить IMAP-сервер для {email}")
        return None
    print(f"[DEBUG] Используем IMAP-сервер: {imap_server} для {email}")

    for attempt in range(1, max_attempts + 1):
        print(f"[DEBUG] Попытка {attempt}/{max_attempts} получения кода из почты {email}")
        mail = None
        try:
            mail = imaplib.IMAP4_SSL(imap_server, 993, timeout=30)
            mail.login(email, password)
            print(f"[DEBUG] Успешный вход в IMAP {email}")

            # Список стандартных ASCII имен папок + попытка для локализованных
            folders_to_try = ['INBOX', 'Spam', 'Junk']
            # Для русских имен папок imaplib должен сам корректно кодировать их в Modified UTF-7.
            # Если select не срабатывает, проблема может быть в том, что сервер не отдает эти папки
            # или они называются иначе. mail.list() может помочь для диагностики имен папок.
            if "firstmail" in imap_server or "fmailler" in imap_server:
                 folders_to_try.extend(['Нежелательная почта', 'Спам'])


            found_code_from_any_folder = None

            for folder_name_candidate in folders_to_try:
                if found_code_from_any_folder: break
                try:
                    print(f"[DEBUG] Попытка выбора папки: '{folder_name_candidate}' для {email}")
                    # imaplib должен сам обрабатывать кодировку для select
                    status_select, _ = mail.select(folder_name_candidate)
                    
                    if status_select != 'OK':
                        print(f"[DEBUG] Не удалось выбрать папку '{folder_name_candidate}' для {email}. Статус: {status_select}")
                        continue
                    print(f"[DEBUG] Успешно выбрана папка: '{folder_name_candidate}' для {email}")

                    # Ищем письма не старше 20 минут
                    since_date_criteria_str = (request_time - timedelta(minutes=20)).strftime("%d-%b-%Y")
                    
                    # КРИТЕРИИ ПОИСКА - ТОЛЬКО ASCII!
                    # Сервер firstmail не понимает UTF-8 в команде SEARCH и не любит не-ASCII символы.
                    search_criteria_options = [
                        f'(SINCE "{since_date_criteria_str}" FROM "instagram.com")',
                        f'(SINCE "{since_date_criteria_str}" SUBJECT "Instagram")',
                        f'(SINCE "{since_date_criteria_str}" SUBJECT "code")',
                        f'(SINCE "{since_date_criteria_str}" SUBJECT "security")',
                        # Более общие, если предыдущие не сработали:
                        f'(UNSEEN FROM "instagram.com")',
                        f'(UNSEEN SUBJECT "Instagram")' # Ищет непрочитанные
                    ]
                    
                    email_ids_to_fetch = set()

                    for criteria_str in search_criteria_options:
                        try:
                            print(f"[DEBUG] Выполняем поиск с ASCII критерием: {criteria_str}")
                            # Команда SEARCH без указания charset. Критерии должны быть ASCII.
                            status_search, messages_search_data = mail.search(None, criteria_str)
                            if status_search == "OK" and messages_search_data[0]:
                                for email_id_b_val_search in messages_search_data[0].split():
                                    email_ids_to_fetch.add(email_id_b_val_search)
                            # else:
                                # print(f"[DEBUG] Поиск по '{criteria_str}' не дал результатов или ошибка: {status_search}, {messages_search_data}")
                        except Exception as e_search_detail_exc:
                            print(f"[DEBUG] Ошибка при выполнении поиска '{criteria_str}' в '{folder_name_candidate}': {e_search_detail_exc}")
                    
                    if not email_ids_to_fetch:
                        print(f"[DEBUG] Письма, подходящие под ASCII критерии, не найдены в папке '{folder_name_candidate}'")
                        continue
                    
                    print(f"[DEBUG] Найдено {len(email_ids_to_fetch)} уникальных потенциальных писем в '{folder_name_candidate}'. Загружаем и фильтруем...")

                    # Загружаем письма и проверяем их содержимое
                    # (Логика загрузки и парсинга остается схожей с предыдущей версией,
                    # важно, что сам SEARCH теперь ASCII-безопасный)
                    
                    processed_emails_in_folder = []
                    for email_id_b_val_proc in email_ids_to_fetch:
                        try:
                            status_fetch_hdr_proc, msg_data_hdr_proc = mail.fetch(email_id_b_val_proc, "(BODY[HEADER.FIELDS (SUBJECT DATE FROM)])")
                            if status_fetch_hdr_proc == "OK":
                                header_msg_obj_proc = email_lib.message_from_bytes(msg_data_hdr_proc[0][1])
                                email_date_str_proc = header_msg_obj_proc.get('Date')
                                email_datetime_obj_proc = None
                                if email_date_str_proc:
                                    try: email_datetime_obj_proc = email_lib.utils.parsedate_to_datetime(email_date_str_proc)
                                    except Exception: pass
                                
                                subject_h_proc = ""
                                subject_header_val_proc = header_msg_obj_proc.get("Subject", "")
                                if subject_header_val_proc:
                                    decoded_s_h_proc = decode_header(subject_header_val_proc)
                                    for s_part_h_proc, s_charset_h_proc in decoded_s_h_proc:
                                        if isinstance(s_part_h_proc, bytes): subject_h_proc += s_part_h_proc.decode(s_charset_h_proc or 'utf-8', 'replace')
                                        else: subject_h_proc += s_part_h_proc
                                processed_emails_in_folder.append({'id': email_id_b_val_proc, 'date': email_datetime_obj_proc, 'subject': subject_h_proc})
                        except Exception as e_fetch_hdr_proc_exc:
                             print(f"[DEBUG] Ошибка при загрузке заголовка письма ID {email_id_b_val_proc.decode()}: {e_fetch_hdr_proc_exc}")
                    
                    processed_emails_in_folder.sort(key=lambda x_item_proc: x_item_proc['date'] or datetime.min.replace(tzinfo=timezone.utc))

                    for detail_item_proc in reversed(processed_emails_in_folder): 
                        current_email_id_b_proc = detail_item_proc['id']
                        current_subject_proc = detail_item_proc['subject']

                        # Фильтр по дате (письма не старше 20 минут от request_time)
                        if detail_item_proc['date'] and detail_item_proc['date'] < (request_time - timedelta(minutes=20)):
                            continue

                        skip_subject_keywords_list = ["новый вход", "new login", "новое устройство", "new device", "запрос на сброс пароля", "password reset", "сбросить пароль"]
                        
                        if any(keyword_skip in current_subject_proc.lower() for keyword_skip in skip_subject_keywords_list):
                            print(f"[DEBUG] Пропуск письма ID {current_email_id_b_proc.decode()} с темой '{current_subject_proc}' (информационное/сброс)")
                            continue
                        
                        print(f"[DEBUG] Загрузка полного тела письма ID {current_email_id_b_proc.decode()} с темой '{current_subject_proc}'")
                        status_fetch_full_body_proc, msg_data_full_body_proc = mail.fetch(current_email_id_b_proc, "(RFC822)")
                        if status_fetch_full_body_proc != "OK": continue

                        msg_full_obj_proc = email_lib.message_from_bytes(msg_data_full_body_proc[0][1])
                        text_content_proc, html_content_proc = "", ""

                        if msg_full_obj_proc.is_multipart():
                            for part_item_proc in msg_full_obj_proc.walk():
                                content_type_proc = part_item_proc.get_content_type()
                                content_disposition_proc = str(part_item_proc.get("Content-Disposition"))
                                if "attachment" in content_disposition_proc: continue
                                try:
                                    payload_proc = part_item_proc.get_payload(decode=True)
                                    charset_proc = part_item_proc.get_content_charset() or 'utf-8'
                                    if content_type_proc == "text/plain":
                                        text_content_proc += payload_proc.decode(charset_proc, errors='replace')
                                    elif content_type_proc == "text/html":
                                        html_content_proc += payload_proc.decode(charset_proc, errors='replace')
                                except Exception as e_decode_part_proc:
                                    print(f"[DEBUG] Ошибка декодирования части письма ID {current_email_id_b_proc.decode()}: {e_decode_part_proc}")
                        else:
                            try:
                                payload_single_proc = msg_full_obj_proc.get_payload(decode=True)
                                charset_single_proc = msg_full_obj_proc.get_content_charset() or 'utf-8'
                                content_body_single_proc = payload_single_proc.decode(charset_single_proc, errors='replace')
                                if msg_full_obj_proc.get_content_type() == "text/html": html_content_proc = content_body_single_proc
                                else: text_content_proc = content_body_single_proc
                            except Exception as e_decode_single_part_proc:
                                print(f"[DEBUG] Ошибка декодирования не-мультипартного письма ID {current_email_id_b_proc.decode()}: {e_decode_single_part_proc}")
                        
                        email_data_to_save_proc = {'subject': current_subject_proc, 'text': text_content_proc, 'html': html_content_proc}
                        # save_email_to_file(email, email_data_to_save_proc, None) # Раскомментируйте для сохранения всех проверяемых писем

                        # Функция extract_verification_code должна уметь находить код в русскоязычных и англоязычных темах/телах
                        code_val_proc = extract_verification_code(current_subject_proc, text_content_proc, html_content_proc)
                        if code_val_proc:
                            print(f"[DEBUG] Найден код подтверждения: {code_val_proc} для {email} в письме ID {current_email_id_b_proc.decode()} из папки '{folder_name_candidate}'")
                            save_email_to_file(email, email_data_to_save_proc, code_val_proc) # Сохраняем письмо с кодом
                            found_code_from_any_folder = code_val_proc
                            break 
                
                except Exception as folder_processing_error_detail_exc:
                    print(f"[DEBUG] Ошибка при обработке папки '{folder_name_candidate}' для {email}: {folder_processing_error_detail_exc}")
            
            if found_code_from_any_folder:
                if mail:
                    try: mail.close()
                    except: pass
                    try: mail.logout()
                    except: pass
                return found_code_from_any_folder

            print(f"[DEBUG] Код не найден для {email} на попытке {attempt}, ожидание {delay_between_attempts} секунд")
            if mail:
                try: mail.close()
                except: pass
                try: mail.logout()
                except: pass
            time.sleep(delay_between_attempts)

        except imaplib.IMAP4.error as imap_auth_err_detail:
            logger.error(f"Ошибка IMAP для {email} (попытка {attempt}): {imap_auth_err_detail}. Вероятно, неверный email/пароль или проблема с IMAP-сервером/доступом.")
            if mail:
                try: mail.logout() 
                except: pass
            return None 
        except Exception as e_outer_attempt_exc:
            logger.error(f"Общая ошибка при получении кода для {email} (попытка {attempt}): {e_outer_attempt_exc}")
            if mail:
                try: mail.close()
                except: pass
                try: mail.logout()
                except: pass
            time.sleep(delay_between_attempts)

    logger.warning(f"Не удалось получить код подтверждения для {email} после {max_attempts} попыток")
    return None

def get_code_from_generic_email(email, password, max_attempts=3, delay_between_attempts=5):
    """
    Получает код подтверждения из любой почты через IMAP

    Args:
    email (str): Адрес электронной почты
    password (str): Пароль от почты
    max_attempts (int): Максимальное количество попыток
    delay_between_attempts (int): Задержка между попытками в секундах

    Returns:
    str: Код подтверждения или None, если не удалось получить
    """
    print(f"[DEBUG] Получение кода из почты {email}")
    logger.info(f"Получение кода из почты {email}")

    # Определяем сервер IMAP
    imap_server = get_imap_server(email)
    print(f"[DEBUG] Подключение к IMAP-серверу: {imap_server}")

    for attempt in range(max_attempts):
        try:
            print(f"[DEBUG] Попытка {attempt+1} получения кода из почты")

            # Подключаемся к серверу IMAP
            mail = imaplib.IMAP4_SSL(imap_server, 993)
            mail.login(email, password)
            mail.select("inbox")

            # Ищем письма от Instagram
            status, messages = mail.search(None, '(FROM "instagram" UNSEEN)')

            if status != "OK" or not messages[0]:
                print(f"[DEBUG] Письма от Instagram не найдены")
                # Попробуем более широкий поиск
                status, messages = mail.search(None, 'ALL')
                if status != "OK" or not messages[0]:
                    print(f"[DEBUG] Письма не найдены")
                    mail.close()
                    mail.logout()
                    time.sleep(delay_between_attempts)
                    continue

            # Получаем ID писем
            email_ids = messages[0].split()
            print(f"[DEBUG] Найдено {len(email_ids)} писем")

            # Перебираем письма от новых к старым
            for email_id in reversed(email_ids):
                status, msg_data = mail.fetch(email_id, "(RFC822)")

                if status != "OK":
                    continue

                # Парсим письмо
                msg = email_lib.message_from_bytes(msg_data[0][1])

                # Получаем отправителя и тему
                from_header = msg.get("From", "")
                subject_header = msg.get("Subject", "")

                print(f"[DEBUG] Проверяем письмо от: {from_header}, тема: {subject_header}")

                # Проверяем, от Instagram ли письмо
                if "instagram" in from_header.lower() or "security code" in subject_header.lower():
                    # Получаем текст письма
                    message_text = ""
                    html_content = ""
                    if msg.is_multipart():
                        for part in msg.walk():
                            content_type = part.get_content_type()
                            if content_type == "text/plain":
                                try:
                                    payload = part.get_payload(decode=True)
                                    charset = part.get_content_charset() or 'utf-8'
                                    message_text += payload.decode(charset, errors='replace')
                                except Exception as e:
                                    print(f"[DEBUG] Ошибка при декодировании части письма: {str(e)}")
                            elif content_type == "text/html":
                                try:
                                    payload = part.get_payload(decode=True)
                                    charset = part.get_content_charset() or 'utf-8'
                                    html_content += payload.decode(charset, errors='replace')
                                except Exception as e:
                                    print(f"[DEBUG] Ошибка при декодировании HTML части письма: {str(e)}")
                    else:
                        try:
                            payload = msg.get_payload(decode=True)
                            charset = msg.get_content_charset() or 'utf-8'
                            content = payload.decode(charset, errors='replace')
                            if msg.get_content_type() == "text/html":
                                html_content = content
                            else:
                                message_text = content
                        except Exception as e:
                            print(f"[DEBUG] Ошибка при декодировании письма: {str(e)}")

                    # Создаем словарь с содержимым письма
                    email_content = {
                        'subject': subject_header,
                        'text': message_text,
                        'html': html_content,
                        'from': from_header
                    }

                    # Сохраняем письмо в файл
                    save_email_to_file(email, email_content)

                    print(f"[DEBUG] Текст письма: {message_text[:100]}...")

                    # Ищем код подтверждения в тексте письма
                    # Сначала ищем по шаблону "код: XXXX" или "code: XXXX"
                    code_match = re.search(r'[Cc]ode:?\s*(\d{6})', message_text)
                    if not code_match:
                        # Если не нашли, ищем просто 6 цифр подряд
                        code_match = re.search(r'(\d{6})', message_text)

                    if code_match:
                        verification_code = code_match.group(1)
                        print(f"[DEBUG] Найден код подтверждения: {verification_code}")
                        # Сохраняем письмо с найденным кодом
                        save_email_to_file(email, email_content, verification_code)
                        mail.close()
                        mail.logout()
                        return verification_code

            print(f"[DEBUG] Код подтверждения не найден в письмах. Ждем {delay_between_attempts} секунд...")
            mail.close()
            mail.logout()
            time.sleep(delay_between_attempts)

        except Exception as e:
            print(f"[DEBUG] Ошибка при получении кода из почты: {str(e)}")
            logger.error(f"Ошибка при получении кода из почты: {str(e)}")
            time.sleep(delay_between_attempts)

    print(f"[DEBUG] Не удалось получить код подтверждения после {max_attempts} попыток")
    return None

def test_email_connection(email_address, password):
    """
    Проверяет подключение к почтовому ящику

    Возвращает:
    - success: True, если подключение успешно
    - message: Сообщение об успехе или ошибке
    """
    # Определяем сервер IMAP
    imap_server = get_imap_server(email_address)
    print(f"[DEBUG] Подключение к IMAP-серверу: {imap_server}")

    try:
        # Подключаемся к серверу IMAP с использованием SSL и порта 993
        mail = imaplib.IMAP4_SSL(imap_server, 993)

        # Пытаемся войти
        mail.login(email_address, password)

        # Если дошли до этой точки, значит вход успешен
        mail.logout()
        return True, "Подключение к почте успешно установлено"

    except imaplib.IMAP4.error as e:
        return False, f"Ошибка аутентификации: {str(e)}"
    except Exception as e:
        return False, f"Ошибка подключения: {str(e)}"

def get_verification_code_combined(email, password, instagram_client=None):
    """Комбинированный метод получения кода подтверждения"""

    # Сначала пробуем получить код через Telegram-бот
    if VERIFICATION_BOT_TOKEN and VERIFICATION_BOT_ADMIN_ID:
        code = get_code_from_telegram_bot_sync(email, password)
        if code:
            return code

    # Проверяем, доступен ли модуль OCR
    try:
        from ocr_verification import get_verification_code_with_fallbacks
        return get_verification_code_with_fallbacks(email, password, instagram_client)
    except ImportError:
        # Если модуль OCR недоступен, используем только стандартный метод
        return get_code_from_firstmail(email, password)

async def send_email_to_telegram(email_content):
    """
    Отправляет содержимое письма в Telegram-бот

    Args:
    email_content (dict): Словарь с содержимым письма (subject, text, html)

    Returns:
    bool: True, если сообщение отправлено успешно
    """
    url = f"https://api.telegram.org/bot{VERIFICATION_BOT_TOKEN}/sendMessage"

    # Формируем сообщение
    message = f"📧 <b>Письмо от Instagram</b>\n\n"
    message += f"<b>Тема:</b> {email_content.get('subject', 'Нет темы')}\n\n"

    # Добавляем текст письма, если он есть
    if email_content.get('text'):
        # Ограничиваем размер текста и экранируем специальные символы HTML
        text_preview = email_content['text'][:1000] + "..." if len(email_content['text']) > 1000 else email_content['text']
        text_preview = text_preview.replace('<', '&lt;').replace('>', '&gt;').replace('&', '&amp;')
        message += f"<b>Текст:</b>\n{text_preview}\n\n"

    # Добавляем информацию о всех найденных 6-значных числах
    if email_content.get('text'):
        six_digit_numbers = re.findall(r'\b\d{6}\b', email_content['text'])
        if six_digit_numbers:
            message += f"<b>Найденные 6-значные числа в тексте:</b> {', '.join(six_digit_numbers)}\n\n"

    if email_content.get('html'):
        six_digit_numbers_html = re.findall(r'\b\d{6}\b', email_content['html'])
        if six_digit_numbers_html:
            message += f"<b>Найденные 6-значные числа в HTML:</b> {', '.join(six_digit_numbers_html)}\n\n"

    message += "Пожалуйста, отправьте правильный код подтверждения."

    data = {
        "chat_id": VERIFICATION_BOT_ADMIN_ID,
        "text": message,
        "parse_mode": "HTML"
    }

    try:
        print(f"[DEBUG] Отправка сообщения в Telegram. URL: {url}, chat_id: {VERIFICATION_BOT_ADMIN_ID}")
        async with aiohttp.ClientSession() as session:
            async with session.post(url, data=data) as response:
                response_text = await response.text()
                if response.status == 200:
                    logger.info(f"Содержимое письма отправлено в Telegram")
                    return True
                else:
                    logger.error(f"Ошибка при отправке содержимого письма в Telegram: {response.status}. Ответ: {response_text}")
                    print(f"[DEBUG] Ошибка при отправке содержимого письма в Telegram: {response.status}. Ответ: {response_text}")
                    return False
    except Exception as e:
        logger.error(f"Ошибка при отправке содержимого письма в Telegram: {str(e)}")
        print(f"[DEBUG] Исключение при отправке содержимого письма в Telegram: {str(e)}")
        return False

async def wait_for_telegram_code(timeout=60):
    """
    Ожидает код подтверждения от Telegram-бота

    Args:
    timeout (int): Время ожидания в секундах

    Returns:
    str: Код подтверждения или None, если время ожидания истекло
    """
    # Путь к файлу с кодом
    code_file = "verification_code.txt"

    # Проверяем, существует ли файл
    if os.path.exists(code_file):
        # Удаляем файл, чтобы не использовать старый код
        try:
            os.remove(code_file)
            print(f"[DEBUG] Удален старый файл с кодом: {code_file}")
        except Exception as e:
            print(f"[DEBUG] Ошибка при удалении файла с кодом: {str(e)}")

    # Получаем текущее время
    start_time = time.time()

    print(f"[DEBUG] Ожидание кода подтверждения от Telegram в течение {timeout} секунд")

    # Ждем, пока не появится файл с кодом или не истечет таймаут
    while time.time() - start_time < timeout:
        if os.path.exists(code_file):
            try:
                with open(code_file, "r") as f:
                    code = f.read().strip()

                if code and re.match(r'^\d{6}$', code):
                    print(f"[DEBUG] Найден код в файле: {code}")
                    return code
            except Exception as e:
                print(f"[DEBUG] Ошибка при чтении файла с кодом: {str(e)}")

        # Ждем перед следующей проверкой
        await asyncio.sleep(1)

    print(f"[DEBUG] Время ожидания кода подтверждения истекло ({timeout} секунд)")
    return None

async def get_code_from_telegram_bot(email, password, max_attempts=3, delay_between_attempts=10):
    """
    Получает код подтверждения через Telegram-бот

    Args:
    email (str): Адрес электронной почты
    password (str): Пароль от почты
    max_attempts (int): Максимальное количество попыток
    delay_between_attempts (int): Задержка между попытками в секундах

    Returns:
    str: Код подтверждения или None, если не удалось получить
    """
    print(f"[DEBUG] Получение кода через Telegram-бот для {email}")
    logger.info(f"Получение кода через Telegram-бот для {email}")

    # Проверяем настройки
    if not VERIFICATION_BOT_TOKEN or not VERIFICATION_BOT_ADMIN_ID:
        print("[DEBUG] VERIFICATION_BOT_TOKEN или VERIFICATION_BOT_ADMIN_ID не настроены")
        logger.error("VERIFICATION_BOT_TOKEN или VERIFICATION_BOT_ADMIN_ID не настроены")
        return None

    for attempt in range(max_attempts):
        try:
            print(f"[DEBUG] Попытка {attempt+1} получения кода через Telegram-бот")

            # Получаем письмо от Instagram
            email_content = await get_latest_instagram_email(email, password)

            if not email_content:
                print(f"[DEBUG] Не удалось получить письмо от Instagram для {email}")
                await asyncio.sleep(delay_between_attempts)
                continue

            # Отправляем содержимое письма в Telegram
            sent = await send_email_to_telegram(email_content)

            if not sent:
                print(f"[DEBUG] Не удалось отправить содержимое письма в Telegram для {email}")
                await asyncio.sleep(delay_between_attempts)
                continue

            # Ждем код от Telegram-бота
            code = await wait_for_telegram_code(timeout=60)  # Ждем 1 минуту

            if code:
                print(f"[DEBUG] Получен код {code} через Telegram-бот для {email}")
                return code

            print(f"[DEBUG] Не получен код через Telegram-бот для {email}, ожидание {delay_between_attempts} секунд")
            await asyncio.sleep(delay_between_attempts)

        except Exception as e:
            print(f"[DEBUG] Ошибка при получении кода через Telegram-бот: {str(e)}")
            logger.error(f"Ошибка при получении кода через Telegram-бот: {str(e)}")
            await asyncio.sleep(delay_between_attempts)

    print(f"[DEBUG] Не удалось получить код через Telegram-бот после {max_attempts} попыток")
    return None

async def get_latest_instagram_email(email, password):
    """
    Получает последнее письмо от Instagram

    Args:
    email (str): Адрес электронной почты
    password (str): Пароль от почты

    Returns:
    dict: Словарь с содержимым письма или None, если не удалось получить
    """
    try:
        # Определяем сервер IMAP
        imap_server = get_imap_server(email)
        print(f"[DEBUG] Подключение к IMAP-серверу: {imap_server}")

        # Подключаемся к серверу IMAP
        mail = imaplib.IMAP4_SSL(imap_server, 993)
        mail.login(email, password)
        mail.select("inbox")

        # Ищем письма от Instagram
        status, messages = mail.search(None, '(FROM "instagram")')

        if status != "OK" or not messages[0]:
            print(f"[DEBUG] Письма от Instagram не найдены для {email}")
            mail.close()
            mail.logout()
            return None

        # Получаем ID последнего письма
        email_ids = messages[0].split()
        latest_email_id = email_ids[-1]

        # Получаем содержимое письма
        status, msg_data = mail.fetch(latest_email_id, "(RFC822)")

        if status != "OK":
            print(f"[DEBUG] Не удалось получить содержимое письма для {email}")
            mail.close()
            mail.logout()
            return None

        # Парсим письмо
        msg = email_lib.message_from_bytes(msg_data[0][1])

        # Получаем тему
        subject = ""
        subject_header = msg.get("Subject", "")
        if subject_header:
            decoded_subject = decode_header(subject_header)
            subject = decoded_subject[0][0]
            if isinstance(subject, bytes):
                subject = subject.decode(decoded_subject[0][1] or 'utf-8')

        # Получаем текст и HTML
        text = ""
        html = ""

        if msg.is_multipart():
            for part in msg.walk():
                content_type = part.get_content_type()
                if content_type == "text/plain":
                    try:
                        payload = part.get_payload(decode=True)
                        charset = part.get_content_charset() or 'utf-8'
                        text += payload.decode(charset, errors='replace')
                    except Exception as e:
                        print(f"[DEBUG] Ошибка при декодировании текстовой части: {e}")
                elif content_type == "text/html":
                    try:
                        payload = part.get_payload(decode=True)
                        charset = part.get_content_charset() or 'utf-8'
                        html += payload.decode(charset, errors='replace')
                    except Exception as e:
                        print(f"[DEBUG] Ошибка при декодировании HTML части: {e}")
        else:
            try:
                payload = msg.get_payload(decode=True)
                charset = msg.get_content_charset() or 'utf-8'
                content = payload.decode(charset, errors='replace')
                if msg.get_content_type() == "text/html":
                    html = content
                else:
                    text = content
            except Exception as e:
                print(f"[DEBUG] Ошибка при декодировании письма: {e}")

        mail.close()
        mail.logout()

        return {
            'subject': subject,
            'text': text,
            'html': html
        }

    except Exception as e:
        print(f"[DEBUG] Ошибка при получении письма: {str(e)}")
        logger.error(f"Ошибка при получении письма: {str(e)}")
        return None

def get_code_from_telegram_bot_sync(email, password, max_attempts=3, delay_between_attempts=10):
    """
    Синхронная обертка для получения кода через Telegram-бот

    Args:
    email (str): Адрес электронной почты
    password (str): Пароль от почты
    max_attempts (int): Максимальное количество попыток
    delay_between_attempts (int): Задержка между попытками в секундах

    Returns:
    str: Код подтверждения или None, если не удалось получить
    """
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(get_code_from_telegram_bot(email, password, max_attempts, delay_between_attempts))
    finally:
        loop.close()

def cleanup_email_logs(email):
    """
    Удаляет файлы писем для указанного email после успешного входа

    Args:
    email (str): Email аккаунта
    """
    email_logs_dir = 'email_logs'
    if not os.path.exists(email_logs_dir):
        return

    # Безопасное представление email для использования в имени файла
    safe_email = email.replace('@', '_at_').replace('.', '_dot_')

    try:
        # Находим все файлы, связанные с этим email
        for filename in os.listdir(email_logs_dir):
            # Проверяем, содержит ли имя файла email (в безопасном формате)
            if email.replace('@', '_at_') in filename and not filename.startswith(f"last_code_{safe_email}"):
                file_path = os.path.join(email_logs_dir, filename)
                if os.path.isfile(file_path):
                    os.remove(file_path)
                    print(f"[DEBUG] Удален файл: {file_path}")

        print(f"[DEBUG] Очистка файлов писем для {email} завершена")
    except Exception as e:
        print(f"[DEBUG] Ошибка при очистке файлов писем: {str(e)}")
        logger.error(f"Ошибка при очистке файлов писем: {str(e)}")