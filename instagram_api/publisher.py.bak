import os
import logging
import tempfile
from datetime import datetime

from instagrapi import Client
import moviepy.editor
VideoFileClip = moviepy.editor.VideoFileClip

from config import ACCOUNTS_DIR
from database.db_manager import get_session, get_instagram_account, update_publish_task_status
from database.models import PublishTask, TaskStatus

logger = logging.getLogger(__name__)

def get_instagram_client(account_id):
    """Получает клиент Instagram для указанного аккаунта"""
    session = get_session()
    account = get_instagram_account(account_id)

    if not account:
        logger.error(f"Аккаунт с ID {account_id} не найден")
        return None, "Аккаунт не найден"

    client = Client()

    # Проверяем наличие сессии
    session_file = os.path.join(ACCOUNTS_DIR, str(account_id), 'session.json')
    if os.path.exists(session_file):
        try:
            client.load_settings(session_file)
            logger.info(f"Загружены настройки для аккаунта {account.username}")
        except Exception as e:
            logger.error(f"Ошибка при загрузке настроек: {e}")

    # Выполняем вход
    try:
        client.login(account.username, account.password)
        logger.info(f"Успешный вход в аккаунт {account.username}")

        # Сохраняем сессию
        os.makedirs(os.path.join(ACCOUNTS_DIR, str(account_id)), exist_ok=True)
        client.dump_settings(session_file)

        return client, None
    except Exception as e:
        logger.error(f"Ошибка при входе в аккаунт {account.username}: {e}")
        return None, str(e)

def process_video(video_path):
    """Обрабатывает видео перед публикацией"""
    try:
        # Создаем временный файл для обработанного видео
        with tempfile.NamedTemporaryFile(delete=False, suffix='.mp4') as temp_file:
            processed_path = temp_file.name

        # Загружаем видео
        video = VideoFileClip(video_path)

        # Проверяем соотношение сторон
        width, height = video.size
        aspect_ratio = width / height

        # Для Reels рекомендуется соотношение 9:16
        target_ratio = 9/16

        # Если соотношение сторон не соответствует требуемому, обрезаем видео
        if abs(aspect_ratio - target_ratio) > 0.1:
            logger.info(f"Обрезаем видео с соотношением {aspect_ratio} до {target_ratio}")

            if aspect_ratio > target_ratio:
                # Видео слишком широкое, обрезаем по ширине
                new_width = int(height * target_ratio)
                x_center = width / 2
                video = video.crop(x1=x_center - new_width/2, y1=0, x2=x_center + new_width/2, y2=height)
            else:
                # Видео слишком высокое, обрезаем по высоте
                new_height = int(width / target_ratio)
                y_center = height / 2
                video = video.crop(x1=0, y1=y_center - new_height/2, x2=width, y2=y_center + new_height/2)

        # Проверяем длительность
        if video.duration > 90:
            logger.info(f"Обрезаем видео с длительностью {video.duration} до 90 секунд")
            video = video.subclip(0, 90)

        # Сохраняем обработанное видео
        video.write_videofile(processed_path, codec='libx264', audio_codec='aac')
        video.close()

        return processed_path, None
    except Exception as e:
        logger.error(f"Ошибка при обработке видео: {e}")
        return None, str(e)

def publish_video(task_id):
    """Публикует видео в Instagram"""
    session = get_session()
    task = session.query(PublishTask).filter_by(id=task_id).first()

    if not task:
        logger.error(f"Задача с ID {task_id} не найдена")
        return False, "Задача не найдена"

    # Обновляем статус задачи
    update_publish_task_status(task_id, TaskStatus.PROCESSING)

    # Получаем клиент Instagram
    client, error = get_instagram_client(task.account_id)
    if error:
        update_publish_task_status(task_id, TaskStatus.FAILED, error)
        return False, error

    try:
        # Обрабатываем видео
        processed_path, error = process_video(task.media_path)
        if error:
            update_publish_task_status(task_id, TaskStatus.FAILED, error)
            return False, error

        # Публикуем видео как Reels
        # Удаляем параметры mentions и locations, которые вызывают ошибку
        result = client.clip_upload(
            processed_path,
            task.caption,
            thumbnail=None,
            configure_timeout=120
        )

        # Обновляем статус задачи
        update_publish_task_status(task_id, TaskStatus.COMPLETED, media_id=result.id)

        # Удаляем временные файлы
        try:
            os.remove(processed_path)
        except:
            pass

        logger.info(f"Видео успешно опубликовано, ID: {result.id}")
        return True, result.id
    except Exception as e:
        error_message = str(e)
        logger.error(f"Ошибка при публикации видео: {error_message}")
        update_publish_task_status(task_id, TaskStatus.FAILED, error_message)
        return False, error_message