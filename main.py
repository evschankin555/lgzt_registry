import os
import asyncio
from vars import *
from functions import *
from modules.auth import (
    is_developer, get_developer_role, set_developer_role, should_show_as_admin
)
from modules.logger import log_role_switch, setup_logging

# Настройка логирования
setup_logging()


@bot.message_handler(['start'])
async def start(msg):

    user_id = msg.from_user.id

    # Проверяем, показывать ли админ-интерфейс
    # Для developer учитывается текущий режим (admin/user)
    show_admin = should_show_as_admin(user_id, admin_ids)

    if show_admin:

        await bot.send_message(chat_id=msg.chat.id, text=text_admin_welcome)

        await bot.send_message(chat_id=msg.chat.id, text="Узнать статистику по пользователям - сколько регистраций было за день, неделю, месяц.", reply_markup=markup_get_user_stats)
        # await bot.send_message(chat_id=msg.chat.id, text="Узнать, кто заблокировал бота.", reply_markup=markup_get_blocked_users)
        await bot.send_message(chat_id=msg.chat.id, text="Узнать статистику по предприятиям.", reply_markup=markup_get_company_stats)
        await bot.send_message(chat_id=msg.chat.id, text="Общая выгрузка данных.\n\nПользователи, предприятия, кто заблокировал бота, кто был удален, собранная информация по пользователям.", reply_markup=markup_get_total_excel)
        await bot.send_message(chat_id=msg.chat.id, text="Изменить информацию по пользователю (предприятие) или удалить его.", reply_markup=markup_change_user_data)
        await bot.send_message(chat_id=msg.chat.id, text="Добавить волонтера", reply_markup=markup_add_volunteer)

        # Кнопка переключения режима только для developer
        if is_developer(user_id):
            current_role = get_developer_role(user_id)
            if current_role == 'admin':
                await bot.send_message(
                    chat_id=msg.chat.id,
                    text="🔧 Режим разработчика: АДМИН\nНажмите для переключения в режим пользователя:",
                    reply_markup=markup_switch_to_user
                )
            else:
                await bot.send_message(
                    chat_id=msg.chat.id,
                    text="🔧 Режим разработчика: ПОЛЬЗОВАТЕЛЬ\nНажмите для переключения в режим админа:",
                    reply_markup=markup_switch_to_admin
                )

        await bot.set_state(user_id=msg.chat.id, chat_id=msg.from_user.id, state=MyStates.admin_menu)

    elif await is_volunteer(user_id):
        await bot.send_message(chat_id=msg.chat.id, text='Привет, волонтер! Ты можешь регистрировать пользователей. Для старта регистрации нажми кнопку "регистрация"', reply_markup=markup_default_volunteer)

    else:
        # Обычный пользователь
        # Если это developer в режиме user, показываем кнопку переключения
        if is_developer(user_id):
            await bot.send_message(chat_id=msg.chat.id, text="Приветствую. Я могу зарегистрировать вас в XYZ.", reply_markup=markup_default)
            await bot.send_message(
                chat_id=msg.chat.id,
                text="🔧 Режим разработчика: ПОЛЬЗОВАТЕЛЬ\nНажмите для переключения в режим админа:",
                reply_markup=markup_switch_to_admin
            )
        else:
            await bot.send_message(chat_id=msg.chat.id, text="Приветствую. Я могу зарегистрировать вас в XYZ.", reply_markup=markup_default)



@bot.message_handler(content_types='text', regexp='Регистрация')
async def start_signup(msg):

    user_tg_id = int(msg.from_user.id)

    user_id_in_db = await find_user_by_tg_id(user_tg_id)

    if user_id_in_db and await is_volunteer(user_tg_id) is False:
        await bot.send_message(chat_id=msg.chat.id, text="Вы уже зарегистрированы")
    else:
        await bot.send_message(chat_id=msg.chat.id, text=surname_check_text)

        await bot.set_state(user_id=msg.chat.id, chat_id=msg.from_user.id, state=MyStates.handle_surname)

@bot.message_handler(content_types='text', regexp='Профиль')
async def show_profile(msg):

    user_tg_id = int(msg.from_user.id)

    user_id_in_db = await find_user_by_tg_id(user_tg_id)

    if user_id_in_db:

        user_info = await prepare_user_info(user_id_in_db)

        await bot.send_message(chat_id=msg.chat.id, text=user_info, reply_markup=markup_default)
    else:

        await bot.send_message(chat_id=msg.chat.id, text="Вы еще не зарегистрировались, поэтому пока что у вас нет профиля.", reply_markup=markup_default)



