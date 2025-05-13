from instagrapi import Client
import logging

logger = logging.getLogger(__name__)

class CustomClient(Client):
    """
    Кастомный клиент Instagram с поддержкой уникальных устройств
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._custom_user_agent = None
        self._device_name = None
        logger.info("Инициализирован CustomClient с поддержкой уникальных устройств")

    def set_settings(self, settings):
        """
        Переопределенный метод для установки настроек устройства
        """
        # Вызываем оригинальный метод
        result = super().set_settings(settings)

        # Если в настройках есть user_agent, сохраняем его
        if "user_agent" in settings:
            self._custom_user_agent = settings["user_agent"]
            self.user_agent = settings["user_agent"]
            logger.info(f"Установлен пользовательский User-Agent: {self.user_agent}")

        # Сохраняем имя устройства для логов
        if "device_name" in settings:
            self._device_name = settings["device_name"]
            logger.info(f"Установлено устройство: {self._device_name}")

        return result

    def _send_private_request(self, endpoint, **kwargs):
        """
        Переопределенный метод для отправки запросов с правильным User-Agent
        """
        # Если есть кастомный User-Agent, устанавливаем его
        if self._custom_user_agent:
            old_user_agent = self.user_agent
            self.user_agent = self._custom_user_agent
            logger.debug(f"User-Agent изменен с {old_user_agent} на {self.user_agent}")

        # Вызываем оригинальный метод
        return super()._send_private_request(endpoint, **kwargs)

    def login(self, username, password, **kwargs):
        """
        Переопределенный метод для входа с правильным User-Agent
        """
        # Если есть кастомный User-Agent, устанавливаем его
        if self._custom_user_agent:
            old_user_agent = self.user_agent
            self.user_agent = self._custom_user_agent
            logger.debug(f"User-Agent изменен с {old_user_agent} на {self.user_agent}")

        # Вызываем оригинальный метод
        return super().login(username, password, **kwargs)

    def __str__(self):
        """
        Строковое представление клиента
        """
        if self._device_name:
            return f"CustomClient({self.username or 'anonymous'}, {self._device_name})"
        return f"CustomClient({self.username or 'anonymous'})"