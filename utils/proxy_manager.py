import logging
import requests
import datetime
import concurrent.futures
import re
import random  # Добавлен импорт для random.choice
from sqlalchemy.sql import func  # Добавлен импорт для func.count
from database.db_manager import get_proxies, update_proxy, get_instagram_accounts, update_instagram_account, get_session
from database.models import Proxy, InstagramAccount  # Добавлены модели
from config import MAX_WORKERS

logger = logging.getLogger(__name__)

def check_proxy(proxy_id, proxy_url):
    """
    Проверка работоспособности прокси

    Args:
        proxy_id: ID прокси в базе данных (может быть None для новых прокси)
        proxy_url: URL прокси в формате protocol://[username:password@]host:port

    Returns:
        tuple: (proxy_id, is_working, error_message)
    """
    try:
        # Настраиваем прокси для запроса
        proxies = {
            'http': proxy_url,
            'https': proxy_url
        }

        # Делаем запрос к Google с таймаутом 10 секунд
        response = requests.get('https://www.google.com', proxies=proxies, timeout=10)

        # Если статус 200, прокси работает
        if response.status_code == 200:
            logger.info(f"Прокси {proxy_url} работает")
            return proxy_id, True, None
        else:
            logger.warning(f"Прокси {proxy_url} вернул статус {response.status_code}")
            return proxy_id, False, f"Статус {response.status_code}"
    except requests.exceptions.RequestException as e:
        logger.error(f"Ошибка при проверке прокси {proxy_url}: {e}")
        return proxy_id, False, str(e)

def check_all_proxies():
    """
    Проверка всех прокси в базе данных

    Returns:
        dict: Словарь с результатами проверки {proxy_id: {'working': bool, 'error': str}}
    """
    from database.db_manager import Session
    from database.models import Proxy

    session = Session()
    try:
        # Получаем все прокси
        proxies = get_proxies()
        results = {}

        # Проверяем прокси параллельно
        with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            futures = []
            for proxy in proxies:
                # Формируем URL прокси
                proxy_url = f"{proxy.protocol}://"
                if proxy.username and proxy.password:
                    proxy_url += f"{proxy.username}:{proxy.password}@"
                proxy_url += f"{proxy.host}:{proxy.port}"

                futures.append(executor.submit(check_proxy, proxy.id, proxy_url))

            for future in concurrent.futures.as_completed(futures):
                try:
                    proxy_id, is_working, error = future.result()

                    # Обновляем статус прокси в базе данных
                    proxy = session.query(Proxy).filter_by(id=proxy_id).first()
                    if proxy:
                        proxy.is_active = is_working
                        proxy.last_checked = datetime.datetime.utcnow()
                        session.commit()

                    results[proxy_id] = {'working': is_working, 'error': error}
                except Exception as e:
                    logger.error(f"Ошибка при обработке результата проверки прокси: {e}")

        return results
    except Exception as e:
        logger.error(f"Ошибка при проверке прокси: {e}")
        session.rollback()
        return {}
    finally:
        session.close()

def distribute_proxies():
    """
    Распределение прокси по аккаунтам Instagram

    Returns:
        tuple: (success, message)
    """
    try:
        # Получаем все активные прокси
        from database.db_manager import Session
        from database.models import Proxy

        session = Session()
        active_proxies = session.query(Proxy).filter_by(is_active=True).all()
        session.close()

        if not active_proxies:
            logger.warning("Нет активных прокси для распределения")
            return False, "Нет активных прокси"

        # Получаем все аккаунты
        accounts = get_instagram_accounts()

        if not accounts:
            logger.warning("Нет аккаунтов для назначения прокси")
            return False, "Нет аккаунтов"

        # Распределяем прокси циклически
        for i, account in enumerate(accounts):
            proxy = active_proxies[i % len(active_proxies)]
            update_instagram_account(account.id, proxy_id=proxy.id)
            logger.info(f"Аккаунту {account.username} назначен прокси {proxy.host}:{proxy.port}")

        return True, f"Прокси распределены между {len(accounts)} аккаунтами"
    except Exception as e:
        logger.error(f"Ошибка при распределении прокси: {e}")
        return False, str(e)

