from instagrapi import Client
from instagrapi.mixins.private import PrivateRequestMixin
import logging

logger = logging.getLogger(__name__)

# Сохраняем оригинальный метод
original_send_private_request = PrivateRequestMixin._send_private_request

# Создаем патч для метода _send_private_request
def patched_send_private_request(self, endpoint, *args, **kwargs):
    """
    Патч для метода _send_private_request, который обеспечивает использование
    правильного User-Agent из настроек устройства
    """
    # Если в настройках есть user_agent, устанавливаем его
    if hasattr(self, "settings") and isinstance(self.settings, dict) and "user_agent" in self.settings:
        self.user_agent = self.settings["user_agent"]
        logger.debug(f"Установлен User-Agent из настроек: {self.user_agent}")

    # Вызываем оригинальный метод
    return original_send_private_request(self, endpoint, *args, **kwargs)

# Применяем патч
PrivateRequestMixin._send_private_request = patched_send_private_request

# Патч для метода set_settings
original_set_settings = Client.set_settings

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

# Применяем патч
Client.set_settings = patched_set_settings

logger.info("Патчи для instagrapi успешно применены")