import os
import asyncio
from datetime import datetime, timezone, timedelta
from typing import Optional
from telethon import TelegramClient
from telethon.tl.functions.messages import ImportChatInviteRequest
from telethon.tl.functions.channels import JoinChannelRequest, LeaveChannelRequest
from telethon.errors import SessionPasswordNeededError, PhoneCodeInvalidError
from config import get_settings

settings = get_settings()

# Хранилище активных клиентов
clients: dict[str, TelegramClient] = {}
pending_codes: dict[str, dict] = {}  # phone -> {phone_code_hash, client}


def get_session_path(phone: str) -> str:
    """Путь к файлу сессии"""
    clean_phone = phone.replace("+", "").replace(" ", "")
    return os.path.join("data", "sessions", clean_phone)


async def get_client(phone: str) -> TelegramClient:
    """Получить или создать клиент для номера"""
    if phone in clients:
        return clients[phone]

    session_path = get_session_path(phone)
    client = TelegramClient(
        session_path,
        settings.telegram_api_id,
        settings.telegram_api_hash
    )
    clients[phone] = client
    return client


async def send_code(phone: str) -> dict:
    """Отправить код авторизации на телефон"""
    client = await get_client(phone)

    if not client.is_connected():
        await client.connect()

    # Проверяем, может уже авторизованы
    if await client.is_user_authorized():
        me = await client.get_me()
        return {
            "status": "already_authorized",
            "user": {
                "first_name": me.first_name,
                "last_name": me.last_name,
                "username": me.username,
                "phone": me.phone
            }
        }

    # Отправляем код
    result = await client.send_code_request(phone)
    pending_codes[phone] = {
        "phone_code_hash": result.phone_code_hash,
        "client": client
    }

    return {"status": "code_sent"}


async def verify_code(phone: str, code: str, password: Optional[str] = None) -> dict:
    """Подтвердить код авторизации"""
    if phone not in pending_codes:
        # Попробуем подключиться к существующей сессии
        client = await get_client(phone)
        if not client.is_connected():
            await client.connect()

        if await client.is_user_authorized():
            me = await client.get_me()
            return {
                "status": "success",
                "user": {
                    "first_name": me.first_name,
                    "last_name": me.last_name,
                    "username": me.username,
                    "phone": me.phone
                }
            }
        return {"status": "error", "message": "Code not sent. Please request new code."}

    data = pending_codes[phone]
    client = data["client"]

    try:
        await client.sign_in(
            phone=phone,
            code=code,
            phone_code_hash=data["phone_code_hash"]
        )
    except SessionPasswordNeededError:
        # Требуется 2FA пароль
        if not password:
            return {"status": "2fa_required"}
        await client.sign_in(password=password)
    except PhoneCodeInvalidError:
        return {"status": "error", "message": "Invalid code"}
    except Exception as e:
        return {"status": "error", "message": str(e)}

    me = await client.get_me()
    del pending_codes[phone]

    return {
        "status": "success",
        "user": {
            "first_name": me.first_name,
            "last_name": me.last_name,
            "username": me.username,
            "phone": me.phone
        }
    }


async def get_status(phone: str) -> dict:
    """Проверить статус авторизации"""
    client = await get_client(phone)

    if not client.is_connected():
        try:
            await client.connect()
        except Exception:
            return {"authorized": False}

    if await client.is_user_authorized():
        me = await client.get_me()
        return {
            "authorized": True,
            "user": {
                "first_name": me.first_name,
                "last_name": me.last_name,
                "username": me.username,
                "phone": me.phone
            }
        }

    return {"authorized": False}


async def join_group(phone: str, link: str) -> dict:
    """Вступить в группу по ссылке"""
    client = await get_client(phone)

    if not client.is_connected():
        await client.connect()

    if not await client.is_user_authorized():
        return {"status": "error", "message": "Not authorized"}

    try:
        # Извлекаем хеш из ссылки
        if "t.me/" in link:
            if "/+" in link or "/joinchat/" in link:
                # Приватная группа
                hash_part = link.split("/")[-1].replace("+", "")
                result = await client(ImportChatInviteRequest(hash_part))
            else:
                # Публичная группа
                username = link.split("/")[-1].split("?")[0]
                result = await client(JoinChannelRequest(username))
        else:
            return {"status": "error", "message": "Invalid link format"}

        return {
            "status": "success",
            "group": {
                "id": result.chats[0].id if result.chats else None,
                "title": result.chats[0].title if result.chats else None
            }
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}