@bot.message_handler(content_types='text', state=[MyStates.handle_surname])
async def handle_surname(msg):

    surname = msg.text.strip().capitalize()

    if await check_surname(surname):
        print('user found')

        await bot.send_message(chat_id=msg.chat.id, text="Пришлите вашу дату рождения в формате - 01.01.2000 (пример)")

        async with bot.retrieve_data(msg.from_user.id, msg.chat.id) as data:

            data['surname'] = surname
            data['user_tg_id'] = msg.from_user.id


        await bot.set_state(chat_id=msg.chat.id, user_id=msg.chat.id, state=MyStates.handle_dob)

    else:

        await bot.send_message(chat_id=msg.chat.id, text="Не вижу вашу фамилию в базе.")

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

                await bot.send_message(chat_id=msg.chat.id, text="Нашел в базе, вы еще не зарегистрированы.")

                async with bot.retrieve_data(msg.from_user.id, msg.chat.id) as data:

                    data['id'] = user.id

                # ask for name and father name
                await bot.send_message(chat_id=msg.chat.id, text=f"Пришлите имя и отчество")
                await bot.set_state(chat_id=msg.chat.id, user_id=msg.chat.id, state=MyStates.handle_names)

            else:

                await bot.send_message(chat_id=msg.chat.id, text=f"Вы уже зарегистрированы в системе.")
                await bot.delete_state(user_id=msg.from_user.id, chat_id=msg.chat.id)

        else:
            await bot.send_message(chat_id=msg.chat.id, text="Не нашел пользователя")
    except:

        await bot.send_message(chat_id=msg.chat.id, text="Неправильный формат даты рождения.")


@bot.message_handler(content_types='text', state=[MyStates.handle_names])
async def handle_names(msg):

    user_string = msg.text

    user_str_to_list = user_string.split()

    if len(user_str_to_list) < 2:
        await bot.send_message(chat_id=msg.chat.id,
                               text="Имя и отчество должны состоять как минимум из 2 слов.")

    else:

        name, father_name = await extract_name_father_name(user_str_to_list)

        async with bot.retrieve_data(msg.from_user.id, msg.chat.id) as data:

            data['name'] = name
            data['father_name'] = father_name

        await bot.send_message(chat_id=msg.chat.id,
                               text="Хорошо. Пришлите свой номер телефона, без знака плюс, без пробелов, начиная с 7, например, 79275550150. На него прийдет СМС с кодом, нужно ввести его сюда.")
        await bot.set_state(chat_id=msg.chat.id, user_id=msg.chat.id, state=MyStates.handle_phone_number)


@bot.message_handler(content_types='text', state=[MyStates.handle_phone_number])
async def handle_phone_number(msg):

    phone_number = msg.text

    async with bot.retrieve_data(msg.from_user.id, msg.chat.id) as data:
        data['phone_number'] = phone_number

    # send an SMS code ...
    code = await send_code(phone_number)

    async with bot.retrieve_data(user_id=msg.from_user.id, chat_id=msg.chat.id) as data:

        data['code'] = code


    await bot.send_message(chat_id=msg.chat.id,
                           text="Введите код из СМС")

    await bot.set_state(chat_id=msg.chat.id, user_id=msg.chat.id, state=MyStates.check_sms)



@bot.message_handler(content_types='text', state=[MyStates.check_sms])
async def check_sms(msg):

    code_from_user = msg.text.strip()

    print(f'code from user is {code_from_user}')

    async with bot.retrieve_data(user_id=msg.from_user.id, chat_id=msg.chat.id) as data:

        code_from_backend = data.get('code')


    print(f'code from backend is {code_from_backend}')


    if code_from_user == code_from_backend:
        await bot.send_message(chat_id=msg.chat.id,
                               text="Введите свой адрес проживания в свободной форме.")

        await bot.set_state(chat_id=msg.chat.id, user_id=msg.chat.id, state=MyStates.handle_home_address)

    else:

        await bot.send_message(chat_id=msg.chat.id,
                               text="Код неверный. Попробуйте снова.")


@bot.message_handler(content_types='text', state=[MyStates.handle_home_address])
async def handle_home_address(msg):

    home_address = msg.text.strip()

    async with bot.retrieve_data(user_id=msg.from_user.id, chat_id=msg.chat.id) as data:

        data['home_address'] = home_address
        id_from_db = data['id']

    await bot.send_message(chat_id=msg.chat.id,
                           text=f"ID - {id_from_db}\n\nОзнакомьтесь с информацией о неразглашении.", reply_markup=markup_agree_to_nda)



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

        await bot.send_message(chat_id=msg.chat.id, text="Неправильный ID")
        return

    print('before adding volunteer')
    if await add_volunteer(user_tg_id):

        print('outside adding volunteer')

        await bot.send_message(chat_id=msg.chat.id, text="Волонтер добавлен.")

    else:
        await bot.send_message(chat_id=msg.chat.id, text="Волонтер с таким айди уже существует.")

    await bot.set_state(chat_id=msg.chat.id, user_id=msg.from_user.id, state=MyStates.admin_menu)


