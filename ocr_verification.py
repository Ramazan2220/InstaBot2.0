import os
import re
import time
import threading
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from PIL import Image, ImageEnhance, ImageFilter
import pytesseract
import logging

# Настройка логирования
logger = logging.getLogger('ocr_verification')

class EmailServiceFactory:
    @staticmethod
    def get_service(email):
        domain = email.split('@')[1].lower()

        if domain == 'gmail.com':
            return GmailService()
        elif domain == 'yahoo.com':
            return YahooService()
        elif domain == 'outlook.com' or domain == 'hotmail.com':
            return OutlookService()
        elif domain == 'fmailler.com':
            return FirstMailService()
        else:
            # Общий сервис для неизвестных доменов
            return GenericEmailService()

class EmailService:
    def login(self, driver, email, password):
        raise NotImplementedError

    def navigate_to_instagram_emails(self, driver):
        raise NotImplementedError

    def open_latest_email(self, driver):
        raise NotImplementedError

class FirstMailService(EmailService):
    def login(self, driver, email, password):
        try:
            driver.get('https://firstmail.ltd/webmail/')

            # Добавим небольшую задержку для полной загрузки страницы
            time.sleep(3)

            # Сделаем скриншот страницы для отладки
            debug_screenshot_path = os.path.join(os.getcwd(), 'screenshots', 'debug_firstmail_login.png')
            driver.save_screenshot(debug_screenshot_path)
            logger.info(f"Создан отладочный скриншот: {debug_screenshot_path}")

            # Попробуем найти элементы по разным селекторам
            try:
                # Попытка 1: по ID
                username_field = driver.find_element(By.ID, 'rcmloginuser')
                password_field = driver.find_element(By.ID, 'rcmloginpwd')
                submit_button = driver.find_element(By.ID, 'rcmloginsubmit')
            except:
                try:
                    # Попытка 2: по имени
                    username_field = driver.find_element(By.NAME, '_user')
                    password_field = driver.find_element(By.NAME, '_pass')
                    submit_button = driver.find_element(By.NAME, '_action')
                except:
                    try:
                        # Попытка 3: по XPath
                        username_field = driver.find_element(By.XPATH, '//input[@type="text"]')
                        password_field = driver.find_element(By.XPATH, '//input[@type="password"]')
                        submit_button = driver.find_element(By.XPATH, '//input[@type="submit"]')
                    except:
                        # Попытка 4: по CSS селектору
                        username_field = driver.find_element(By.CSS_SELECTOR, 'input[type="text"]')
                        password_field = driver.find_element(By.CSS_SELECTOR, 'input[type="password"]')
                        submit_button = driver.find_element(By.CSS_SELECTOR, 'input[type="submit"]')

            # Ввод учетных данных
            username_field.clear()
            username_field.send_keys(email)
            password_field.clear()
            password_field.send_keys(password)
            submit_button.click()

            # Ожидание загрузки почтового ящика
            time.sleep(5)

            # Сделаем еще один скриншот после входа
            after_login_screenshot = os.path.join(os.getcwd(), 'screenshots', 'debug_firstmail_after_login.png')
            driver.save_screenshot(after_login_screenshot)
            logger.info(f"Создан скриншот после входа: {after_login_screenshot}")

            # Проверим, успешно ли вошли, ищем элементы, которые должны быть на странице после входа
            try:
                # Попытка найти элементы, которые должны быть на странице после входа
                driver.find_element(By.ID, 'messagelist') or driver.find_element(By.ID, 'mailboxlist') or driver.find_element(By.XPATH, '//div[contains(@class, "mailbox")]')
                logger.info(f"Успешный вход в FirstMail для {email}")
                return True
            except:
                logger.error(f"Не удалось подтвердить успешный вход в FirstMail для {email}")
                return False

        except Exception as e:
            logger.error(f"Ошибка входа в FirstMail: {e}")
            return False

    def navigate_to_instagram_emails(self, driver):
        try:
            # Сделаем скриншот перед поиском
            before_search = os.path.join(os.getcwd(), 'screenshots', 'debug_firstmail_before_search.png')
            driver.save_screenshot(before_search)

            # Попробуем разные способы поиска
            try:
                # Попытка 1: по ID
                search_box = driver.find_element(By.ID, 'quicksearchbox')
            except:
                try:
                    # Попытка 2: по атрибуту placeholder
                    search_box = driver.find_element(By.XPATH, '//input[contains(@placeholder, "Search")]')
                except:
                    # Попытка 3: по CSS селектору
                    search_box = driver.find_element(By.CSS_SELECTOR, 'input[type="text"][name*="search"]')

            search_box.clear()
            search_box.send_keys('from:instagram')
            search_box.submit()

            # Ожидание результатов поиска
            time.sleep(5)

            # Скриншот после поиска
            after_search = os.path.join(os.getcwd(), 'screenshots', 'debug_firstmail_after_search.png')
            driver.save_screenshot(after_search)
            logger.info(f"Создан скриншот после поиска: {after_search}")

            return True
        except Exception as e:
            logger.error(f"Ошибка поиска писем в FirstMail: {e}")

            # Попробуем альтернативный подход - просто открыть входящие
            try:
                # Найти и кликнуть на папку "Входящие"
                inbox = driver.find_element(By.XPATH, '//div[contains(text(), "Inbox")]') or driver.find_element(By.XPATH, '//a[contains(text(), "Inbox")]')
                inbox.click()
                time.sleep(3)
                return True
            except:
                return False

    def open_latest_email(self, driver):
        try:
            # Скриншот перед открытием письма
            before_open = os.path.join(os.getcwd(), 'screenshots', 'debug_firstmail_before_open.png')
            driver.save_screenshot(before_open)

            # Попробуем разные способы найти первое письмо
            try:
                # Попытка 1: по XPath для таблицы сообщений
                first_email = driver.find_element(By.XPATH, '//table[@id="messagelist"]//tr[1]')
            except:
                try:
                    # Попытка 2: по CSS селектору
                    first_email = driver.find_element(By.CSS_SELECTOR, '.message:first-child') or driver.find_element(By.CSS_SELECTOR, '.messagelist tr:first-child')
                except:
                    # Попытка 3: любое письмо с "Instagram" в отправителе
                    first_email = driver.find_element(By.XPATH, '//tr[contains(., "Instagram")]')

            first_email.click()

            # Ожидание загрузки содержимого письма
            time.sleep(3)

            # Скриншот после открытия письма
            after_open = os.path.join(os.getcwd(), 'screenshots', 'debug_firstmail_after_open.png')
            driver.save_screenshot(after_open)
            logger.info(f"Создан скриншот после открытия письма: {after_open}")

            return True
        except Exception as e:
            logger.error(f"Ошибка открытия письма в FirstMail: {e}")

            # Если не удалось открыть письмо, сделаем скриншот всей страницы
            full_page = os.path.join(os.getcwd(), 'screenshots', 'debug_firstmail_full_page.png')
            driver.save_screenshot(full_page)
            logger.info(f"Создан скриншот всей страницы: {full_page}")

            return False

