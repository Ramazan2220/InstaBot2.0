import os
import json
import logging
import time
from .email_utils import get_verification_code_from_email
from pathlib import Path
from instagrapi import Client
from instagrapi.exceptions import LoginRequired, BadPassword, ChallengeRequired

from config import ACCOUNTS_DIR
from database.db_manager import get_instagram_account, update_account_session_data

logger = logging.getLogger(__name__)

class InstagramClient:
    def __init__(self, account_id):
        """
        Инициализирует клиент Instagram для указанного аккаунта.

        Args:
            account_id (int): ID аккаунта Instagram в базе данных
        """
        self.account_id = account_id
        self.account = get_instagram_account(account_id)
        self.client = Client()
        self.is_logged_in = False

    def login(self, challenge_handler=None):
        """
        Выполняет вход в аккаунт Instagram.

        Args:
            challenge_handler: Обработчик запросов на подтверждение (опционально)

        Returns:
            bool: True, если вход успешен, False в противном случае
        """
        if not self.account:
            logger.error(f"Аккаунт с ID {self.account_id} не найден")
            return False

        try:
            # Пытаемся использовать сохраненную сессию
            session_file = os.path.join(ACCOUNTS_DIR, str(self.account_id), "session.json")

            if os.path.exists(session_file):
                logger.info(f"Найден файл сессии для аккаунта {self.account.username}")

                try:
                    # Загружаем данные сессии
                    with open(session_file, 'r') as f:
                        session_data = json.load(f)

                    # Устанавливаем настройки клиента из сессии
                    if 'settings' in session_data:
                        self.client.set_settings(session_data['settings'])

                    # Пытаемся использовать сохраненную сессию
                    self.client.login(self.account.username, self.account.password)
                    self.is_logged_in = True
                    logger.info(f"Успешный вход по сохраненной сессии для {self.account.username}")
                    return True
                except Exception as e:
                    logger.warning(f"Не удалось использовать сохраненную сессию для {self.account.username}: {e}")
                    # Продолжаем с обычным входом

            # Если у аккаунта есть email и email_password, настраиваем автоматическое получение кода
            if hasattr(self.account, 'email') and hasattr(self.account, 'email_password') and self.account.email and self.account.email_password:
                # Определяем функцию-обработчик для получения кода
                def auto_challenge_code_handler(username, choice):
                    print(f"[DEBUG] Запрошен код подтверждения для {username}, тип: {choice}")
                    # Пытаемся получить код из почты
                    verification_code = get_verification_code_from_email(self.account.email, self.account.email_password, max_attempts=5, delay_between_attempts=10)
                    if verification_code:
                        print(f"[DEBUG] Получен код подтверждения из почты: {verification_code}")
                        return verification_code
                    else:
                        print(f"[DEBUG] Не удалось получить код из почты, запрашиваем через консоль")
                        # Если не удалось получить код из почты, запрашиваем через консоль
                        return input(f"Enter code (6 digits) for {username} ({choice}): ")

                # Устанавливаем обработчик
                self.client.challenge_code_handler = auto_challenge_code_handler
            # Если предоставлен обработчик запросов на подтверждение
            elif challenge_handler:
                # Устанавливаем обработчик для клиента
                self.client.challenge_code_handler = lambda username, choice: challenge_handler.handle_challenge(username, choice)

            # Обычный вход
            logger.info(f"Выполняется вход для пользователя {self.account.username}")
            self.client.login(self.account.username, self.account.password)
            self.is_logged_in = True

            # Сохраняем сессию
            self._save_session()

            logger.info(f"Успешный вход для пользователя {self.account.username}")
            return True

        except BadPassword:
            logger.error(f"Неверный пароль для пользователя {self.account.username}")
            return False

        except ChallengeRequired as e:
            logger.error(f"Требуется подтверждение для пользователя {self.account.username}: {e}")
            return False

        except LoginRequired:
            logger.error(f"Не удалось войти для пользователя {self.account.username}")
            return False

        except Exception as e:
            logger.error(f"Ошибка при входе для пользователя {self.account.username}: {str(e)}")
            return False

    def _save_session(self):
        """Сохраняет данные сессии"""
        try:
            # Создаем директорию для аккаунта, если она не существует
            account_dir = os.path.join(ACCOUNTS_DIR, str(self.account_id))
            os.makedirs(account_dir, exist_ok=True)

            # Получаем настройки клиента
            settings = self.client.get_settings()

            # Формируем данные сессии
            session_data = {
                'username': self.account.username,
                'account_id': self.account_id,
                'last_login': time.strftime('%Y-%m-%d %H:%M:%S'),
                'settings': settings
            }

            # Сохраняем в файл
            session_file = os.path.join(account_dir, "session.json")
            with open(session_file, 'w') as f:
                json.dump(session_data, f)

            # Обновляем данные сессии в базе данных
            update_account_session_data(self.account_id, json.dumps(session_data))

            logger.info(f"Сессия сохранена для пользователя {self.account.username}")

        except Exception as e:
            logger.error(f"Ошибка при сохранении сессии для {self.account.username}: {e}")

    def check_login(self):
        """
        Проверяет статус входа и выполняет вход при необходимости.

        Returns:
            bool: True, если вход выполнен, False в противном случае
        """
        if not self.is_logged_in:
            return self.login()

        try:
            # Проверяем, активна ли сессия
            self.client.get_timeline_feed()
            return True
        except Exception:
            # Если сессия не активна, пытаемся войти снова
            logger.info(f"Сессия не активна для {self.account.username}, выполняется повторный вход")
            return self.login()

    def logout(self):
        """Выполняет выход из аккаунта Instagram"""
        if self.is_logged_in:
            try:
                self.client.logout()
                self.is_logged_in = False
                logger.info(f"Выход выполнен для пользователя {self.account.username}")
                return True
            except Exception as e:
                logger.error(f"Ошибка при выходе для пользователя {self.account.username}: {str(e)}")
                return False
        return True

