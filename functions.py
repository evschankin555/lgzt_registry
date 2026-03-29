from db import SessionLocal, engine
from models import User, Company, User_who_blocked, User_volunteer
from sqlalchemy import select, update, MetaData, func, insert
from datetime import datetime, timedelta
import aiohttp
import pandas as pd
from random import randint
from pprint import pprint
import logging
import asyncio
from services.platform import IdentityService, PlatformSchemaUnavailable

logger = logging.getLogger(__name__)


async def _link_telegram_user_identity(session, user: User, payload: dict | None = None):
    if user is None or user.tg_id is None:
        return None
    try:
        return await IdentityService.link_user_identity(
            session=session,
            user_id=user.id,
            provider="telegram",
            external_user_id=user.tg_id,
            payload=payload,
        )
    except PlatformSchemaUnavailable:
        return None


async def _link_telegram_volunteer_identity(session, volunteer: User_volunteer, payload: dict | None = None):
    if volunteer is None or volunteer.tg_id is None:
        return None
    try:
        return await IdentityService.link_volunteer_identity(
            session=session,
            volunteer_id=volunteer.id,
            provider="telegram",
            external_user_id=volunteer.tg_id,
            payload=payload,
        )
    except PlatformSchemaUnavailable:
        return None

async def check_surname(surname):

    stmt = select(User).where(User.last_name == surname)

    async with SessionLocal() as session:

        result = await session.execute(stmt)

        user_result = result.scalars().all()

        if len(user_result) == 0:

            return False
        else:
            return True


async def check_dob_and_status(dob, surname):

    print('checking user with dob', dob)

    stmt = select(User).where(User.date_of_birth == dob).where(User.last_name == surname)

    async with SessionLocal() as session:

        result = await session.execute(stmt)

        result = result.scalars().all()

        if len(result) == 0:

            return False
        else:

            return result[0]




async def send_code(phone_number):

    code = randint(10, 99)

    message = f"Ваш код для подтверждения: {code}"
    timeout = aiohttp.ClientTimeout(total=10, connect=5, sock_read=5)
    sms_url = "https://smsc.ru/sys/send.php"
    params = {
        "login": "lgjt",
        "psw": "123456",
        "phones": phone_number,
        "mes": message,
        "sender": "kotelnikiru",
    }

    try:
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.post(url=sms_url, params=params) as response:
                response_text = (await response.text()).strip()
                if response.status != 200:
                    logger.error("SMS API HTTP %s: %s", response.status, response_text)
                    return None
                logger.info("SMS API response: %s", response_text)
                if not response_text:
                    return None
                return str(code)
    except aiohttp.ClientError as e:
        logger.error("SMS API network error: %s", e)
        return None
    except asyncio.TimeoutError:
        logger.error("SMS API timeout for phone %s", phone_number)
        return None
    except Exception as e:
        logger.error("SMS API unexpected error: %s", e, exc_info=True)
        return None

async def get_company_list() -> str:

    stmt = select(Company)

    async with SessionLocal() as session:

        result = await session.execute(stmt)

        companies_objects = result.scalars().all()

        mystr = ''

        for i in companies_objects:
            mystr = f"{mystr}\n{i.id} - {i.name}"

        return mystr



async def check_if_company_exists(company_id: int) -> Company | None:

    async with SessionLocal() as session:

        return await session.get(Company, company_id)

async def find_user_by_tg_id(user_tg_id):

    async with SessionLocal() as session:
        try:
            user = await IdentityService.get_user_by_identity(session, "telegram", user_tg_id)
            if user:
                await _link_telegram_user_identity(
                    session,
                    user,
                    payload={"source": "identity_lookup"},
                )
                await session.commit()
                return user.id
        except PlatformSchemaUnavailable:
            pass

        stmt = select(User).where(User.tg_id == user_tg_id)

        query = await session.execute(stmt)

        user = query.scalars().first()
        if user:
            linked = await _link_telegram_user_identity(
                session,
                user,
                payload={"source": "legacy_tg_id_lookup"},
            )
            if linked is not None:
                await session.commit()

            return user.id
        else:
            print('no such registered user in db!')
            return False


async def assign_company(user_id, company_id):

    stmt = select(User).where(User.id == user_id)

    async with SessionLocal() as session:

        result = await session.execute(stmt)

        user = result.scalars().one_or_none()

        if user is not None:

            company = await session.get(Company, company_id)

            if company is None:

                print("Tried to assign a company, but company is None...")
                return False
            else:
                user.company = company
                await session.commit()
                return True

        else:

            print("User is none in assign company function!")
            return False

