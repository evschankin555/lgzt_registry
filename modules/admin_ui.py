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
ITEMS_PER_PAGE = 10

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


async def get_company_detail(company_id: int) -> Optional[dict]:
    """
    Получить детали предприятия

    Args:
        company_id: ID предприятия

    Returns:
        dict с данными предприятия или None
    """
    async with SessionLocal() as session:
        result = await session.execute(
            select(Company).where(Company.id == company_id)
        )
        company = result.scalar_one_or_none()

        if not company:
            return None

        # Считаем пользователей по статусам
        stats_result = await session.execute(
            select(User.status, func.count(User.id))
            .where(User.company_id == company_id)
            .group_by(User.status)
        )
        stats = {row[0]: row[1] for row in stats_result.all()}

        return {
            'id': company.id,
            'name': company.name,
            'registered': stats.get('registered', 0),
            'not_registered': stats.get('not registered', 0),
            'blocked': stats.get('blocked', 0),
            'deleted': stats.get('deleted', 0),
            'total': sum(stats.values())
        }


async def get_company_users_page(company_id: int, page: int = 0) -> Tuple[List[dict], int]:
    """
    Получить страницу сотрудников предприятия

    Args:
        company_id: ID предприятия
        page: Номер страницы (с 0)

    Returns:
        Tuple[список пользователей, общее количество]
    """
    async with SessionLocal() as session:
        # Общее количество
        total_result = await session.execute(
            select(func.count(User.id)).where(User.company_id == company_id)
        )
        total = total_result.scalar() or 0

        # Получаем пользователей
        stmt = (
            select(User)
            .where(User.company_id == company_id)
            .order_by(User.last_name, User.first_name)
            .offset(page * ITEMS_PER_PAGE)
            .limit(ITEMS_PER_PAGE)
        )

        result = await session.execute(stmt)
        users = result.scalars().all()

        users_list = [
            {
                'id': u.id,
                'last_name': u.last_name,
                'first_name': u.first_name,
                'father_name': u.father_name or '',
                'status': u.status
            }
            for u in users
        ]

        return users_list, total


def build_company_card_keyboard(company_id: int, page: int, total_users: int) -> InlineKeyboardMarkup:
    """
    Построить клавиатуру карточки предприятия
    """
    keyboard = InlineKeyboardMarkup(row_width=1)

    # Пагинация сотрудников
    total_pages = (total_users + ITEMS_PER_PAGE - 1) // ITEMS_PER_PAGE if total_users > 0 else 1

    if total_pages > 1:
        nav_buttons = []

        if page > 0:
            nav_buttons.append(
                InlineKeyboardButton("◀️", callback_data=f"comp_users_{company_id}_{page - 1}")
            )

        nav_buttons.append(
            InlineKeyboardButton(f"{page + 1}/{total_pages}", callback_data="noop")
        )

        if page < total_pages - 1:
            nav_buttons.append(
                InlineKeyboardButton("▶️", callback_data=f"comp_users_{company_id}_{page + 1}")
            )

        keyboard.row(*nav_buttons)

    # Навигация
    keyboard.add(
        InlineKeyboardButton("↩️ К предприятиям", callback_data="admin_companies"),
        InlineKeyboardButton("🏠 В меню", callback_data="admin_menu")
    )

    return keyboard


async def show_company_card(bot: AsyncTeleBot, chat_id: int, message_id: int, company_id: int, page: int = 0):
    """
    Показать карточку предприятия со списком сотрудников
    """
    company = await get_company_detail(company_id)

    if not company:
        await safe_edit_message(bot, chat_id, message_id, "❌ Предприятие не найдено")
        return

    users, total_users = await get_company_users_page(company_id, page)

    # Формируем текст карточки
    text = (
        f"🏭 <b>{company['name']}</b>\n"
        f"ID: {company['id']}\n\n"
        f"📊 <b>Статистика:</b>\n"
        f"• 🟢 Зарегистрировано: {company['registered']}\n"
        f"• 🟡 Не зарегистрировано: {company['not_registered']}\n"
        f"• 🔴 Заблокировано: {company['blocked']}\n"
        f"• ⚫ Удалено: {company['deleted']}\n"
        f"• Всего: {company['total']}\n\n"
    )

    if users:
        text += "<b>👥 Сотрудники:</b>\n"
        for u in users:
            emoji = STATUS_EMOJI.get(u['status'], '⚪')
            full_name = f"{u['last_name']} {u['first_name']}"
            if u['father_name']:
                full_name += f" {u['father_name']}"
            text += f"{emoji} <code>{u['id']}</code> {full_name}\n"
    else:
        text += "📭 Сотрудников нет"

    keyboard = build_company_card_keyboard(company_id, page, total_users)

    await safe_edit_message(bot, chat_id, message_id, text, reply_markup=keyboard)