async def send_photo_to_group(phone: str, group_id: str, photo_path: str, caption: str = "") -> dict:
    """Отправить фото в группу"""
    client = await get_client(phone)

    if not client.is_connected():
        await client.connect()

    if not await client.is_user_authorized():
        return {"status": "error", "message": "Not authorized"}

    try:
        # Отправляем фото
        message = await client.send_file(
            int(group_id),
            photo_path,
            caption=caption
        )
        return {
            "status": "success",
            "message_id": message.id
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}


async def check_already_posted(phone: str, group_id: str, hours: int = 24) -> dict:
    """Проверить, публиковали ли мы уже сообщение в этот чат за последние N часов"""
    client = await get_client(phone)

    if not client.is_connected():
        await client.connect()

    if not await client.is_user_authorized():
        return {"posted": False, "error": "Not authorized"}

    try:
        me = await client.get_me()
        cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)

        messages = await client.get_messages(
            int(group_id),
            from_user=me,
            limit=10
        )

        for msg in messages:
            if msg.date and msg.date > cutoff:
                return {
                    "posted": True,
                    "message_id": msg.id,
                    "date": msg.date.isoformat(),
                    "text": (msg.text or "")[:100],
                    "has_media": msg.media is not None
                }

        return {"posted": False}
    except Exception as e:
        return {"posted": False, "error": str(e)}


async def get_dialogs(phone: str) -> dict:
    """Получить список групп/каналов"""
    client = await get_client(phone)

    if not client.is_connected():
        await client.connect()

    if not await client.is_user_authorized():
        return {"status": "error", "message": "Not authorized"}

    try:
        dialogs = await client.get_dialogs()
        groups = []
        for dialog in dialogs:
            if dialog.is_group or dialog.is_channel:
                groups.append({
                    "id": dialog.id,
                    "title": dialog.title,
                    "is_channel": dialog.is_channel,
                    "is_group": dialog.is_group
                })
        return {"status": "success", "groups": groups}
    except Exception as e:
        return {"status": "error", "message": str(e)}


async def leave_group(phone: str, group_id: str) -> dict:
    """Выйти из группы"""
    client = await get_client(phone)

    if not client.is_connected():
        await client.connect()

    if not await client.is_user_authorized():
        return {"status": "error", "message": "Not authorized"}

    try:
        await client(LeaveChannelRequest(int(group_id)))
        return {"status": "success"}
    except Exception as e:
        return {"status": "error", "message": str(e)}


async def get_channel_messages(phone: str, channel_username: str, limit: int = 200) -> list:
    """Считать сообщения из канала/группы"""
    client = await get_client(phone)

    if not client.is_connected():
        await client.connect()

    if not await client.is_user_authorized():
        return {"status": "error", "message": "Not authorized"}

    try:
        entity = await client.get_entity(channel_username)
        messages = []
        async for message in client.iter_messages(entity, limit=limit):
            msg_data = {
                "id": message.id,
                "date": message.date.isoformat() if message.date else None,
                "text": message.text or "",
                "grouped_id": str(message.grouped_id) if message.grouped_id else None,
                "has_media": message.media is not None,
                "media_type": None,
                "views": message.views,
            }
            if message.photo:
                msg_data["media_type"] = "photo"
            elif message.document:
                msg_data["media_type"] = "document"
            elif message.video:
                msg_data["media_type"] = "video"
            messages.append(msg_data)

        return {"status": "success", "messages": messages, "count": len(messages)}
    except Exception as e:
        return {"status": "error", "message": str(e)}


async def download_channel_media(phone: str, channel_username: str, output_dir: str, limit: int = 200) -> dict:
    """Скачать медиа из канала"""
    client = await get_client(phone)

    if not client.is_connected():
        await client.connect()

    if not await client.is_user_authorized():
        return {"status": "error", "message": "Not authorized"}

    try:
        os.makedirs(output_dir, exist_ok=True)
        entity = await client.get_entity(channel_username)
        downloaded = []
        async for message in client.iter_messages(entity, limit=limit):
            if message.photo:
                filename = f"{message.id}_0.jpg"
                filepath = os.path.join(output_dir, filename)
                await client.download_media(message, file=filepath)
                downloaded.append(filename)
                await asyncio.sleep(0.5)

        return {"status": "success", "downloaded": downloaded, "count": len(downloaded)}
    except Exception as e:
        return {"status": "error", "message": str(e)}


async def disconnect_all():
    """Отключить все клиенты"""
    for client in clients.values():
        if client.is_connected():
            await client.disconnect()
    clients.clear()
