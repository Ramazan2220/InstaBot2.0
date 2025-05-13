# debug_email.py
import imaplib
import email as email_lib
from email.header import decode_header
import re
from datetime import datetime
import sys

def debug_email(email_address, password):
    """Проверяет все письма в почтовом ящике и выводит подробную информацию"""
    print(f"Отладка почты {email_address}")

    try:
        # Подключаемся к FirstMail через IMAP
        mail = imaplib.IMAP4_SSL("imap.firstmail.ltd", 993)
        mail.login(email_address, password)
        mail.select("inbox")

        # Получаем все письма
        status, messages = mail.search(None, 'ALL')

        if status != "OK" or not messages[0]:
            print("Письма не найдены")
            return

        # Получаем ID писем
        email_ids = messages[0].split()
        print(f"Найдено {len(email_ids)} писем")

        # Перебираем письма от новых к старым
        for email_id in reversed(email_ids):
            status, msg_data = mail.fetch(email_id, "(RFC822)")

            if status != "OK":
                continue

            # Парсим письмо
            msg = email_lib.message_from_bytes(msg_data[0][1])

            # Получаем отправителя, тему и дату
            from_header = msg.get("From", "")
            subject_header = msg.get("Subject", "")
            date_header = msg.get("Date", "")

            # Декодируем заголовки, если нужно
            subject = ""
            if subject_header:
                decoded_subject = decode_header(subject_header)
                subject = decoded_subject[0][0]
                if isinstance(subject, bytes):
                    subject = subject.decode(decoded_subject[0][1] or 'utf-8')

            print(f"\n--- Письмо ID: {email_id.decode()} ---")
            print(f"От: {from_header}")
            print(f"Тема: {subject}")
            print(f"Дата: {date_header}")

            # Получаем текст письма
            message_text = ""
            if msg.is_multipart():
                for part in msg.walk():
                    content_type = part.get_content_type()
                    content_disposition = str(part.get("Content-Disposition", ""))

                    # Пропускаем вложения
                    if "attachment" in content_disposition:
                        continue

                    if content_type == "text/plain" or content_type == "text/html":
                        try:
                            payload = part.get_payload(decode=True)
                            charset = part.get_content_charset() or 'utf-8'
                            message_text += payload.decode(charset, errors='replace')
                        except Exception as e:
                            print(f"Ошибка при декодировании части письма: {str(e)}")
            else:
                try:
                    payload = msg.get_payload(decode=True)
                    charset = msg.get_content_charset() or 'utf-8'
                    message_text = payload.decode(charset, errors='replace')
                except Exception as e:
                    print(f"Ошибка при декодировании письма: {str(e)}")

            # Выводим первые 500 символов текста письма
            print(f"Текст письма (первые 500 символов): {message_text[:500]}")

            # Ищем все 6-значные числа в тексте письма
            all_codes = re.findall(r'\b\d{6}\b', message_text)
            if all_codes:
                print(f"Найдены потенциальные коды: {all_codes}")
                # Проверяем наличие конкретных кодов
                if '734400' in all_codes:
                    print("ВНИМАНИЕ! Найден код 734400")
                if '400791' in all_codes:
                    print("ВНИМАНИЕ! Найден код 400791")
                if '604352' in all_codes:
                    print("ВНИМАНИЕ! Найден код 604352")
                if '104534' in all_codes:
                    print("ВНИМАНИЕ! Найден код 104534")
            else:
                print("Коды не найдены")

        mail.close()
        mail.logout()

    except Exception as e:
        print(f"Ошибка при отладке почты: {str(e)}")

if __name__ == "__main__":
    if len(sys.argv) == 3:
        email_address = sys.argv[1]
        password = sys.argv[2]
    else:
        email_address = input("Введите адрес электронной почты: ")
        password = input("Введите пароль: ")

    debug_email(email_address, password)