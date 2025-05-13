try:
    import moviepy.editor as mp
    print("moviepy.editor успешно импортирован.")

    # Создаем простой цветной клип
    clip = mp.ColorClip(size=(320, 240), color=(255, 0, 0), duration=1)

    # Выводим информацию о клипе
    print(f"Создан клип: размер={clip.size}, длительность={clip.duration}с")

    print("moviepy.editor работает корректно!")
except ImportError as e:
    print(f"Ошибка импорта: {e}")
except Exception as e:
    print(f"Ошибка при тестировании moviepy.editor: {e}")