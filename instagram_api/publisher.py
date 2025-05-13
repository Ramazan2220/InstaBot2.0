import os
import logging
import json
import tempfile
from datetime import datetime

from instagrapi import Client
from moviepy import editor as moviepy_editor
VideoFileClip = moviepy_editor.VideoFileClip

from config import ACCOUNTS_DIR
from database.db_manager import get_session, get_instagram_account, update_publish_task_status, get_publish_task
from database.models import PublishTask, TaskStatus
from instagram.reels_manager import ReelsManager

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

    # Настраиваем обработчик кода подтверждения, если у аккаунта есть email и email_password
    if hasattr(account, 'email') and hasattr(account, 'email_password') and account.email and account.email_password:
        # Импортируем функцию получения кода из почты
        from instagram.email_utils import get_verification_code_from_email

        # Определяем функцию-обработчик для получения кода
        def auto_challenge_code_handler(username, choice):
            print(f"[DEBUG] Запрошен код подтверждения для {username}, тип: {choice}")
            # Пытаемся получить код из почты
            verification_code = get_verification_code_from_email(
                account.email,
                account.email_password,
                max_attempts=5,
                delay_between_attempts=10
            )
            if verification_code:
                print(f"[DEBUG] Получен код подтверждения из почты: {verification_code}")
                return verification_code
            else:
                print(f"[DEBUG] Не удалось получить код из почты, запрашиваем через консоль")
                # Если не удалось получить код из почты, запрашиваем через консоль
                return input(f"Enter code (6 digits) for {username} ({choice}): ")

        # Устанавливаем обработчик
        client.challenge_code_handler = auto_challenge_code_handler
        logger.info(f"Настроен автоматический обработчик кода подтверждения для {account.username}")

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
    try:
        # Получаем задачу
        task = get_publish_task(task_id)
        if not task:
            logger.error(f"Задача {task_id} не найдена")
            return False, "Задача не найдена"

        # Получаем аккаунт
        account = get_instagram_account(task.account_id)
        if not account:
            logger.error(f"Аккаунт {task.account_id} не найден")
            update_publish_task_status(task_id, TaskStatus.FAILED, "Аккаунт не найден")
            return False, "Аккаунт не найден"

        # Получаем дополнительные данные
        additional_data = {}
        if hasattr(task, 'options') and task.options:
            try:
                additional_data = json.loads(task.options)
            except:
                logger.warning(f"Не удалось разобрать options для задачи {task_id}")
        elif hasattr(task, 'additional_data') and task.additional_data:
            try:
                additional_data = json.loads(task.additional_data)
            except:
                logger.warning(f"Не удалось разобрать additional_data для задачи {task_id}")

        hide_from_feed = additional_data.get('hide_from_feed', False)

        # Получаем клиент Instagram
        client, error = get_instagram_client(account.id)
        if not client:
            logger.error(f"Не удалось создать клиент Instagram для аккаунта {account.username}: {error}")
            update_publish_task_status(task_id, TaskStatus.FAILED, f"Ошибка создания клиента Instagram: {error}")
            return False, f"Ошибка создания клиента Instagram: {error}"

        # Проверяем существование файла
        if not os.path.exists(task.media_path):
            logger.error(f"Файл {task.media_path} не найден")
            update_publish_task_status(task_id, TaskStatus.FAILED, f"Файл не найден: {task.media_path}")
            return False, f"Файл не найден: {task.media_path}"

        # Публикуем видео
        reels_manager = ReelsManager(account.id)
        success, result = reels_manager.publish_reel(
            task.media_path,
            task.caption,
            hide_from_feed=hide_from_feed
        )

        if success:
            update_publish_task_status(task_id, TaskStatus.COMPLETED, media_id=result)
            logger.info(f"Видео успешно опубликовано: {result}")
            return True, result
        else:
            update_publish_task_status(task_id, TaskStatus.FAILED, error_message=result)
            logger.error(f"Ошибка при публикации видео: {result}")
            return False, result

    except Exception as e:
        logger.error(f"Ошибка при публикации видео: {e}")
        update_publish_task_status(task_id, TaskStatus.FAILED, error_message=str(e))
        return False, str(e)