def test_instagram_login(username, password, email=None, email_password=None):
    """
    Тестирует вход в Instagram с указанными учетными данными.

    Args:
        username (str): Имя пользователя Instagram
        password (str): Пароль пользователя Instagram
        email (str, optional): Email для получения кода подтверждения
        email_password (str, optional): Пароль от email

    Returns:
        bool: True, если вход успешен, False в противном случае
    """
    try:
        logger.info(f"Тестирование входа для пользователя {username}")

        # Создаем клиент Instagram
        client = Client()

        # Если предоставлены данные почты, настраиваем автоматическое получение кода
        if email and email_password:
            # Определяем функцию-обработчик для получения кода
            def auto_challenge_code_handler(username, choice):
                print(f"[DEBUG] Запрошен код подтверждения для {username}, тип: {choice}")
                # Пытаемся получить код из почты
                verification_code = get_verification_code_from_email(email, email_password, max_attempts=5, delay_between_attempts=10)
                if verification_code:
                    print(f"[DEBUG] Получен код подтверждения из почты: {verification_code}")
                    return verification_code
                else:
                    print(f"[DEBUG] Не удалось получить код из почты, запрашиваем через консоль")
                    # Если не удалось получить код из почты, запрашиваем через консоль
                    return input(f"Enter code (6 digits) for {username} ({choice}): ")

            # Устанавливаем обработчик
            client.challenge_code_handler = auto_challenge_code_handler

        # Пытаемся войти
        client.login(username, password)

        # Если дошли до этой точки, значит вход успешен
        logger.info(f"Вход успешен для пользователя {username}")

        # Выходим из аккаунта
        client.logout()

        return True

    except BadPassword:
        logger.error(f"Неверный пароль для пользователя {username}")
        return False

    except ChallengeRequired:
        logger.error(f"Требуется подтверждение для пользователя {username}")
        return False

    except LoginRequired:
        logger.error(f"Не удалось войти для пользователя {username}")
        return False

    except Exception as e:
        logger.error(f"Ошибка при входе для пользователя {username}: {str(e)}")
        return False

