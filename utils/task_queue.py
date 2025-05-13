import threading
import logging
import queue
import time
from datetime import datetime
import concurrent.futures
import traceback
import random

from database.db_manager import update_publish_task_status, get_publish_task
from database.models import TaskStatus
from instagram_api.publisher import publish_video

logger = logging.getLogger(__name__)

# Создаем очередь задач
task_queue = queue.Queue()

# Словарь для хранения результатов выполнения задач
task_results = {}

# Пул потоков для параллельного выполнения задач
# Устанавливаем максимальное количество одновременных задач
MAX_WORKERS = 5
executor = concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS)

def process_task(task_id, chat_id, bot):
    """Обрабатывает одну задачу публикации"""
    logger.info(f"Обработка задачи #{task_id} для чата {chat_id}")

    try:
        # Добавляем случайную задержку между действиями (2-5 секунд)
        delay = random.uniform(2, 5)
        logger.info(f"Добавлена задержка {delay:.2f} секунд перед выполнением задачи")
        time.sleep(delay)

        success, result = publish_video(task_id)

        # Сохраняем результат
        task_results[task_id] = {
            'success': success,
            'result': result,
            'completed_at': datetime.now()
        }

        # Отправляем уведомление пользователю
        if success:
            message = f"✅ Задача #{task_id} успешно выполнена!\nВидео опубликовано в Instagram."
        else:
            message = f"❌ Задача #{task_id} завершилась с ошибкой:\n{result}"

        try:
            bot.send_message(chat_id=chat_id, text=message)
        except Exception as e:
            logger.error(f"Ошибка при отправке уведомления для задачи #{task_id}: {e}")

        logger.info(f"Задача #{task_id} завершена: {'успешно' if success else 'с ошибкой'}")

        return success, result
    except Exception as e:
        error_msg = f"Ошибка при выполнении задачи #{task_id}: {e}"
        logger.error(error_msg)
        logger.error(traceback.format_exc())  # Добавляем полный стек-трейс

        try:
            bot.send_message(
                chat_id=chat_id,
                text=f"❌ Произошла ошибка при выполнении задачи #{task_id}:\n{str(e)}"
            )
        except Exception as notify_error:
            logger.error(f"Не удалось отправить уведомление об ошибке: {notify_error}")

        # Обновляем статус задачи в БД
        try:
            update_publish_task_status(task_id, TaskStatus.FAILED, error_message=str(e))
        except Exception as db_error:
            logger.error(f"Ошибка при обновлении статуса задачи в БД: {db_error}")

        # Сохраняем результат
        task_results[task_id] = {
            'success': False,
            'result': str(e),
            'completed_at': datetime.now()
        }

        return False, str(e)

def task_worker():
    """Функция-обработчик очереди задач"""
    logger.info("Запущен обработчик очереди задач")

    # Словарь для отслеживания выполняющихся задач
    futures = {}

    while True:
        try:
            # Проверяем завершенные задачи
            done_futures = []
            for future, task_info in list(futures.items()):
                if future.done():
                    try:
                        # Получаем результат, чтобы обработать возможные исключения
                        future.result()
                    except Exception as e:
                        logger.error(f"Ошибка в задаче {task_info}: {e}")
                        logger.error(traceback.format_exc())
                    done_futures.append(future)

            # Удаляем завершенные задачи из словаря
            for future in done_futures:
                del futures[future]

            # Получаем новую задачу из очереди, если есть место в пуле
            if len(futures) < MAX_WORKERS:
                try:
                    # Неблокирующее получение задачи с таймаутом
                    task = task_queue.get(block=True, timeout=1.0)

                    if task is None:
                        # Сигнал для завершения
                        break

                    task_id, chat_id, bot = task

                    # Запускаем задачу в пуле потоков
                    future = executor.submit(process_task, task_id, chat_id, bot)
                    futures[future] = (task_id, chat_id)

                    # Отмечаем задачу как взятую из очереди
                    task_queue.task_done()

                except queue.Empty:
                    # Если очередь пуста, просто продолжаем цикл
                    pass
            else:
                # Если все рабочие потоки заняты, ждем немного
                time.sleep(0.5)

        except Exception as e:
            logger.error(f"Критическая ошибка в обработчике очереди: {e}")
            logger.error(traceback.format_exc())
            time.sleep(1)  # Пауза перед следующей итерацией

# Запускаем обработчик в отдельном потоке
worker_thread = None

def start_task_queue():
    """Запускает обработчик очереди задач"""
    global worker_thread

    if worker_thread is None or not worker_thread.is_alive():
        worker_thread = threading.Thread(target=task_worker, daemon=True)
        worker_thread.start()
        logger.info("Запущен поток обработки очереди задач")
    else:
        logger.info("Поток обработки очереди задач уже запущен")

def stop_task_queue():
    """Останавливает обработчик очереди задач"""
    global worker_thread, executor

    if worker_thread and worker_thread.is_alive():
        task_queue.put(None)  # Сигнал для завершения
        worker_thread.join(timeout=5.0)

        # Завершаем пул потоков
        executor.shutdown(wait=False)

        # Создаем новый пул потоков для следующего запуска
        executor = concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS)

        logger.info("Поток обработки очереди задач остановлен")

def add_task_to_queue(task_id, chat_id, bot):
    """Добавляет задачу в очередь на выполнение"""
    try:
        # Проверяем, что задача существует
        task = get_publish_task(task_id)
        if not task:
            logger.error(f"Задача #{task_id} не найдена")
            return False

        # Обновляем статус задачи
        update_publish_task_status(task_id, TaskStatus.PROCESSING)

        # Добавляем задачу в очередь
        task_queue.put((task_id, chat_id, bot))
        logger.info(f"Задача #{task_id} добавлена в очередь")

        return True
    except Exception as e:
        logger.error(f"Ошибка при добавлении задачи #{task_id} в очередь: {e}")
        logger.error(traceback.format_exc())
        return False

def get_task_status(task_id):
    """Возвращает статус выполнения задачи"""
    try:
        if task_id in task_results:
            return task_results[task_id]

        # Если задача не найдена в результатах, проверяем БД
        task = get_publish_task(task_id)
        if task:
            return {
                'success': task.status == TaskStatus.COMPLETED,
                'result': task.error_message or "В процессе выполнения",
                'completed_at': task.updated_at
            }

        return None
    except Exception as e:
        logger.error(f"Ошибка при получении статуса задачи #{task_id}: {e}")
        return {'success': False, 'result': f"Ошибка: {str(e)}"}