# ===== ПОЛЬЗОВАТЕЛИ =====

async def get_users_page(page: int = 0, status_filter: Optional[str] = None) -> Tuple[List[dict], int]:
    """
    Получить страницу всех пользователей

    Args:
        page: Номер страницы (с 0)
        status_filter: Фильтр по статусу (опционально)

    Returns:
        Tuple[список пользователей, общее количество]
    """
    async with SessionLocal() as session:
        # Базовый запрос
        base_query = select(User)
        count_query = select(func.count(User.id))

        if status_filter:
            base_query = base_query.where(User.status == status_filter)
            count_query = count_query.where(User.status == status_filter)

        # Общее количество
        total_result = await session.execute(count_query)
        total = total_result.scalar() or 0

        # Получаем пользователей с компанией
        stmt = (
            base_query
            .options(selectinload(User.company))
            .order_by(User.id.asc())
            .offset(page * ITEMS_PER_PAGE)
            .limit(ITEMS_PER_PAGE)
        )

        result = await session.execute(stmt)
        users = result.scalars().all()

        users_list = [
            {
                'id': u.id,
                'last_name': u.last_name,
                'first_name': u.first_name,
                'status': u.status,
                'company_name': u.company.name if u.company else 'Не назначено'
            }
            for u in users
        ]

        return users_list, total


def build_users_list_keyboard(users: List[dict], page: int, total: int, status_filter: Optional[str] = None) -> InlineKeyboardMarkup:
    """
    Построить клавиатуру списка пользователей с пагинацией
    """
    keyboard = InlineKeyboardMarkup(row_width=1)

    # Кнопки пользователей
    for user in users:
        emoji = STATUS_EMOJI.get(user['status'], '⚪')
        btn_text = f"{emoji} {user['id']}. {user['last_name']} {user['first_name']}"
        # Обрезаем текст если слишком длинный
        if len(btn_text) > 55:
            btn_text = btn_text[:52] + "..."
        keyboard.add(
            InlineKeyboardButton(btn_text, callback_data=f"user_{user['id']}")
        )

    # Пагинация
    total_pages = (total + ITEMS_PER_PAGE - 1) // ITEMS_PER_PAGE
    filter_suffix = f"_{status_filter}" if status_filter else ""

    if total_pages > 1:
        nav_buttons = []

        if page > 0:
            nav_buttons.append(
                InlineKeyboardButton("◀️", callback_data=f"users_page_{page - 1}{filter_suffix}")
            )

        nav_buttons.append(
            InlineKeyboardButton(f"{page + 1}/{total_pages}", callback_data="noop")
        )

        if page < total_pages - 1:
            nav_buttons.append(
                InlineKeyboardButton("▶️", callback_data=f"users_page_{page + 1}{filter_suffix}")
            )

        keyboard.row(*nav_buttons)

    # Фильтры по статусу
    keyboard.row(
        InlineKeyboardButton("🟢", callback_data="users_filter_registered"),
        InlineKeyboardButton("🟡", callback_data="users_filter_not registered"),
        InlineKeyboardButton("🔴", callback_data="users_filter_blocked"),
        InlineKeyboardButton("Все", callback_data="admin_users")
    )

    # Навигация
    keyboard.add(
        InlineKeyboardButton("🔍 Поиск", callback_data="admin_search"),
        InlineKeyboardButton("↩️ В меню", callback_data="admin_menu")
    )

    return keyboard


