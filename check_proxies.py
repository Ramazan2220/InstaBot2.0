import logging
from database.db_manager import get_session
from database.models import InstagramAccount, Proxy

# Настраиваем логирование
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def check_account_proxies():
    """Проверяет, прикреплены ли прокси ко всем аккаунтам"""
    session = get_session()
    try:
        # Получаем все аккаунты
        accounts = session.query(InstagramAccount).all()
        
        logger.info(f"Всего аккаунтов: {len(accounts)}")
        
        # Счетчики
        accounts_with_proxy = 0
        accounts_without_proxy = 0
        
        # Выводим информацию о каждом аккаунте и его прокси
        for account in accounts:
            logger.info(f"Аккаунт ID: {account.id}")
            logger.info(f"Имя пользователя: {account.username}")
            logger.info(f"Email: {account.email}")
            logger.info(f"Активен: {'Да' if account.is_active else 'Нет'}")
            
            if account.proxy_id:
                proxy = session.query(Proxy).filter_by(id=account.proxy_id).first()
                if proxy:
                    logger.info(f"Прокси: {proxy.protocol}://{proxy.host}:{proxy.port}")
                    logger.info(f"Прокси активен: {'Да' if proxy.is_active else 'Нет'}")
                    accounts_with_proxy += 1
                else:
                    logger.warning(f"Прокси ID {account.proxy_id} указан, но прокси не найден в базе данных")
                    accounts_without_proxy += 1
            else:
                logger.warning(f"Прокси не назначен для аккаунта {account.username}")
                accounts_without_proxy += 1
            
            logger.info("-" * 50)
        
        # Выводим статистику
        logger.info(f"Аккаунтов с прокси: {accounts_with_proxy}")
        logger.info(f"Аккаунтов без прокси: {accounts_without_proxy}")
        
    except Exception as e:
        logger.error(f"Ошибка при проверке прокси: {str(e)}")
    finally:
        session.close()

if __name__ == "__main__":
    check_account_proxies()