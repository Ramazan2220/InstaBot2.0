"""
Патч для метода clip_upload в instagrapi для поддержки скрытия рилсов из основной сетки
"""
import logging
from instagrapi import Client
from instagrapi.types import Media
from pathlib import Path
from typing import List, Optional

logger = logging.getLogger(__name__)

# Сохраняем оригинальный метод
original_clip_upload = Client.clip_upload

def patched_clip_upload(
    self,
    path: Path,
    caption: str = "",
    thumbnail: Optional[Path] = None,
    mentions: List[str] = [],
    locations: List[str] = [],
    configure_timeout: int = 10,
    show_in_feed: bool = True  # Новый параметр
) -> Media:
    """
    Патч для метода clip_upload с поддержкой скрытия из основной сетки

    Args:
        path: Путь к видеофайлу
        caption: Подпись к видео
        thumbnail: Путь к миниатюре (опционально)
        mentions: Упоминания пользователей
        locations: Локации
        configure_timeout: Таймаут конфигурации
        show_in_feed: Показывать ли в основной сетке профиля

    Returns:
        Media: Объект опубликованного медиа
    """
    logger.info(f"Публикация рилса с параметром show_in_feed={show_in_feed}")

    # Вызываем оригинальный метод для загрузки видео
    media = original_clip_upload(
        self,
        path,
        caption,
        thumbnail,
        mentions,
        locations,
        configure_timeout
    )

    # Если нужно скрыть из основной сетки, делаем дополнительный запрос
    if not show_in_feed and media:
        try:
            logger.info(f"Скрытие рилса {media.id} из основной сетки")

            # Используем внутренний метод _send_private_request для отправки запроса
            # Без параметра method, который не поддерживается в вашей версии
            endpoint = f"media/{media.id}/configure_to_clips/"
            params = {
                "remove_from_profile_grid": "1",
                "clips_uses_original_audio": "1"
            }

            # Используем POST запрос напрямую
            result = self._send_private_request(endpoint, params=params)

            if result.get("status") == "ok":
                logger.info(f"Рилс {media.id} успешно скрыт из основной сетки")
            else:
                logger.warning(f"Не удалось скрыть рилс из основной сетки: {result}")

        except Exception as e:
            logger.error(f"Ошибка при скрытии рилса из основной сетки: {e}")
            # Не выбрасываем исключение, так как рилс уже опубликован

    return media

# Применяем патч
Client.clip_upload = patched_clip_upload

logger.info("Патч для метода clip_upload успешно применен")