class GmailService(EmailService):
    def login(self, driver, email, password):
        try:
            driver.get('https://mail.google.com')

            # Ввод email
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.ID, 'identifierId'))
            )
            driver.find_element(By.ID, 'identifierId').send_keys(email)
            driver.find_element(By.ID, 'identifierNext').click()

            # Ввод пароля
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.NAME, 'password'))
            )
            driver.find_element(By.NAME, 'password').send_keys(password)
            driver.find_element(By.ID, 'passwordNext').click()

            # Ожидание загрузки почтового ящика
            WebDriverWait(driver, 20).until(
                EC.presence_of_element_located((By.XPATH, '//div[contains(text(), "Inbox")]'))
            )
            return True
        except Exception as e:
            logger.error(f"Ошибка входа в Gmail: {e}")
            return False

    def navigate_to_instagram_emails(self, driver):
        try:
            # Поиск писем от Instagram
            search_box = driver.find_element(By.XPATH, '//input[@aria-label="Search mail"]')
            search_box.clear()
            search_box.send_keys('from:instagram verification code')
            search_box.submit()

            # Ожидание результатов поиска
            time.sleep(3)
            return True
        except Exception as e:
            logger.error(f"Ошибка поиска писем в Gmail: {e}")
            return False

    def open_latest_email(self, driver):
        try:
            # Открытие первого письма
            first_email = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.XPATH, '//div[contains(@role, "main")]//tr[1]'))
            )
            first_email.click()

            # Ожидание загрузки содержимого письма
            time.sleep(2)
            return True
        except Exception as e:
            logger.error(f"Ошибка открытия письма в Gmail: {e}")
            return False

