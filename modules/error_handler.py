# modules/error_handler.py
"""
Централизованная обработка ошибок для всех обработчиков бота
"""

import logging
import functools
from telebot.async_telebot import AsyncTeleBot
from telebot.apihelper import ApiTelegramException

logger = logging.getLogger(__name__)


class BotError(Exception):
    """Базовый класс для ошибок бота"""
    pass


class UserNotFoundError(BotError):
    """Пользователь не найден в БД"""
    pass


class CompanyNotFoundError(BotError):
    """Предприятие не найдено в БД"""
    pass


class AccessDeniedError(BotError):
    """Доступ запрещен"""
    pass


def handle_errors(func):
    """
    Декоратор для обработки ошибок в callback handlers

    Использование:
        @handle_errors
        async def my_handler(call):
            ...
    """
    @functools.wraps(func)
    async def wrapper(*args, **kwargs):
        # Определяем call/message из аргументов
        call_or_message = args[0] if args else None
        bot = kwargs.get('bot') or (args[1] if len(args) > 1 else None)

        try:
            return await func(*args, **kwargs)

        except UserNotFoundError:
            logger.warning(f"User not found in {func.__name__}")
            if hasattr(call_or_message, 'id'):  # callback_query
                try:
                    await bot.answer_callback_query(
                        call_or_message.id,
                        "Пользователь не найден",
                        show_alert=True
                    )
                except Exception:
                    pass

        except CompanyNotFoundError:
            logger.warning(f"Company not found in {func.__name__}")
            if hasattr(call_or_message, 'id'):
                try:
                    await bot.answer_callback_query(
                        call_or_message.id,
                        "Предприятие не найдено",
                        show_alert=True
                    )
                except Exception:
                    pass

        except AccessDeniedError:
            logger.warning(f"Access denied in {func.__name__}")
            if hasattr(call_or_message, 'id'):
                try:
                    await bot.answer_callback_query(
                        call_or_message.id,
                        "Доступ запрещен",
                        show_alert=True
                    )
                except Exception:
                    pass

        except ApiTelegramException as e:
            error_msg = str(e)

            # Сообщение не изменилось
            if "message is not modified" in error_msg:
                logger.debug(f"Message not modified in {func.__name__}")
                if hasattr(call_or_message, 'id'):
                    try:
                        await bot.answer_callback_query(call_or_message.id)
                    except Exception:
                        pass

            # Сообщение удалено или недоступно
            elif "message to edit not found" in error_msg or "message can't be edited" in error_msg:
                logger.warning(f"Message not found/editable in {func.__name__}")
                if hasattr(call_or_message, 'id'):
                    try:
                        await bot.answer_callback_query(
                            call_or_message.id,
                            "Сообщение устарело. Используйте /start",
                            show_alert=True
                        )
                    except Exception:
                        pass

            # Другие ошибки Telegram API
            else:
                logger.error(f"Telegram API error in {func.__name__}: {e}")
                if hasattr(call_or_message, 'id'):
                    try:
                        await bot.answer_callback_query(
                            call_or_message.id,
                            "Произошла ошибка. Попробуйте позже.",
                            show_alert=True
                        )
                    except Exception:
                        pass

        except Exception as e:
            logger.error(f"Unexpected error in {func.__name__}: {e}", exc_info=True)
            if hasattr(call_or_message, 'id'):
                try:
                    await bot.answer_callback_query(
                        call_or_message.id,
                        "Произошла ошибка. Попробуйте позже.",
                        show_alert=True
                    )
                except Exception:
                    pass

    return wrapper


async def safe_edit_message(
    bot: AsyncTeleBot,
    chat_id: int,
    message_id: int,
    text: str,
    reply_markup=None,
    parse_mode: str = 'HTML'
) -> bool:
    """
    Безопасное редактирование сообщения с fallback на отправку нового

    Returns:
        True если успешно, False если ошибка
    """
    try:
        await bot.edit_message_text(
            text=text,
            chat_id=chat_id,
            message_id=message_id,
            reply_markup=reply_markup,
            parse_mode=parse_mode
        )
        return True

    except ApiTelegramException as e:
        error_msg = str(e)

        # Сообщение не изменилось - это ОК
        if "message is not modified" in error_msg:
            return True

        # Сообщение недоступно - отправляем новое
        if "message to edit not found" in error_msg or "message can't be edited" in error_msg:
            logger.warning(f"Message {message_id} not editable, sending new")
            try:
                await bot.send_message(
                    chat_id=chat_id,
                    text=text,
                    reply_markup=reply_markup,
                    parse_mode=parse_mode
                )
                return True
            except Exception as send_error:
                logger.error(f"Failed to send fallback message: {send_error}")
                return False

        logger.error(f"Failed to edit message: {e}")
        return False

    except Exception as e:
        logger.error(f"Unexpected error editing message: {e}")
        return False


async def safe_send_message(
    bot: AsyncTeleBot,
    chat_id: int,
    text: str,
    reply_markup=None,
    parse_mode: str = 'HTML'
) -> bool:
    """
    Безопасная отправка сообщения

    Returns:
        True если успешно, False если ошибка
    """
    try:
        await bot.send_message(
            chat_id=chat_id,
            text=text,
            reply_markup=reply_markup,
            parse_mode=parse_mode
        )
        return True

    except ApiTelegramException as e:
        logger.error(f"Failed to send message to {chat_id}: {e}")
        return False

    except Exception as e:
        logger.error(f"Unexpected error sending message: {e}")
        return False


async def safe_answer_callback(
    bot: AsyncTeleBot,
    callback_id: str,
    text: str = None,
    show_alert: bool = False
) -> bool:
    """
    Безопасный ответ на callback query

    Returns:
        True если успешно, False если ошибка
    """
    try:
        await bot.answer_callback_query(
            callback_id,
            text=text,
            show_alert=show_alert
        )
        return True

    except Exception as e:
        logger.debug(f"Failed to answer callback: {e}")
        return False