async def show_users_list(bot: AsyncTeleBot, chat_id: int, message_id: Optional[int] = None, page: int = 0, status_filter: Optional[str] = None):
    """
    Показать список пользователей с пагинацией
    """
    users, total = await get_users_page(page, status_filter)

    filter_text = ""
    if status_filter:
        filter_text = f" ({STATUS_TEXT.get(status_filter, status_filter)})"

    if not users:
        text = f"👥 <b>Пользователи{filter_text}</b>\n\n📭 Список пуст"
    else:
        text = f"👥 <b>Пользователи{filter_text}</b> (всего: {total})\n\n"
        text += "Нажмите на пользователя для просмотра:"

    keyboard = build_users_list_keyboard(users, page, total, status_filter)

    if message_id:
        await safe_edit_message(bot, chat_id, message_id, text, reply_markup=keyboard)
    else:
        await safe_send_message(bot, chat_id, text, reply_markup=keyboard)


# ===== КАРТОЧКА ПОЛЬЗОВАТЕЛЯ =====

async def get_user_detail(user_id: int) -> Optional[dict]:
    """
    Получить детали пользователя

    Args:
        user_id: ID пользователя

    Returns:
        dict с данными пользователя или None
    """
    async with SessionLocal() as session:
        result = await session.execute(
            select(User)
            .options(selectinload(User.company))
            .where(User.id == user_id)
        )
        user = result.scalar_one_or_none()

        if not user:
            return None

        return {
            'id': user.id,
            'last_name': user.last_name,
            'first_name': user.first_name,
            'father_name': user.father_name or '',
            'date_of_birth': user.date_of_birth,
            'phone_number': user.phone_number or 'Не указан',
            'address': user.address or 'Не указан',
            'status': user.status,
            'tg_id': user.tg_id,
            'company_id': user.company_id,
            'company_name': user.company.name if user.company else 'Не назначено',
            'registered_at': user.registered_at,
            'blocked_at': user.blocked_at
        }


def build_user_card_keyboard(user_id: int, company_id: Optional[int] = None) -> InlineKeyboardMarkup:
    """
    Построить клавиатуру карточки пользователя
    """
    keyboard = InlineKeyboardMarkup(row_width=2)

    # Действия с пользователем
    keyboard.add(
        InlineKeyboardButton("✏️ Изменить предпр.", callback_data=f"edit_user_company_{user_id}"),
        InlineKeyboardButton("🗑 Удалить", callback_data=f"delete_user_{user_id}")
    )

    # Навигация
    nav_buttons = []
    if company_id:
        nav_buttons.append(InlineKeyboardButton("↩️ К предприятию", callback_data=f"company_{company_id}"))

    nav_buttons.append(InlineKeyboardButton("👥 К пользователям", callback_data="admin_users"))
    nav_buttons.append(InlineKeyboardButton("🏠 В меню", callback_data="admin_menu"))

    keyboard.row(*nav_buttons)

    return keyboard


async def show_user_card(bot: AsyncTeleBot, chat_id: int, message_id: int, user_id: int):
    """
    Показать карточку пользователя
    """
    user = await get_user_detail(user_id)

    if not user:
        await safe_edit_message(bot, chat_id, message_id, "❌ Пользователь не найден")
        return

    # Формируем ФИО
    full_name = f"{user['last_name']} {user['first_name']}"
    if user['father_name']:
        full_name += f" {user['father_name']}"

    # Статус
    status_emoji = STATUS_EMOJI.get(user['status'], '⚪')
    status_text = STATUS_TEXT.get(user['status'], user['status'])

    # Дата рождения
    dob_str = user['date_of_birth'].strftime('%d.%m.%Y') if user['date_of_birth'] else 'Не указана'

    # Дата регистрации
    reg_str = user['registered_at'].strftime('%d.%m.%Y %H:%M') if user['registered_at'] else 'Не зарегистрирован'

    text = (
        f"👤 <b>{full_name}</b>\n\n"
        f"🆔 ID в базе: <code>{user['id']}</code>\n"
        f"📱 Telegram ID: <code>{user['tg_id'] or 'Не привязан'}</code>\n\n"
        f"📋 <b>Статус:</b> {status_emoji} {status_text}\n"
        f"🏭 <b>Предприятие:</b> {user['company_name']}\n\n"
        f"📅 Дата рождения: {dob_str}\n"
        f"📞 Телефон: {user['phone_number']}\n"
        f"🏠 Адрес: {user['address']}\n\n"
        f"📝 Дата регистрации: {reg_str}"
    )

    if user['blocked_at']:
        text += f"\n🚫 Заблокирован: {user['blocked_at'].strftime('%d.%m.%Y %H:%M')}"

    keyboard = build_user_card_keyboard(user_id, user['company_id'])

    await safe_edit_message(bot, chat_id, message_id, text, reply_markup=keyboard)