def parse_proxy_url(proxy_url):
    """
    Парсит URL прокси

    Args:
        proxy_url: URL прокси в формате protocol://[username:password@]host:port

    Returns:
        dict: Словарь с параметрами прокси или None в случае ошибки
    """
    try:
        # Проверяем формат URL
        if '://' not in proxy_url:
            return None

        protocol, rest = proxy_url.split('://', 1)

        if protocol not in ['http', 'socks5']:
            return None

        auth_part = None
        if '@' in rest:
            auth_part, rest = rest.split('@', 1)

        host, port = rest.split(':', 1)
        port = int(port)

        username = None
        password = None
        if auth_part:
            username, password = auth_part.split(':', 1)

        return {
            'protocol': protocol,
            'host': host,
            'port': port,
            'username': username,
            'password': password
        }
    except Exception as e:
        logger.error(f"Ошибка при парсинге URL прокси {proxy_url}: {e}")
        return None

def get_proxy_for_account(account_id):
    """
    Получает прокси, назначенный аккаунту

    Args:
        account_id (int): ID аккаунта

    Returns:
        tuple: (proxy_url, proxy_type) если прокси назначен, иначе None
    """
    session = get_session()

    try:
        # Получаем аккаунт с прокси
        account = session.query(InstagramAccount).filter_by(id=account_id).first()

        if not account or not account.proxy_id:
            return None

        # Получаем прокси
        proxy = session.query(Proxy).filter_by(id=account.proxy_id).first()

        if not proxy or not proxy.is_active:
            return None

        # Формируем URL прокси
        if proxy.username and proxy.password:
            proxy_url = f"{proxy.username}:{proxy.password}@{proxy.host}:{proxy.port}"
        else:
            proxy_url = f"{proxy.host}:{proxy.port}"

        return (proxy_url, proxy.type)
    except Exception as e:
        logger.error(f"Ошибка при получении прокси для аккаунта {account_id}: {str(e)}")
        return None
    finally:
        session.close()

def get_proxy_url(proxy_dict):
    """
    Формирует URL прокси из словаря с параметрами

    Args:
        proxy_dict: Словарь с параметрами прокси

    Returns:
        str: URL прокси в формате protocol://[username:password@]host:port
    """
    if not proxy_dict:
        return None

    proxy_url = f"{proxy_dict['protocol']}://"

    if proxy_dict['username'] and proxy_dict['password']:
        proxy_url += f"{proxy_dict['username']}:{proxy_dict['password']}@"

    proxy_url += f"{proxy_dict['host']}:{proxy_dict['port']}"

    return proxy_url

def assign_proxy_to_account(account_id):
    """
    Автоматически назначает наименее загруженный прокси для аккаунта.

    Args:
    account_id (int): ID аккаунта

    Returns:
    tuple: (success, message)
    - success (bool): True, если прокси успешно назначен
    - message (str): Сообщение о результате операции
    """
    session = get_session()
    try:
        # Проверяем наличие прокси в системе
        proxies_count = session.query(Proxy).filter_by(is_active=True).count()

        if proxies_count == 0:
            return False, "Нет доступных прокси. Пожалуйста, добавьте хотя бы один рабочий прокси перед добавлением аккаунта."

        # Если есть только один прокси, используем его
        if proxies_count == 1:
            proxy = session.query(Proxy).filter_by(is_active=True).first()

            # Назначаем прокси аккаунту
            account = session.query(InstagramAccount).filter_by(id=account_id).first()
            if not account:
                return False, f"Аккаунт с ID {account_id} не найден."

            account.proxy_id = proxy.id
            session.commit()

            return True, f"Прокси {proxy.host}:{proxy.port} успешно назначен аккаунту."

        # Если прокси больше одного, выбираем наименее загруженный
        # Получаем количество аккаунтов для каждого прокси
        proxy_load = session.query(
            Proxy.id,
            func.count(InstagramAccount.id).label('account_count')
        ).outerjoin(
            InstagramAccount,
            InstagramAccount.proxy_id == Proxy.id
        ).filter(
            Proxy.is_active == True
        ).group_by(
            Proxy.id
        ).all()

        # Если есть прокси без аккаунтов, выбираем первый из них
        empty_proxies = [p for p in proxy_load if p.account_count == 0]
        if empty_proxies:
            selected_proxy_id = empty_proxies[0].id
        else:
            # Находим прокси с минимальной нагрузкой
            min_load = min(proxy_load, key=lambda x: x.account_count)

            # Если есть несколько прокси с одинаковой минимальной нагрузкой, выбираем случайный
            min_load_proxies = [p.id for p in proxy_load if p.account_count == min_load.account_count]
            selected_proxy_id = random.choice(min_load_proxies)

        # Получаем выбранный прокси
        selected_proxy = session.query(Proxy).filter_by(id=selected_proxy_id).first()

        # Назначаем прокси аккаунту
        account = session.query(InstagramAccount).filter_by(id=account_id).first()
        if not account:
            return False, f"Аккаунт с ID {account_id} не найден."

        account.proxy_id = selected_proxy.id
        session.commit()

        return True, f"Прокси {selected_proxy.host}:{selected_proxy.port} успешно назначен аккаунту."

    except Exception as e:
        session.rollback()
        logger.error(f"Ошибка при назначении прокси аккаунту: {e}")
        return False, f"Ошибка при назначении прокси: {str(e)}"
    finally:
        session.close()

