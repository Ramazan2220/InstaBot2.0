import time
import logging
import threading
import queue
from enum import Enum
from telegram import ParseMode
import asyncio

# Импортируем наш новый модуль для получения кода через Telegram
try:
    from email_to_telegram import get_code_from_email_via_telegram_sync
    EMAIL_TO_TELEGRAM_AVAILABLE = True
except ImportError:
    EMAIL_TO_TELEGRAM_AVAILABLE = False
    logging.warning("Модуль email_to_telegram не найден. Функция получения кода через Telegram недоступна.")

logger = logging.getLogger(__name__)

class ChallengeChoice(Enum):
    SMS = 0
    EMAIL = 1

class TelegramChallengeHandler:
    """Обработчик запросов на подтверждение через Telegram"""

    # Глобальный словарь для хранения кодов подтверждения
    verification_codes = {}

    def __init__(self, bot, chat_id):
        self.bot = bot
        self.chat_id = chat_id
        self.code_queue = queue.Queue()
        self.is_waiting = False
        logger.info(f"Создан обработчик запросов для пользователя {chat_id}")

        # Регистрируем пользователя в глобальном словаре
        TelegramChallengeHandler.verification_codes[chat_id] = self.code_queue

    def reset(self):
        """Сбрасывает состояние обработчика"""
        self.is_waiting = False

        # Очищаем очередь
        while not self.code_queue.empty():
            try:
                self.code_queue.get_nowait()
            except queue.Empty:
                break

    @classmethod
    def set_code(cls, user_id, code):
        """Устанавливает код для пользователя"""
        print(f"[AUTH_MANAGER] Устанавливаем код {code} для пользователя {user_id}")
        if user_id in cls.verification_codes:
            cls.verification_codes[user_id].put(code)
            print(f"[AUTH_MANAGER] Код {code} добавлен в очередь для пользователя {user_id}")
            return True
        return False

    def handle_challenge(self, username, choice_type, email=None, email_password=None):
        """Обработчик запроса кода подтверждения"""
        print(f"[AUTH_MANAGER] Вызван handle_challenge для {username}, choice_type={choice_type}")

        # Если выбран EMAIL и у нас есть данные почты и доступен модуль email_to_telegram,
        # пробуем получить код автоматически
        if (choice_type == ChallengeChoice.EMAIL and email and email_password and
            EMAIL_TO_TELEGRAM_AVAILABLE):
            print(f"[AUTH_MANAGER] Пробуем получить код через email_to_telegram для {username}")

            # Отправляем сообщение о начале процесса
            self.bot.send_message(
                chat_id=self.chat_id,
                text=f"🔄 Автоматическое получение кода для аккаунта *{username}* через Telegram...",
                parse_mode='Markdown'
            )

            # Пытаемся получить код через email_to_telegram
            try:
                code = get_code_from_email_via_telegram_sync(email, email_password)
                if code:
                    print(f"[AUTH_MANAGER] Получен код {code} через email_to_telegram для {username}")

                    # Отправляем подтверждение получения кода
                    self.bot.send_message(
                        chat_id=self.chat_id,
                        text=f"✅ Код `{code}` автоматически получен и будет использован для входа в аккаунт *{username}*",
                        parse_mode='Markdown'
                    )

                    return code
                else:
                    print(f"[AUTH_MANAGER] Не удалось получить код через email_to_telegram для {username}")

                    # Сообщаем о неудаче и переходим к ручному вводу
                    self.bot.send_message(
                        chat_id=self.chat_id,
                        text=f"⚠️ Не удалось автоматически получить код для аккаунта *{username}*. Переходим к ручному вводу.",
                        parse_mode='Markdown'
                    )
            except Exception as e:
                print(f"[AUTH_MANAGER] Ошибка при получении кода через email_to_telegram: {str(e)}")

                # Сообщаем об ошибке и переходим к ручному вводу
                self.bot.send_message(
                    chat_id=self.chat_id,
                    text=f"❌ Ошибка при автоматическом получении кода: {str(e)}. Переходим к ручному вводу.",
                    parse_mode='Markdown'
                )

        # Если автоматическое получение не удалось или недоступно, используем ручной ввод
        if choice_type == ChallengeChoice.EMAIL:
            choice_name = "электронной почты"
            # Добавляем информацию о почте, если она доступна
            email_info = f"\nПочта: {email}" if email else ""
        elif choice_type == ChallengeChoice.SMS:
            choice_name = "SMS"
            email_info = ""
        else:
            choice_name = "неизвестного источника"
            email_info = ""

        # Отправляем сообщение в Telegram
        message = (
            f"📱 Требуется подтверждение для аккаунта *{username}*\n\n"
            f"Instagram запрашивает код подтверждения, отправленный на {choice_name}.{email_info}\n\n"
            f"Пожалуйста, введите код подтверждения (6 цифр):"
        )

        self.bot.send_message(
            chat_id=self.chat_id,
            text=message,
            parse_mode='Markdown'
        )

        # Устанавливаем флаг ожидания
        self.is_waiting = True
        print(f"[AUTH_MANAGER] Ожидание кода подтверждения для {username}, is_waiting={self.is_waiting}")

        # Ждем, пока код не будет введен (максимум 300 секунд = 5 минут)
        start_time = time.time()
        while self.is_waiting and time.time() - start_time < 300:
            try:
                # Пытаемся получить код из очереди с таймаутом
                code = self.code_queue.get(timeout=1)
                print(f"[AUTH_MANAGER] Получен код {code} для {username}")
                self.reset()

                # Отправляем подтверждение получения кода
                self.bot.send_message(
                    chat_id=self.chat_id,
                    text=f"✅ Код `{code}` получен и будет использован для входа в аккаунт *{username}*",
                    parse_mode='Markdown'
                )

                return code
            except queue.Empty:
                # Если очередь пуста, продолжаем ожидание
                pass

        # Если код не был введен за отведенное время
        self.bot.send_message(
            chat_id=self.chat_id,
            text="⏱ Время ожидания кода истекло. Пожалуйста, попробуйте снова."
        )

        self.reset()
        return None