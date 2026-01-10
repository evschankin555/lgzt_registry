# modules/user_ui.py
"""
Пользовательский интерфейс - форматирование сообщений для регистрации и профиля
"""

from typing import Tuple, List, Optional, Dict, Any
from datetime import datetime
from telebot.async_telebot import types
from db import SessionLocal
from models import User, Company
from sqlalchemy import select, func

# Константы
ITEMS_PER_PAGE = 5  # Компаний на странице при выборе

# Шаги регистрации
REGISTRATION_STEPS = {
    1: ("👤", "Фамилия"),
    2: ("📅", "Дата рождения"),
    3: ("✏️", "Имя и отчество"),
    4: ("📱", "Номер телефона"),
    5: ("🔐", "Код подтверждения"),
    6: ("🏠", "Адрес проживания"),
    7: ("🏢", "Предприятие"),
}

TOTAL_STEPS = len(REGISTRATION_STEPS)


def format_progress_bar(current: int, total: int, width: int = 14) -> str:
    """
    Генерация визуального прогресс-бара

    Args:
        current: Текущий шаг (1-based)
        total: Общее количество шагов
        width: Ширина прогресс-бара в символах

    Returns:
        Строка прогресс-бара, например: ━━━━●━━━━━━━━━
    """
    if current < 1:
        current = 1
    if current > total:
        current = total

    # Позиция маркера (0-based индекс в строке шириной width)
    position = int((current - 1) / (total - 1) * (width - 1)) if total > 1 else 0

    bar = ""
    for i in range(width):
        if i == position:
            bar += "●"
        else:
            bar += "━"

    return bar


def format_registration_header(step: int, title: Optional[str] = None) -> str:
    """
    Форматирование заголовка шага регистрации

    Args:
        step: Номер текущего шага (1-7)
        title: Опциональный заголовок (если не указан, берется из REGISTRATION_STEPS)

    Returns:
        Отформатированный заголовок с прогресс-баром
    """
    emoji, step_title = REGISTRATION_STEPS.get(step, ("📋", "Регистрация"))
    if title:
        step_title = title

    progress = format_progress_bar(step, TOTAL_STEPS)

    header = f"📋 <b>Регистрация</b> • Шаг {step} из {TOTAL_STEPS}\n"
    header += f"{progress}\n\n"
    header += f"{emoji} <b>{step_title}</b>\n"

    return header


def format_step_message(step: int, description: str, hint: Optional[str] = None) -> str:
    """
    Полное сообщение для шага регистрации

    Args:
        step: Номер шага
        description: Описание что нужно сделать
        hint: Подсказка/пример (опционально)

    Returns:
        Полностью отформатированное сообщение
    """
    message = format_registration_header(step)
    message += f"\n{description}"

    if hint:
        message += f"\n\n💡 <i>{hint}</i>"

    return message


def format_success_message(title: str, description: Optional[str] = None) -> str:
    """
    Сообщение об успехе

    Args:
        title: Заголовок
        description: Описание (опционально)

    Returns:
        Отформатированное сообщение
    """
    message = f"✅ <b>{title}</b>"
    if description:
        message += f"\n\n{description}"
    return message


def format_error_message(title: str, description: Optional[str] = None, hint: Optional[str] = None) -> str:
    """
    Сообщение об ошибке

    Args:
        title: Заголовок ошибки
        description: Описание проблемы
        hint: Подсказка как исправить

    Returns:
        Отформатированное сообщение
    """
    message = f"❌ <b>{title}</b>"
    if description:
        message += f"\n\n{description}"
    if hint:
        message += f"\n\n💡 <i>{hint}</i>"
    return message


def format_info_message(title: str, description: Optional[str] = None) -> str:
    """
    Информационное сообщение

    Args:
        title: Заголовок
        description: Описание

    Returns:
        Отформатированное сообщение
    """
    message = f"ℹ️ <b>{title}</b>"
    if description:
        message += f"\n\n{description}"
    return message


def format_phone_number(phone: str) -> str:
    """
    Форматирование номера телефона для отображения

    Args:
        phone: Номер в формате 79271234567

    Returns:
        Отформатированный номер: +7 927 123-45-67
    """
    if not phone or len(phone) < 11:
        return phone or "Не указан"

    # Убираем все кроме цифр
    digits = ''.join(filter(str.isdigit, phone))

    if len(digits) == 11:
        return f"+{digits[0]} {digits[1:4]} {digits[4:7]}-{digits[7:9]}-{digits[9:11]}"

    return phone


