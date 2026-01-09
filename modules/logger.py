# modules/logger.py
"""
Логирование действий админов и важных событий
"""

import logging
from logging.handlers import RotatingFileHandler
from datetime import datetime
from pathlib import Path
from typing import Optional

# Создаем папку для логов если не существует
log_dir = Path('logs')
log_dir.mkdir(exist_ok=True)

# Настройка основного логгера приложения
def setup_logging():
    """Настройка логирования для всего приложения"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(),
            RotatingFileHandler(
                log_dir / 'bot.log',
                maxBytes=5*1024*1024,  # 5 MB
                backupCount=5,
                encoding='utf-8'
            )
        ]
    )


# Специальный логгер для действий админов
admin_log_handler = RotatingFileHandler(
    log_dir / 'admin_actions.log',
    maxBytes=5*1024*1024,  # 5 MB
    backupCount=10,
    encoding='utf-8'
)
admin_log_handler.setFormatter(
    logging.Formatter('[%(asctime)s] %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
)

admin_logger = logging.getLogger('admin_actions')
admin_logger.setLevel(logging.INFO)
admin_logger.addHandler(admin_log_handler)


def log_admin_action(
    admin_id: int,
    action: str,
    target_type: str,
    target_id: Optional[int] = None,
    details: Optional[str] = None
) -> None:
    """
    Логирование действия администратора

    Args:
        admin_id: Telegram ID админа
        action: Тип действия (например: 'change_company', 'delete_user', 'add_volunteer')
        target_type: Тип объекта ('user', 'company', 'volunteer')
        target_id: ID объекта (опционально)
        details: Дополнительные детали (опционально)

    Пример лога:
        [2026-01-09 14:30:15] Admin 1632759029: change_company user 125 - Changed from "ООО А" to "ООО Б"
    """
    message_parts = [f"Admin {admin_id}: {action}"]

    if target_type:
        message_parts.append(target_type)

    if target_id is not None:
        message_parts.append(str(target_id))

    if details:
        message_parts.append(f"- {details}")

    admin_logger.info(" ".join(message_parts))


def log_user_registration(
    user_id: int,
    user_name: str,
    company_name: Optional[str] = None,
    registered_by: Optional[int] = None
) -> None:
    """
    Логирование регистрации пользователя

    Args:
        user_id: ID пользователя в БД
        user_name: ФИО пользователя
        company_name: Название предприятия
        registered_by: ID волонтера/админа (если регистрировал кто-то)
    """
    message = f"Registration: user {user_id} ({user_name})"

    if company_name:
        message += f" - Company: {company_name}"

    if registered_by:
        message += f" - By: {registered_by}"

    admin_logger.info(message)


def log_company_change(
    admin_id: int,
    user_id: int,
    old_company: Optional[str],
    new_company: str
) -> None:
    """
    Логирование изменения предприятия пользователя

    Args:
        admin_id: ID админа
        user_id: ID пользователя
        old_company: Старое предприятие
        new_company: Новое предприятие
    """
    old = old_company or "Не назначено"
    log_admin_action(
        admin_id=admin_id,
        action='change_company',
        target_type='user',
        target_id=user_id,
        details=f'Changed from "{old}" to "{new_company}"'
    )


def log_user_delete(
    admin_id: int,
    user_id: int,
    user_name: str
) -> None:
    """
    Логирование удаления пользователя

    Args:
        admin_id: ID админа
        user_id: ID пользователя
        user_name: ФИО пользователя
    """
    log_admin_action(
        admin_id=admin_id,
        action='delete_user',
        target_type='user',
        target_id=user_id,
        details=f'Deleted user: {user_name}'
    )


def log_volunteer_add(
    admin_id: int,
    volunteer_tg_id: int
) -> None:
    """
    Логирование добавления волонтера

    Args:
        admin_id: ID админа
        volunteer_tg_id: Telegram ID волонтера
    """
    log_admin_action(
        admin_id=admin_id,
        action='add_volunteer',
        target_type='volunteer',
        target_id=volunteer_tg_id,
        details='Added as volunteer'
    )


def log_role_switch(
    user_id: int,
    new_role: str
) -> None:
    """
    Логирование переключения роли разработчиком

    Args:
        user_id: ID разработчика
        new_role: Новая роль ('admin' или 'user')
    """
    admin_logger.info(f"Developer {user_id}: switched to {new_role} mode")


def log_error(
    context: str,
    error: Exception,
    user_id: Optional[int] = None
) -> None:
    """
    Логирование ошибки

    Args:
        context: Контекст где произошла ошибка
        error: Объект исключения
        user_id: ID пользователя (опционально)
    """
    message = f"Error in {context}: {str(error)}"
    if user_id:
        message = f"User {user_id} - {message}"

    logging.getLogger(__name__).error(message, exc_info=True)
