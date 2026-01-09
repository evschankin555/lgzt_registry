# modules/admin_ui.py
"""
Модуль админ-интерфейса с пагинацией и карточками
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Optional, List, Tuple
from telebot.async_telebot import AsyncTeleBot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery, Message
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload

from db import SessionLocal
from models import User, Company
from modules.auth import is_developer, get_developer_role
from modules.error_handler import safe_edit_message, safe_send_message

logger = logging.getLogger(__name__)

# Константы
ITEMS_PER_PAGE = 20

# Emoji для статусов
STATUS_EMOJI = {
    'registered': '🟢',
    'not registered': '🟡',
    'blocked': '🔴',
    'deleted': '⚫'
}

STATUS_TEXT = {
    'registered': 'Зарегистрирован',
    'not registered': 'Не зарегистрирован',
    'blocked': 'Заблокирован',
    'deleted': 'Удален'
}


async def get_stats() -> dict:
    """
    Получить статистику для главного меню админа

    Returns:
        dict с ключами: total_users, total_companies, registered_today, registered_week
    """
    async with SessionLocal() as session:
        now = datetime.now(timezone.utc)

        # Общее количество пользователей
        total_users_result = await session.execute(
            select(func.count(User.id))
        )
        total_users = total_users_result.scalar() or 0

        # Количество предприятий
        total_companies_result = await session.execute(
            select(func.count(Company.id))
        )
        total_companies = total_companies_result.scalar() or 0

        # Зарегистрировано сегодня
        registered_today_result = await session.execute(
            select(func.count(User.id)).where(
                User.status == 'registered',
                User.registered_at >= now - timedelta(hours=24)
            )
        )
        registered_today = registered_today_result.scalar() or 0

        # Зарегистрировано за неделю
        registered_week_result = await session.execute(
            select(func.count(User.id)).where(
                User.status == 'registered',
                User.registered_at >= now - timedelta(days=7)
            )
        )
        registered_week = registered_week_result.scalar() or 0

        # Всего зарегистрировано
        total_registered_result = await session.execute(
            select(func.count(User.id)).where(User.status == 'registered')
        )
        total_registered = total_registered_result.scalar() or 0

        return {
            'total_users': total_users,
            'total_companies': total_companies,
            'registered_today': registered_today,
            'registered_week': registered_week,
            'total_registered': total_registered
        }


def build_admin_menu_keyboard(user_id: int) -> InlineKeyboardMarkup:
    """
    Построить клавиатуру главного меню админа

    Args:
        user_id: ID пользователя (для проверки developer)
    """
    keyboard = InlineKeyboardMarkup(row_width=2)

    # Основные разделы
    keyboard.add(
        InlineKeyboardButton("🏭 Предприятия", callback_data="admin_companies"),
        InlineKeyboardButton("👥 Пользователи", callback_data="admin_users")
    )

    keyboard.add(
        InlineKeyboardButton("📊 Статистика", callback_data="admin_stats_detail"),
        InlineKeyboardButton("📥 Выгрузка Excel", callback_data="get_total_excel")
    )

    keyboard.add(
        InlineKeyboardButton("🔍 Поиск", callback_data="admin_search")
    )

    keyboard.add(
        InlineKeyboardButton("✏️ Изменить пользователя", callback_data="change_user_data"),
        InlineKeyboardButton("➕ Добавить волонтера", callback_data="add_volunteer")
    )

    # Кнопка переключения режима только для developer
    if is_developer(user_id):
        current_role = get_developer_role(user_id)
        if current_role == 'admin':
            keyboard.add(
                InlineKeyboardButton("🔄 Режим пользователя", callback_data="switch_to_user")
            )
        else:
            keyboard.add(
                InlineKeyboardButton("🔄 Режим админа", callback_data="switch_to_admin")
            )

    return keyboard


async def show_admin_menu(bot: AsyncTeleBot, chat_id: int, user_id: int, message_id: Optional[int] = None):
    """
    Показать главное меню админа с статистикой

    Args:
        bot: Экземпляр бота
        chat_id: ID чата
        user_id: ID пользователя
        message_id: ID сообщения для редактирования (опционально)
    """
    stats = await get_stats()

    text = (
        "📋 <b>Панель администратора</b>\n\n"
        "📊 <b>Статистика:</b>\n"
        f"• Всего в базе: {stats['total_users']}\n"
        f"• Зарегистрировано: {stats['total_registered']}\n"
        f"• Предприятий: {stats['total_companies']}\n"
        f"• За сегодня: {stats['registered_today']}\n"
        f"• За неделю: {stats['registered_week']}\n\n"
        "Выберите раздел:"
    )

    keyboard = build_admin_menu_keyboard(user_id)

    if message_id:
        await safe_edit_message(bot, chat_id, message_id, text, reply_markup=keyboard)
    else:
        await safe_send_message(bot, chat_id, text, reply_markup=keyboard)


async def get_companies_page(page: int = 0) -> Tuple[List[dict], int]:
    """
    Получить страницу предприятий с количеством сотрудников

    Args:
        page: Номер страницы (с 0)

    Returns:
        Tuple[список предприятий, общее количество]
    """
    async with SessionLocal() as session:
        # Общее количество
        total_result = await session.execute(select(func.count(Company.id)))
        total = total_result.scalar() or 0

        # Получаем предприятия с количеством пользователей
        stmt = (
            select(
                Company.id,
                Company.name,
                func.count(User.id).label("user_count")
            )
            .outerjoin(User, User.company_id == Company.id)
            .group_by(Company.id, Company.name)
            .order_by(Company.id)
            .offset(page * ITEMS_PER_PAGE)
            .limit(ITEMS_PER_PAGE)
        )

        result = await session.execute(stmt)
        rows = result.all()

        companies = [
            {'id': row[0], 'name': row[1], 'user_count': row[2]}
            for row in rows
        ]

        return companies, total


def build_companies_list_keyboard(companies: List[dict], page: int, total: int) -> InlineKeyboardMarkup:
    """
    Построить клавиатуру списка предприятий с пагинацией
    """
    keyboard = InlineKeyboardMarkup(row_width=1)

    # Кнопки предприятий
    for company in companies:
        btn_text = f"🏭 {company['id']}. {company['name']} ({company['user_count']} чел.)"
        # Обрезаем текст если слишком длинный
        if len(btn_text) > 60:
            btn_text = btn_text[:57] + "..."
        keyboard.add(
            InlineKeyboardButton(btn_text, callback_data=f"company_{company['id']}")
        )

    # Пагинация
    total_pages = (total + ITEMS_PER_PAGE - 1) // ITEMS_PER_PAGE
    if total_pages > 1:
        nav_buttons = []

        if page > 0:
            nav_buttons.append(
                InlineKeyboardButton("◀️", callback_data=f"companies_page_{page - 1}")
            )

        nav_buttons.append(
            InlineKeyboardButton(f"{page + 1}/{total_pages}", callback_data="noop")
        )

        if page < total_pages - 1:
            nav_buttons.append(
                InlineKeyboardButton("▶️", callback_data=f"companies_page_{page + 1}")
            )

        keyboard.row(*nav_buttons)

    # Навигация
    keyboard.add(
        InlineKeyboardButton("🔍 Поиск", callback_data="admin_search"),
        InlineKeyboardButton("↩️ В меню", callback_data="admin_menu")
    )

    return keyboard


async def show_companies_list(bot: AsyncTeleBot, chat_id: int, message_id: Optional[int] = None, page: int = 0):
    """
    Показать список предприятий с пагинацией
    """
    companies, total = await get_companies_page(page)

    if not companies:
        text = "🏭 <b>Предприятия</b>\n\n📭 Список пуст"
    else:
        text = f"🏭 <b>Предприятия</b> (всего: {total})\n\n"
        text += "Нажмите на предприятие для просмотра:"

    keyboard = build_companies_list_keyboard(companies, page, total)

    if message_id:
        await safe_edit_message(bot, chat_id, message_id, text, reply_markup=keyboard)
    else:
        await safe_send_message(bot, chat_id, text, reply_markup=keyboard)


async def handle_admin_callback(call: CallbackQuery, bot: AsyncTeleBot):
    """
    Обработчик callback'ов админ-панели

    Args:
        call: CallbackQuery объект
        bot: Экземпляр бота
    """
    user_id = call.from_user.id
    chat_id = call.message.chat.id
    message_id = call.message.message_id
    data = call.data

    try:
        # Главное меню админа
        if data == "admin_menu":
            await show_admin_menu(bot, chat_id, user_id, message_id)
            await bot.answer_callback_query(call.id)

        # Список предприятий
        elif data == "admin_companies":
            await show_companies_list(bot, chat_id, message_id, page=0)
            await bot.answer_callback_query(call.id)

        # Пагинация предприятий
        elif data.startswith("companies_page_"):
            page = int(data.split("_")[2])
            await show_companies_list(bot, chat_id, message_id, page=page)
            await bot.answer_callback_query(call.id)

        # Заглушка для noop
        elif data == "noop":
            await bot.answer_callback_query(call.id)

        # Неизвестный callback
        else:
            logger.warning(f"Unknown admin callback: {data}")
            return False  # Не обработан

        return True  # Обработан

    except Exception as e:
        logger.error(f"Error handling admin callback {data}: {e}", exc_info=True)
        await bot.answer_callback_query(call.id, "Произошла ошибка", show_alert=True)
        return True