def format_date_readable(date_obj) -> str:
    """
    Форматирование даты в читаемый вид

    Args:
        date_obj: Объект даты или datetime

    Returns:
        Строка вида "09 января 2026"
    """
    if not date_obj:
        return "Не указана"

    months = {
        1: "января", 2: "февраля", 3: "марта", 4: "апреля",
        5: "мая", 6: "июня", 7: "июля", 8: "августа",
        9: "сентября", 10: "октября", 11: "ноября", 12: "декабря"
    }

    if isinstance(date_obj, str):
        return date_obj

    day = date_obj.day
    month = months.get(date_obj.month, "")
    year = date_obj.year

    return f"{day} {month} {year}"


def format_datetime_readable(dt_obj) -> str:
    """
    Форматирование даты и времени

    Args:
        dt_obj: Объект datetime

    Returns:
        Строка вида "09 января 2026, 14:30"
    """
    if not dt_obj:
        return "Не указано"

    date_str = format_date_readable(dt_obj)
    time_str = dt_obj.strftime("%H:%M")

    return f"{date_str}, {time_str}"


def format_user_profile(user_data: Dict[str, Any]) -> str:
    """
    Форматирование карточки профиля пользователя

    Args:
        user_data: Словарь с данными пользователя:
            - id: ID в базе
            - last_name, first_name, father_name: ФИО
            - date_of_birth: Дата рождения
            - phone_number: Телефон
            - address: Адрес
            - company_name: Название предприятия
            - registered_at: Дата регистрации

    Returns:
        Отформатированная карточка профиля
    """
    separator = "━" * 16

    # ФИО
    fio_parts = [
        user_data.get('last_name', ''),
        user_data.get('first_name', ''),
        user_data.get('father_name', '')
    ]
    fio = ' '.join(p for p in fio_parts if p).strip() or "Не указано"

    # Форматируем данные
    phone = format_phone_number(user_data.get('phone_number', ''))
    dob = format_date_readable(user_data.get('date_of_birth'))
    registered = format_datetime_readable(user_data.get('registered_at'))
    address = user_data.get('address') or "Не указан"
    company = user_data.get('company_name') or "Не назначено"
    user_id = user_data.get('id', '—')

    profile = f"""👤 <b>Мой профиль</b>
{separator}

📋 <b>ID:</b> {user_id}

👤 <b>ФИО</b>
   {fio}

📅 <b>Дата рождения</b>
   {dob}

📱 <b>Телефон</b>
   {phone}

🏠 <b>Адрес</b>
   {address}

🏢 <b>Предприятие</b>
   {company}

📆 <b>Дата регистрации</b>
   {registered}"""

    return profile


async def get_user_profile_data(user_id: int) -> Optional[Dict[str, Any]]:
    """
    Получение данных пользователя для профиля

    Args:
        user_id: ID пользователя в базе

    Returns:
        Словарь с данными или None
    """
    async with SessionLocal() as session:
        user = await session.get(User, user_id)

        if not user:
            return None

        company_name = None
        if user.company_id:
            company = await session.get(Company, user.company_id)
            if company:
                company_name = company.name

        return {
            'id': user.id,
            'last_name': user.last_name,
            'first_name': user.first_name,
            'father_name': user.father_name,
            'date_of_birth': user.date_of_birth,
            'phone_number': user.phone_number,
            'address': user.address,
            'company_name': company_name,
            'registered_at': user.registered_at,
            'status': user.status,
        }


async def get_companies_for_selection(page: int = 0) -> Tuple[List[Dict], int]:
    """
    Получение списка предприятий для выбора пользователем

    Args:
        page: Номер страницы (0-based)

    Returns:
        Tuple[список предприятий, общее количество страниц]
    """
    async with SessionLocal() as session:
        # Считаем общее количество
        count_stmt = select(func.count(Company.id))
        total_count = await session.scalar(count_stmt)
        total_pages = (total_count + ITEMS_PER_PAGE - 1) // ITEMS_PER_PAGE if total_count > 0 else 1

        # Получаем страницу
        stmt = (
            select(Company)
            .order_by(Company.name.asc())
            .offset(page * ITEMS_PER_PAGE)
            .limit(ITEMS_PER_PAGE)
        )

        result = await session.execute(stmt)
        companies = result.scalars().all()

        return [{'id': c.id, 'name': c.name} for c in companies], total_pages