# ===== ПОИСК =====

async def search_users_page(query: str, page: int = 0) -> Tuple[List[dict], int]:
    """
    Поиск пользователей по ФИО, ID или телефону с пагинацией

    Args:
        query: Поисковый запрос
        page: Номер страницы

    Returns:
        Tuple[список пользователей, общее количество]
    """
    async with SessionLocal() as session:
        query_text = query.strip()
        # Создаем паттерны для обоих регистров (первая буква)
        pattern_original = f"%{query_text}%"
        pattern_lower = f"%{query_text.lower()}%"
        pattern_upper = f"%{query_text.upper()}%"
        pattern_capitalize = f"%{query_text.capitalize()}%"

        logger.info(f"Search query: '{query}', patterns: original='{pattern_original}', lower='{pattern_lower}', capitalize='{pattern_capitalize}'")

        # Базовые условия поиска - ищем по всем вариантам регистра
        search_conditions = (
            (User.last_name.like(pattern_original)) |
            (User.last_name.like(pattern_lower)) |
            (User.last_name.like(pattern_upper)) |
            (User.last_name.like(pattern_capitalize)) |
            (User.first_name.like(pattern_original)) |
            (User.first_name.like(pattern_lower)) |
            (User.first_name.like(pattern_upper)) |
            (User.first_name.like(pattern_capitalize)) |
            (User.father_name.like(pattern_original)) |
            (User.father_name.like(pattern_lower)) |
            (User.father_name.like(pattern_upper)) |
            (User.father_name.like(pattern_capitalize)) |
            (User.phone_number.like(pattern_original))
        )

        # Если это число - добавляем поиск по ID
        if query.strip().isdigit():
            user_id = int(query.strip())
            search_conditions = search_conditions | (User.id == user_id)

        # Общее количество
        count_result = await session.execute(
            select(func.count(User.id)).where(search_conditions)
        )
        total = count_result.scalar() or 0

        logger.info(f"Search found {total} results for '{query}'")

        # Получаем пользователей с пагинацией
        stmt = (
            select(User)
            .options(selectinload(User.company))
            .where(search_conditions)
            .order_by(User.id.asc())
            .offset(page * ITEMS_PER_PAGE)
            .limit(ITEMS_PER_PAGE)
        )

        result = await session.execute(stmt)
        users = result.scalars().all()

        logger.info(f"Search returned {len(users)} users on page {page}")

        users_list = [
            {
                'id': u.id,
                'last_name': u.last_name,
                'first_name': u.first_name,
                'status': u.status,
                'company_name': u.company.name if u.company else 'Не назначено'
            }
            for u in users
        ]

        return users_list, total