# Добавьте другие классы для разных почтовых сервисов по аналогии

class OutlookService(EmailService):
    def login(self, driver, email, password):
        try:
            driver.get('https://outlook.live.com/mail/0/')

            # Ввод email
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.NAME, 'loginfmt'))
            )
            driver.find_element(By.NAME, 'loginfmt').send_keys(email)
            driver.find_element(By.ID, 'idSIButton9').click()

            # Ввод пароля
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.NAME, 'passwd'))
            )
            driver.find_element(By.NAME, 'passwd').send_keys(password)
            driver.find_element(By.ID, 'idSIButton9').click()

            # Возможный запрос "Оставаться в системе?"
            try:
                WebDriverWait(driver, 5).until(
                    EC.presence_of_element_located((By.ID, 'idSIButton9'))
                )
                driver.find_element(By.ID, 'idSIButton9').click()
            except:
                pass

            # Ожидание загрузки почтового ящика
            WebDriverWait(driver, 20).until(
                EC.presence_of_element_located((By.XPATH, '//div[contains(@aria-label, "Message list")]'))
            )
            return True
        except Exception as e:
            logger.error(f"Ошибка входа в Outlook: {e}")
            return False

    def navigate_to_instagram_emails(self, driver):
        try:
            # Поиск писем от Instagram
            search_box = driver.find_element(By.XPATH, '//input[contains(@aria-label, "Search")]')
            search_box.clear()
            search_box.send_keys('from:instagram')
            search_box.submit()

            # Ожидание результатов поиска
            time.sleep(3)
            return True
        except Exception as e:
            logger.error(f"Ошибка поиска писем в Outlook: {e}")
            return False

    def open_latest_email(self, driver):
        try:
            # Открытие первого письма
            first_email = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.XPATH, '//div[contains(@aria-label, "Message list")]//div[contains(@aria-label, "Instagram")]'))
            )
            first_email.click()

            # Ожидание загрузки содержимого письма
            time.sleep(2)
            return True
        except Exception as e:
            logger.error(f"Ошибка открытия письма в Outlook: {e}")
            return False

class YahooService(EmailService):
    def login(self, driver, email, password):
        try:
            driver.get('https://mail.yahoo.com')

            # Нажатие на кнопку входа
            WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.XPATH, '//a[contains(@class, "signin")]'))
            ).click()

            # Ввод email
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.ID, 'login-username'))
            )
            driver.find_element(By.ID, 'login-username').send_keys(email)
            driver.find_element(By.ID, 'login-signin').click()

            # Ввод пароля
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.ID, 'login-passwd'))
            )
            driver.find_element(By.ID, 'login-passwd').send_keys(password)
            driver.find_element(By.ID, 'login-signin').click()

            # Ожидание загрузки почтового ящика
            WebDriverWait(driver, 20).until(
                EC.presence_of_element_located((By.XPATH, '//div[contains(@data-test-id, "mail-list")]'))
            )
            return True
        except Exception as e:
            logger.error(f"Ошибка входа в Yahoo: {e}")
            return False

    def navigate_to_instagram_emails(self, driver):
        try:
            # Поиск писем от Instagram
            search_box = driver.find_element(By.XPATH, '//input[contains(@aria-label, "Search")]')
            search_box.clear()
            search_box.send_keys('from:instagram')
            search_box.submit()

            # Ожидание результатов поиска
            time.sleep(3)
            return True
        except Exception as e:
            logger.error(f"Ошибка поиска писем в Yahoo: {e}")
            return False

    def open_latest_email(self, driver):
        try:
            # Открытие первого письма
            first_email = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.XPATH, '//div[contains(@data-test-id, "mail-list")]//li[1]'))
            )
            first_email.click()

            # Ожидание загрузки содержимого письма
            time.sleep(2)
            return True
        except Exception as e:
            logger.error(f"Ошибка открытия письма в Yahoo: {e}")
            return False

class GenericEmailService(EmailService):
    def login(self, driver, email, password):
        # Базовая реализация для неизвестных почтовых сервисов
        # Здесь можно добавить логику определения интерфейса по внешнему виду страницы
        logger.warning(f"Используется общий сервис для {email}. Возможны проблемы с авторизацией.")
        return False

    def navigate_to_instagram_emails(self, driver):
        return False

    def open_latest_email(self, driver):
        return False

