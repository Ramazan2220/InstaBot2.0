"""
Объединенный модуль для применения патчей к библиотеке instagrapi
"""
import logging
from instagrapi import Client
from instagrapi.mixins.private import PrivateRequestMixin

logger = logging.getLogger(__name__)

# Сохраняем оригинальные методы
original_send_private_request = PrivateRequestMixin._send_private_request
original_set_settings = Client.set_settings

# Создаем патч для метода _send_private_request
def patched_send_private_request(self, endpoint, *args, **kwargs):
    """
    Патч для метода _send_private_request, который обеспечивает использование
    правильного User-Agent из настроек устройства
    """
    # Если в настройках есть user_agent, устанавливаем его
    if hasattr(self, "settings") and isinstance(self.settings, dict) and "user_agent" in self.settings:
        self.user_agent = self.settings["user_agent"]
        logger.info(f"Установлен User-Agent: {self.user_agent}")

    # Вызываем оригинальный метод
    return original_send_private_request(self, endpoint, *args, **kwargs)

# Создаем патч для метода set_settings
def patched_set_settings(self, settings):
    """
    Патч для метода set_settings, который обеспечивает установку
    правильного User-Agent из настроек устройства
    """
    # Вызываем оригинальный метод
    result = original_set_settings(self, settings)

    # Если в настройках есть user_agent, устанавливаем его
    if "user_agent" in settings:
        self.user_agent = settings["user_agent"]
        logger.debug(f"Установлен User-Agent из настроек: {self.user_agent}")

    return result

# Применяем патчи
PrivateRequestMixin._send_private_request = patched_send_private_request
Client.set_settings = patched_set_settings

logger.info("Объединенные патчи для instagrapi успешно применены")