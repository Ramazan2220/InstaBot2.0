# Интеграция SessionManager в InstaBot2.0

from instagram.session_manager import SessionManager, SessionStatus
import logging
import threading
import time

class SessionManagerIntegration:
    def __init__(self, bot, config):
        """
        Интеграция менеджера сессий в существующую систему InstaBot2.0

        Args:
            bot: Экземпляр основного класса бота
            config: Конфигурация
        """
        self.bot = bot
        self.config = config
        self.logger = logging.getLogger('session_manager_integration')

        # Инициализация менеджера сессий
        self.session_manager = SessionManager(config, bot.db_connection if hasattr(bot, 'db_connection') else None)

        # Флаг для контроля фонового потока
        self.running = False
        self.check_thread = None

        # Интервал проверки здоровья сессий (в минутах)
        self.check_interval = config.get('session_check_interval_minutes', 30)

    def start(self):
        """Запуск интеграции и фонового потока проверки сессий"""
        self.logger.info("Starting session manager integration")
        self.running = True

        # Запуск фонового потока для проверки здоровья сессий
        self.check_thread = threading.Thread(target=self._health_check_loop)
        self.check_thread.daemon = True
        self.check_thread.start()

        self.logger.info("Session manager integration started")

    def stop(self):
        """Остановка фонового потока"""
        self.logger.info("Stopping session manager integration")
        self.running = False

        if self.check_thread and self.check_thread.is_alive():
            self.check_thread.join(timeout=5)

        self.logger.info("Session manager integration stopped")

    def _health_check_loop(self):
        """Фоновый поток для периодической проверки здоровья сессий"""
        while self.running:
            try:
                self.logger.debug("Running periodic health checks")

                # Получаем словарь сессий из бота
                sessions_dict = self._get_sessions_from_bot()

                # Проверяем здоровье сессий
                health_results = self.session_manager.schedule_health_checks(sessions_dict)

                # Обрабатываем результаты проверки
                self._process_health_results(health_results)

                # Пауза перед следующей проверкой
                time.sleep(self.check_interval * 60)
            except Exception as e:
                self.logger.error(f"Error in health check loop: {e}")
                time.sleep(60)  # Короткая пауза перед повторной попыткой

    def _get_sessions_from_bot(self):
        """
        Получение словаря сессий из бота

        Returns:
            dict: Словарь {username: session}
        """
        # Этот метод нужно адаптировать под вашу структуру бота
        # Пример:
        sessions_dict = {}

        # Если в боте есть атрибут accounts или подобный
        if hasattr(self.bot, 'accounts'):
            for account in self.bot.accounts:
                if hasattr(account, 'session') and hasattr(account, 'username'):
                    sessions_dict[account.username] = account.session

        # Или если сессии хранятся в другой структуре
        # sessions_dict = self.bot.sessions

        return sessions_dict

    def _process_health_results(self, health_results):
        """
        Обработка результатов проверки здоровья сессий

        Args:
            health_results: Результаты проверок {username: SessionStatus}
        """
        for username, status in health_results.items():
            if status != SessionStatus.HEALTHY:
                self.logger.warning(f"Unhealthy session detected for {username}: {status.value}")

                # Получаем аккаунт из бота
                account = self._get_account_by_username(username)

                if account:
                    # Если сессия временно заблокирована, ставим на паузу
                    if status == SessionStatus.TEMP_BLOCKED:
                        self.logger.info(f"Pausing account {username} due to temporary block")
                        # Здесь код для паузы аккаунта
                        # Например: account.pause(3600)  # Пауза на 1 час

                    # Если сессия истекла или требует challenge, пытаемся восстановить
                    elif status in [SessionStatus.EXPIRED, SessionStatus.CHALLENGED]:
                        self.logger.info(f"Attempting to recover session for {username}")
                        # Получаем пароль и прокси
                        password = account.password if hasattr(account, 'password') else None
                        proxy = account.proxy if hasattr(account, 'proxy') else None

                        if password:
                            # Пытаемся восстановить сессию
                            success = self.session_manager.recover_session(
                                account.session,
                                username,
                                password,
                                proxy
                            )

                            if success:
                                self.logger.info(f"Successfully recovered session for {username}")
                            else:
                                self.logger.warning(f"Failed to recover session for {username}")
                        else:
                            self.logger.error(f"Cannot recover session for {username}: password not available")

    def _get_account_by_username(self, username):
        """
        Получение объекта аккаунта по имени пользователя

        Args:
            username: Имя пользователя

        Returns:
            object: Объект аккаунта или None
        """
        # Этот метод нужно адаптировать под вашу структуру бота
        # Пример:
        if hasattr(self.bot, 'accounts'):
            for account in self.bot.accounts:
                if hasattr(account, 'username') and account.username == username:
                    return account

        return None

    def check_session(self, username):
        """
        Проверка здоровья конкретной сессии

        Args:
            username: Имя пользователя

        Returns:
            SessionStatus: Статус сессии
        """
        account = self._get_account_by_username(username)

        if account and hasattr(account, 'session'):
            return self.session_manager.check_session_health(account.session, username)

        return None

    def get_stats(self):
        """
        Получение статистики по сессиям

        Returns:
            dict: Статистика по сессиям
        """
        return self.session_manager.get_session_stats()