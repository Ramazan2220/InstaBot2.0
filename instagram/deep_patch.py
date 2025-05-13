"""
Модуль для глубокого патчинга библиотеки instagrapi
"""
import logging
import inspect
import types
from instagrapi.mixins.private import PrivateRequestMixin

logger = logging.getLogger(__name__)

def apply_deep_patch():
    """
    Применяет глубокий патч к библиотеке instagrapi
    """
    # Патчим метод _send_private_request
    original_send_private_request = PrivateRequestMixin._send_private_request

    def patched_send_private_request(self, endpoint, **kwargs):
        """
        Патч для метода _send_private_request, который обеспечивает использование
        правильного User-Agent из настроек устройства
        """
        # Если в настройках есть user_agent, устанавливаем его
        if hasattr(self, "settings") and "user_agent" in self.settings:
            self.user_agent = self.settings["user_agent"]
            logger.info(f"Установлен User-Agent: {self.user_agent}")

        # Вызываем оригинальный метод
        return original_send_private_request(self, endpoint, **kwargs)

    # Применяем патч
    PrivateRequestMixin._send_private_request = patched_send_private_request
    logger.info("Патч для метода _send_private_request успешно применен")

    # Патчим метод _call_api
    if hasattr(PrivateRequestMixin, "_call_api"):
        original_call_api = PrivateRequestMixin._call_api

        def patched_call_api(self, *args, **kwargs):
            """
            Патч для метода _call_api, который обеспечивает отображение
            правильного User-Agent в логах
            """
            # Вызываем оригинальный метод
            result = original_call_api(self, *args, **kwargs)

            # Изменяем информацию в логах
            if hasattr(self, "settings") and "device_name" in self.settings:
                logger.info(f"Используется устройство: {self.settings['device_name']}")

            return result

        # Применяем патч
        PrivateRequestMixin._call_api = patched_call_api
        logger.info("Патч для метода _call_api успешно применен")

    # Патчим метод _send_request
    if hasattr(PrivateRequestMixin, "_send_request"):
        original_send_request = PrivateRequestMixin._send_request

        def patched_send_request(self, *args, **kwargs):
            """
            Патч для метода _send_request, который обеспечивает отображение
            правильного User-Agent в логах
            """
            # Вызываем оригинальный метод
            result = original_send_request(self, *args, **kwargs)

            # Изменяем информацию в логах
            if hasattr(self, "settings") and "device_name" in self.settings:
                logger.info(f"Используется устройство: {self.settings['device_name']}")

            return result

        # Применяем патч
        PrivateRequestMixin._send_request = patched_send_request
        logger.info("Патч для метода _send_request успешно применен")

    # Патчим метод _request
    if hasattr(PrivateRequestMixin, "_request"):
        original_request = PrivateRequestMixin._request

        def patched_request(self, *args, **kwargs):
            """
            Патч для метода _request, который обеспечивает отображение
            правильного User-Agent в логах
            """
            # Вызываем оригинальный метод
            result = original_request(self, *args, **kwargs)

            # Изменяем информацию в логах
            if hasattr(self, "settings") and "device_name" in self.settings:
                logger.info(f"Используется устройство: {self.settings['device_name']}")

            return result

        # Применяем патч
        PrivateRequestMixin._request = patched_request
        logger.info("Патч для метода _request успешно применен")

    logger.info("Глубокий патч для instagrapi успешно применен")