def extract_code_from_page_source(driver):
    """Извлекает код подтверждения напрямую из исходного кода страницы"""
    try:
        # Получаем исходный код страницы
        page_source = driver.page_source

        # Ищем 6-значные коды в исходном коде
        codes = re.findall(r'\b\d{6}\b', page_source)

        # Фильтруем известные не-коды
        valid_codes = [code for code in codes if code not in ['262626', '999999', '730247']]

        if valid_codes:
            return valid_codes[0]

        # Ищем код в контексте
        verification_contexts = [
            r'verification code[^\d]*(\d+)',
            r'код подтверждения[^\d]*(\d+)',
            r'instagram code[^\d]*(\d+)',
            r'code is[^\d]*(\d+)',
            r'код:[^\d]*(\d+)',
            r'code:[^\d]*(\d+)'
        ]

        for pattern in verification_contexts:
            match = re.search(pattern, page_source, re.IGNORECASE)
            if match:
                code = match.group(1)
                if len(code) == 6 and code.isdigit():
                    return code

        return None
    except Exception as e:
        logger.error(f"Ошибка при извлечении кода из исходного кода: {e}")
        return None

def preprocess_image_for_ocr(image_path, output_path=None):
    """Предобработка изображения для улучшения результатов OCR"""
    if output_path is None:
        output_path = image_path

    try:
        # Открываем изображение
        image = Image.open(image_path)

        # Преобразование в оттенки серого
        image = image.convert('L')

        # Увеличение контраста
        enhancer = ImageEnhance.Contrast(image)
        image = enhancer.enhance(2.0)

        # Увеличение резкости
        image = image.filter(ImageFilter.SHARPEN)

        # Бинаризация (преобразование в черно-белое)
        threshold = 150
        image = image.point(lambda p: p > threshold and 255)

        # Сохранение обработанного изображения
        image.save(output_path)
        return True
    except Exception as e:
        logger.error(f"Ошибка при обработке изображения: {e}")
        return False

def extract_code_from_screenshot(screenshot_path):
    """Извлекает 6-значный код подтверждения из скриншота с помощью OCR"""
    try:
        # Предобработка изображения
        processed_path = screenshot_path.replace('.png', '_processed.png')
        preprocess_image_for_ocr(screenshot_path, processed_path)

        # Загрузка обработанного изображения
        image = Image.open(processed_path)

        # Применение OCR для извлечения текста
        text = pytesseract.image_to_string(image)

        # Удаление временного файла
        try:
            os.remove(processed_path)
        except:
            pass

        # Поиск всех 6-значных чисел в тексте
        codes = re.findall(r'\b\d{6}\b', text)

        # Фильтрация известных не-кодов
        valid_codes = [code for code in codes if code not in ['262626', '999999', '730247']]

        if valid_codes:
            # Возвращаем первый найденный код
            return valid_codes[0]

        # Если не нашли 6-значный код, ищем в контексте
        verification_contexts = [
            r'verification code[^\d]*(\d+)',
            r'код подтверждения[^\d]*(\d+)',
            r'instagram code[^\d]*(\d+)',
            r'code is[^\d]*(\d+)',
            r'код:[^\d]*(\d+)',
            r'code:[^\d]*(\d+)'
        ]

        for pattern in verification_contexts:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                code = match.group(1)
                # Проверяем, что это 6-значный код
                if len(code) == 6 and code.isdigit():
                    return code

        logger.warning(f"Код не найден в тексте: {text}")
        return None

    except Exception as e:
        logger.error(f"Ошибка при извлечении кода из скриншота: {e}")
        return None