def login_with_session(username, password, account_id, email=None, email_password=None):
    """
    Выполняет вход в Instagram с использованием сохраненной сессии.

    Args:
        username (str): Имя пользователя Instagram
        password (str): Пароль пользователя Instagram
        account_id (int): ID аккаунта в базе данных
        email (str, optional): Email для получения кода подтверждения
        email_password (str, optional): Пароль от email

    Returns:
        Client: Клиент Instagram или None в случае ошибки
    """
    try:
        logger.info(f"Вход с сессией для пользователя {username}")

        # Создаем клиент Instagram
        client = Client()

        # Если предоставлены данные почты, настраиваем автоматическое получение кода
        if email and email_password:
            # Определяем функцию-обработчик для получения кода
            def auto_challenge_code_handler(username, choice):
                print(f"[DEBUG] Запрошен код подтверждения для {username}, тип: {choice}")
                # Пытаемся получить код из почты
                verification_code = get_verification_code_from_email(email, email_password, max_attempts=5, delay_between_attempts=10)
                if verification_code:
                    print(f"[DEBUG] Получен код подтверждения из почты: {verification_code}")
                    return verification_code
                else:
                    print(f"[DEBUG] Не удалось получить код из почты, запрашиваем через консоль")
                    # Если не удалось получить код из почты, запрашиваем через консоль
                    return input(f"Enter code (6 digits) for {username} ({choice}): ")

            # Устанавливаем обработчик
            client.challenge_code_handler = auto_challenge_code_handler

        # Проверяем наличие файла сессии
        session_file = os.path.join(ACCOUNTS_DIR, str(account_id), "session.json")

        if os.path.exists(session_file):
            logger.info(f"Найден файл сессии для аккаунта {username}")

            try:
                # Загружаем данные сессии
                with open(session_file, 'r') as f:
                    session_data = json.load(f)

                # Устанавливаем настройки клиента из сессии
                if 'settings' in session_data:
                    client.set_settings(session_data['settings'])

                # Пытаемся использовать сохраненную сессию
                client.login(username, password)
                logger.info(f"Успешный вход по сохраненной сессии для {username}")
                return client
            except Exception as e:
                logger.warning(f"Не удалось использовать сохраненную сессию для {username}: {e}")
                # Продолжаем с обычным входом

        # Обычный вход
        client.login(username, password)

        # Сохраняем сессию
        try:
            # Создаем директорию для аккаунта, если она не существует
            account_dir = os.path.join(ACCOUNTS_DIR, str(account_id))
            os.makedirs(account_dir, exist_ok=True)

            # Получаем настройки клиента
            settings = client.get_settings()

            # Формируем данные сессии
            session_data = {
                'username': username,
                'account_id': account_id,
                'last_login': time.strftime('%Y-%m-%d %H:%M:%S'),
                'settings': settings
            }

            # Сохраняем в файл
            with open(session_file, 'w') as f:
                json.dump(session_data, f)

            # Обновляем данные сессии в базе данных
            update_account_session_data(account_id, json.dumps(session_data))

            logger.info(f"Сессия сохранена для пользователя {username}")

        except Exception as e:
            logger.error(f"Ошибка при сохранении сессии для {username}: {e}")

        return client

    except Exception as e:
        logger.error(f"Ошибка при входе для пользователя {username}: {str(e)}")
        return None