def build_search_results_keyboard(users: List[dict], query: str, page: int, total: int) -> InlineKeyboardMarkup:
    """
    Построить клавиатуру результатов поиска с пагинацией
    """
    keyboard = InlineKeyboardMarkup(row_width=1)

    for user in users:
        emoji = STATUS_EMOJI.get(user['status'], '⚪')
        btn_text = f"{emoji} {user['id']}. {user['last_name']} {user['first_name']}"
        if len(btn_text) > 55:
            btn_text = btn_text[:52] + "..."
        keyboard.add(
            InlineKeyboardButton(btn_text, callback_data=f"user_{user['id']}")
        )

    # Пагинация
    total_pages = (total + ITEMS_PER_PAGE - 1) // ITEMS_PER_PAGE
    if total_pages > 1:
        nav_buttons = []

        if page > 0:
            nav_buttons.append(
                InlineKeyboardButton("◀️", callback_data=f"search_page_{page - 1}")
            )

        nav_buttons.append(
            InlineKeyboardButton(f"{page + 1}/{total_pages}", callback_data="noop")
        )

        if page < total_pages - 1:
            nav_buttons.append(
                InlineKeyboardButton("▶️", callback_data=f"search_page_{page + 1}")
            )

        keyboard.row(*nav_buttons)

    keyboard.add(
        InlineKeyboardButton("🔍 Новый поиск", callback_data="admin_search"),
        InlineKeyboardButton("👥 К пользователям", callback_data="admin_users")
    )

    return keyboard


async def show_search_prompt(bot: AsyncTeleBot, chat_id: int, message_id: Optional[int] = None):
    """
    Показать приглашение к поиску
    """
    text = (
        "🔍 <b>Поиск пользователя</b>\n\n"
        "Введите для поиска:\n"
        "• Часть фамилии или имени\n"
        "• ID пользователя\n"
        "• Номер телефона\n\n"
        "Отправьте текст сообщением:"
    )

    keyboard = InlineKeyboardMarkup()
    keyboard.add(InlineKeyboardButton("👥 К пользователям", callback_data="admin_users"))

    if message_id:
        await safe_edit_message(bot, chat_id, message_id, text, reply_markup=keyboard)
    else:
        await safe_send_message(bot, chat_id, text, reply_markup=keyboard)


async def show_search_results(bot: AsyncTeleBot, chat_id: int, query: str, page: int = 0, message_id: Optional[int] = None) -> bool:
    """
    Показать результаты поиска с пагинацией

    Returns:
        True если найдены результаты, False если не найдено (нужно остаться в режиме поиска)
    """
    users, total = await search_users_page(query, page)

    if not users:
        text = (
            f"🔍 <b>Поиск: {query}</b>\n\n"
            f"❌ Ничего не найдено\n\n"
            f"Введите другой запрос или нажмите кнопку ниже:"
        )
        keyboard = InlineKeyboardMarkup()
        keyboard.add(InlineKeyboardButton("👥 К пользователям", callback_data="admin_users"))

        if message_id:
            await safe_edit_message(bot, chat_id, message_id, text, reply_markup=keyboard)
        else:
            await safe_send_message(bot, chat_id, text, reply_markup=keyboard)

        return False  # Не найдено - остаемся в режиме поиска
    else:
        text = f"🔍 <b>Поиск: {query}</b>\n\nНайдено: {total}\n\nВыберите пользователя:"
        keyboard = build_search_results_keyboard(users, query, page, total)

        if message_id:
            await safe_edit_message(bot, chat_id, message_id, text, reply_markup=keyboard)
        else:
            await safe_send_message(bot, chat_id, text, reply_markup=keyboard)

        return True  # Найдено - можно выйти из режима поиска


# ===== ИЗМЕНЕНИЕ ПРЕДПРИЯТИЯ =====

async def get_all_companies() -> List[dict]:
    """
    Получить все предприятия для выбора
    """
    async with SessionLocal() as session:
        result = await session.execute(
            select(Company).order_by(Company.id)
        )
        companies = result.scalars().all()

        return [{'id': c.id, 'name': c.name} for c in companies]


