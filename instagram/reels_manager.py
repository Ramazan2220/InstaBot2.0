import logging
import os
import json
from pathlib import Path
import concurrent.futures

from instagram.client import InstagramClient
from database.db_manager import update_task_status, get_instagram_accounts
from config import MAX_WORKERS
from instagram.clip_upload_patch import *  # Импортируем патч

logger = logging.getLogger(__name__)

class ReelsManager:
    def __init__(self, account_id):
        self.instagram = InstagramClient(account_id)

    def publish_reel(self, video_path, caption=None, thumbnail_path=None, hide_from_feed=False):
        """Публикация видео в Reels"""
        try:
            # Проверяем статус входа
            if not self.instagram.check_login():
                logger.error(f"Не удалось войти в аккаунт для публикации Reels")
                return False, "Ошибка входа в аккаунт"

            # Проверяем существование файла
            if not os.path.exists(video_path):
                logger.error(f"Файл {video_path} не найден")
                return False, f"Файл не найден: {video_path}"

            # Публикуем Reels с параметром show_in_feed (обратным к hide_from_feed)
            media = self.instagram.client.clip_upload(
                Path(video_path),
                caption=caption or "",
                thumbnail=Path(thumbnail_path) if thumbnail_path and os.path.exists(thumbnail_path) else None,
            )

            logger.info(f"Reels успешно опубликован: {media.pk}")
            return True, media.pk
        except Exception as e:
            logger.error(f"Ошибка при публикации Reels: {e}")
            return False, str(e)

    def hide_reel_from_feed(self, media_id):
        """Удаляет рилс из основной сетки профиля"""
        try:
            # Используем прямой API-запрос через клиент
            endpoint = f"media/{media_id}/configure_to_clips/"
            params = {
                "remove_from_profile_grid": "1",
                "clips_uses_original_audio": "1"
            }

            result = self.instagram.client._request(endpoint, params=params, method="POST")
            logger.info(f"Рилс {media_id} удален из основной сетки")
            return True, "Рилс удален из основной сетки"
        except Exception as e:
            logger.error(f"Ошибка при удалении рилса из основной сетки: {e}")
            return False, str(e)

    def execute_reel_task(self, task):
        """Выполнение задачи по публикации Reels"""
        try:
            # Обновляем статус задачи
            update_task_status(task.id, 'processing')

            # Получаем параметр hide_from_feed из дополнительных данных задачи
            hide_from_feed = False
            if hasattr(task, 'options') and task.options:
                try:
                    options = json.loads(task.options)
                    hide_from_feed = options.get('hide_from_feed', False)
                except Exception as e:
                    logger.warning(f"Не удалось разобрать options для задачи {task.id}: {e}")
            elif hasattr(task, 'additional_data') and task.additional_data:
                try:
                    additional_data = json.loads(task.additional_data)
                    hide_from_feed = additional_data.get('hide_from_feed', False)
                except Exception as e:
                    logger.warning(f"Не удалось разобрать additional_data для задачи {task.id}: {e}")

            # Публикуем Reels
            success, result = self.publish_reel(
                task.media_path,
                task.caption,
                hide_from_feed=hide_from_feed
            )

            if success:
                update_task_status(task.id, 'completed')
                logger.info(f"Задача {task.id} по публикации Reels выполнена успешно")
                return True, None
            else:
                update_task_status(task.id, 'failed', error_message=result)
                logger.error(f"Задача {task.id} по публикации Reels не выполнена: {result}")
                return False, result
        except Exception as e:
            update_task_status(task.id, 'failed', error_message=str(e))
            logger.error(f"Ошибка при выполнении задачи {task.id} по публикации Reels: {e}")
            return False, str(e)

def publish_reels_in_parallel(video_path, caption, account_ids, hide_from_feed=False):
    """Публикация Reels в несколько аккаунтов параллельно"""
    results = {}

    def publish_to_account(account_id):
        manager = ReelsManager(account_id)
        success, result = manager.publish_reel(video_path, caption, hide_from_feed=hide_from_feed)
        return account_id, success, result

    # Используем ThreadPoolExecutor для параллельной публикации
    with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = [executor.submit(publish_to_account, account_id) for account_id in account_ids]

        for future in concurrent.futures.as_completed(futures):
            try:
                account_id, success, result = future.result()
                results[account_id] = {'success': success, 'result': result}
            except Exception as e:
                logger.error(f"Ошибка при параллельной публикации: {e}")

    return results