def check_login_challenge(self, username, password, email=None, email_password=None):
    """
    Проверяет, требуется ли проверка при входе, и обрабатывает ее

    Args:
        username (str): Имя пользователя Instagram
        password (str): Пароль от аккаунта Instagram
        email (str, optional): Адрес электронной почты для получения кода
        email_password (str, optional): Пароль от почты

    Returns:
        bool: True, если вход выполнен успешно, False в противном случае
    """
    print(f"[DEBUG] check_login_challenge вызван для {username}")

    # Максимальное количество попыток обработки проверок
    max_challenge_attempts = 3

    for attempt in range(max_challenge_attempts):
        try:
            # Пытаемся войти
            self.client.login(username, password)
            print(f"[DEBUG] Вход выполнен успешно для {username}")
            return True
        except ChallengeRequired as e:
            print(f"[DEBUG] Требуется проверка для {username}, попытка {attempt+1}")

            # Получаем API-путь для проверки
            api_path = self.client.last_json.get('challenge', {}).get('api_path')
            if not api_path:
                print(f"[DEBUG] Не удалось получить API-путь для проверки")
                return False

            # Получаем информацию о проверке
            try:
                self.client.get_challenge_url(api_path)
                challenge_type = self.client.last_json.get('step_name')
                print(f"[DEBUG] Тип проверки: {challenge_type}")

                # Выбираем метод проверки (email)
                if challenge_type == 'select_verify_method':
                    self.client.challenge_send_code(ChallengeChoice.EMAIL)
                    print(f"[DEBUG] Запрошен код подтверждения для {username}, тип: {ChallengeChoice.EMAIL}")

                # Получаем код подтверждения
                if email and email_password:
                    print(f"[DEBUG] Получение кода подтверждения из почты {email}")
                    from instagram.email_utils import get_verification_code_from_email

                    verification_code = get_verification_code_from_email(email, email_password)
                    if verification_code:
                        print(f"[DEBUG] Получен код подтверждения из почты: {verification_code}")
                        # Отправляем код
                        self.client.challenge_send_security_code(verification_code)

                        # Проверяем, успешно ли прошла проверка
                        if self.client.last_json.get('status') == 'ok':
                            print(f"[DEBUG] Код подтверждения принят для {username}")

                            # Пытаемся снова войти после успешной проверки
                            try:
                                self.client.login(username, password)
                                print(f"[DEBUG] Вход выполнен успешно после проверки для {username}")
                                return True
                            except Exception as login_error:
                                print(f"[DEBUG] Ошибка при повторном входе: {str(login_error)}")
                                # Продолжаем цикл для обработки следующей проверки
                                continue
                        else:
                            print(f"[DEBUG] Код подтверждения не принят для {username}")
                    else:
                        print(f"[DEBUG] Не удалось получить код из почты, запрашиваем через консоль")
                        # Если не удалось получить код из почты, запрашиваем через консоль
                        self.client.challenge_send_security_code(
                            self.client.challenge_code_handler(username, ChallengeChoice.EMAIL)
                        )
                else:
                    print(f"[DEBUG] Email не указан, запрашиваем код через консоль")
                    # Если email не указан, запрашиваем код через консоль
                    self.client.challenge_send_security_code(
                        self.client.challenge_code_handler(username, ChallengeChoice.EMAIL)
                    )

                # Пытаемся снова войти после проверки
                try:
                    self.client.login(username, password)
                    print(f"[DEBUG] Вход выполнен успешно после проверки для {username}")
                    return True
                except Exception as login_error:
                    print(f"[DEBUG] Ошибка при повторном входе: {str(login_error)}")
                    # Если это последняя попытка, возвращаем False
                    if attempt == max_challenge_attempts - 1:
                        return False
                    # Иначе продолжаем цикл для обработки следующей проверки
                    continue

            except Exception as challenge_error:
                print(f"[DEBUG] Ошибка при обработке проверки: {str(challenge_error)}")
                return False

        except Exception as e:
            print(f"[DEBUG] Ошибка при входе для {username}: {str(e)}")
            logger.error(f"Ошибка при входе для пользователя {username}: {str(e)}")
            return False

    print(f"[DEBUG] Не удалось войти после {max_challenge_attempts} попыток обработки проверок")
    return False

def submit_challenge_code(username, password, code, challenge_info=None):
    """
    Отправляет код подтверждения

    Возвращает:
    - success: True, если код принят
    - result: Результат операции или сообщение об ошибке
    """
    print(f"[DEBUG] submit_challenge_code вызван для {username} с кодом {code}")
    try:
        client = Client()

        # Восстанавливаем состояние клиента, если предоставлена информация о запросе
        if challenge_info and 'client_settings' in challenge_info:
            print(f"[DEBUG] Восстанавливаем настройки клиента для {username}")
            client.set_settings(challenge_info['client_settings'])

        # Отправляем код подтверждения
        print(f"[DEBUG] Отправляем код подтверждения {code} для {username}")
        client.challenge_code(code)

        # Пробуем войти снова
        print(f"[DEBUG] Пробуем войти снова для {username}")
        client.login(username, password)
        print(f"[DEBUG] Вход успешен для {username}")

        return True, "Код подтверждения принят"
    except Exception as e:
        print(f"[DEBUG] Ошибка при отправке кода подтверждения для {username}: {str(e)}")
        logger.error(f"Ошибка при отправке кода подтверждения: {str(e)}")
        return False, str(e)