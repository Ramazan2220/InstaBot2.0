# test_publisher_import.py
try:
    import sys
    print(f"Python version: {sys.version}")
    print(f"Python executable: {sys.executable}")

    print("\nПроверка импорта moviepy...")
    import moviepy
    print(f"moviepy успешно импортирован. Версия: {moviepy.__version__}")

    print("\nПроверка импорта publisher...")
    from instagram_api.publisher import publish_video
    print("publish_video успешно импортирован")
except Exception as e:
    print(f"Ошибка: {e}")