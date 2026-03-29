import os
import asyncio
import logging
from vars import *
from vars import PRODUCTION_MODE
from functions import *
from functions import check_volunteer_exists
from modules.auth import (
    is_developer, get_developer_role, set_developer_role, should_show_as_admin
)
from modules.logger import log_role_switch, setup_logging
from modules.admin_ui import (
    show_admin_menu, show_companies_list, handle_admin_callback,
    show_search_results, show_volunteer_added, show_edit_volunteer_name_prompt,
    update_volunteer_name, show_volunteer_card, show_company_search_results
)
from modules.user_ui import (
    format_step_message, format_success_message, format_error_message,
    format_user_profile, get_user_profile_data, get_profile_keyboard,
    show_company_selection, get_step_text
)
from modules.auto_migrate import check_and_migrate
from services.platform import sync_telegram_platform_data

# Настройка логирования
setup_logging()
logger = logging.getLogger(__name__)


def _repair_text_encoding(text: str) -> str:
    """
    Попытаться восстановить типичную mojibake-перекодировку (UTF-8 -> latin1/cp1251).
    """
    if not text:
        return ""

    candidates = [text]
    for src, dst in (("latin1", "utf-8"), ("cp1251", "utf-8")):
        try:
            candidates.append(text.encode(src).decode(dst))
        except UnicodeError:
            continue

    def cyrillic_score(value: str) -> int:
        value = value.lower()
        return sum(1 for ch in value if ("а" <= ch <= "я") or ch == "ё")

    repaired = max(candidates, key=cyrillic_score)
    if repaired != text:
        logger.warning("Detected mojibake input: original=%r repaired=%r", text, repaired)
    return repaired


def _normalize_user_text(text: str) -> str:
    repaired = _repair_text_encoding((text or "").strip())
    normalized = " ".join(repaired.split()).lower()
    return normalized.replace("ё", "е")


def _is_registration_trigger(text: str) -> bool:
    return _normalize_user_text(text) in {"регистрация", "/регистрация"}


def _is_profile_trigger(text: str) -> bool:
    return _normalize_user_text(text) in {"мой профиль", "профиль", "/профиль"}


@bot.message_handler(['start'])
async def start(msg):

    user_id = msg.from_user.id
    await bot.delete_state(user_id=user_id, chat_id=msg.chat.id)

    # Проверяем, показывать ли админ-интерфейс
    # Для developer учитывается текущий режим (admin/user)
    show_admin = should_show_as_admin(user_id, admin_ids)

    if show_admin:
        # Используем новое компактное админ-меню с одним сообщением
        await show_admin_menu(bot, msg.chat.id, user_id)
        await bot.set_state(user_id=user_id, chat_id=msg.chat.id, state=MyStates.admin_menu)

    elif await is_volunteer(user_id):
        await update_volunteer_tg_name(user_id, msg.from_user.first_name, msg.from_user.last_name)
        await bot.send_message(chat_id=msg.chat.id, text='Привет, волонтер! Ты можешь регистрировать пользователей. Для старта регистрации нажми кнопку "регистрация"', reply_markup=markup_default_volunteer)

    else:
        # Обычный пользователь
        # Если это developer в режиме user, показываем кнопку переключения (только в dev режиме)
        if is_developer(user_id) and not PRODUCTION_MODE:
            await bot.send_message(chat_id=msg.chat.id, text="Добрый день! Это бот по регистрации актива г.о.Котельники. Заполните, пожалуйста, все поля и подтвердите номер телефона!", reply_markup=markup_default)
            await bot.send_message(
                chat_id=msg.chat.id,
                text="🔧 Режим разработчика: ПОЛЬЗОВАТЕЛЬ\nНажмите для переключения в режим админа:",
                reply_markup=markup_switch_to_admin
            )
        else:
            await bot.send_message(chat_id=msg.chat.id, text="Добрый день! Это бот по регистрации актива г.о.Котельники. Заполните, пожалуйста, все поля и подтвердите номер телефона!", reply_markup=markup_default)



@bot.message_handler(content_types='text', func=lambda message: _is_registration_trigger(message.text), state='*')
async def start_signup(msg):

    await bot.delete_state(user_id=msg.from_user.id, chat_id=msg.chat.id)
    user_tg_id = int(msg.from_user.id)

    user_id_in_db = await find_user_by_tg_id(user_tg_id)

    if user_id_in_db and await is_volunteer(user_tg_id) is False:
        text = format_error_message(
            "Вы уже зарегистрированы",
            "Ваш профиль уже существует в системе."
        )
        await bot.send_message(chat_id=msg.chat.id, text=text, parse_mode='HTML')
    else:
        text = "Введите номер волонтёра (если есть), или нажмите «Пропустить»."
        await bot.send_message(chat_id=msg.chat.id, text=text, reply_markup=markup_skip_volunteer_id)
        await bot.set_state(user_id=msg.from_user.id, chat_id=msg.chat.id, state=MyStates.handle_volunteer_id)

