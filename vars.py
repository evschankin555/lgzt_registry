from telebot.asyncio_handler_backends import StatesGroup, State
from telebot.asyncio_storage import StateMemoryStorage
from telebot.async_telebot import types
from dotenv import load_dotenv
import os
from pathlib import Path
import shutil
from telebot import async_telebot, asyncio_filters
from emoji import emojize

# Автоматическое создание .env из example.env если .env не существует
env_path = Path('.env')
example_env_path = Path('example.env')

if not env_path.exists() and example_env_path.exists():
    shutil.copy(example_env_path, env_path)
    print(f"Создан файл .env из {example_env_path}")

load_dotenv()
tg_bot_api_key = os.environ.get('telegram_bot_api')

bot = async_telebot.AsyncTeleBot(tg_bot_api_key, state_storage=StateMemoryStorage())

surname_check_text = """Пожалуйста, отправьте мне фамилию, я найду ее в базе."""

text_admin_welcome = "Добро пожаловать в админ часть бота 🍓🍓🍓.\n\nЧтобы повторно вызвать меню ниже, вводите команду /start"

class MyStates(StatesGroup):

    handle_surname = State()
    handle_dob = State()
    handle_names = State()
    handle_phone_number = State()
    check_sms = State()
    handle_home_address = State()
    handle_company = State()
    handle_info_correction = State()
    admin_menu = State()
    admin_read_user_id_for_edit = State()
    admin_read_comp_id_for_edit = State()
    admin_read_volunteer_id = State()


markup_agree_to_nda = types.InlineKeyboardMarkup()
markup_agree_to_nda.add(types.InlineKeyboardButton(text=f'Ознакомлен {emojize(":check_mark:")}', callback_data='agreed_to_nda'))

markup_correct_info = types.InlineKeyboardMarkup()
markup_correct_info.add(types.InlineKeyboardButton(text=f'Исправить {emojize(":pencil:")}', callback_data='correct_info'))

markup_correct_info_cancel = types.InlineKeyboardMarkup()
markup_correct_info_cancel.add(types.InlineKeyboardButton(text=f'Отмена {emojize(":cross_mark:")}', callback_data='correct_info_cancel'))

markup_get_total_excel = types.InlineKeyboardMarkup()
markup_get_total_excel.add(types.InlineKeyboardButton(text=f'Выгрузить {emojize(":floppy_disk:")}', callback_data='get_total_excel'))

markup_get_company_stats = types.InlineKeyboardMarkup()
markup_get_company_stats.add(types.InlineKeyboardButton(text=f'Посчитать {emojize(":factory_worker:")}', callback_data='get_comp_stats'))

markup_get_blocked_users = types.InlineKeyboardMarkup()
markup_get_blocked_users.add(types.InlineKeyboardButton(text=f'Показать {emojize(":stop_sign:")}', callback_data='get_blocked_users'))


markup_get_user_stats = types.InlineKeyboardMarkup()
markup_get_user_stats.add(types.InlineKeyboardButton(text=f'Показать {emojize(":card_file_box:")}', callback_data='get_user_stats'))


markup_change_user_data = types.InlineKeyboardMarkup()
markup_change_user_data.add(types.InlineKeyboardButton(text=f'Изменить {emojize(":pencil:")}', callback_data='change_user_data'))

markup_add_volunteer = types.InlineKeyboardMarkup()
markup_add_volunteer.add(types.InlineKeyboardButton(text=f'{emojize(":plus_sign:")}', callback_data='add_volunteer'))

markup_default_volunteer = types.ReplyKeyboardMarkup(resize_keyboard=True)
markup_default_volunteer.add(types.KeyboardButton("Регистрация"))


markup_default = types.ReplyKeyboardMarkup(resize_keyboard=True)
markup_default.add(types.KeyboardButton("Регистрация"),types.KeyboardButton("Мой профиль"))

bot.add_custom_filter(asyncio_filters.StateFilter(bot))

admin_ids = [9958633101, 2693757140, 1632759029]
superadmin_ids = [995863310, 2693757140, 1632759029]