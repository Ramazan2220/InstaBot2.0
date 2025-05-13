"""
Простой тест для проверки работы moviepy
"""
try:
    import moviepy
    print(f"moviepy успешно импортирован.")

    # Выведем доступные модули
    print("Доступные модули в moviepy:")
    for module in dir(moviepy):
        if not module.startswith('__'):
            print(f"- {module}")

    # Попробуем импортировать основные компоненты
    try:
        from moviepy.video.io.VideoFileClip import VideoFileClip
        print("VideoFileClip успешно импортирован.")
    except ImportError as e:
        print(f"Ошибка импорта VideoFileClip: {e}")

    try:
        from moviepy.video.VideoClip import ColorClip
        print("ColorClip успешно импортирован.")
    except ImportError as e:
        print(f"Ошибка импорта ColorClip: {e}")

    print("Тест moviepy завершен.")
except ImportError as e:
    print(f"Ошибка импорта: {e}")
except Exception as e:
    print(f"Ошибка при тестировании moviepy: {e}")