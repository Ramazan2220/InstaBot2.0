import os
import json
import logging
import time
import random
from pathlib import Path
from .custom_client import CustomClient as Client
from instagrapi.exceptions import LoginRequired, BadPassword, ChallengeRequired
from .email_utils import get_verification_code_from_email, cleanup_email_logs
from config import ACCOUNTS_DIR
from database.db_manager import get_instagram_account, update_account_session_data, get_proxy_for_account
from device_manager import generate_device_settings, get_or_create_device_settings
from .client_patch import *
#from instagram.clip_upload_patch import *

logger = logging.getLogger(__name__)

# Глобальный кэш клиентов
_instagram_clients = {}

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

        # Проверяем, активна ли текущая сессия
        try:
            # Пробуем выполнить простой запрос для проверки сессии
            self.client.get_timeline_feed()
            logger.info(f"Сессия уже активна для {self.account.username}")
            self.is_logged_in = True
            return True
        except Exception as e:
            # Если сессия не активна, продолжаем с обычным входом
            logger.info(f"Сессия не активна для {self.account.username}, выполняется вход: {e}")

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
                        logger.info(f"Загружены сохраненные настройки устройства для {self.account.username}")

                    # Пытаемся использовать сохраненную сессию
                    self.client.login(self.account.username, self.account.password)
                    self.is_logged_in = True
                    logger.info(f"Успешный вход по сохраненной сессии для {self.account.username}")
                    return True
                except Exception as e:
                    logger.warning(f"Не удалось использовать сохраненную сессию для {self.account.username}: {e}")
                    # Продолжаем с обычным входом
            else:
                # Если сессия не найдена, генерируем новые настройки устройства
                logger.info(f"Файл сессии не найден для {self.account.username}, генерируем новые настройки устройства")
                device_settings = generate_device_settings(self.account_id)
                self.client.set_settings(device_settings)
                logger.info(f"Применены новые настройки устройства для {self.account.username}")

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

def test_instagram_login(username, password, email=None, email_password=None, account_id=None):
    """
    Тестирует вход в Instagram с указанными учетными данными.

    Args:
    username (str): Имя пользователя Instagram
    password (str): Пароль пользователя Instagram
    email (str, optional): Email для получения кода подтверждения
    email_password (str, optional): Пароль от email
    account_id (int, optional): ID аккаунта для генерации уникальных настроек устройства

    Returns:
    bool: True, если вход успешен, False в противном случае
    """
    try:
        logger.info(f"Тестирование входа для пользователя {username}")

        # Создаем клиент Instagram
        client = Client()

        # Если предоставлен account_id, генерируем и применяем уникальные настройки устройства
        if account_id:
            device_settings = generate_device_settings(account_id)
            client.set_settings(device_settings)
            logger.info(f"Применены уникальные настройки устройства для {username}")

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

