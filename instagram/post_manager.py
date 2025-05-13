import logging
import os
from pathlib import Path

from instagram.client import InstagramClient
from database.db_manager import update_task_status
from utils.image_splitter import split_image_for_mosaic

logger = logging.getLogger(__name__)

class PostManager:
    def __init__(self, account_id):
        self.instagram = InstagramClient(account_id)

    def publish_photo(self, photo_path, caption=None):
        """Публикация одиночного фото"""
        try:
            # Проверяем статус входа
            if not self.instagram.check_login():
                logger.error(f"Не удалось войти в аккаунт для публикации фото")
                return False, "Ошибка входа в аккаунт"

            # Проверяем существование файла
            if not os.path.exists(photo_path):
                logger.error(f"Файл {photo_path} не найден")
                return False, f"Файл не найден: {photo_path}"

            # Публикуем фото
            media = self.instagram.client.photo_upload(
                Path(photo_path),
                caption=caption or ""
            )

            logger.info(f"Фото успешно опубликовано: {media.pk}")
            return True, media.pk
        except Exception as e:
            logger.error(f"Ошибка при публикации фото: {e}")
            return False, str(e)

    def publish_carousel(self, photo_paths, caption=None):
        """Публикация карусели из нескольких фото"""
        try:
            # Проверяем статус входа
            if not self.instagram.check_login():
                logger.error(f"Не удалось войти в аккаунт для публикации карусели")
                return False, "Ошибка входа в аккаунт"

            # Проверяем существование файлов
            paths = [Path(path) for path in photo_paths if os.path.exists(path)]
            if not paths:
                logger.error(f"Не найдено ни одного файла для публикации")
                return False, "Не найдено ни одного файла для публикации"

            # Публикуем карусель
            media = self.instagram.client.album_upload(
                paths,
                caption=caption or ""
            )

            logger.info(f"Карусель успешно опубликована: {media.pk}")
            return True, media.pk
        except Exception as e:
            logger.error(f"Ошибка при публикации карусели: {e}")
            return False, str(e)

    def publish_mosaic(self, image_path, caption=None):
        """Публикация мозаики из 6 частей"""
        try:
            # Проверяем статус входа
            if not self.instagram.check_login():
                logger.error(f"Не удалось войти в аккаунт для публикации мозаики")
                return False, "Ошибка входа в аккаунт"

            # Проверяем существование файла
            if not os.path.exists(image_path):
                logger.error(f"Файл {image_path} не найден")
                return False, f"Файл не найден: {image_path}"

            # Разделяем изображение на 6 частей
            split_images = split_image_for_mosaic(image_path)
            if not split_images:
                logger.error(f"Не удалось разделить изображение на части")
                return False, "Не удалось разделить изображение на части"

            # Публикуем части в обратном порядке (чтобы в профиле они отображались правильно)
            for i, img_path in enumerate(reversed(split_images)):
                # Для первой публикации используем указанное описание, для остальных - пустое
                part_caption = caption if i == 0 else ""

                success, result = self.publish_photo(img_path, part_caption)
                if not success:
                    logger.error(f"Ошибка при публикации части {i+1} мозаики: {result}")
                    return False, f"Ошибка при публикации части {i+1} мозаики: {result}"

                # Небольшая пауза между публикациями
                import time
                time.sleep(5)

            logger.info(f"Мозаика успешно опубликована")
            return True, None
        except Exception as e:
            logger.error(f"Ошибка при публикации мозаики: {e}")
            return False, str(e)

    def execute_post_task(self, task):
        """Выполнение задачи по публикации поста"""
        try:
            # Обновляем статус задачи
            update_task_status(task.id, 'processing')

            # Определяем тип задачи и выполняем соответствующее действие
            if task.task_type == 'post':
                success, result = self.publish_photo(task.media_path, task.caption)
            elif task.task_type == 'mosaic':
                success, result = self.publish_mosaic(task.media_path, task.caption)
            else:
                logger.error(f"Неизвестный тип задачи: {task.task_type}")
                update_task_status(task.id, 'failed', error_message=f"Неизвестный тип задачи: {task.task_type}")
                return False, f"Неизвестный тип задачи: {task.task_type}"

            if success:
                update_task_status(task.id, 'completed')
                logger.info(f"Задача {task.id} по публикации {task.task_type} выполнена успешно")
                return True, None
            else:
                update_task_status(task.id, 'failed', error_message=result)
                logger.error(f"Задача {task.id} по публикации {task.task_type} не выполнена: {result}")
                return False, result
        except Exception as e:
            update_task_status(task.id, 'failed', error_message=str(e))
            logger.error(f"Ошибка при выполнении задачи {task.id} по публикации {task.task_type}: {e}")
            return False, str(e)