def build_company_select_keyboard(companies: List[dict], user_id: int, page: int = 0) -> InlineKeyboardMarkup:
    """
    Построить клавиатуру выбора предприятия
    """
    keyboard = InlineKeyboardMarkup(row_width=1)

    # Пагинация компаний (по 10 на страницу)
    start = page * ITEMS_PER_PAGE
    end = start + ITEMS_PER_PAGE
    page_companies = companies[start:end]

    for company in page_companies:
        btn_text = f"🏭 {company['id']}. {company['name']}"
        if len(btn_text) > 55:
            btn_text = btn_text[:52] + "..."
        keyboard.add(
            InlineKeyboardButton(btn_text, callback_data=f"set_company_{user_id}_{company['id']}")
        )

    # Пагинация
    total_pages = (len(companies) + ITEMS_PER_PAGE - 1) // ITEMS_PER_PAGE
    if total_pages > 1:
        nav_buttons = []

        if page > 0:
            nav_buttons.append(
                InlineKeyboardButton("◀️", callback_data=f"sel_comp_page_{user_id}_{page - 1}")
            )

        nav_buttons.append(
            InlineKeyboardButton(f"{page + 1}/{total_pages}", callback_data="noop")
        )

        if page < total_pages - 1:
            nav_buttons.append(
                InlineKeyboardButton("▶️", callback_data=f"sel_comp_page_{user_id}_{page + 1}")
            )

        keyboard.row(*nav_buttons)

    keyboard.add(
        InlineKeyboardButton("❌ Отмена", callback_data=f"user_{user_id}")
    )

    return keyboard


async def show_company_select(bot: AsyncTeleBot, chat_id: int, message_id: int, user_id: int, page: int = 0):
    """
    Показать выбор предприятия для пользователя
    """
    user = await get_user_detail(user_id)
    if not user:
        await safe_edit_message(bot, chat_id, message_id, "❌ Пользователь не найден")
        return

    companies = await get_all_companies()

    full_name = f"{user['last_name']} {user['first_name']}"
    text = (
        f"✏️ <b>Изменение предприятия</b>\n\n"
        f"Пользователь: {full_name}\n"
        f"Текущее: {user['company_name']}\n\n"
        f"Выберите новое предприятие:"
    )

    keyboard = build_company_select_keyboard(companies, user_id, page)

    await safe_edit_message(bot, chat_id, message_id, text, reply_markup=keyboard)


async def change_user_company(user_id: int, new_company_id: int) -> bool:
    """
    Изменить предприятие пользователя

    Returns:
        True если успешно
    """
    async with SessionLocal() as session:
        result = await session.execute(
            select(User).where(User.id == user_id)
        )
        user = result.scalar_one_or_none()

        if not user:
            return False

        user.company_id = new_company_id
        await session.commit()
        return True


# ===== УДАЛЕНИЕ ПОЛЬЗОВАТЕЛЯ =====

def build_delete_confirm_keyboard(user_id: int) -> InlineKeyboardMarkup:
    """
    Построить клавиатуру подтверждения удаления
    """
    keyboard = InlineKeyboardMarkup(row_width=2)
    keyboard.add(
        InlineKeyboardButton("✅ Да, удалить", callback_data=f"confirm_delete_{user_id}"),
        InlineKeyboardButton("❌ Отмена", callback_data=f"user_{user_id}")
    )
    return keyboard


async def show_delete_confirm(bot: AsyncTeleBot, chat_id: int, message_id: int, user_id: int):
    """
    Показать подтверждение удаления
    """
    user = await get_user_detail(user_id)
    if not user:
        await safe_edit_message(bot, chat_id, message_id, "❌ Пользователь не найден")
        return

    full_name = f"{user['last_name']} {user['first_name']}"
    if user['father_name']:
        full_name += f" {user['father_name']}"

    text = (
        f"⚠️ <b>Подтверждение удаления</b>\n\n"
        f"Вы уверены, что хотите удалить пользователя?\n\n"
        f"👤 {full_name}\n"
        f"🆔 ID: {user['id']}\n"
        f"🏭 {user['company_name']}\n\n"
        f"<i>Пользователь сможет зарегистрироваться снова.</i>"
    )

    keyboard = build_delete_confirm_keyboard(user_id)

    await safe_edit_message(bot, chat_id, message_id, text, reply_markup=keyboard)


