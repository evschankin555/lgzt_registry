# modules/__init__.py
"""
Модули для улучшенного интерфейса бота lgzt_registry
"""

from .error_handler import handle_errors, safe_edit_message, safe_send_message
from .auth import require_admin, require_developer, is_admin, is_developer
from .logger import admin_logger

__all__ = [
    'handle_errors',
    'safe_edit_message',
    'safe_send_message',
    'require_admin',
    'require_developer',
    'is_admin',
    'is_developer',
    'admin_logger',
]
