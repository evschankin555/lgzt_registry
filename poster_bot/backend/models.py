from sqlalchemy import Column, Integer, String, DateTime, Text, Boolean, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime
from database import Base


class TelegramAccount(Base):
    """Авторизованный Telegram аккаунт"""
    __tablename__ = "telegram_accounts"

    id = Column(Integer, primary_key=True)
    phone = Column(String(20), unique=True, nullable=False)
    session_file = Column(String(255), nullable=False)
    is_authorized = Column(Boolean, default=False)
    first_name = Column(String(100), nullable=True)
    last_name = Column(String(100), nullable=True)
    username = Column(String(100), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    posts = relationship("Post", back_populates="account")


class Group(Base):
    """Группы для рассылки"""
    __tablename__ = "groups"

    id = Column(Integer, primary_key=True)
    telegram_id = Column(String(50), nullable=True)  # ID группы в TG (заполняется после входа)
    link = Column(String(255), nullable=False)  # Ссылка на группу
    title = Column(String(255), nullable=True)  # Название (заполняется после входа)

    # Дополнительная информация из Excel
    city = Column(String(100), nullable=True)  # Город
    address = Column(String(255), nullable=True)  # Адрес

    # Статус вступления
    status = Column(String(20), default="pending")  # pending, joining, joined, failed, left
    join_error = Column(Text, nullable=True)  # Текст ошибки если failed
    join_attempts = Column(Integer, default=0)  # Количество попыток входа
    last_attempt_at = Column(DateTime, nullable=True)  # Время последней попытки
    joined_at = Column(DateTime, nullable=True)  # Когда успешно вошли

    # Источник
    source = Column(String(20), default="manual")  # manual, excel

    # Legacy поле (для совместимости)
    is_joined = Column(Boolean, default=False)

    added_at = Column(DateTime, default=datetime.utcnow)

    post_results = relationship("PostResult", back_populates="group")

    @property
    def is_available(self):
        """Группа доступна для рассылки"""
        return self.status == "joined"


class Post(Base):
    """Рассылка"""
    __tablename__ = "posts"

    id = Column(Integer, primary_key=True)
    account_id = Column(Integer, ForeignKey("telegram_accounts.id"), nullable=False)
    caption = Column(Text, nullable=True)  # Подпись к фото
    photo_path = Column(String(255), nullable=True)  # Путь к фото
    status = Column(String(20), default="pending")  # pending, in_progress, completed, failed
    created_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)

    # Настройки рассылки
    delay_seconds = Column(Integer, default=5)  # Задержка между отправками

    account = relationship("TelegramAccount", back_populates="posts")
    results = relationship("PostResult", back_populates="post")


class PostResult(Base):
    """Результат отправки в конкретную группу"""
    __tablename__ = "post_results"

    id = Column(Integer, primary_key=True)
    post_id = Column(Integer, ForeignKey("posts.id"), nullable=False)
    group_id = Column(Integer, ForeignKey("groups.id"), nullable=False)
    status = Column(String(20), default="pending")  # pending, sending, success, failed
    error_message = Column(Text, nullable=True)
    sent_at = Column(DateTime, nullable=True)

    # Новые поля для отслеживания
    message_id = Column(Integer, nullable=True)  # ID сообщения в TG
    message_link = Column(String(255), nullable=True)  # Ссылка на сообщение

    post = relationship("Post", back_populates="results")
    group = relationship("Group", back_populates="post_results")