def build_company_selection_keyboard(
    companies: List[Dict],
    page: int,
    total_pages: int
) -> types.InlineKeyboardMarkup:
    """
    Создание клавиатуры для выбора предприятия

    Args:
        companies: Список предприятий
        page: Текущая страница
        total_pages: Всего страниц

    Returns:
        InlineKeyboardMarkup
    """
    markup = types.InlineKeyboardMarkup(row_width=1)

    # Кнопки предприятий
    for company in companies:
        markup.add(types.InlineKeyboardButton(
            text=f"🏭 {company['name']}",
            callback_data=f"reg_company_{company['id']}"
        ))

    # Навигация
    nav_buttons = []

    if page > 0:
        nav_buttons.append(types.InlineKeyboardButton(
            text="◀️ Назад",
            callback_data=f"reg_comp_page_{page - 1}"
        ))

    if total_pages > 1:
        nav_buttons.append(types.InlineKeyboardButton(
            text=f"{page + 1}/{total_pages}",
            callback_data="noop"
        ))

    if page < total_pages - 1:
        nav_buttons.append(types.InlineKeyboardButton(
            text="Вперед ▶️",
            callback_data=f"reg_comp_page_{page + 1}"
        ))

    if nav_buttons:
        markup.row(*nav_buttons)

    return markup


async def show_company_selection(
    bot,
    chat_id: int,
    page: int = 0,
    message_id: Optional[int] = None
) -> None:
    """
    Показать выбор предприятия

    Args:
        bot: Объект бота
        chat_id: ID чата
        page: Страница
        message_id: ID сообщения для редактирования
    """
    companies, total_pages = await get_companies_for_selection(page)

    # Заголовок с прогрессом
    header = format_registration_header(7, "Выбор предприятия")
    text = header + "\nВыберите ваше предприятие из списка:"

    markup = build_company_selection_keyboard(companies, page, total_pages)

    if message_id:
        try:
            await bot.edit_message_text(
                text=text,
                chat_id=chat_id,
                message_id=message_id,
                parse_mode='HTML',
                reply_markup=markup
            )
        except Exception:
            await bot.send_message(
                chat_id=chat_id,
                text=text,
                parse_mode='HTML',
                reply_markup=markup
            )
    else:
        await bot.send_message(
            chat_id=chat_id,
            text=text,
            parse_mode='HTML',
            reply_markup=markup
        )


def get_profile_keyboard() -> types.InlineKeyboardMarkup:
    """
    Клавиатура для профиля пользователя

    Returns:
        InlineKeyboardMarkup
    """
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton(
        text="✏️ Изменить данные",
        callback_data="profile_edit"
    ))
    return markup


# Тексты для шагов регистрации
STEP_MESSAGES = {
    1: {
        'description': "Пожалуйста, отправьте мне вашу фамилию.",
        'hint': "Введите фамилию точно как в документах"
    },
    2: {
        'description': "Пришлите вашу дату рождения.",
        'hint': "Формат: 01.01.2000"
    },
    3: {
        'description': "Пришлите имя и отчество.",
        'hint': "Например: Иван Иванович"
    },
    4: {
        'description': "Пришлите свой номер телефона.",
        'hint': "Без плюса, начиная с 7: 79271234567"
    },
    5: {
        'description': "Введите код из SMS.",
        'hint': "Код из 2 цифр"
    },
    6: {
        'description': "Введите свой адрес проживания.",
        'hint': "В свободной форме"
    },
    7: {
        'description': "Выберите предприятие, за которым вы закреплены.",
        'hint': None
    },
}


def get_step_text(step: int) -> str:
    """
    Получить полный текст для шага регистрации

    Args:
        step: Номер шага (1-7)

    Returns:
        Отформатированное сообщение
    """
    step_data = STEP_MESSAGES.get(step, {'description': '', 'hint': None})
    return format_step_message(
        step=step,
        description=step_data['description'],
        hint=step_data.get('hint')
    )