@bot.callback_query_handler(func=lambda call: True, state=[MyStates.admin_menu, MyStates.admin_read_user_id_for_edit])
async def callback(call):

    user_id = call.from_user.id

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


    elif call.data == 'add_volunteer':

        await bot.send_message(chat_id=user_id,
                               text=f"Пришли мне ID волонтера в телеграме.")

        await bot.set_state(chat_id=user_id, user_id=user_id, state=MyStates.admin_read_volunteer_id)


@bot.my_chat_member_handler(func=lambda member: member.new_chat_member.status == 'kicked' and member.chat.type == 'private')
async def bot_blocked(mb):
    print('юзер заблокал бота', mb.chat.id)

    user_id = int(mb.chat.id)

    await record_block(user_id)



@bot.callback_query_handler(func=lambda call: True)
async def callback(call):

    user_id = call.from_user.id

    if call.data == 'agreed_to_nda':
        print('user agreed to nda')

        companies_list = await get_company_list()

        await bot.send_message(chat_id=user_id,
                               text=f"Введите номер предприятия, за которым вы закреплены\n\n{companies_list}")

        await bot.set_state(chat_id=user_id, user_id=user_id, state=MyStates.handle_company)


    elif call.data == 'correct_info':

        await bot.send_message(chat_id=user_id,
                               text=f"Напишите, пожалуйста, что нужно исправить и как. Я перешлю ваше сообщение менеджеру.", reply_markup=markup_correct_info_cancel)

        await bot.set_state(chat_id=user_id, user_id=user_id, state=MyStates.handle_info_correction)

    elif call.data == 'correct_info_cancel':

        await bot.delete_message(chat_id=call.message.chat.id, message_id=call.message.message_id)
        await bot.delete_state(user_id=call.from_user.id, chat_id=call.message.chat.id)

    # Обработка переключения режимов для developer
    elif call.data == 'switch_to_user':
        if is_developer(user_id):
            set_developer_role(user_id, 'user')
            log_role_switch(user_id, 'user')
            await bot.answer_callback_query(call.id, "Переключено в режим пользователя")
            # Удаляем сообщение с кнопкой и отправляем /start заново
            try:
                await bot.delete_message(chat_id=call.message.chat.id, message_id=call.message.message_id)
            except:
                pass
            # Имитируем /start
            await bot.send_message(chat_id=user_id, text="Приветствую. Я могу зарегистрировать вас в XYZ.", reply_markup=markup_default)
            await bot.send_message(
                chat_id=user_id,
                text="🔧 Режим разработчика: ПОЛЬЗОВАТЕЛЬ\nНажмите для переключения в режим админа:",
                reply_markup=markup_switch_to_admin
            )
            await bot.delete_state(user_id=user_id, chat_id=call.message.chat.id)
        else:
            await bot.answer_callback_query(call.id, "Только для разработчиков", show_alert=True)

    elif call.data == 'switch_to_admin':
        if is_developer(user_id):
            set_developer_role(user_id, 'admin')
            log_role_switch(user_id, 'admin')
            await bot.answer_callback_query(call.id, "Переключено в режим админа")
            # Удаляем сообщение с кнопкой
            try:
                await bot.delete_message(chat_id=call.message.chat.id, message_id=call.message.message_id)
            except:
                pass
            # Показываем админ-меню
            await bot.send_message(chat_id=user_id, text=text_admin_welcome)
            await bot.send_message(chat_id=user_id, text="Узнать статистику по пользователям - сколько регистраций было за день, неделю, месяц.", reply_markup=markup_get_user_stats)
            await bot.send_message(chat_id=user_id, text="Узнать статистику по предприятиям.", reply_markup=markup_get_company_stats)
            await bot.send_message(chat_id=user_id, text="Общая выгрузка данных.\n\nПользователи, предприятия, кто заблокировал бота, кто был удален, собранная информация по пользователям.", reply_markup=markup_get_total_excel)
            await bot.send_message(chat_id=user_id, text="Изменить информацию по пользователю (предприятие) или удалить его.", reply_markup=markup_change_user_data)
            await bot.send_message(chat_id=user_id, text="Добавить волонтера", reply_markup=markup_add_volunteer)
            await bot.send_message(
                chat_id=user_id,
                text="🔧 Режим разработчика: АДМИН\nНажмите для переключения в режим пользователя:",
                reply_markup=markup_switch_to_user
            )
            await bot.set_state(user_id=user_id, chat_id=call.message.chat.id, state=MyStates.admin_menu)
        else:
            await bot.answer_callback_query(call.id, "Только для разработчиков", show_alert=True)


asyncio.run(bot.infinity_polling())