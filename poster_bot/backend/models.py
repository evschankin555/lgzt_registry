from sqlalchemy import Column, Integer, String, DateTime, Text, Boolean, ForeignKey, Date
from sqlalchemy.orm import relationship
from datetime import datetime, date
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

    # Глобальный статус вступления (актуальное состояние в TG)
    status = Column(String(20), default="pending")  # pending, joining, joined, failed, left
    join_error = Column(Text, nullable=True)  # Текст ошибки если failed
    join_attempts = Column(Integer, default=0)  # Количество попыток входа
    last_attempt_at = Column(DateTime, nullable=True)  # Время последней попытки
    joined_at = Column(DateTime, nullable=True)  # Когда успешно вошли

    # Для авто-выхода
    can_leave = Column(Boolean, default=False)  # Можно выходить (успешно отправили)
    left_at = Column(DateTime, nullable=True)  # Когда вышли из группы

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
    """Результат отправки в конкретную группу (legacy)"""
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


class Message(Base):
    """Подготовленное сообщение для рассылки"""
    __tablename__ = "messages"

    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=True)  # Название для удобства
    caption = Column(Text, nullable=True)  # Текст сообщения
    photo_path = Column(String(255), nullable=True)  # Путь к фото
    status = Column(String(20), default="draft")  # draft, ready, sending, completed
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Связь с целевыми группами
    targets = relationship("MessageTarget", back_populates="message", cascade="all, delete-orphan")


class MessageTarget(Base):
    """Целевая группа для сообщения - содержит статус вступления и отправки"""
    __tablename__ = "message_targets"

    id = Column(Integer, primary_key=True)
    message_id = Column(Integer, ForeignKey("messages.id", ondelete="CASCADE"), nullable=False)
    group_id = Column(Integer, ForeignKey("groups.id"), nullable=False)

    # Включена в рассылку (можно исключить вручную)
    included = Column(Boolean, default=True)

    # Статус отправки для этого сообщения
    send_status = Column(String(20), default="pending")  # pending, waiting, sending, sent, failed
    send_error = Column(Text, nullable=True)
    sent_at = Column(DateTime, nullable=True)

    # Результат отправки
    telegram_message_id = Column(Integer, nullable=True)  # ID сообщения в TG
    message_link = Column(String(255), nullable=True)  # Ссылка на пост

    created_at = Column(DateTime, default=datetime.utcnow)

    message = relationship("Message", back_populates="targets")
    group = relationship("Group")


# Legacy alias for compatibility
MessageSend = MessageTarget


class DailyStats(Base):
    """Статистика действий за день"""
    __tablename__ = "daily_stats"

    date = Column(Date, primary_key=True, default=date.today)
    joins_count = Column(Integer, default=0)   # Вступлений
    sends_count = Column(Integer, default=0)   # Отправок
    leaves_count = Column(Integer, default=0)  # Выходов


class BotSettings(Base):
    """Настройки автоматического постинга"""
    __tablename__ = "bot_settings"

    id = Column(Integer, primary_key=True)

    # Активное сообщение для автопостинга
    active_message_id = Column(Integer, ForeignKey("messages.id"), nullable=True)

    # Лимиты
    daily_limit = Column(Integer, default=100)  # Действий в день
    join_limit_per_session = Column(Integer, default=20)
    send_limit_per_session = Column(Integer, default=20)

    # Расписание (часы, МСК)
    join_start_hour = Column(Integer, default=8)   # Начало вступлений
    join_end_hour = Column(Integer, default=16)    # Конец вступлений
    send_start_hour = Column(Integer, default=16)  # Начало рассылки
    send_end_hour = Column(Integer, default=21)    # Конец рассылки

    # Задержки (секунды)
    join_delay_min = Column(Integer, default=30)
    join_delay_max = Column(Integer, default=60)
    send_delay_min = Column(Integer, default=30)
    send_delay_max = Column(Integer, default=60)

    # Ожидание перед отправкой
    wait_before_send_hours = Column(Integer, default=4)  # Часов ждать после вступления

    # Авто-выход
    auto_leave_enabled = Column(Boolean, default=True)
    leave_after_days = Column(Integer, default=7)  # Выйти через N дней после отправки

    # Автоматика
    auto_mode_enabled = Column(Boolean, default=False)  # Автоматический режим включен

    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
