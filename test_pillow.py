"""
Тест для проверки работы Pillow
"""
try:
    from PIL import Image, ImageDraw, ImageFont
    import PIL

    print(f"Pillow успешно импортирован. Версия: {PIL.__version__}")

    # Создаем тестовое изображение
    img = Image.new('RGB', (100, 100), color='red')
    draw = ImageDraw.Draw(img)
    draw.rectangle([(10, 10), (90, 90)], fill='blue')

    # Сохраняем во временный файл
    import tempfile
    temp_file = tempfile.NamedTemporaryFile(suffix='.jpg', delete=False)
    img.save(temp_file.name)

    print(f"Тестовое изображение сохранено в {temp_file.name}")
    print("Pillow работает корректно!")
except ImportError as e:
    print(f"Ошибка импорта: {e}")
except Exception as e:
    print(f"Ошибка при тестировании Pillow: {e}")