async def delete_user(user_id: int) -> bool:
    """
    Удалить пользователя (установить статус deleted)

    Returns:
        True если успешно
    """
    async with SessionLocal() as session:
        result = await session.execute(
            select(User).where(User.id == user_id)
        )
        user = result.scalar_one_or_none()

        if not user:
            return False

        user.status = 'deleted'
        user.tg_id = None  # Отвязываем Telegram
        await session.commit()
        return True


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

        # Карточка предприятия
        elif data.startswith("company_"):
            company_id = int(data.split("_")[1])
            await show_company_card(bot, chat_id, message_id, company_id, page=0)
            await bot.answer_callback_query(call.id)

        # Пагинация сотрудников предприятия
        elif data.startswith("comp_users_"):
            parts = data.split("_")
            company_id = int(parts[2])
            page = int(parts[3])
            await show_company_card(bot, chat_id, message_id, company_id, page=page)
            await bot.answer_callback_query(call.id)

        # Список пользователей
        elif data == "admin_users":
            await show_users_list(bot, chat_id, message_id, page=0)
            await bot.answer_callback_query(call.id)

        # Пагинация пользователей
        elif data.startswith("users_page_"):
            parts = data.replace("users_page_", "").split("_", 1)
            page = int(parts[0])
            status_filter = parts[1] if len(parts) > 1 else None
            await show_users_list(bot, chat_id, message_id, page=page, status_filter=status_filter)
            await bot.answer_callback_query(call.id)

        # Фильтр пользователей по статусу
        elif data.startswith("users_filter_"):
            status_filter = data.replace("users_filter_", "")
            await show_users_list(bot, chat_id, message_id, page=0, status_filter=status_filter)
            await bot.answer_callback_query(call.id)

        # Карточка пользователя
        elif data.startswith("user_"):
            user_db_id = int(data.split("_")[1])
            await show_user_card(bot, chat_id, message_id, user_db_id)
            await bot.answer_callback_query(call.id)

        # Поиск - показать приглашение
        elif data == "admin_search":
            await show_search_prompt(bot, chat_id, message_id)
            await bot.answer_callback_query(call.id)
            # Устанавливаем состояние ожидания поиска
            return {"action": "set_search_state"}

        # Пагинация результатов поиска
        elif data.startswith("search_page_"):
            page = int(data.split("_")[2])
            await bot.answer_callback_query(call.id)
            # Возвращаем запрос на пагинацию поиска
            return {"action": "search_paginate", "page": page}

        # Изменение предприятия - показать выбор
        elif data.startswith("edit_user_company_"):
            user_db_id = int(data.split("_")[3])
            await show_company_select(bot, chat_id, message_id, user_db_id)
            await bot.answer_callback_query(call.id)

        # Пагинация выбора предприятия
        elif data.startswith("sel_comp_page_"):
            parts = data.split("_")
            user_db_id = int(parts[3])
            page = int(parts[4])
            await show_company_select(bot, chat_id, message_id, user_db_id, page)
            await bot.answer_callback_query(call.id)

        # Установка предприятия
        elif data.startswith("set_company_"):
            parts = data.split("_")
            user_db_id = int(parts[2])
            company_id = int(parts[3])
            success = await change_user_company(user_db_id, company_id)
            if success:
                await bot.answer_callback_query(call.id, "✅ Предприятие изменено")
                await show_user_card(bot, chat_id, message_id, user_db_id)
            else:
                await bot.answer_callback_query(call.id, "❌ Ошибка", show_alert=True)

        # Удаление - показать подтверждение
        elif data.startswith("delete_user_"):
            user_db_id = int(data.split("_")[2])
            await show_delete_confirm(bot, chat_id, message_id, user_db_id)
            await bot.answer_callback_query(call.id)

        # Подтверждение удаления
        elif data.startswith("confirm_delete_"):
            user_db_id = int(data.split("_")[2])
            success = await delete_user(user_db_id)
            if success:
                await bot.answer_callback_query(call.id, "✅ Пользователь удален")
                await show_user_card(bot, chat_id, message_id, user_db_id)
            else:
                await bot.answer_callback_query(call.id, "❌ Ошибка", show_alert=True)

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
