import asyncio
import logging
import time
import aiohttp
import imaplib
import email as email_lib
from email.header import decode_header
import re
from datetime import datetime, timedelta, timezone
from config import VERIFICATION_BOT_TOKEN, VERIFICATION_BOT_ADMIN_ID

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def send_telegram_message(chat_id, text):
    """
    Отправляет сообщение в Telegram
    """
    url = f"https://api.telegram.org/bot{VERIFICATION_BOT_TOKEN}/sendMessage"
    data = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML"
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, data=data) as response:
                if response.status == 200:
                    logger.info(f"Сообщение отправлено в Telegram")
                    return True
                else:
                    logger.error(f"Ошибка при отправке сообщения в Telegram: {response.status}")
                    return False
    except Exception as e:
        logger.error(f"Ошибка при отправке сообщения в Telegram: {str(e)}")
        return False

async def get_verification_code_from_telegram(timeout=300):
    """
    Получает код подтверждения от Telegram-бота
    """
    url = f"https://api.telegram.org/bot{VERIFICATION_BOT_TOKEN}/getUpdates"
    params = {
        "offset": -1,
        "timeout": 30
    }

    start_time = time.time()

    while time.time() - start_time < timeout:
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params) as response:
                    if response.status == 200:
                        data = await response.json()
                        if data["ok"] and data["result"]:
                            for update in data["result"]:
                                if "message" in update and "text" in update["message"]:
                                    # Проверяем, что сообщение от нашего бота
                                    if str(update["message"]["from"]["id"]) == str(VERIFICATION_BOT_ADMIN_ID):
                                        text = update["message"]["text"]
                                        # Ищем код в тексте
                                        code_match = re.search(r'Получен код подтверждения: (\d{6})', text)
                                        if code_match:
                                            return code_match.group(1)

                        # Обновляем offset для следующего запроса
                        if data["result"]:
                            params["offset"] = data["result"][-1]["update_id"] + 1

                    # Ждем перед следующим запросом
                    await asyncio.sleep(2)
        except Exception as e:
            logger.error(f"Ошибка при получении обновлений от Telegram: {str(e)}")
            await asyncio.sleep(5)

    logger.warning(f"Время ожидания кода подтверждения истекло ({timeout} секунд)")
    return None

async def get_email_content(email_address, password):
    """
    Получает содержимое последнего письма от Instagram
    """
    # Определяем сервер IMAP в зависимости от домена почты
    if email_address.endswith('@gmail.com'):
        imap_server = 'imap.gmail.com'
    elif any(email_address.endswith(domain) for domain in [
        '@fmailler.com', '@fmailler.net', '@fmaillerbox.net', '@firstmail.ltd',
        '@fmailler.ltd', '@firstmail.net', '@firstmail.com'
    ]):
        imap_server = 'imap.firstmail.ltd'
    else:
        # Для других доменов можно попробовать стандартный формат
        domain = email_address.split('@')[1]
        imap_server = f'imap.{domain}'

    try:
        # Подключаемся к серверу IMAP
        mail = imaplib.IMAP4_SSL(imap_server, 993)
        mail.login(email_address, password)
        mail.select("inbox")

        # Ищем письма от Instagram
        status, messages = mail.search(None, '(FROM "instagram" UNSEEN)')

        if status != "OK" or not messages[0]:
            # Попробуем более широкий поиск
            status, messages = mail.search(None, 'FROM "instagram"')
            if status != "OK" or not messages[0]:
                mail.close()
                mail.logout()
                return None

        # Получаем ID писем
        email_ids = messages[0].split()

        # Берем последнее письмо
        latest_email_id = email_ids[-1]
        status, msg_data = mail.fetch(latest_email_id, "(RFC822)")

        if status != "OK":
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

        # Получаем текст письма
        body = ""
        if msg.is_multipart():
            for part in msg.walk():
                content_type = part.get_content_type()
                if content_type == "text/plain" or content_type == "text/html":
                    try:
                        payload = part.get_payload(decode=True)
                        charset = part.get_content_charset() or 'utf-8'
                        body += payload.decode(charset, errors='replace')
                    except:
                        pass
        else:
            try:
                payload = msg.get_payload(decode=True)
                charset = msg.get_content_charset() or 'utf-8'
                body = payload.decode(charset, errors='replace')
            except:
                pass

        mail.close()
        mail.logout()

        return {
            "subject": subject,
            "body": body
        }

    except Exception as e:
        logger.error(f"Ошибка при получении содержимого письма: {str(e)}")
        return None

async def get_code_from_email_via_telegram(email, password, timeout=300):
    """
    Асинхронная функция для получения кода через Telegram-бот
    """
    logger.info(f"Получение кода подтверждения через Telegram для {email}")

    # Проверяем настройки
    if not VERIFICATION_BOT_TOKEN or not VERIFICATION_BOT_ADMIN_ID:
        logger.error("VERIFICATION_BOT_TOKEN или VERIFICATION_BOT_ADMIN_ID не настроены")
        return None

    try:
        # Получаем содержимое письма
        email_content = await get_email_content(email, password)

        if not email_content:
            logger.error(f"Не удалось получить содержимое письма для {email}")
            return None

        # Отправляем содержимое письма в Telegram
        message = f"📧 <b>Письмо от Instagram</b>\n\n"
        message += f"<b>Тема:</b> {email_content['subject']}\n\n"

        # Ограничиваем размер сообщения
        body_preview = email_content['body'][:3000] + "..." if len(email_content['body']) > 3000 else email_content['body']
        message += f"<b>Содержимое:</b>\n{body_preview}"

        await send_telegram_message(VERIFICATION_BOT_ADMIN_ID, message)

        # Ждем получения кода от бота
        verification_code = await get_verification_code_from_telegram(timeout)

        if verification_code:
            logger.info(f"Получен код подтверждения: {verification_code}")
            return verification_code
        else:
            logger.warning("Не удалось получить код подтверждения через Telegram")
            return None

    except Exception as e:
        logger.error(f"Ошибка при получении кода через Telegram: {str(e)}")
        return None

def get_code_from_email_via_telegram_sync(email, password, timeout=300):
    """
    Синхронная обертка для асинхронной функции
    """
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(get_code_from_email_via_telegram(email, password, timeout))
    finally:
        loop.close()

# Тестовая функция
if __name__ == "__main__":
    email = "test@example.com"
    email_password = "password"

    print(f"Получение кода подтверждения для {email}...")
    code = get_code_from_email_via_telegram_sync(email, email_password)

    if code:
        print(f"Получен код: {code}")
    else:
        print("Не удалось получить код")