def capture_email_screenshot(email, password, screenshot_path):
    """Делает скриншот последнего письма от Instagram в почтовом ящике"""

    # Настройка драйвера
    chrome_options = Options()
    chrome_options.add_argument("--headless")  # Запуск в фоновом режиме
    chrome_options.add_argument("--window-size=1920,1080")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")

    try:
        driver = webdriver.Chrome(options=chrome_options)

        # Получаем сервис для конкретного почтового провайдера
        email_service = EmailServiceFactory.get_service(email)

        # Вход в почту
        if not email_service.login(driver, email, password):
            logger.error(f"Не удалось войти в почту {email}")

            # Попробуем извлечь код напрямую из страницы
            code = extract_code_from_page_source(driver)
            if code:
                logger.info(f"Найден код {code} в исходном коде страницы")
                driver.quit()
                return code

            driver.quit()
            return False

        # Переход к письмам от Instagram
        if not email_service.navigate_to_instagram_emails(driver):
            logger.error(f"Не удалось найти письма от Instagram для {email}")

            # Попробуем извлечь код напрямую из страницы
            code = extract_code_from_page_source(driver)
            if code:
                logger.info(f"Найден код {code} в исходном коде страницы")
                driver.quit()
                return code

            driver.quit()
            return False

        # Открытие последнего письма
        if not email_service.open_latest_email(driver):
            logger.error(f"Не удалось открыть последнее письмо для {email}")

            # Попробуем извлечь код напрямую из страницы
            code = extract_code_from_page_source(driver)
            if code:
                logger.info(f"Найден код {code} в исходном коде страницы")
                driver.quit()
                return code

            driver.quit()
            return False

        # Делаем скриншот
        driver.save_screenshot(screenshot_path)
        logger.info(f"Скриншот успешно создан: {screenshot_path}")

        # Попробуем также извлечь код напрямую из страницы
        code = extract_code_from_page_source(driver)
        if code:
            logger.info(f"Найден код {code} в исходном коде страницы")

        driver.quit()
        return True

    except Exception as e:
        logger.error(f"Ошибка при создании скриншота для {email}: {e}")
        try:
            driver.quit()
        except:
            pass
        return False

def get_verification_code_with_ocr(email, password):
    """Получает код подтверждения Instagram с помощью скриншота и OCR"""

    # Создаем временную директорию для скриншотов, если её нет
    screenshots_dir = os.path.join(os.getcwd(), 'screenshots')
    os.makedirs(screenshots_dir, exist_ok=True)

    # Путь для сохранения скриншота
    screenshot_filename = f"{email.replace('@', '_').replace('.', '_')}_{int(time.time())}.png"
    screenshot_path = os.path.join(screenshots_dir, screenshot_filename)

    # Делаем скриншот почтового ящика
    success = capture_email_screenshot(email, password, screenshot_path)

    if not success:
        logger.error(f"Не удалось создать скриншот для {email}")
        return None

    # Извлекаем код из скриншота
    verification_code = extract_code_from_screenshot(screenshot_path)

    # Удаляем скриншот после использования
    try:
        os.remove(screenshot_path)
        logger.info(f"Скриншот удален: {screenshot_path}")
    except Exception as e:
        logger.warning(f"Не удалось удалить скриншот {screenshot_path}: {e}")

    if verification_code:
        logger.info(f"Найден код подтверждения: {verification_code}")
        return verification_code
    else:
        logger.warning("Код подтверждения не найден на скриншоте")
        return None

def get_verification_code_with_fallbacks(email, password, instagram_client=None):
    """Получает код подтверждения с несколькими резервными методами"""

    # Попытка 1: OCR со скриншотом
    logger.info(f"Попытка получения кода через OCR для {email}")
    code = get_verification_code_with_ocr(email, password)
    if code:
        return code

    # Попытка 2: Стандартный метод через IMAP
    # Импортируем здесь, чтобы избежать циклических импортов
    from email_utils import get_code_from_firstmail

    logger.info(f"Попытка получения кода через IMAP для {email}")
    code = get_code_from_firstmail(email, password)
    if code:
        return code

    # Попытка 3: Запрос повторной отправки кода
    if instagram_client:
        logger.info(f"Запрос повторной отправки кода для {email}")
        instagram_client.request_new_code()
        time.sleep(15)  # Ожидание нового письма

        # Повторная попытка OCR
        logger.info(f"Повторная попытка OCR после запроса нового кода для {email}")
        code = get_verification_code_with_ocr(email, password)
        if code:
            return code

        # Повторная попытка IMAP
        logger.info(f"Повторная попытка IMAP после запроса нового кода для {email}")
        code = get_code_from_firstmail(email, password)
        if code:
            return code

    # Если все методы не сработали, возвращаем None
    logger.error(f"Не удалось получить код подтверждения для {email}")
    return None