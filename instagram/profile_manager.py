import os
import logging
import random
import time
from pathlib import Path

from database.db_manager import get_instagram_account
from instagram.client import get_instagram_client

logger = logging.getLogger(__name__)

class ProfileManager:
    def __init__(self, account_id):
        self.account_id = account_id
        self.account = get_instagram_account(account_id)
        self.client = get_instagram_client(account_id)

        # Проверяем, что клиент успешно инициализирован
        if self.client is None:
            logger.error(f"Не удалось инициализировать клиент для аккаунта {account_id}")
            # Пробуем выполнить вход еще раз
            if self.account:
                logger.info(f"Пробуем повторно войти в аккаунт {self.account.username}")
                from instagram.client import test_instagram_login_with_proxy
                success = test_instagram_login_with_proxy(
                    account_id,
                    self.account.username,
                    self.account.password,
                    getattr(self.account, 'email', None),
                    getattr(self.account, 'email_password', None)
                )
                if success:
                    self.client = get_instagram_client(account_id)
                    logger.info(f"Повторный вход в аккаунт {self.account.username} успешен")
                else:
                    logger.error(f"Повторный вход в аккаунт {self.account.username} не удался")

            # Если клиент все еще None, вызываем исключение
            if self.client is None:
                raise Exception(f"Клиент Instagram не инициализирован для аккаунта {account_id}")

    def get_profile_info(self):
        """Получает информацию о профиле"""
        try:
            # Добавляем небольшую задержку для имитации человеческого поведения
            time.sleep(random.uniform(1, 3))
            profile_info = self.client.account_info()
            return profile_info
        except Exception as e:
            logger.error(f"Ошибка при получении информации о профиле: {e}")
            return {}

    def get_profile_links(self):
        """Получает ссылки профиля"""
        try:
            # Добавляем небольшую задержку для имитации человеческого поведения
            time.sleep(random.uniform(1, 2))
            profile_info = self.client.account_info()
            return profile_info.external_url  # Исправлено: используем external_url вместо get('external_links')
        except Exception as e:
            logger.error(f"Ошибка при получении ссылок профиля: {e}")
            return ""

    def update_profile_name(self, full_name):
        """Обновляет имя профиля"""
        try:
            # Добавляем задержку для имитации человеческого поведения
            time.sleep(random.uniform(2, 4))
            result = self.client.account_edit(full_name=full_name)
            return True, "Имя профиля успешно обновлено"
        except Exception as e:
            logger.error(f"Ошибка при обновлении имени профиля: {e}")
            return False, str(e)

    def update_username(self, username):
        """Обновляет имя пользователя"""
        try:
            # Добавляем задержку для имитации человеческого поведения
            time.sleep(random.uniform(2, 4))

            # Обновляем имя пользователя в Instagram
            result = self.client.account_edit(username=username)

            # Если успешно обновлено в Instagram, обновляем в базе данных
            if result:
                from database.db_manager import update_instagram_account
                success, message = update_instagram_account(self.account_id, username=username)

                if not success:
                    logger.warning(f"Имя пользователя обновлено в Instagram, но не обновлено в базе данных: {message}")
                else:
                    logger.info(f"Имя пользователя успешно обновлено в Instagram и в базе данных")

                # Обновляем имя пользователя в объекте аккаунта
                self.account.username = username

            return True, "Имя пользователя успешно обновлено"
        except Exception as e:
            logger.error(f"Ошибка при обновлении имени пользователя: {e}")
            return False, str(e)

    def update_biography(self, biography):
        """Обновляет описание профиля"""
        try:
            # Добавляем задержку для имитации человеческого поведения
            time.sleep(random.uniform(2, 4))
            result = self.client.account_edit(biography=biography)
            return True, "Описание профиля успешно обновлено"
        except Exception as e:
            logger.error(f"Ошибка при обновлении описания профиля: {e}")
            return False, str(e)

    def update_profile_links(self, link):
        """Обновляет ссылку профиля"""
        try:
            # Добавляем задержку для имитации человеческого поведения
            time.sleep(random.uniform(2, 4))

            # Получаем URL из первой ссылки, если передан список
            url = link
            if isinstance(link, list) and link:
                url = link[0].get('url', '')
            elif isinstance(link, str):
                url = link

            logger.info(f"Попытка обновления ссылки профиля на: {url}")

            # Получаем текущую информацию о профиле
            profile_info = self.client.account_info()

            # Обновляем профиль с новой ссылкой
            result = self.client.account_edit(external_url=url)
            logger.info(f"Результат обновления ссылки: {result}")

            return True, "Ссылка профиля успешно обновлена"
        except Exception as e:
            logger.error(f"Ошибка при обновлении ссылки профиля: {e}")
            return False, str(e)

    def update_profile_picture(self, photo_path):
        """Обновляет фото профиля"""
        try:
            # Добавляем задержку для имитации человеческого поведения
            time.sleep(random.uniform(3, 6))
            result = self.client.account_change_picture(photo_path)
            return True, "Фото профиля успешно обновлено"
        except Exception as e:
            logger.error(f"Ошибка при обновлении фото профиля: {e}")
            return False, str(e)

    def remove_profile_picture(self):
        """Удаляет фото профиля"""
        try:
            # Добавляем задержку для имитации человеческого поведения
            time.sleep(random.uniform(2, 4))
            result = self.client.account_remove_picture()
            return True, "Фото профиля успешно удалено"
        except Exception as e:
            logger.error(f"Ошибка при удалении фото профиля: {e}")
            return False, str(e)

    def upload_photo(self, photo_path, caption="", pin=False):
        """Загружает фото в профиль"""
        try:
            # Добавляем задержку для имитации человеческого поведения
            time.sleep(random.uniform(4, 8))
            result = self.client.photo_upload(photo_path, caption)

            # Если нужно закрепить пост
            if pin and result.get('pk'):
                # Добавляем небольшую задержку перед закреплением
                time.sleep(random.uniform(2, 4))
                self.client.highlight_create("Закрепленные", [result.get('pk')])

            return True, "Фото успешно загружено"
        except Exception as e:
            logger.error(f"Ошибка при загрузке фото: {e}")
            return False, str(e)

    def upload_video(self, video_path, caption="", pin=False):
        """Загружает видео в профиль"""
        try:
            # Добавляем задержку для имитации человеческого поведения
            time.sleep(random.uniform(5, 10))
            result = self.client.video_upload(video_path, caption)

            # Если нужно закрепить пост
            if pin and result.get('pk'):
                # Добавляем небольшую задержку перед закреплением
                time.sleep(random.uniform(2, 4))
                self.client.highlight_create("Закрепленные", [result.get('pk')])

            return True, "Видео успешно загружено"
        except Exception as e:
            logger.error(f"Ошибка при загрузке видео: {e}")
            return False, str(e)

    def delete_all_posts(self):
        """Удаляет все посты из профиля"""
        try:
            # Получаем все медиа из профиля
            media_items = self.client.user_medias(self.client.user_id, 50)

            if not media_items:
                return True, "В профиле нет постов для удаления"

            # Удаляем каждый пост с задержкой
            for media in media_items:
                # Добавляем задержку между удалениями
                time.sleep(random.uniform(2, 5))
                self.client.media_delete(media.id)

            return True, f"Удалено {len(media_items)} постов"
        except Exception as e:
            logger.error(f"Ошибка при удалении постов: {e}")
            return False, str(e)

    def execute_profile_task(self, task):
        """Выполняет задачу по обновлению профиля"""
        try:
            # Добавляем задержку перед началом выполнения задачи
            time.sleep(random.uniform(2, 5))

            # Получаем опции задачи
            options = task.options or {}

            # Обновляем имя пользователя, если оно указано
            if options.get('username'):
                success, message = self.update_username(options.get('username'))
                if not success:
                    logger.error(f"Ошибка при обновлении имени пользователя: {message}")
                # Добавляем задержку между действиями
                time.sleep(random.uniform(2, 4))

            # Обновляем полное имя, если оно указано
            if options.get('full_name'):
                success, message = self.update_profile_name(options.get('full_name'))
                if not success:
                    logger.error(f"Ошибка при обновлении полного имени: {message}")
                # Добавляем задержку между действиями
                time.sleep(random.uniform(2, 4))

                # Обновляем в базе данных
                from database.db_manager import update_instagram_account
                update_instagram_account(self.account_id, full_name=options.get('full_name'))

            # Обновляем описание профиля, если оно указано
            if task.caption or options.get('biography'):
                bio = task.caption or options.get('biography')
                success, message = self.update_biography(bio)
                if not success:
                    logger.error(f"Ошибка при обновлении описания профиля: {message}")
                # Добавляем задержку между действиями
                time.sleep(random.uniform(2, 4))

                # Обновляем в базе данных
                from database.db_manager import update_instagram_account
                update_instagram_account(self.account_id, biography=bio)

            # Обновляем ссылку профиля, если она указана
            if options.get('external_url'):
                success, message = self.update_profile_links(options.get('external_url'))
                if not success:
                    logger.error(f"Ошибка при обновлении ссылки профиля: {message}")
                # Добавляем задержку между действиями
                time.sleep(random.uniform(2, 4))

            # Обновляем фото профиля, если оно указано
            if task.media_path and os.path.exists(task.media_path):
                success, message = self.update_profile_picture(task.media_path)
                if not success:
                    logger.error(f"Ошибка при обновлении фото профиля: {message}")

            # После всех изменений, получаем обновленную информацию о профиле
            profile_info = self.get_profile_info()

            # Обновляем информацию в базе данных
            if profile_info:
                from database.db_manager import update_instagram_account
                update_data = {
                    'username': profile_info.username,
                    'full_name': profile_info.full_name,
                    'biography': profile_info.biography
                }
                success, message = update_instagram_account(self.account_id, **update_data)
                if not success:
                    logger.error(f"Ошибка при обновлении информации аккаунта в базе данных: {message}")

            return True, "Профиль успешно обновлен"
        except Exception as e:
            logger.error(f"Ошибка при выполнении задачи обновления профиля: {e}")
            return False, str(e)