def auto_replace_failed_proxy(account_id, error_message):
    """
    Автоматически заменяет прокси, если текущий не работает

    Args:
    account_id (int): ID аккаунта
    error_message (str): Сообщение об ошибке

    Returns:
    tuple: (success, message)
    - success (bool): True, если прокси успешно заменен
    - message (str): Сообщение о результате операции
    """
    session = get_session()
    try:
        # Проверяем, связана ли ошибка с прокси
        proxy_related_errors = [
            "proxy error", "timeout", "connection refused",
            "no route to host", "proxy connection failed",
            "socks error", "network error", "connection error",
            "connect timeout", "read timeout", "connection aborted"
        ]

        is_proxy_error = any(err in error_message.lower() for err in proxy_related_errors)

        if not is_proxy_error:
            return False, "Ошибка не связана с прокси"

        # Получаем аккаунт
        account = session.query(InstagramAccount).filter_by(id=account_id).first()
        if not account:
            return False, f"Аккаунт с ID {account_id} не найден"

        # Если у аккаунта нет прокси, назначаем новый
        if not account.proxy_id:
            success, message = assign_proxy_to_account(account_id)
            return success, message

        # Отмечаем текущий прокси как неработающий
        current_proxy = session.query(Proxy).filter_by(id=account.proxy_id).first()
        if current_proxy:
            current_proxy.is_active = False
            current_proxy.last_check = datetime.datetime.now()
            logger.info(f"Прокси {current_proxy.host}:{current_proxy.port} отмечен как неработающий")

        # Проверяем наличие других рабочих прокси
        working_proxies_count = session.query(Proxy).filter_by(is_active=True).count()

        if working_proxies_count == 0:
            session.commit()
            return False, "Нет доступных рабочих прокси для замены"

        # Находим наименее загруженный прокси
        proxy_load = session.query(
            Proxy.id,
            func.count(InstagramAccount.id).label('account_count')
        ).outerjoin(
            InstagramAccount,
            InstagramAccount.proxy_id == Proxy.id
        ).filter(
            Proxy.is_active == True,
            Proxy.id != account.proxy_id  # Исключаем текущий прокси
        ).group_by(
            Proxy.id
        ).all()

        if not proxy_load:
            session.commit()
            return False, "Нет доступных рабочих прокси для замены"

        # Выбираем прокси с минимальной нагрузкой
        min_load = min(proxy_load, key=lambda x: x.account_count)

        # Если есть несколько прокси с одинаковой минимальной нагрузкой, выбираем случайный
        min_load_proxies = [p.id for p in proxy_load if p.account_count == min_load.account_count]
        new_proxy_id = random.choice(min_load_proxies)

        # Назначаем новый прокси аккаунту
        account.proxy_id = new_proxy_id
        session.commit()

        # Получаем информацию о новом прокси для сообщения
        new_proxy = session.query(Proxy).filter_by(id=new_proxy_id).first()

        return True, f"Прокси заменен на {new_proxy.host}:{new_proxy.port}"

    except Exception as e:
        session.rollback()
        logger.error(f"Ошибка при автоматической замене прокси: {e}")
        return False, f"Ошибка при замене прокси: {str(e)}"
    finally:
        session.close()