@bot.message_handler(content_types='text', func=lambda message: _is_profile_trigger(message.text), state='*')
async def show_profile(msg):

    user_tg_id = int(msg.from_user.id)

    user_id_in_db = await find_user_by_tg_id(user_tg_id)

    if user_id_in_db:
        # Получаем данные и форматируем красивую карточку
        user_data = await get_user_profile_data(user_id_in_db)
        if user_data:
            profile_text = format_user_profile(user_data)
            markup = get_profile_keyboard()
            await bot.send_message(
                chat_id=msg.chat.id,
                text=profile_text,
                parse_mode='HTML',
                reply_markup=markup
            )
        else:
            text = format_error_message("Ошибка", "Не удалось загрузить профиль.")
            await bot.send_message(chat_id=msg.chat.id, text=text, parse_mode='HTML')
    else:
        text = format_error_message(
            "Профиль не найден",
            "Вы еще не зарегистрировались в системе.",
            "Нажмите кнопку «Регистрация» чтобы начать"
        )
        await bot.send_message(chat_id=msg.chat.id, text=text, parse_mode='HTML', reply_markup=markup_default)



@bot.message_handler(content_types='text', state=[MyStates.handle_volunteer_id])
async def handle_volunteer_id(msg):
    text_input = msg.text.strip()
    try:
        vol_id = int(text_input)
    except ValueError:
        await bot.send_message(chat_id=msg.chat.id, text="Введите число — номер волонтёра, или нажмите «Пропустить».", reply_markup=markup_skip_volunteer_id)
        return

    if not await check_volunteer_exists(vol_id):
        await bot.send_message(chat_id=msg.chat.id, text="Волонтёр с таким номером не найден. Попробуйте ещё раз или нажмите «Пропустить».", reply_markup=markup_skip_volunteer_id)
        return

    async with bot.retrieve_data(msg.from_user.id, msg.chat.id) as data:
        data['volunteer_id'] = vol_id

    text = get_step_text(1)
    await bot.send_message(chat_id=msg.chat.id, text=text, parse_mode='HTML')
    await bot.set_state(user_id=msg.chat.id, chat_id=msg.from_user.id, state=MyStates.handle_surname)


@bot.message_handler(content_types='text', state=[MyStates.handle_surname])
async def handle_surname(msg):

    surname = msg.text.strip().capitalize()

    if await check_surname(surname):
        # Шаг 2: Дата рождения
        text = get_step_text(2)
        await bot.send_message(chat_id=msg.chat.id, text=text, parse_mode='HTML')

        async with bot.retrieve_data(msg.from_user.id, msg.chat.id) as data:
            data['surname'] = surname
            data['user_tg_id'] = msg.from_user.id

        await bot.set_state(chat_id=msg.chat.id, user_id=msg.chat.id, state=MyStates.handle_dob)

    else:
        text = format_error_message(
            "Фамилия не найдена",
            "Не вижу вашу фамилию в базе данных.",
            "Проверьте правильность написания и попробуйте снова"
        )
        await bot.send_message(chat_id=msg.chat.id, text=text, parse_mode='HTML')

@bot.message_handler(content_types='text', state=[MyStates.handle_dob])
async def handle_dob(msg):

    try:
        dob = datetime.strptime(msg.text, "%d.%m.%Y").date()

        async with bot.retrieve_data(msg.from_user.id, msg.chat.id) as data:
            data['dob'] = dob
            surname = data.get('surname')

        user = await check_dob_and_status(dob, surname)

        if user:
            # user exists in the db
            if user.status != 'registered':
                async with bot.retrieve_data(msg.from_user.id, msg.chat.id) as data:
                    data['id'] = user.id

                # Шаг 3: Имя и отчество
                text = get_step_text(3)
                await bot.send_message(chat_id=msg.chat.id, text=text, parse_mode='HTML')
                await bot.set_state(chat_id=msg.chat.id, user_id=msg.chat.id, state=MyStates.handle_names)

            else:
                text = format_error_message(
                    "Уже зарегистрированы",
                    "Вы уже зарегистрированы в системе."
                )
                await bot.send_message(chat_id=msg.chat.id, text=text, parse_mode='HTML')
                await bot.delete_state(user_id=msg.from_user.id, chat_id=msg.chat.id)

        else:
            text = format_error_message(
                "Пользователь не найден",
                "Не нашел пользователя с такой датой рождения.",
                "Проверьте данные и попробуйте снова"
            )
            await bot.send_message(chat_id=msg.chat.id, text=text, parse_mode='HTML')
    except:
        text = format_error_message(
            "Неверный формат",
            "Неправильный формат даты рождения.",
            "Используйте формат: 01.01.2000"
        )
        await bot.send_message(chat_id=msg.chat.id, text=text, parse_mode='HTML')


