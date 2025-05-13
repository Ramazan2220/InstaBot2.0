# Session Manager Module
# Functionality for session management in InstaBot2.0

import time
import random
import logging
import requests
from datetime import datetime, timedelta
import json
import os
from enum import Enum

class SessionStatus(Enum):
    HEALTHY = "healthy"
    TEMP_BLOCKED = "temporarily_blocked"
    CHALLENGED = "challenged"
    EXPIRED = "expired"
    UNKNOWN_ERROR = "unknown_error"

class SessionManager:
    def __init__(self, config, db_connection=None):
        self.config = config
        self.db = db_connection
        self.logger = logging.getLogger('session_manager')
        self.setup_logging()

        # Публичные эндпоинты для проверки здоровья сессии
        self.health_check_endpoints = [
            "https://www.instagram.com/",
            "https://www.instagram.com/explore/",
            "https://www.instagram.com/explore/tags/instagram/"
        ]

        # Интервалы для экспоненциальной задержки (в секундах)
        self.retry_intervals = [60, 300, 900, 3600, 7200, 14400]  # 1мин, 5мин, 15мин, 1ч, 2ч, 4ч

        # Словарь для хранения информации о сессиях
        self.sessions_info = {}

        # Загрузка User-Agent и параметров устройств
        self.user_agents = self._load_user_agents()
        self.device_params = self._load_device_params()

    def setup_logging(self):
        """Настройка логирования"""
        if not self.logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)
            self.logger.setLevel(logging.INFO)

    def _load_user_agents(self):
        """Загрузка списка User-Agent"""
        try:
            # Пытаемся загрузить из файла, если он существует
            if os.path.exists('user_agents.json'):
                with open('user_agents.json', 'r') as f:
                    return json.load(f)
            # Иначе возвращаем базовый список
            return [
                "Mozilla/5.0 (iPhone; CPU iPhone OS 14_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.0 Mobile/15E148 Safari/604.1",
                "Mozilla/5.0 (iPhone; CPU iPhone OS 15_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.0 Mobile/15E148 Safari/604.1",
                "Mozilla/5.0 (iPhone; CPU iPhone OS 15_4 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.4 Mobile/15E148 Safari/604.1",
                "Mozilla/5.0 (iPhone; CPU iPhone OS 15_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) CriOS/102.0.5005.87 Mobile/15E148 Safari/604.1",
                "Mozilla/5.0 (iPhone; CPU iPhone OS 15_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.6 Mobile/15E148 Safari/604.1"
            ]
        except Exception as e:
            self.logger.error(f"Error loading user agents: {e}")
            return ["Mozilla/5.0 (iPhone; CPU iPhone OS 15_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.0 Mobile/15E148 Safari/604.1"]

    def _load_device_params(self):
        """Загрузка параметров устройств"""
        try:
            # Пытаемся загрузить из файла, если он существует
            if os.path.exists('device_params.json'):
                with open('device_params.json', 'r') as f:
                    return json.load(f)
            # Иначе возвращаем базовый список
            return [
                {
                    "device_id": "ios_" + ''.join(random.choices('0123456789abcdef', k=16)),
                    "manufacturer": "Apple",
                    "model": "iPhone13,4",
                    "os_version": "15.5",
                    "screen_width": 1170,
                    "screen_height": 2532
                },
                {
                    "device_id": "ios_" + ''.join(random.choices('0123456789abcdef', k=16)),
                    "manufacturer": "Apple",
                    "model": "iPhone12,1",
                    "os_version": "15.4",
                    "screen_width": 828,
                    "screen_height": 1792
                },
                {
                    "device_id": "ios_" + ''.join(random.choices('0123456789abcdef', k=16)),
                    "manufacturer": "Apple",
                    "model": "iPhone14,3",
                    "os_version": "16.0",
                    "screen_width": 1284,
                    "screen_height": 2778
                }
            ]
        except Exception as e:
            self.logger.error(f"Error loading device parameters: {e}")
            return [{
                "device_id": "ios_" + ''.join(random.choices('0123456789abcdef', k=16)),
                "manufacturer": "Apple",
                "model": "iPhone13,4",
                "os_version": "15.5",
                "screen_width": 1170,
                "screen_height": 2532
            }]

    def check_session_health(self, session, username):
        """
        Проверка здоровья сессии через запросы к публичным эндпоинтам

        Args:
            session: Объект сессии
            username: Имя пользователя для идентификации сессии

        Returns:
            SessionStatus: Статус сессии
        """
        self.logger.info(f"Checking session health for {username}")

        # Выбираем случайный эндпоинт для проверки
        endpoint = random.choice(self.health_check_endpoints)

        try:
            response = session.get(endpoint, timeout=10)

            # Анализируем ответ
            if response.status_code == 200:
                if "login" not in response.url and "challenge" not in response.url:
                    self.logger.info(f"Session for {username} is healthy")
                    self._update_session_info(username, SessionStatus.HEALTHY)
                    return SessionStatus.HEALTHY
                elif "challenge" in response.url:
                    self.logger.warning(f"Session for {username} requires challenge")
                    self._update_session_info(username, SessionStatus.CHALLENGED)
                    return SessionStatus.CHALLENGED
                else:
                    self.logger.warning(f"Session for {username} is expired")
                    self._update_session_info(username, SessionStatus.EXPIRED)
                    return SessionStatus.EXPIRED
            elif response.status_code == 429:
                self.logger.warning(f"Session for {username} is temporarily blocked (rate limit)")
                self._update_session_info(username, SessionStatus.TEMP_BLOCKED)
                return SessionStatus.TEMP_BLOCKED
            else:
                self.logger.error(f"Unknown error for {username}: Status code {response.status_code}")
                self._update_session_info(username, SessionStatus.UNKNOWN_ERROR)
                return SessionStatus.UNKNOWN_ERROR

        except Exception as e:
            self.logger.error(f"Error checking session health for {username}: {e}")
            self._update_session_info(username, SessionStatus.UNKNOWN_ERROR)
            return SessionStatus.UNKNOWN_ERROR

    def _update_session_info(self, username, status):
        """Обновление информации о сессии"""
        now = datetime.now()

        if username not in self.sessions_info:
            self.sessions_info[username] = {
                "status": status,
                "last_check": now,
                "status_history": [(now, status)],
                "retry_count": 0,
                "last_retry": None
            }
        else:
            self.sessions_info[username]["status"] = status
            self.sessions_info[username]["last_check"] = now
            self.sessions_info[username]["status_history"].append((now, status))

            # Ограничиваем историю до 20 записей
            if len(self.sessions_info[username]["status_history"]) > 20:
                self.sessions_info[username]["status_history"] = self.sessions_info[username]["status_history"][-20:]

        # Сохраняем в БД, если она доступна
        if self.db:
            try:
                # Здесь должен быть код для сохранения в БД
                pass
            except Exception as e:
                self.logger.error(f"Error saving session info to database: {e}")

    def recover_session(self, session, username, password, proxy=None):
        """
        Попытка восстановления сессии с экспоненциальной задержкой

        Args:
            session: Объект сессии
            username: Имя пользователя
            password: Пароль
            proxy: Прокси (опционально)

        Returns:
            bool: Успешность восстановления
        """
        if username not in self.sessions_info:
            self.sessions_info[username] = {
                "status": SessionStatus.UNKNOWN_ERROR,
                "last_check": datetime.now(),
                "status_history": [],
                "retry_count": 0,
                "last_retry": None
            }

        info = self.sessions_info[username]

        # Если превышено максимальное количество попыток, ждем дольше
        if info["retry_count"] >= len(self.retry_intervals):
            wait_time = self.retry_intervals[-1]
        else:
            wait_time = self.retry_intervals[info["retry_count"]]

        # Проверяем, прошло ли достаточно времени с последней попытки
        if info["last_retry"] and datetime.now() - info["last_retry"] < timedelta(seconds=wait_time):
            self.logger.info(f"Waiting for retry cooldown for {username}. Next retry in {wait_time - (datetime.now() - info['last_retry']).seconds} seconds")
            return False

        # Обновляем информацию о попытке
        info["retry_count"] += 1
        info["last_retry"] = datetime.now()

        # Ротация User-Agent и параметров устройства
        self._rotate_session_params(session, username)

        try:
            # Здесь должен быть код для повторного входа в аккаунт
            # Это зависит от вашей реализации логина
            self.logger.info(f"Attempting to recover session for {username}")

            # Пример кода для восстановления сессии:
            # login_successful = login_to_instagram(session, username, password, proxy)
            login_successful = True  # Заглушка, замените на реальный код

            if login_successful:
                self.logger.info(f"Successfully recovered session for {username}")
                self._update_session_info(username, SessionStatus.HEALTHY)
                info["retry_count"] = 0  # Сбрасываем счетчик попыток
                return True
            else:
                self.logger.warning(f"Failed to recover session for {username}")
                return False

        except Exception as e:
            self.logger.error(f"Error recovering session for {username}: {e}")
            return False

    def _rotate_session_params(self, session, username):
        """
        Ротация User-Agent и параметров устройства

        Args:
            session: Объект сессии
            username: Имя пользователя
        """
        # Выбираем случайный User-Agent
        new_user_agent = random.choice(self.user_agents)
        # Выбираем случайные параметры устройства
        new_device = random.choice(self.device_params)

        # Обновляем заголовки сессии
        session.headers.update({
            'User-Agent': new_user_agent,
            'X-IG-App-ID': '936619743392459',  # Стандартный App ID для Instagram
            'X-IG-Device-ID': new_device["device_id"],
            'X-IG-Android-ID': new_device["device_id"],
            'X-IG-Capabilities': '3brTvw==',  # Стандартное значение
            'X-IG-Connection-Type': 'WIFI',
            'X-IG-Connection-Speed': f"{random.randint(1000, 3000)}kbps",
            'Accept-Language': 'en-US',
            'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8'
        })

        self.logger.info(f"Rotated session parameters for {username}")

        # Сохраняем информацию о ротации
        if username in self.sessions_info:
            self.sessions_info[username]["current_user_agent"] = new_user_agent
            self.sessions_info[username]["current_device"] = new_device

    def schedule_health_checks(self, sessions_dict, interval_minutes=30):
        """
        Планирование регулярных проверок здоровья сессий

        Args:
            sessions_dict: Словарь {username: session}
            interval_minutes: Интервал между проверками в минутах

        Returns:
            dict: Результаты проверок {username: SessionStatus}
        """
        results = {}

        for username, session in sessions_dict.items():
            # Проверяем, нужно ли выполнять проверку
            if username in self.sessions_info:
                last_check = self.sessions_info[username]["last_check"]
                if datetime.now() - last_check < timedelta(minutes=interval_minutes):
                    self.logger.debug(f"Skipping health check for {username}, last check was {(datetime.now() - last_check).seconds // 60} minutes ago")
                    results[username] = self.sessions_info[username]["status"]
                    continue

            # Выполняем проверку
            status = self.check_session_health(session, username)
            results[username] = status

        return results

    def get_session_stats(self, username=None):
        """
        Получение статистики по сессиям

        Args:
            username: Имя пользователя (если None, то для всех сессий)

        Returns:
            dict: Статистика по сессиям
        """
        if username:
            if username in self.sessions_info:
                return self.sessions_info[username]
            return None

        # Агрегированная статистика по всем сессиям
        stats = {
            "total_sessions": len(self.sessions_info),
            "healthy_sessions": sum(1 for info in self.sessions_info.values() if info["status"] == SessionStatus.HEALTHY),
            "blocked_sessions": sum(1 for info in self.sessions_info.values() if info["status"] == SessionStatus.TEMP_BLOCKED),
            "challenged_sessions": sum(1 for info in self.sessions_info.values() if info["status"] == SessionStatus.CHALLENGED),
            "expired_sessions": sum(1 for info in self.sessions_info.values() if info["status"] == SessionStatus.EXPIRED),
            "unknown_error_sessions": sum(1 for info in self.sessions_info.values() if info["status"] == SessionStatus.UNKNOWN_ERROR),
            "sessions_info": self.sessions_info
        }

        return stats
