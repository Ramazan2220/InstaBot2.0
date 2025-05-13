"""
Модуль для применения monkey patching к библиотеке instagrapi
"""
import logging
from instagrapi.mixins.private import PrivateRequestMixin

logger = logging.getLogger(__name__)

# Сохраняем оригинальный метод
original_send_private_request = PrivateRequestMixin._send_private_request

# Создаем новый метод
def patched_send_private_request(self, endpoint, *args, **kwargs):
    """
    Патч для метода _send_private_request, который обеспечивает использование
    правильного User-Agent из настроек устройства
    """
    # Если в настройках есть user_agent, устанавливаем его
    if hasattr(self, "settings") and "user_agent" in self.settings:
        self.user_agent = self.settings["user_agent"]
        logger.info(f"Установлен User-Agent: {self.user_agent}")

    # Вызываем оригинальный метод
    return original_send_private_request(self, endpoint, *args, **kwargs)

# Применяем патч
PrivateRequestMixin._send_private_request = patched_send_private_request

logger.info("Патч для метода _send_private_request успешно применен")