async def register_user(user_botdata) -> True | False:

    user_id = user_botdata['id']
    name = user_botdata['name']
    father_name = user_botdata['father_name']
    phone_number = user_botdata['phone_number']
    home_address = user_botdata['home_address']
    registered_at = datetime.now()
    tg_id = user_botdata['user_tg_id']

    async with SessionLocal() as session:

        user = await session.get(User, user_id)

        if user:

            print(f'\nUser before registration:\n')
            print(f"User id: {user.id}")
            print(f"User name: {user.first_name}")
            print(f"User last name: {user.last_name}")
            print(f"User father name: {user.father_name}")
            print(f"User phone_number: {user.phone_number}")
            print(f"User dob: {user.date_of_birth}")
            print(f"User status: {user.status}")
            print(f"User address: {user.address}")
            print(f"User registered at: {user.registered_at}")
            print(f"User tg id: {user.tg_id}")


            user.status = 'registered'
            user.first_name = name
            user.father_name = father_name
            user.phone_number = phone_number
            user.address = home_address
            user.registered_at = registered_at
            user.tg_id = tg_id
            user.volunteer_id = user_botdata.get('volunteer_id')
            user.sms_code = user_botdata.get('sms_code')
            sms_ts = user_botdata.get('sms_confirmed_at')
            if sms_ts:
                user.sms_confirmed_at = datetime.fromisoformat(sms_ts)

            await _link_telegram_user_identity(
                session,
                user,
                payload={
                    "first_name": user.first_name,
                    "last_name": user.last_name,
                    "father_name": user.father_name,
                    "phone_number": user.phone_number,
                },
            )
            await session.commit()

            await session.refresh(user)

            print("\n\nUser after registration:\n")
            print(f"User id: {user.id}")
            print(f"User name: {user.first_name}")
            print(f"User last name: {user.last_name}")
            print(f"User father name: {user.father_name}")
            print(f"User phone_number: {user.phone_number}")
            print(f"User dob: {user.date_of_birth}")
            print(f"User status: {user.status}")
            print(f"User address: {user.address}")
            print(f"User registered at: {user.registered_at}")
            print(f"User tg id: {user.tg_id}")

            return True
        else:
            print('no such user with id', user_id, 'in function register user')
            return False


async def prepare_user_info(user_id):

    async with SessionLocal() as session:

        user = await session.get(User, user_id)

        if user:

            user_company_id = user.company_id
            user_company_query = await session.get(Company, user_company_id)
            company_name = user_company_query.name

            registered_at = datetime.strftime(user.registered_at, "%d %m %Y %H:%M")

            user_info = f"ID - {user.id}\n\nФИО - {user.last_name} {user.first_name} {user.father_name}\n\nДата рождения - {user.date_of_birth}\n\nНомер телефона - {user.phone_number}\n\nАдрес - {user.address}\n\nПредприятие - {company_name}\n\nВремя и дата регистрации - {registered_at}"

            if user.volunteer_id:
                volunteer = await session.get(User_volunteer, user.volunteer_id)
                if volunteer:
                    vol_name = volunteer.name or f"#{volunteer.id}"
                    user_info += f"\n\nВолонтёр - {vol_name}"

            return user_info

async def extract_name_father_name(mlist: list):

    name = mlist[0]

    father_name = ''

    del mlist[0]

    for i in mlist:
        father_name = f'{father_name} {i}'

    father_name = father_name.strip()

    return name, father_name


