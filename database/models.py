from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Text, Float, JSON, Enum, Table
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from datetime import datetime
import enum

Base = declarative_base()

# Таблица связи между аккаунтами и прокси
account_proxy = Table(
    'account_proxy',
    Base.metadata,
    Column('account_id', Integer, ForeignKey('instagram_accounts.id'), primary_key=True),
    Column('proxy_id', Integer, ForeignKey('proxies.id'), primary_key=True)
)

class TaskStatus(enum.Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    SCHEDULED = "scheduled"

class TaskType(enum.Enum):
    VIDEO = "video"
    PHOTO = "photo"
    CAROUSEL = "carousel"
    STORY = "story"
    REEL = "reel"

class Proxy(Base):
    __tablename__ = 'proxies'

    id = Column(Integer, primary_key=True)
    host = Column(String(255), nullable=False)
    port = Column(Integer, nullable=False)
    username = Column(String(255), nullable=True)
    password = Column(String(255), nullable=True)
    protocol = Column(String(10), default='http')
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)

    # Отношения
    accounts = relationship("InstagramAccount", secondary=account_proxy, back_populates="proxies")

class InstagramAccount(Base):
    __tablename__ = 'instagram_accounts'

    id = Column(Integer, primary_key=True)
    username = Column(String(255), nullable=False, unique=True)
    password = Column(String(255), nullable=False)
    email = Column(String(255))
    email_password = Column(String(255))
    full_name = Column(String(255))  # Добавляем поле для полного имени
    biography = Column(Text)  # Добавляем поле для описания профиля
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)
    session_data = Column(Text)

    # Отношения
    proxies = relationship("Proxy", secondary=account_proxy, back_populates="accounts")
    tasks = relationship("PublishTask", back_populates="account")
    proxy_id = Column(Integer, ForeignKey('proxies.id'), nullable=True)
    proxy = relationship("Proxy", foreign_keys=[proxy_id])

class PublishTask(Base):
    __tablename__ = 'publish_tasks'

    id = Column(Integer, primary_key=True)
    account_id = Column(Integer, ForeignKey('instagram_accounts.id'), nullable=False)
    task_type = Column(Enum(TaskType), nullable=False)
    status = Column(Enum(TaskStatus), default=TaskStatus.PENDING)
    media_path = Column(String(255), nullable=True)  # Путь к медиафайлу
    caption = Column(Text, nullable=True)  # Текст публикации
    hashtags = Column(Text, nullable=True)  # Хэштеги
    scheduled_time = Column(DateTime, nullable=True)  # Время запланированной публикации
    completed_time = Column(DateTime, nullable=True)  # Время выполнения задачи
    error_message = Column(Text, nullable=True)  # Сообщение об ошибке, если задача не выполнена
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)

    # Дополнительные поля для разных типов публикаций
    location = Column(String(255), nullable=True)  # Местоположение
    first_comment = Column(Text, nullable=True)  # Первый комментарий
    options = Column(JSON, nullable=True)  # Дополнительные опции в формате JSON

    # Для карусели
    media_paths = Column(JSON, nullable=True)  # Список путей к медиафайлам для карусели

    # Для историй
    story_options = Column(JSON, nullable=True)  # Опции для историй (стикеры, опросы и т.д.)

    # Для рилс
    audio_path = Column(String(255), nullable=True)  # Путь к аудиофайлу для рилс
    audio_start_time = Column(Float, nullable=True)  # Время начала аудио

    # Отношения
    account = relationship("InstagramAccount", back_populates="tasks")

class TelegramUser(Base):
    __tablename__ = 'telegram_users'

    id = Column(Integer, primary_key=True)
    telegram_id = Column(Integer, unique=True, nullable=False)
    username = Column(String(255), nullable=True)
    first_name = Column(String(255), nullable=True)
    last_name = Column(String(255), nullable=True)
    is_admin = Column(Boolean, default=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)
    last_activity = Column(DateTime, nullable=True)

class Setting(Base):
    __tablename__ = 'settings'

    id = Column(Integer, primary_key=True)
    key = Column(String(255), unique=True, nullable=False)
    value = Column(Text, nullable=True)
    description = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)

class Log(Base):
    __tablename__ = 'logs'

    id = Column(Integer, primary_key=True)
    level = Column(String(20), nullable=False)  # INFO, WARNING, ERROR, DEBUG
    message = Column(Text, nullable=False)
    source = Column(String(255), nullable=True)  # Источник лога (модуль, функция)
    created_at = Column(DateTime, default=datetime.now)

    # Дополнительные данные
    data = Column(JSON, nullable=True)  # Дополнительные данные в формате JSON