@bot.message_handler(content_types='text', state=[MyStates.handle_names])
async def handle_names(msg):

    user_string = msg.text
    user_str_to_list = user_string.split()

    if len(user_str_to_list) < 2:
        text = format_error_message(
            "Недостаточно данных",
            "Имя и отчество должны состоять как минимум из 2 слов.",
            "Например: Иван Иванович"
        )
        await bot.send_message(chat_id=msg.chat.id, text=text, parse_mode='HTML')

    else:
        name, father_name = await extract_name_father_name(user_str_to_list)

        async with bot.retrieve_data(msg.from_user.id, msg.chat.id) as data:
            data['name'] = name
            data['father_name'] = father_name

        # Шаг 4: Номер телефона
        text = get_step_text(4)
        await bot.send_message(chat_id=msg.chat.id, text=text, parse_mode='HTML')
        await bot.set_state(chat_id=msg.chat.id, user_id=msg.chat.id, state=MyStates.handle_phone_number)


@bot.message_handler(content_types='text', state=[MyStates.handle_phone_number])
async def handle_phone_number(msg):

    phone_number = msg.text.strip()

    # Проверка формата номера
    if not phone_number.isdigit() or len(phone_number) != 11 or not phone_number.startswith('7'):
        text = format_error_message(
            "Неверный формат",
            "Номер телефона должен состоять из 11 цифр и начинаться с 7.",
            "Например: 79271234567"
        )
        await bot.send_message(chat_id=msg.chat.id, text=text, parse_mode='HTML')
        return

    async with bot.retrieve_data(msg.from_user.id, msg.chat.id) as data:
        data['phone_number'] = phone_number

    # send an SMS code ...
    code = await send_code(phone_number)
    if not code:
        text = format_error_message(
            "Проблема с SMS",
            "Не удалось отправить код подтверждения.",
            "Попробуйте еще раз через минуту"
        )
        await bot.send_message(chat_id=msg.chat.id, text=text, parse_mode='HTML')
        return

    async with bot.retrieve_data(user_id=msg.from_user.id, chat_id=msg.chat.id) as data:
        data['code'] = code

    # Шаг 5: Код подтверждения
    text = get_step_text(5)
    await bot.send_message(chat_id=msg.chat.id, text=text, parse_mode='HTML')

    await bot.set_state(chat_id=msg.chat.id, user_id=msg.chat.id, state=MyStates.check_sms)



@bot.message_handler(content_types='text', state=[MyStates.check_sms])
async def check_sms(msg):

    code_from_user = msg.text.strip()

    async with bot.retrieve_data(user_id=msg.from_user.id, chat_id=msg.chat.id) as data:
        code_from_backend = data.get('code')

    if code_from_user == code_from_backend:
        async with bot.retrieve_data(user_id=msg.from_user.id, chat_id=msg.chat.id) as data:
            data['sms_code'] = code_from_user
            data['sms_confirmed_at'] = datetime.now().isoformat()

        # Шаг 6: Адрес проживания
        text = get_step_text(6)
        await bot.send_message(chat_id=msg.chat.id, text=text, parse_mode='HTML')

        await bot.set_state(chat_id=msg.chat.id, user_id=msg.chat.id, state=MyStates.handle_home_address)

    else:
        text = format_error_message(
            "Неверный код",
            "Код не совпадает. Попробуйте ввести еще раз.",
            "Проверьте SMS и введите код повторно"
        )
        await bot.send_message(chat_id=msg.chat.id, text=text, parse_mode='HTML')


@bot.message_handler(content_types='text', state=[MyStates.handle_home_address])
async def handle_home_address(msg):

    home_address = msg.text.strip()

    async with bot.retrieve_data(user_id=msg.from_user.id, chat_id=msg.chat.id) as data:
        data['home_address'] = home_address
        id_from_db = data['id']

    # Сообщение о NDA перед выбором предприятия
    text = f"""📋 <b>Регистрация</b> • Шаг 6 из 7
━━━━━━━━━━━●━━━

📄 <b>Соглашение о неразглашении</b>

Ваш ID: <code>{id_from_db}</code>

Перед выбором предприятия ознакомьтесь с информацией о неразглашении и подтвердите согласие."""

    await bot.send_message(chat_id=msg.chat.id, text=text, parse_mode='HTML', reply_markup=markup_agree_to_nda)



@bot.message_handler(content_types='text', state=[MyStates.handle_company])
async def handle_company(msg):

    try:
        company_id_from_user = int(msg.text.strip())

        company = await check_if_company_exists(company_id_from_user)

        if company is None:
            await bot.send_message(chat_id=msg.chat.id,
                                   text=f"Нет предприятия с таким номером.")

        else:

            company_id = company.id

            async with bot.retrieve_data(user_id=msg.from_user.id, chat_id=msg.chat.id) as data:

                user_id = data.get('id')

                if await assign_company(user_id, company_id):
                    await bot.send_message(chat_id=msg.chat.id,
                                           text=f"Предприятие выбрано успешно.")

                    if await register_user(data):

                        await bot.send_message(chat_id=msg.chat.id,
                                               text=f"Регистрация прошла успешно.")

                        user_info = await prepare_user_info(user_id)

                        await bot.send_message(chat_id=msg.chat.id,
                                               text=user_info)

                        await bot.send_message(chat_id=msg.chat.id,
                                               text="Если нужно исправить информацию, нажмите кнопку ниже.", reply_markup=markup_correct_info)

                        if await is_volunteer(int(msg.from_user.id)):

                            await bot.send_message(chat_id=msg.chat.id,
                                                   text='Для начала следующей регистрации нажмите кнопку "регистрация" ниже.',
                                                   reply_markup=markup_default_volunteer)

                        await bot.delete_state(user_id=msg.from_user.id, chat_id=msg.chat.id)


                    else:

                        await bot.send_message(chat_id=msg.chat.id,
                                               text=f"Регистрация не удалась, ошибка.")
                else:

                    await bot.send_message(chat_id=msg.chat.id,
                                           text=f"Ошибка при выборе компании.")

    except ValueError:

        await bot.send_message(chat_id=msg.chat.id,
                               text=f"Неверный номер предприятия. Введите число.")