async def generate_excel():
    TABLE_EXPORT_CONFIG = {
        "user": {
            "sheet_name": "Пользователи",
            "column_order": [
                "id", "last_name", "first_name", "father_name",
                "passport_number", "date_of_birth", "counter",
                "address", "phone_number", "status", "registered_at",
                "blocked_at", "company_id"
            ],
            "rename": {
                "id": "ID",
                "last_name": "Фамилия",
                "first_name": "Имя",
                "father_name": "Отчество",
                "passport_number": "Серия номер паспорта",
                "date_of_birth": "Дата рождения",
                "counter": "Порядковый номер",
                "address": "Адрес",
                "phone_number": "Номер телефона",
                "status": "Статус",
                "registered_at": "Дата время регистрации",
                "blocked_at": "Дата время блокировки",
                "company_id": "ID предприятия",
            },
        },
        "company": {
            "sheet_name": "Предприятия",
            "column_order": ["id", "name"],
            "rename": {
                "id": "ID",
                "name": "Название",
            },
        },
    }

    EXTRA_USER_SHEETS = {
        "blocked": "Заблокировали после регистрации",
        "deleted": "Удалены",
    }

    USER_WHO_BLOCKED_SHEET_NAME = "Заблокировали до регистрации"
    EXCLUDED_TABLES = ["alembic_version", "user_who_blocked"]

    metadata = MetaData()

    async with engine.begin() as conn:
        await conn.run_sync(metadata.reflect)

    async with SessionLocal() as session:
        with pd.ExcelWriter("excel_dump.xlsx", engine="openpyxl") as writer:
            for idx, table in enumerate(metadata.sorted_tables, start=1):
                if table.name in EXCLUDED_TABLES:
                    continue

                config = TABLE_EXPORT_CONFIG.get(table.name, {})
                column_order = config.get("column_order")
                rename_map = config.get("rename", {})
                sheet_name = config.get("sheet_name", table.name.title())
                sheet_name = (sheet_name or f"table_{idx}")[:31]

                result = await session.execute(select(table))
                rows = result.mappings().all()

                if rows:
                    df_raw = pd.DataFrame(rows)
                else:
                    source_cols = [column.name for column in table.columns]
                    use_cols = column_order or source_cols
                    df_raw = pd.DataFrame(
                        columns=[col for col in use_cols if col in source_cols]
                    )

                df_export = df_raw.copy()
                if column_order:
                    df_export = df_export[
                        [col for col in column_order if col in df_export.columns]
                    ]

                if rename_map:
                    df_export.rename(columns=rename_map, inplace=True)

                df_export.to_excel(writer, sheet_name=sheet_name, index=False)

                if table.name == "user" and "status" in df_raw.columns:
                    for status_value, extra_sheet_name in EXTRA_USER_SHEETS.items():
                        filtered = df_raw[df_raw["status"] == status_value].copy()

                        if column_order:
                            filtered = filtered[
                                [col for col in column_order if col in filtered.columns]
                            ]

                        if rename_map:
                            filtered.rename(columns=rename_map, inplace=True)

                        filtered.to_excel(
                            writer,
                            sheet_name=extra_sheet_name[:31],
                            index=False,
                        )

                print("Done")

            user_who_blocked_table = metadata.tables.get("user_who_blocked")
            if user_who_blocked_table is not None:
                result = await session.execute(
                    select(
                        user_who_blocked_table.c.tg_id,
                        user_who_blocked_table.c.blocked_at,
                    )
                )
                rows = result.mappings().all()

                if rows:
                    df_uwb = pd.DataFrame(rows)
                else:
                    df_uwb = pd.DataFrame(columns=["tg_id", "blocked_at"])

                df_uwb.rename(
                    columns={
                        "tg_id": "ID телеграм",
                        "blocked_at": "Время и дата блокировки",
                    },
                    inplace=True,
                )

                df_uwb.to_excel(
                    writer,
                    sheet_name=USER_WHO_BLOCKED_SHEET_NAME[:31],
                    index=False,
                )


async def gather_company_stats():

    async with SessionLocal() as session:
        stmt = (
            select(
                Company.id,
                Company.name,
                func.count(User.id).label("user_count"),
            )
            .outerjoin(User)
            .group_by(Company.id, Company.name)
            .order_by(func.count(User.id).desc(), Company.name)  # secondary sort keeps deterministic order
        )

        result = await session.execute(stmt)
        rows = result.all()

        result_str = ''

        for company_id, company_name, user_count in rows:

            result_str = f"{result_str}\n{company_name}: {user_count}"


    return result_str

async def get_user_stats():
    async with SessionLocal() as session:
        now = datetime.utcnow()

        stmt = select(
            func.count(User.id)
            .filter(User.registered_at >= now - timedelta(hours=24))
            .label("last_24h"),
            func.count(User.id)
            .filter(User.registered_at >= now - timedelta(days=7))
            .label("last_7d"),
            func.count(User.id)
            .filter(User.registered_at >= now - timedelta(days=30))  # or use relativedelta for calendar month
            .label("last_30d"),
        ).where(User.status == 'registered')

        result = await session.execute(stmt)
        counts = result.one()

    output_str = f"Кол-во регистраций за последнее время\n\nСутки - {counts.last_24h}\n\nНеделя - {counts.last_7d}\n\nМесяц - {counts.last_30d}"

    return output_str

async def prepare_user_info_for_admin(user_id):

    async with SessionLocal() as session:

        user = await session.get(User, user_id)

        if user:

            print("User found")

            user_company_id = user.company_id
            user_company_query = await session.get(Company, user_company_id)

            print("User company query - ", user_company_query)

            if user_company_query is None:
                company_name = 'Не назначено'
            else:
                company_name = user_company_query.name

            if user.registered_at is not None:
                registered_at = datetime.strftime(user.registered_at, "%d %m %Y %H:%M")
            else:
                registered_at = 'Еще не загеристрирован'

            user_info = f"ID - {user.id}\n\nФИО - {user.last_name} {user.first_name} {user.father_name}\n\nСерия номер паспорта - {user.passport_number}\n\nДата рождения - {user.date_of_birth}\n\nНомер телефона - {user.phone_number}\n\nАдрес - {user.address}\n\n<b>Предприятие - {company_name}</b>\n\nВремя и дата регистрации - {registered_at}\n\n<b>Статус - {user.status}</b>"

            if user.volunteer_id:
                volunteer = await session.get(User_volunteer, user.volunteer_id)
                if volunteer:
                    vol_name = volunteer.name or f"#{volunteer.id}"
                    user_info += f"\n\nВолонтёр - {vol_name}"

            return user_info