def test_instagram_login_with_proxy(account_id, username, password, email=None, email_password=None):
    try:
        logger.info(f"Тестирование входа для пользователя {username} с прокси")

        # Проверяем наличие файла сессии
        session_file = os.path.join(ACCOUNTS_DIR, str(account_id), "session.json")

        # Создаем клиент Instagram
        client = Client()
        logger.info(f"Создан клиент Instagram для {username}")

        # Проверяем существующую сессию
        if os.path.exists(session_file):
            logger.info(f"Найден файл сессии для аккаунта {username}")
            try:
                # Загружаем данные сессии
                with open(session_file, 'r') as f:
                    session_data = json.load(f)

                # Устанавливаем настройки клиента из сессии
                if 'settings' in session_data:
                    client.set_settings(session_data['settings'])
                    logger.info(f"Загружены сохраненные настройки устройства для {username}")

                # Получаем прокси для аккаунта
                proxy = get_proxy_for_account(account_id)
                if proxy:
                    proxy_url = f"{proxy.protocol}://{proxy.host}:{proxy.port}"
                    if proxy.username and proxy.password:
                        proxy_url = f"{proxy.protocol}://{proxy.username}:{proxy.password}@{proxy.host}:{proxy.port}"
                    client.set_proxy(proxy_url)

                # Пробуем использовать сохраненную сессию
                client.login(username, password)
                logger.info(f"Успешный вход по сохраненной сессии для {username}")

                # Сохраняем клиент в глобальный кэш
                _instagram_clients[account_id] = client
                return True
            except Exception as e:
                logger.warning(f"Не удалось использовать сохраненную сессию для {username}: {e}")
                # Удаляем недействительный файл сессии
                try:
                    os.remove(session_file)
                    logger.info(f"Удален недействительный файл сессии для {username}")
                except Exception as del_error:
                    logger.warning(f"Не удалось удалить файл сессии для {username}: {del_error}")

                # Очищаем клиент перед повторной попыткой
                client = Client()
                logger.info(f"Создан новый клиент Instagram для {username} после неудачной попытки входа")

        # Если сессия не найдена или недействительна, выполняем обычный вход
        # Получаем прокси для аккаунта
        proxy = get_proxy_for_account(account_id)

        # Генерируем и применяем настройки устройства
        device_settings = generate_device_settings(account_id)
        client.set_settings(device_settings)

        # Устанавливаем прокси
        if proxy:
            proxy_url = f"{proxy.protocol}://{proxy.host}:{proxy.port}"
            if proxy.username and proxy.password:
                proxy_url = f"{proxy.protocol}://{proxy.username}:{proxy.password}@{proxy.host}:{proxy.port}"
            client.set_proxy(proxy_url)
            logger.info(f"Установлен прокси {proxy_url} для {username}")
        else:
            logger.warning(f"Прокси не найден для аккаунта {username}")

        # Настраиваем обработчик кодов подтверждения
        if email and email_password:
            client.challenge_code_handler = lambda username, choice: get_verification_code_from_email(
                email, email_password, max_attempts=5, delay_between_attempts=10
            ) or input(f"Enter code for {username}: ")
            logger.info(f"Настроен обработчик кодов подтверждения для {username}")

        # Добавляем случайную задержку перед входом
        delay = random.uniform(2, 5)
        logger.info(f"Добавлена задержка {delay:.2f} секунд перед входом для {username}")
        time.sleep(delay)

        # Выполняем вход
        client.login(username, password)
        logger.info(f"Успешный вход для {username}")

        # Сохраняем сессию
        account_dir = os.path.join(ACCOUNTS_DIR, str(account_id))
        os.makedirs(account_dir, exist_ok=True)

        session_data = {
            'username': username,
            'account_id': account_id,
            'last_login': time.strftime('%Y-%m-%d %H:%M:%S'),
            'settings': client.get_settings()
        }

        with open(session_file, 'w') as f:
            json.dump(session_data, f)
        logger.info(f"Сохранена сессия для {username}")

        # Сохраняем клиент в глобальный кэш
        _instagram_clients[account_id] = client

        return True
    except Exception as e:
        logger.error(f"Ошибка при входе для пользователя {username}: {str(e)}")
        # Если файл сессии существует, удаляем его
        if os.path.exists(session_file):
            try:
                os.remove(session_file)
                logger.info(f"Удален файл сессии после ошибки входа для {username}")
            except Exception as del_error:
                logger.warning(f"Не удалось удалить файл сессии для {username}: {del_error}")
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
                    logger.info(f"Загружены сохраненные настройки устройства для {username}")

                # Пытаемся использовать сохраненную сессию
                client.login(username, password)
                logger.info(f"Успешный вход по сохраненной сессии для {username}")
                return client
            except Exception as e:
                logger.warning(f"Не удалось использовать сохраненную сессию для {username}: {e}")
                # Продолжаем с обычным входом
        else:
            # Если сессия не найдена, генерируем новые настройки устройства
            logger.info(f"Файл сессии не найден для {username}, генерируем новые настройки устройства")
            device_settings = generate_device_settings(account_id)
            client.set_settings(device_settings)
            logger.info(f"Применены новые настройки устройства для {username}")

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

