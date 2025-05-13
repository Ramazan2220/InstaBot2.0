"""
Тест для проверки работы moviepy
"""
try:
    import moviepy
    print(f"moviepy успешно импортирован.")

    # Проверяем доступность основных модулей
    import moviepy.editor
    print("moviepy.editor успешно импортирован.")

    # Проверяем доступность ffmpeg
    try:
        import subprocess
        result = subprocess.run(['ffmpeg', '-version'], capture_output=True, text=True)
        if result.returncode == 0:
            print("ffmpeg доступен и работает корректно.")
        else:
            print("ffmpeg недоступен или не работает корректно.")
    except Exception as e:
        print(f"Ошибка при проверке ffmpeg: {e}")

    print("moviepy работает корректно!")
except ImportError as e:
    print(f"Ошибка импорта: {e}")
except Exception as e:
    print(f"Ошибка при тестировании moviepy: {e}")