async def remove_user(user_id):

    # set status to deleted
    # set company to none

    async with SessionLocal() as session:

        user = await session.get(User, user_id)

        if user:

            user.status = 'deleted'
            user.company = None
            await session.commit()
            await session.refresh(user)

            print(f"Removed user with id {user_id}")
            print(f"Status: {user.status}")
            print(f"Company: {user.company}")

async def reassign_company(user_id, new_company_id):

    async with SessionLocal() as session:

        user = await session.get(User, user_id)
        company = await session.get(Company, new_company_id)

        user.company = company

        await session.commit()

async def record_block(user_tg_id):

    timenow = datetime.now()

    async with SessionLocal() as session:

        print('437')

        stmt = select(User).where(User.tg_id == user_tg_id)
        query = await session.execute(stmt)
        print('441')
        user = query.scalars().one_or_none()

        if user:
            print('445')
            user.status = 'blocked'
            user.blocked_at = timenow

            print('User status updated to blocked.')
        else:
            print("No registered user to update for blocked.")

        user_who_blocked = User_who_blocked(tg_id=user_tg_id, blocked_at=timenow)
        session.add(user_who_blocked)

        try:
            await IdentityService.record_blocked_identity_event(
                session=session,
                provider="telegram",
                external_user_id=user_tg_id,
                blocked_at=timenow,
                user_id=user.id if user else None,
                payload={"source": "record_block"},
            )
        except PlatformSchemaUnavailable:
            pass

        print("Added user to blocked table")

        await session.commit()

async def add_volunteer(user_tg_id: int, added_by: int = None, name: str = None):
    """
    Добавить волонтера

    Args:
        user_tg_id: Telegram ID волонтера
        added_by: Telegram ID админа, который добавляет
        name: Имя волонтера (опционально)

    Returns:
        True если добавлен, False если уже существует
    """
    stmt = select(User_volunteer).where(User_volunteer.tg_id == user_tg_id)

    async with SessionLocal() as session:
        query = await session.execute(stmt)
        volunteer = query.scalars().one_or_none()

        if volunteer is None:
            volunteer = User_volunteer()
            volunteer.tg_id = user_tg_id
            volunteer.added_at = datetime.now()
            volunteer.added_by = added_by
            volunteer.name = name
            session.add(volunteer)
            await session.flush()
            await _link_telegram_volunteer_identity(
                session,
                volunteer,
                payload={"name": volunteer.name, "added_by": added_by},
            )
            await session.commit()
            await session.refresh(volunteer)
            return volunteer.id
        else:
            return False


async def is_volunteer(user_tg_id):

    async with SessionLocal() as session:
        try:
            volunteer = await IdentityService.get_volunteer_by_identity(
                session,
                "telegram",
                user_tg_id,
            )
            if volunteer is not None:
                await _link_telegram_volunteer_identity(
                    session,
                    volunteer,
                    payload={"source": "identity_lookup"},
                )
                await session.commit()
                return True
        except PlatformSchemaUnavailable:
            pass

        stmt = select(User_volunteer).where(User_volunteer.tg_id == user_tg_id)

        query = await session.execute(stmt)

        volunteer = query.scalars().one_or_none()

        if volunteer is None:
            return False
        else:
            linked = await _link_telegram_volunteer_identity(
                session,
                volunteer,
                payload={"source": "legacy_tg_id_lookup"},
            )
            if linked is not None:
                await session.commit()
            return True


async def update_volunteer_tg_name(tg_id: int, first_name: str, last_name: str = None):
    """Обновить имя волонтёра из Telegram, если оно не задано вручную"""
    async with SessionLocal() as session:
        try:
            volunteer = await IdentityService.get_volunteer_by_identity(session, "telegram", tg_id)
        except PlatformSchemaUnavailable:
            volunteer = None

        if volunteer is None:
            stmt = select(User_volunteer).where(User_volunteer.tg_id == tg_id)
            result = await session.execute(stmt)
            volunteer = result.scalars().one_or_none()

        if volunteer and not volunteer.name_manual:
            tg_name = first_name
            if last_name:
                tg_name += f" {last_name}"
            volunteer.name = tg_name
            await _link_telegram_volunteer_identity(
                session,
                volunteer,
                payload={"name": tg_name},
            )
            await session.commit()


async def check_volunteer_exists(volunteer_id: int) -> bool:
    """
    Проверить существует ли волонтёр с таким ID

    Args:
        volunteer_id: ID волонтёра в БД

    Returns:
        True если существует, False если нет
    """
    async with SessionLocal() as session:
        volunteer = await session.get(User_volunteer, volunteer_id)
        return volunteer is not None
        
