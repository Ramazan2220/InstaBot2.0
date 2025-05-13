import os
import logging
import tempfile
from pathlib import Path
from PIL import Image

logger = logging.getLogger(__name__)

def optimize_image_for_instagram(image_path, max_size=(1080, 1350), quality=95):
    """
    Оптимизирует изображение для публикации в Instagram

    Args:
        image_path: Путь к исходному изображению
        max_size: Максимальный размер (ширина, высота)
        quality: Качество сжатия JPEG (1-100)

    Returns:
        str: Путь к оптимизированному изображению
    """
    try:
        # Открываем изображение
        img = Image.open(image_path)

        # Проверяем формат
        if img.format not in ['JPEG', 'PNG']:
            logger.warning(f"Изображение {image_path} имеет формат {img.format}, конвертируем в JPEG")
            img = img.convert('RGB')

        # Изменяем размер, сохраняя пропорции
        img.thumbnail(max_size, Image.LANCZOS)

        # Создаем временный файл для оптимизированного изображения
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.jpg')
        temp_path = temp_file.name
        temp_file.close()

        # Сохраняем оптимизированное изображение
        img.save(temp_path, format='JPEG', quality=quality, optimize=True)

        logger.info(f"Изображение оптимизировано: {os.path.basename(image_path)} -> {os.path.basename(temp_path)}")
        return temp_path

    except Exception as e:
        logger.error(f"Ошибка при оптимизации изображения {image_path}: {e}")
        return image_path  # Возвращаем исходный путь в случае ошибки

def validate_video_for_reels(video_path):
    """
    Проверяет, соответствует ли видео требованиям Instagram Reels

    Args:
        video_path: Путь к видеофайлу

    Returns:
        tuple: (bool, str) - (соответствует ли требованиям, сообщение)
    """
    try:
        # Здесь должна быть проверка видео с использованием ffmpeg или другой библиотеки
        # Для полной реализации потребуется дополнительная библиотека, например, moviepy

        # Проверяем существование файла
        if not os.path.exists(video_path):
            return False, f"Файл не найден: {video_path}"

        # Проверяем расширение файла
        valid_extensions = ['.mp4', '.mov']
        if not any(video_path.lower().endswith(ext) for ext in valid_extensions):
            return False, f"Неподдерживаемый формат видео. Используйте MP4 или MOV."

        # Проверяем размер файла (Instagram ограничивает размер до 4 ГБ)
        max_size_bytes = 4 * 1024 * 1024 * 1024  # 4 ГБ
        file_size = os.path.getsize(video_path)
        if file_size > max_size_bytes:
            return False, f"Размер видео превышает 4 ГБ"

        # Для полной проверки длительности, разрешения и других параметров
        # требуется использование дополнительных библиотек

        return True, "Видео соответствует требованиям"

    except Exception as e:
        logger.error(f"Ошибка при проверке видео {video_path}: {e}")
        return False, f"Ошибка при проверке видео: {e}"

def get_media_type(file_path):
    """
    Определяет тип медиафайла по расширению

    Args:
        file_path: Путь к файлу

    Returns:
        str: 'image', 'video' или 'unknown'
    """
    image_extensions = ['.jpg', '.jpeg', '.png']
    video_extensions = ['.mp4', '.mov']

    file_path = file_path.lower()

    if any(file_path.endswith(ext) for ext in image_extensions):
        return 'image'
    elif any(file_path.endswith(ext) for ext in video_extensions):
        return 'video'
    else:
        return 'unknown'