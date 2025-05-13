import logging
import os
from PIL import Image
import uuid
from pathlib import Path

from config import MEDIA_DIR

logger = logging.getLogger(__name__)

def split_image_for_mosaic(image_path, rows=2, cols=3):
    """
    Разделяет изображение на части для мозаики в Instagram
    По умолчанию делит на 6 частей (2 ряда по 3 колонки)
    """
    try:
        # Открываем изображение
        img = Image.open(image_path)

        # Получаем размеры изображения
        width, height = img.size

        # Вычисляем размеры каждой части
        part_width = width // cols
        part_height = height // rows

        # Создаем директорию для частей, если её нет
        output_dir = Path(MEDIA_DIR) / "mosaic_parts"
        os.makedirs(output_dir, exist_ok=True)

        # Генерируем уникальный идентификатор для этого набора частей
        unique_id = uuid.uuid4().hex[:8]

        # Список путей к созданным частям
        part_paths = []

        # Разрезаем изображение на части
        for row in range(rows):
            for col in range(cols):
                # Вычисляем координаты для вырезания части
                left = col * part_width
                upper = row * part_height
                right = left + part_width
                lower = upper + part_height

                # Вырезаем часть
                part = img.crop((left, upper, right, lower))

                # Сохраняем часть
                part_filename = f"mosaic_{unique_id}_r{row}_c{col}.jpg"
                part_path = output_dir / part_filename
                part.save(part_path, quality=95)

                # Добавляем путь в список
                part_paths.append(str(part_path))

                logger.info(f"Создана часть мозаики: {part_path}")

        return part_paths
    except Exception as e:
        logger.error(f"Ошибка при разделении изображения на части: {e}")
        return []

def optimize_image(image_path, max_size_kb=1024):
    """
    Оптимизирует изображение для загрузки в Instagram
    """
    try:
        # Открываем изображение
        img = Image.open(image_path)

        # Сохраняем оригинальный формат
        img_format = img.format

        # Создаем путь для оптимизированного изображения
        filename = os.path.basename(image_path)
        output_dir = Path(MEDIA_DIR) / "optimized"
        os.makedirs(output_dir, exist_ok=True)
        optimized_path = output_dir / f"opt_{filename}"

        # Начальное качество
        quality = 95

        # Сохраняем с постепенным уменьшением качества, пока не достигнем нужного размера
        while quality > 30:  # Минимальное качество 30%
            img.save(optimized_path, format=img_format, quality=quality)

            # Проверяем размер файла
            file_size_kb = os.path.getsize(optimized_path) / 1024

            if file_size_kb <= max_size_kb:
                logger.info(f"Изображение оптимизировано: {optimized_path} ({file_size_kb:.2f} KB, качество {quality}%)")
                return str(optimized_path)

            # Уменьшаем качество
            quality -= 5

        # Если не удалось достичь нужного размера, пробуем изменить размер изображения
        width, height = img.size
        ratio = 0.9  # Уменьшаем на 10%

        while ratio > 0.5:  # Минимальный размер 50% от оригинала
            new_width = int(width * ratio)
            new_height = int(height * ratio)
            resized_img = img.resize((new_width, new_height), Image.LANCZOS)

            resized_img.save(optimized_path, format=img_format, quality=80)

            # Проверяем размер файла
            file_size_kb = os.path.getsize(optimized_path) / 1024

            if file_size_kb <= max_size_kb:
                logger.info(f"Изображение изменено и оптимизировано: {optimized_path} ({file_size_kb:.2f} KB, {new_width}x{new_height})")
                return str(optimized_path)

            # Уменьшаем размер
            ratio -= 0.1

        logger.warning(f"Не удалось оптимизировать изображение до {max_size_kb} KB: {image_path}")
        return image_path
    except Exception as e:
        logger.error(f"Ошибка при оптимизации изображения: {e}")
        return image_path