@bot.message_handler(content_types='text', state=[MyStates.handle_info_correction])
async def handle_info_correction(msg):

    async with bot.retrieve_data(user_id=msg.from_user.id, chat_id=msg.chat.id) as data:

        user_id_in_db = data.get('id')
        username = data.get('name')
        user_last_name = data.get('surname')
        user_father_name = data.get('father_name')
        user_phone_number = data.get('phone_number')

    request = msg.text.strip()

    msg_to_admin = f"Запрос на исправление информации\n\nОт кого - ID в базе {user_id_in_db} {username} {user_father_name} {user_last_name} {user_phone_number}\n\nСообщение - {request}\n\nЧтобы изменить информацию, нажмите на кнопку ниже."

    await bot.send_message(chat_id=admin_ids[0], text=msg_to_admin, reply_markup=markup_change_user_data)
    await bot.delete_state(user_id=msg.from_user.id, chat_id=msg.chat.id)

@bot.message_handler(content_types='text', state=[MyStates.admin_read_user_id_for_edit])
async def admin_read_user_id_for_edit(msg):

    try:
        user_id = int(msg.text.strip())

        print("user id is", user_id)

        print('entering user info function')
        user_info = await prepare_user_info_for_admin(user_id)

        markup_edit_or_remove = types.InlineKeyboardMarkup()
        markup_edit_or_remove.add(types.InlineKeyboardButton(text=f'Изменить предпр. {emojize(":pencil:")}',
                                                             callback_data=f'changeusrcomp'))
        markup_edit_or_remove.add(
            types.InlineKeyboardButton(text=f'Удалить {emojize(":cross_mark:")}', callback_data=f'removeusr'))
        markup_edit_or_remove.add(
            types.InlineKeyboardButton(text=f'Отмена {emojize(":stop_sign:")}', callback_data='cancel'))

        await bot.send_message(chat_id=admin_ids[0], text=user_info, parse_mode='html', reply_markup=markup_edit_or_remove)


        async with bot.retrieve_data(user_id=msg.from_user.id, chat_id=msg.chat.id) as data:

            data['user_id_to_edit'] = user_id



    except ValueError:

        await bot.send_message(chat_id=admin_ids[0], text="Неправильный ID")


@bot.message_handler(content_types='text', state=[MyStates.admin_read_comp_id_for_edit])
async def admin_read_comp_id_for_edit(msg):

    try:
        new_comp_id = int(msg.text.strip())

        async with bot.retrieve_data(user_id=msg.from_user.id, chat_id=msg.chat.id) as data:

            user_id_to_edit = data['user_id_to_edit']


        await reassign_company(user_id_to_edit,new_comp_id)

        new_user_info = await prepare_user_info_for_admin(user_id_to_edit)

        await bot.send_message(chat_id=admin_ids[0], text=f"Предприятие {new_comp_id} назначено.\n\n{new_user_info}", parse_mode='html')
        await bot.set_state(chat_id=msg.chat.id, user_id=msg.from_user.id, state=MyStates.admin_menu)

    except ValueError:

        await bot.send_message(chat_id=admin_ids[0], text="Неправильный ID")


@bot.message_handler(content_types='text', state=[MyStates.admin_read_volunteer_id])
async def admin_read_volunteer_id(msg):

    try:
        user_tg_id = int(msg.text.strip())
    except:
        text = format_error_message(
            "Неверный формат",
            "Telegram ID должен быть числом.",
            "Попробуйте еще раз или нажмите Назад"
        )
        await bot.send_message(chat_id=msg.chat.id, text=text, parse_mode='HTML')
        return

    # Проверяем что ID похож на реальный Telegram ID (минимум 6 цифр)
    if user_tg_id < 100000:
        text = format_error_message(
            "Неверный Telegram ID",
            "Telegram ID должен содержать минимум 6 цифр.",
            "Проверьте ID и попробуйте снова"
        )
        await bot.send_message(chat_id=msg.chat.id, text=text, parse_mode='HTML')
        return

    # Пробуем получить имя пользователя через Telegram API
    volunteer_name = None
    try:
        chat_info = await bot.get_chat(user_tg_id)
        if chat_info.first_name:
            volunteer_name = chat_info.first_name
            if chat_info.last_name:
                volunteer_name += f" {chat_info.last_name}"
    except Exception as e:
        print(f"Could not get chat info for {user_tg_id}: {e}")
        # Если не удалось получить - оставляем None

    admin_id = msg.from_user.id
    success = await add_volunteer(user_tg_id, added_by=admin_id, name=volunteer_name)
    await show_volunteer_added(bot, msg.chat.id, user_tg_id, success)
    await bot.set_state(chat_id=msg.chat.id, user_id=msg.from_user.id, state=MyStates.admin_menu)


