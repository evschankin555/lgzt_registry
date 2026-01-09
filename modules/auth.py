# modules/auth.py
"""
Модуль авторизации и проверки прав доступа
"""

import logging
import functools
from typing import List, Callable, Any

logger = logging.getLogger(__name__)

# ID разработчика - может видеть кнопку переключения режимов
developer_ids: List[int] = [1632759029]

# ID администраторов (импортируем из vars.py при использовании)
# admin_ids будут браться из vars.py

# ID суперадминов (для критических операций)
# superadmin_ids будут браться из vars.py


def is_developer(user_id: int) -> bool:
    """
    Проверка является ли пользователь разработчиком

    Args:
        user_id: Telegram user ID

    Returns:
        True если разработчик
    """
    return user_id in developer_ids


def is_admin(user_id: int, admin_ids: List[int]) -> bool:
    """
    Проверка является ли пользователь администратором

    Args:
        user_id: Telegram user ID
        admin_ids: Список ID администраторов

    Returns:
        True если админ
    """
    return user_id in admin_ids


def is_superadmin(user_id: int, superadmin_ids: List[int]) -> bool:
    """
    Проверка является ли пользователь суперадмином

    Args:
        user_id: Telegram user ID
        superadmin_ids: Список ID суперадминов

    Returns:
        True если суперадмин
    """
    return user_id in superadmin_ids


def require_admin(admin_ids: List[int]):
    """
    Декоратор для проверки прав администратора

    Использование:
        @require_admin(admin_ids)
        async def admin_handler(call, bot):
            ...
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            # Получаем call из аргументов
            call = args[0] if args else None
            bot = kwargs.get('bot') or (args[1] if len(args) > 1 else None)

            if call is None:
                logger.error(f"No call object in {func.__name__}")
                return None

            user_id = call.from_user.id

            if not is_admin(user_id, admin_ids):
                logger.warning(f"Access denied for user {user_id} in {func.__name__}")
                if bot and hasattr(call, 'id'):
                    try:
                        await bot.answer_callback_query(
                            call.id,
                            "Доступ запрещен. Только для администраторов.",
                            show_alert=True
                        )
                    except Exception:
                        pass
                return None

            return await func(*args, **kwargs)
        return wrapper
    return decorator


def require_developer(func: Callable) -> Callable:
    """
    Декоратор для проверки прав разработчика

    Использование:
        @require_developer
        async def dev_handler(call, bot):
            ...
    """
    @functools.wraps(func)
    async def wrapper(*args, **kwargs):
        call = args[0] if args else None
        bot = kwargs.get('bot') or (args[1] if len(args) > 1 else None)

        if call is None:
            logger.error(f"No call object in {func.__name__}")
            return None

        user_id = call.from_user.id

        if not is_developer(user_id):
            logger.warning(f"Developer access denied for user {user_id} in {func.__name__}")
            if bot and hasattr(call, 'id'):
                try:
                    await bot.answer_callback_query(
                        call.id,
                        "Доступ запрещен. Только для разработчиков.",
                        show_alert=True
                    )
                except Exception:
                    pass
            return None

        return await func(*args, **kwargs)
    return wrapper


def require_superadmin(superadmin_ids: List[int]):
    """
    Декоратор для проверки прав суперадмина (критические операции)

    Использование:
        @require_superadmin(superadmin_ids)
        async def critical_handler(call, bot):
            ...
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            call = args[0] if args else None
            bot = kwargs.get('bot') or (args[1] if len(args) > 1 else None)

            if call is None:
                logger.error(f"No call object in {func.__name__}")
                return None

            user_id = call.from_user.id

            if not is_superadmin(user_id, superadmin_ids):
                logger.warning(f"Superadmin access denied for user {user_id} in {func.__name__}")
                if bot and hasattr(call, 'id'):
                    try:
                        await bot.answer_callback_query(
                            call.id,
                            "Доступ запрещен. Только для суперадминистраторов.",
                            show_alert=True
                        )
                    except Exception:
                        pass
                return None

            return await func(*args, **kwargs)
        return wrapper
    return decorator


# Хранение текущей роли для developer mode
# Ключ: user_id, Значение: 'admin' или 'user'
_developer_mode_roles: dict = {}


def get_developer_role(user_id: int) -> str:
    """
    Получить текущую роль разработчика в тестовом режиме

    Args:
        user_id: Telegram user ID

    Returns:
        'admin' или 'user'
    """
    return _developer_mode_roles.get(user_id, 'admin')


def set_developer_role(user_id: int, role: str) -> None:
    """
    Установить роль разработчика в тестовом режиме

    Args:
        user_id: Telegram user ID
        role: 'admin' или 'user'
    """
    if role in ('admin', 'user'):
        _developer_mode_roles[user_id] = role
        logger.info(f"Developer {user_id} switched to role: {role}")


def should_show_as_admin(user_id: int, admin_ids: List[int]) -> bool:
    """
    Определить, показывать ли пользователю админ-интерфейс

    Учитывает:
    - Является ли пользователь админом
    - Если разработчик - учитывает текущий режим

    Args:
        user_id: Telegram user ID
        admin_ids: Список ID админов

    Returns:
        True если показывать админ-интерфейс
    """
    # Если разработчик - проверяем текущий режим
    if is_developer(user_id):
        role = get_developer_role(user_id)
        return role == 'admin'

    # Для остальных - проверяем админ права
    return is_admin(user_id, admin_ids)