def get_instagram_client(account_id):
    """
    Возвращает инициализированный клиент Instagram для указанного аккаунта.
    Использует кэширование для предотвращения повторных входов.

    Args:
        account_id (int): ID аккаунта Instagram в базе данных

    Returns:
        Client: Инициализированный клиент Instagram или None в случае ошибки
    """
    global _instagram_clients

    # Проверяем, есть ли клиент в кэше
    if account_id in _instagram_clients:
        client = _instagram_clients[account_id]
        # Проверяем, активна ли сессия
        try:
            client.get_timeline_feed()
            logger.info(f"Используем кэшированный клиент для аккаунта {account_id}")
            return client
        except Exception as e:
            # Если сессия не активна, удаляем из кэша и пробуем войти заново
            logger.info(f"Кэшированный клиент не активен для аккаунта {account_id}: {e}")
            del _instagram_clients[account_id]

    # Получаем данные аккаунта из базы
    account = get_instagram_account(account_id)
    if not account:
        logger.error(f"Аккаунт с ID {account_id} не найден")
        return None

    # Пробуем войти и сохранить сессию
    try:
        # Используем функцию для входа с прокси
        success = test_instagram_login_with_proxy(
            account_id,
            account.username,
            account.password,
            getattr(account, 'email', None),
            getattr(account, 'email_password', None)
        )

        if success and account_id in _instagram_clients:
            return _instagram_clients[account_id]
        else:
            logger.error(f"Не удалось войти в аккаунт с ID {account_id}")
            return None
    except Exception as e:
        logger.error(f"Ошибка при получении клиента Instagram для аккаунта {account_id}: {e}")
        return None

def refresh_instagram_sessions():
    """
    Периодически обновляет сессии всех аккаунтов для поддержания их активности.
    Эту функцию можно запускать по расписанию, например, раз в день.
    """
    from database.db_manager import get_all_instagram_accounts

    logger.info("Начинаем обновление сессий Instagram аккаунтов")

    accounts = get_all_instagram_accounts()
    for account in accounts:
        try:
            # Проверяем, есть ли клиент в кэше
            if account.id in _instagram_clients:
                client = _instagram_clients[account.id]
                try:
                    # Выполняем простое действие для обновления сессии
                    client.get_timeline_feed()
                    logger.info(f"Сессия обновлена для аккаунта {account.username}")

                    # Обновляем время последнего входа в session.json
                    session_file = os.path.join(ACCOUNTS_DIR, str(account.id), "session.json")
                    if os.path.exists(session_file):
                        with open(session_file, 'r') as f:
                            session_data = json.load(f)

                        session_data['last_login'] = time.strftime('%Y-%m-%d %H:%M:%S')

                        with open(session_file, 'w') as f:
                            json.dump(session_data, f)
                except Exception as e:
                    logger.warning(f"Ошибка при обновлении сессии для {account.username}: {e}")
                    # Удаляем из кэша и пробуем войти заново
                    del _instagram_clients[account.id]
                    get_instagram_client(account.id)
            else:
                # Если клиента нет в кэше, пробуем войти
                get_instagram_client(account.id)
        except Exception as e:
            logger.error(f"Ошибка при обработке аккаунта {account.username}: {e}")

    logger.info("Обновление сессий Instagram аккаунтов завершено")

def remove_instagram_account(account_id):
    """
    Удаляет аккаунт Instagram и его сессию.

    Args:
        account_id (int): ID аккаунта Instagram в базе данных

    Returns:
        bool: True, если удаление успешно, False в противном случае
    """
    global _instagram_clients

    try:
        # Если клиент в кэше, выходим из аккаунта и удаляем из кэша
        if account_id in _instagram_clients:
            try:
                _instagram_clients[account_id].logout()
                logger.info(f"Выполнен выход из аккаунта {account_id}")
            except Exception as e:
                logger.warning(f"Ошибка при выходе из аккаунта {account_id}: {e}")

            del _instagram_clients[account_id]

        # Удаляем файлы сессии
        session_dir = os.path.join(ACCOUNTS_DIR, str(account_id))
        if os.path.exists(session_dir):
            import shutil
            shutil.rmtree(session_dir)
            logger.info(f"Удалены файлы сессии для аккаунта {account_id}")

        # Удаляем аккаунт из базы данных
        from database.db_manager import delete_instagram_account
        success = delete_instagram_account(account_id)

        if success:
            logger.info(f"Аккаунт {account_id} успешно удален")
        else:
            logger.error(f"Не удалось удалить аккаунт {account_id} из базы данных")

        return success

    except Exception as e:
        logger.error(f"Ошибка при удалении аккаунта {account_id}: {e}")
        return False