@bot.message_handler(content_types='text', state=[MyStates.admin_edit_volunteer_name])
async def admin_edit_volunteer_name(msg):
    """Обработка ввода имени волонтера"""
    new_name = msg.text.strip()

    if not new_name or len(new_name) > 255:
        text = format_error_message(
            "Неверное имя",
            "Имя должно быть от 1 до 255 символов.",
            "Попробуйте еще раз"
        )
        await bot.send_message(chat_id=msg.chat.id, text=text, parse_mode='HTML')
        return

    async with bot.retrieve_data(msg.from_user.id, msg.chat.id) as data:
        volunteer_id = data.get('edit_volunteer_id')

    if volunteer_id:
        success = await update_volunteer_name(volunteer_id, new_name)
        if success:
            text = format_success_message(
                "Имя обновлено",
                f"Новое имя: {new_name}"
            )
            await bot.send_message(chat_id=msg.chat.id, text=text, parse_mode='HTML')
            # Показываем обновленную карточку волонтера
            await show_volunteer_card(bot, msg.chat.id, None, volunteer_id)
        else:
            text = format_error_message("Ошибка", "Не удалось обновить имя.")
            await bot.send_message(chat_id=msg.chat.id, text=text, parse_mode='HTML')
    else:
        text = format_error_message("Ошибка", "Волонтер не найден.")
        await bot.send_message(chat_id=msg.chat.id, text=text, parse_mode='HTML')

    await bot.set_state(chat_id=msg.chat.id, user_id=msg.from_user.id, state=MyStates.admin_menu)


@bot.message_handler(content_types='text', state=[MyStates.admin_search])
async def admin_handle_search(msg):
    """Обработка поискового запроса пользователей"""
    query = msg.text.strip()

    if not query:
        await bot.send_message(chat_id=msg.chat.id, text="Введите текст для поиска")
        return

    # Сохраняем поисковый запрос для пагинации
    async with bot.retrieve_data(msg.from_user.id, msg.chat.id) as data:
        data['search_query'] = query

    found = await show_search_results(bot, msg.chat.id, query, page=0)

    if found:
        # Найдено - выходим из режима поиска
        await bot.set_state(chat_id=msg.chat.id, user_id=msg.from_user.id, state=MyStates.admin_menu)
    # Если не найдено - остаемся в режиме поиска (admin_search state)


@bot.message_handler(content_types='text', state=[MyStates.admin_search_companies])
async def admin_handle_company_search(msg):
    """Обработка поискового запроса предприятий"""
    query = msg.text.strip()

    if not query:
        await bot.send_message(chat_id=msg.chat.id, text="Введите текст для поиска")
        return

    # Сохраняем поисковый запрос для пагинации
    async with bot.retrieve_data(msg.from_user.id, msg.chat.id) as data:
        data['company_search_query'] = query

    found = await show_company_search_results(bot, msg.chat.id, query, page=0)

    if found:
        # Найдено - выходим из режима поиска
        await bot.set_state(chat_id=msg.chat.id, user_id=msg.from_user.id, state=MyStates.admin_menu)
    # Если не найдено - остаемся в режиме поиска


