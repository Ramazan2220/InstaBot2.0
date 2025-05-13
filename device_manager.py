"""
Модуль для управления устройствами
"""
import random
import logging
import hashlib
import os
import json

logger = logging.getLogger(__name__)

# Список производителей и моделей устройств
MANUFACTURERS = {
    "samsung": [
        "SM-G991B",  # Galaxy S21
        "SM-G998B",  # Galaxy S21 Ultra
        "SM-S908B",  # Galaxy S22 Ultra
        "SM-A526B",  # Galaxy A52 5G
        "SM-A505F",  # Galaxy A50
        "SM-N975F",  # Galaxy Note 10+
        "SM-G973F",  # Galaxy S10
        "SM-G781B",  # Galaxy S20 FE
        "SM-A715F",  # Galaxy A71
        "SM-G980F",  # Galaxy S20
    ],
    "xiaomi": [
        "Mi 10T",
        "Mi 11",
        "POCO X3",
        "Redmi Note 10 Pro",
        "Redmi 9",
        "Mi 10 Pro",
        "Redmi Note 9",
        "POCO F3",
    ],
    "google": [
        "Pixel 6",
        "Pixel 7",
        "Pixel 5",
        "Pixel 4a",
        "Pixel 4 XL",
    ],
    "oneplus": [
        "9 Pro",
        "8T",
        "Nord",
        "8 Pro",
        "9",
        "7T",
    ],
    "oppo": [
        "Find X3 Pro",
        "Reno 6 Pro",
        "A74",
        "A54",
        "Find X2",
    ],
}

# Версии Android
ANDROID_VERSIONS = [
    ("10", "10"),
    ("10.0", "10.0"),
    ("11", "11"),
    ("11.0", "11.0"),
    ("12", "12"),
    ("12.0.1", "12.0.1"),
    ("13", "13"),
    ("13.0", "13.0"),
]

# Разрешения экрана
RESOLUTIONS = [
    "1080x2400",
    "1080x2340",
    "1440x3200",
    "1080x2160",
    "1080x2280",
]

# DPI
DPIS = [
    "420dpi",
    "440dpi",
    "480dpi",
    "560dpi",
    "400dpi",
]

def generate_device_settings(account_id):
    """
    Генерирует уникальные настройки устройства для аккаунта

    Args:
        account_id (int): ID аккаунта

    Returns:
        dict: Настройки устройства
    """
    # Используем account_id как seed для генерации устройства
    random.seed(account_id)

    # Выбираем производителя и модель
    manufacturer = random.choice(list(MANUFACTURERS.keys()))
    model = random.choice(MANUFACTURERS[manufacturer])
    device_name = f"{manufacturer} {model}"

    # Выбираем версию Android
    android_version, android_release = random.choice(ANDROID_VERSIONS)

    # Выбираем разрешение и DPI
    resolution = random.choice(RESOLUTIONS)
    dpi = random.choice(DPIS)

    # Генерация уникальных идентификаторов на основе account_id
    seed = f"account_{account_id}"
    device_id = f"android-{hashlib.md5(f'{seed}_device'.encode()).hexdigest()[:16]}"
    phone_id = f"{hashlib.md5(f'{seed}_phone'.encode()).hexdigest()}-{hashlib.md5(f'{seed}_phone2'.encode()).hexdigest()}"
    uuid_value = f"{hashlib.md5(f'{seed}_uuid'.encode()).hexdigest()[:8]}-{hashlib.md5(f'{seed}_uuid2'.encode()).hexdigest()[:4]}-{hashlib.md5(f'{seed}_uuid3'.encode()).hexdigest()[:4]}-{hashlib.md5(f'{seed}_uuid4'.encode()).hexdigest()[:4]}-{hashlib.md5(f'{seed}_uuid5'.encode()).hexdigest()[:12]}"

    # Формируем user_agent
    user_agent = f"Instagram 269.0.0.18.75 Android ({android_version}/{android_release}; {dpi}; {resolution}; {manufacturer}; {model}; {model.lower().replace(' ', '-')}; qcom)"

    # Создаем настройки устройства
    settings = {
        "app_version": "269.0.0.18.75",
        "android_version": android_version,
        "android_release": android_release,
        "dpi": dpi,
        "resolution": resolution,
        "manufacturer": manufacturer,
        "device": model,
        "model": model,
        "cpu": "qcom",
        "version_code": "365203812",
        "user_agent": user_agent,
        "device_id": device_id,
        "phone_id": phone_id,
        "uuid": uuid_value,
        "device_name": device_name,
    }

    # Сохраняем настройки в файл
    save_device_settings(account_id, settings)

    logger.info(f"Сгенерированы настройки устройства для аккаунта {account_id}: {device_name}")

    return settings

def save_device_settings(account_id, settings, directory="devices"):
    """
    Сохраняет настройки устройства в файл

    Args:
        account_id (int): ID аккаунта
        settings (dict): Настройки устройства
        directory (str): Директория для сохранения
    """
    # Создаем директорию, если она не существует
    os.makedirs(directory, exist_ok=True)

    # Путь к файлу
    file_path = os.path.join(directory, f"device_{account_id}.json")

    # Сохраняем настройки в файл
    with open(file_path, 'w') as f:
        json.dump(settings, f, indent=4)

def load_device_settings(account_id, directory="devices"):
    """
    Загружает настройки устройства из файла

    Args:
        account_id (int): ID аккаунта
        directory (str): Директория с сохраненными настройками

    Returns:
        dict: Настройки устройства или None, если файл не найден
    """
    # Путь к файлу
    file_path = os.path.join(directory, f"device_{account_id}.json")

    # Проверяем существование файла
    if not os.path.exists(file_path):
        return None

    # Загружаем настройки из файла
    with open(file_path, 'r') as f:
        settings = json.load(f)

    return settings

def get_or_create_device_settings(account_id, directory="devices"):
    """
    Получает существующие настройки устройства или создает новые

    Args:
        account_id (int): ID аккаунта
        directory (str): Директория с сохраненными настройками

    Returns:
        dict: Настройки устройства
    """
    # Пытаемся загрузить существующие настройки
    settings = load_device_settings(account_id, directory)

    # Если настройки не найдены, генерируем новые
    if settings is None:
        settings = generate_device_settings(account_id)

    return settings