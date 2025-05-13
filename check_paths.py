import sys
import os

# Выводим информацию о Python
print(f"Python version: {sys.version}")
print(f"Python executable: {sys.executable}")

# Выводим пути поиска модулей
print("\nPython search paths:")
for i, path in enumerate(sys.path):
    print(f"{i}: {path}")
print(sys.path)
# Проверяем наличие модулей в путях поиска
print("\nПроверка наличия модулей в путях поиска:")
for path in sys.path:
    if os.path.exists(os.path.join(path, 'sqlalchemy')):
        print(f"SQLAlchemy найден в: {path}")
    if os.path.exists(os.path.join(path, 'PIL')):
        print(f"PIL найден в: {path}")
    if os.path.exists(os.path.join(path, 'instagrapi')):
        print(f"instagrapi найден в: {path}")
    if os.path.exists(os.path.join(path, 'moviepy')):
        print(f"moviepy найден в: {path}")