# Обработчик callback для админ-состояний
# Включает состояния, где пользователь может нажать "Назад" или другие кнопки
@bot.callback_query_handler(func=lambda call: True, state=[
    MyStates.admin_menu,
    MyStates.admin_read_user_id_for_edit,
    MyStates.admin_read_comp_id_for_edit,  # Для обработки кнопки "Отмена" при изменении предприятия
    MyStates.admin_read_volunteer_id,  # Для обработки кнопки "Назад" при добавлении волонтера
    MyStates.admin_search,
    MyStates.admin_search_companies,  # Для обработки кнопки "Назад" при поиске предприятий
    MyStates.admin_edit_volunteer_name
])
async def callback_admin_state(call):

    user_id = call.from_user.id

    # Сначала пробуем обработать через admin_ui
    admin_ui_callbacks = [
        'admin_menu', 'admin_companies', 'admin_stats_detail', 'admin_users',
        'admin_search', 'admin_search_companies', 'admin_add_volunteer', 'admin_volunteers', 'noop'
    ]
    admin_ui_prefixes = [
        'companies_page_', 'company_', 'comp_users_',
        'users_page_', 'users_filter_', 'user_',
        'edit_user_company_', 'sel_comp_page_', 'set_company_',
        'delete_user_', 'confirm_delete_', 'search_page_', 'search_comp_page_',
        'volunteers_page_', 'volunteer_', 'delete_volunteer_',
        'confirm_del_volunteer_', 'edit_volunteer_name_', 'reset_status_'
    ]

    if call.data in admin_ui_callbacks or any(call.data.startswith(p) for p in admin_ui_prefixes):
        result = await handle_admin_callback(call, bot)
        # Обработка специальных действий
        if isinstance(result, dict):
            action = result.get("action")
            if action == "set_admin_menu_state":
                await bot.set_state(user_id=user_id, chat_id=call.message.chat.id, state=MyStates.admin_menu)
            elif action == "set_search_state":
                await bot.set_state(user_id=user_id, chat_id=call.message.chat.id, state=MyStates.admin_search)
            elif action == "search_paginate":
                # Получаем сохраненный поисковый запрос и показываем нужную страницу
                async with bot.retrieve_data(user_id, call.message.chat.id) as data:
                    search_query = data.get('search_query', '')
                if search_query:
                    await show_search_results(bot, call.message.chat.id, search_query, result.get("page", 0), call.message.message_id)
            elif action == "set_company_search_state":
                await bot.set_state(user_id=user_id, chat_id=call.message.chat.id, state=MyStates.admin_search_companies)
            elif action == "company_search_paginate":
                # Получаем сохраненный поисковый запрос предприятий и показываем нужную страницу
                async with bot.retrieve_data(user_id, call.message.chat.id) as data:
                    search_query = data.get('company_search_query', '')
                if search_query:
                    await show_company_search_results(bot, call.message.chat.id, search_query, result.get("page", 0), call.message.message_id)
            elif action == "set_volunteer_state":
                await bot.set_state(user_id=user_id, chat_id=call.message.chat.id, state=MyStates.admin_read_volunteer_id)
            elif action == "set_edit_volunteer_name":
                volunteer_id = result.get("volunteer_id")
                async with bot.retrieve_data(user_id, call.message.chat.id) as data:
                    data['edit_volunteer_id'] = volunteer_id
                await show_edit_volunteer_name_prompt(bot, call.message.chat.id, volunteer_id, call.message.message_id)
                await bot.set_state(user_id=user_id, chat_id=call.message.chat.id, state=MyStates.admin_edit_volunteer_name)
        return

    if call.data == 'get_total_excel':

        print('Generating an excel file...')

        await bot.send_message(chat_id=user_id,
                               text="Собираю файл, подождите...")

        await generate_excel()

        file = types.InputFile("excel_dump.xlsx")

        await bot.send_document(chat_id=user_id, document=file)

    elif call.data == 'get_comp_stats':

        comp_stats = await gather_company_stats()
        comp_stats = f"Статистика по предприятиям\n\n{comp_stats}"

        await bot.send_message(chat_id=user_id,
                               text=comp_stats)

    elif call.data == 'get_user_stats':

        user_stats = await get_user_stats()

        await bot.send_message(chat_id=user_id,
                               text=user_stats)

    elif call.data == 'change_user_data':

        print("Changing user data....")

        if user_id in superadmin_ids:

            await bot.send_message(chat_id=user_id,
                                   text="Пришлите мне ID пользователя, предприятие которого нужно изменить (или которого удалить).")

            await bot.set_state(chat_id=user_id, user_id=user_id, state=MyStates.admin_read_user_id_for_edit)

        else:

            await bot.send_message(chat_id=user_id,
                                   text=f"У вас нет прав на изменение данных.")


    elif call.data == 'cancel':

        await bot.delete_message(chat_id=call.message.chat.id, message_id=call.message.message_id)
        await bot.set_state(user_id=call.from_user.id, chat_id=call.message.chat.id, state=MyStates.admin_menu)

    elif 'removeusr' in call.data:

        print('got call removeusr')

        async with bot.retrieve_data(user_id=call.from_user.id, chat_id=call.message.chat.id) as data:

            user_id_to_remove = data['user_id_to_edit']

        await remove_user(user_id_to_remove)

        new_user_info = await prepare_user_info_for_admin(user_id_to_remove)

        await bot.edit_message_text(text=new_user_info, chat_id=call.message.chat.id, message_id=call.message.message_id, parse_mode='html')

        await bot.send_message(chat_id=user_id,
                               text="Пользователь удален и теперь может зарегистрироваться снова.")


    elif 'changeusrcomp' in call.data:

        print('got call changeusrcomp')



        company_list = await get_company_list()

        await bot.edit_message_reply_markup(chat_id=call.message.chat.id, message_id=call.message.message_id,reply_markup=types.InlineKeyboardMarkup())

        await bot.send_message(chat_id=user_id,
                               text=f"Пришли мне номер предприятия, за которым нужно закрепить этого пользователя. Отправь только номер.\n\n{company_list}")

        await bot.set_state(chat_id=user_id, user_id=user_id, state=MyStates.admin_read_comp_id_for_edit)


    # Обработка переключения режимов для developer (в состоянии admin_menu)
    # Скрыто в продакшн режиме
    elif call.data == 'switch_to_user':
        if is_developer(user_id) and not PRODUCTION_MODE:
            set_developer_role(user_id, 'user')
            log_role_switch(user_id, 'user')
            await bot.answer_callback_query(call.id, "Переключено в режим пользователя")
            try:
                await bot.delete_message(chat_id=call.message.chat.id, message_id=call.message.message_id)
            except:
                pass
            await bot.send_message(chat_id=user_id, text="Добрый день! Это бот по регистрации актива г.о.Котельники. Заполните, пожалуйста, все поля и подтвердите номер телефона!", reply_markup=markup_default)
            await bot.send_message(
                chat_id=user_id,
                text="🔧 Режим разработчика: ПОЛЬЗОВАТЕЛЬ\nНажмите для переключения в режим админа:",
                reply_markup=markup_switch_to_admin
            )
            await bot.delete_state(user_id=user_id, chat_id=call.message.chat.id)
        else:
            await bot.answer_callback_query(call.id, "Только для разработчиков", show_alert=True)

    elif call.data == 'switch_to_admin':
        if is_developer(user_id) and not PRODUCTION_MODE:
            set_developer_role(user_id, 'admin')
            log_role_switch(user_id, 'admin')
            await bot.answer_callback_query(call.id, "Переключено в режим админа")
            try:
                await bot.delete_message(chat_id=call.message.chat.id, message_id=call.message.message_id)
            except:
                pass
            # Используем новое компактное админ-меню
            await show_admin_menu(bot, user_id, user_id)
            await bot.set_state(user_id=user_id, chat_id=call.message.chat.id, state=MyStates.admin_menu)
        else:
            await bot.answer_callback_query(call.id, "Только для разработчиков", show_alert=True)


@bot.my_chat_member_handler(func=lambda member: member.new_chat_member.status == 'kicked' and member.chat.type == 'private')
async def bot_blocked(mb):
    print('юзер заблокал бота', mb.chat.id)

    user_id = int(mb.chat.id)

    await record_block(user_id)



def is_user_flow_callback(call):
    user_flow_callbacks = {
        'skip_volunteer_id',
        'agreed_to_nda',
        'profile_edit',
        'correct_info',
        'correct_info_cancel',
        'switch_to_user',
        'switch_to_admin',
    }
    return (
        call.data in user_flow_callbacks
        or call.data.startswith('reg_comp_page_')
        or call.data.startswith('reg_company_')
    )


@bot.callback_query_handler(func=is_user_flow_callback, state='*')
async def callback_any_state(call):

    user_id = call.from_user.id

    # Обработка выбора предприятия при регистрации (кнопки с пагинацией)
    if call.data.startswith('reg_comp_page_'):
        await bot.answer_callback_query(call.id)
        page = int(call.data.replace('reg_comp_page_', ''))
        await show_company_selection(bot, call.message.chat.id, page, call.message.message_id)
        return

    if call.data.startswith('reg_company_'):
        await bot.answer_callback_query(call.id)
        try:
            company_id = int(call.data.replace('reg_company_', ''))
        except ValueError:
            text = format_error_message("Ошибка", "Некорректный идентификатор предприятия.")
            await bot.send_message(chat_id=user_id, text=text, parse_mode='HTML')
            return

        try:
            async with bot.retrieve_data(user_id=user_id, chat_id=call.message.chat.id) as data:
                user_db_id = data.get('id')

            if not user_db_id:
                text = format_error_message(
                    "Сессия регистрации устарела",
                    "Данные регистрации не найдены.",
                    "Нажмите /start и начните регистрацию заново"
                )
                await bot.send_message(chat_id=user_id, text=text, parse_mode='HTML')
                await bot.delete_state(user_id=user_id, chat_id=call.message.chat.id)
                return

            if await assign_company(user_db_id, company_id):
                async with bot.retrieve_data(user_id=user_id, chat_id=call.message.chat.id) as data:
                    if await register_user(data):
                        # Удаляем сообщение с выбором
                        try:
                            await bot.delete_message(chat_id=call.message.chat.id, message_id=call.message.message_id)
                        except:
                            pass

                        # Успешная регистрация
                        success_text = format_success_message(
                            "Регистрация завершена!",
                            "Добро пожаловать в систему. Ваш профиль успешно создан."
                        )
                        await bot.send_message(chat_id=user_id, text=success_text, parse_mode='HTML')

                        # Показываем профиль
                        user_data = await get_user_profile_data(user_db_id)
                        if user_data:
                            profile_text = format_user_profile(user_data)
                            await bot.send_message(chat_id=user_id, text=profile_text, parse_mode='HTML')

                        # Кнопка исправления
                        await bot.send_message(
                            chat_id=user_id,
                            text="Если нужно исправить информацию, нажмите кнопку ниже.",
                            reply_markup=markup_correct_info
                        )

                        if await is_volunteer(user_id):
                            await bot.send_message(
                                chat_id=user_id,
                                text='Для начала следующей регистрации нажмите кнопку "Регистрация".',
                                reply_markup=markup_default_volunteer
                            )

                        await bot.delete_state(user_id=user_id, chat_id=call.message.chat.id)
                    else:
                        text = format_error_message("Ошибка", "Регистрация не удалась.")
                        await bot.send_message(chat_id=user_id, text=text, parse_mode='HTML')
            else:
                text = format_error_message("Ошибка", "Не удалось выбрать предприятие.")
                await bot.send_message(chat_id=user_id, text=text, parse_mode='HTML')
        except Exception as e:
            text = format_error_message(
                "Ошибка при выборе предприятия",
                str(e),
                "Попробуйте снова или нажмите /start"
            )
            await bot.send_message(chat_id=user_id, text=text, parse_mode='HTML')
        return

    if call.data == 'skip_volunteer_id':
        async with bot.retrieve_data(user_id=user_id, chat_id=call.message.chat.id) as data:
            data['volunteer_id'] = None
        try:
            await bot.delete_message(chat_id=call.message.chat.id, message_id=call.message.message_id)
        except:
            pass
        text = get_step_text(1)
        await bot.send_message(chat_id=call.message.chat.id, text=text, parse_mode='HTML')
        await bot.set_state(user_id=call.message.chat.id, chat_id=user_id, state=MyStates.handle_surname)
        await bot.answer_callback_query(call.id)
        return

    if call.data == 'agreed_to_nda':
        await bot.answer_callback_query(call.id)
        # Показываем выбор предприятия через кнопки
        await show_company_selection(bot, call.message.chat.id, page=0)
        await bot.set_state(chat_id=call.message.chat.id, user_id=user_id, state=MyStates.handle_company)
        return


    elif call.data == 'profile_edit' or call.data == 'correct_info':
        text = """✏️ <b>Изменение данных</b>

Напишите, что нужно исправить и как.
Я перешлю ваше сообщение менеджеру."""

        await bot.send_message(
            chat_id=user_id,
            text=text,
            parse_mode='HTML',
            reply_markup=markup_correct_info_cancel
        )

        # Сохраняем данные пользователя для запроса
        user_id_in_db = await find_user_by_tg_id(user_id)
        if user_id_in_db:
            user_data = await get_user_profile_data(user_id_in_db)
            if user_data:
                async with bot.retrieve_data(user_id, call.message.chat.id) as data:
                    data['id'] = user_data.get('id')
                    data['name'] = user_data.get('first_name')
                    data['surname'] = user_data.get('last_name')
                    data['father_name'] = user_data.get('father_name')
                    data['phone_number'] = user_data.get('phone_number')

        await bot.set_state(chat_id=user_id, user_id=user_id, state=MyStates.handle_info_correction)

    elif call.data == 'correct_info_cancel':

        await bot.delete_message(chat_id=call.message.chat.id, message_id=call.message.message_id)
        await bot.delete_state(user_id=call.from_user.id, chat_id=call.message.chat.id)

    # Обработка переключения режимов для developer
    # Скрыто в продакшн режиме
    elif call.data == 'switch_to_user':
        if is_developer(user_id) and not PRODUCTION_MODE:
            set_developer_role(user_id, 'user')
            log_role_switch(user_id, 'user')
            await bot.answer_callback_query(call.id, "Переключено в режим пользователя")
            # Удаляем сообщение с кнопкой и отправляем /start заново
            try:
                await bot.delete_message(chat_id=call.message.chat.id, message_id=call.message.message_id)
            except:
                pass
            # Имитируем /start
            await bot.send_message(chat_id=user_id, text="Добрый день! Это бот по регистрации актива г.о.Котельники. Заполните, пожалуйста, все поля и подтвердите номер телефона!", reply_markup=markup_default)
            await bot.send_message(
                chat_id=user_id,
                text="🔧 Режим разработчика: ПОЛЬЗОВАТЕЛЬ\nНажмите для переключения в режим админа:",
                reply_markup=markup_switch_to_admin
            )
            await bot.delete_state(user_id=user_id, chat_id=call.message.chat.id)
        else:
            await bot.answer_callback_query(call.id, "Только для разработчиков", show_alert=True)

    elif call.data == 'switch_to_admin':
        if is_developer(user_id) and not PRODUCTION_MODE:
            set_developer_role(user_id, 'admin')
            log_role_switch(user_id, 'admin')
            await bot.answer_callback_query(call.id, "Переключено в режим админа")
            # Удаляем сообщение с кнопкой
            try:
                await bot.delete_message(chat_id=call.message.chat.id, message_id=call.message.message_id)
            except:
                pass
            # Используем новое компактное админ-меню
            await show_admin_menu(bot, user_id, user_id)
            await bot.set_state(user_id=user_id, chat_id=call.message.chat.id, state=MyStates.admin_menu)
        else:
            await bot.answer_callback_query(call.id, "Только для разработчиков", show_alert=True)


async def main():
    """Главная функция запуска бота"""
    # Проверяем и применяем миграции БД
    await check_and_migrate()
    sync_result = await sync_telegram_platform_data(
        admin_ids=admin_ids,
        superadmin_ids=superadmin_ids,
        developer_ids=developer_ids,
    )
    logger.info("Platform foundation sync result: %s", sync_result)
    # Запускаем бота
    await bot.infinity_polling()

asyncio.run(main())
