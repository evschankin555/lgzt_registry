import os
import uuid
import aiofiles
from datetime import datetime, timedelta
from typing import Optional, List
from contextlib import asynccontextmanager

from fastapi import FastAPI, Depends, HTTPException, UploadFile, File, Form, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from sqlalchemy import select, func, or_
from sqlalchemy.ext.asyncio import AsyncSession

from config import get_settings
from database import get_db, init_db
from models import TelegramAccount, Group, Post, PostResult, Message, MessageSend
from auth import (
    Token, LoginRequest, create_access_token, authenticate, get_current_user
)
from excel_import import parse_excel, validate_excel
from join_worker import join_worker
import telegram_client as tg

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    await init_db()
    os.makedirs("data/sessions", exist_ok=True)
    os.makedirs("data/uploads", exist_ok=True)
    yield
    # Shutdown
    await join_worker.stop()
    await tg.disconnect_all()


app = FastAPI(title="Poster Bot API", lifespan=lifespan)

# CORS для React фронтенда
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Статические файлы для загрузок
app.mount("/uploads", StaticFiles(directory="data/uploads"), name="uploads")


# ========== Schemas ==========

class PhoneRequest(BaseModel):
    phone: str


class VerifyCodeRequest(BaseModel):
    phone: str
    code: str
    password: Optional[str] = None


class GroupRequest(BaseModel):
    phone: str
    link: str


class SendPostRequest(BaseModel):
    phone: str
    group_ids: List[int]
    caption: Optional[str] = ""


class StartJoiningRequest(BaseModel):
    phone: str
    limit: int = 0  # 0 = без лимита, иначе - сколько групп вступить
    delay_min: int = 30  # Минимальная задержка (сек)
    delay_max: int = 60  # Максимальная задержка (сек)


# ========== Auth Endpoints ==========

@app.post("/api/login", response_model=Token)
async def login(request: LoginRequest):
    if not authenticate(request.password):
        raise HTTPException(status_code=401, detail="Invalid password")

    access_token = create_access_token(data={"sub": "admin"})
    return {"access_token": access_token, "token_type": "bearer"}


@app.get("/api/me")
async def get_me(user=Depends(get_current_user)):
    return {"user": "admin", "authenticated": True}


# ========== Telegram Auth Endpoints ==========

@app.post("/api/telegram/send-code")
async def send_code(
    request: PhoneRequest,
    user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    result = await tg.send_code(request.phone)

    if result["status"] == "already_authorized":
        # Сохраняем в БД если ещё нет
        stmt = select(TelegramAccount).where(TelegramAccount.phone == request.phone)
        existing = (await db.execute(stmt)).scalar_one_or_none()

        if not existing:
            account = TelegramAccount(
                phone=request.phone,
                session_file=tg.get_session_path(request.phone),
                is_authorized=True,
                first_name=result["user"].get("first_name"),
                last_name=result["user"].get("last_name"),
                username=result["user"].get("username")
            )
            db.add(account)
            await db.commit()

    return result


@app.post("/api/telegram/verify-code")
async def verify_code(
    request: VerifyCodeRequest,
    user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    result = await tg.verify_code(request.phone, request.code, request.password)

    if result["status"] == "success":
        # Сохраняем/обновляем в БД
        stmt = select(TelegramAccount).where(TelegramAccount.phone == request.phone)
        existing = (await db.execute(stmt)).scalar_one_or_none()

        if existing:
            existing.is_authorized = True
            existing.first_name = result["user"].get("first_name")
            existing.last_name = result["user"].get("last_name")
            existing.username = result["user"].get("username")
        else:
            account = TelegramAccount(
                phone=request.phone,
                session_file=tg.get_session_path(request.phone),
                is_authorized=True,
                first_name=result["user"].get("first_name"),
                last_name=result["user"].get("last_name"),
                username=result["user"].get("username")
            )
            db.add(account)

        await db.commit()

    return result


@app.get("/api/telegram/status/{phone}")
async def get_telegram_status(phone: str, user=Depends(get_current_user)):
    return await tg.get_status(phone)


@app.get("/api/telegram/accounts")
async def get_accounts(
    user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    stmt = select(TelegramAccount).order_by(TelegramAccount.created_at.desc())
    result = await db.execute(stmt)
    accounts = result.scalars().all()

    return [
        {
            "id": acc.id,
            "phone": acc.phone,
            "first_name": acc.first_name,
            "last_name": acc.last_name,
            "username": acc.username,
            "is_authorized": acc.is_authorized,
            "created_at": acc.created_at.isoformat()
        }
        for acc in accounts
    ]


# ========== Groups Endpoints ==========

@app.get("/api/telegram/dialogs/{phone}")
async def get_dialogs(phone: str, user=Depends(get_current_user)):
    """Получить список групп/каналов из TG"""
    return await tg.get_dialogs(phone)


@app.post("/api/groups/import")
async def import_groups(
    file: UploadFile = File(...),
    update_existing: bool = Query(False),  # Обновлять существующие группы
    user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Импортировать группы из Excel файла"""
    content = await file.read()

    # Валидация
    is_valid, error, count = validate_excel(content)
    if not is_valid:
        raise HTTPException(status_code=400, detail=error)

    # Парсим группы
    groups_data = parse_excel(content)

    # Получаем существующие группы по ссылкам
    stmt = select(Group)
    result = await db.execute(stmt)
    existing_groups = {g.link: g for g in result.scalars().all()}

    # Добавляем/обновляем группы
    added = 0
    updated = 0
    skipped = 0

    for g in groups_data:
        if g["link"] in existing_groups:
            if update_existing:
                # Обновляем город и адрес для существующих
                existing = existing_groups[g["link"]]
                if g.get("city") and not existing.city:
                    existing.city = g.get("city")
                if g.get("address") and not existing.address:
                    existing.address = g.get("address")
                updated += 1
            else:
                skipped += 1
            continue

        group = Group(
            link=g["link"],
            city=g.get("city"),
            address=g.get("address"),
            status="pending",
            source="excel"
        )
        db.add(group)
        existing_groups[g["link"]] = group
        added += 1

    await db.commit()

    return {
        "status": "success",
        "added": added,
        "updated": updated,
        "skipped": skipped,
        "total_in_file": len(groups_data)
    }


@app.post("/api/groups/join")
async def join_group(
    request: GroupRequest,
    user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    result = await tg.join_group(request.phone, request.link)

    if result["status"] == "success":
        # Проверяем, есть ли уже такая группа
        stmt = select(Group).where(Group.link == request.link)
        existing = (await db.execute(stmt)).scalar_one_or_none()

        if existing:
            existing.telegram_id = str(result["group"]["id"]) if result["group"]["id"] else None
            existing.title = result["group"]["title"]
            existing.status = "joined"
            existing.is_joined = True
            existing.joined_at = datetime.utcnow()
        else:
            group = Group(
                telegram_id=str(result["group"]["id"]) if result["group"]["id"] else None,
                link=request.link,
                title=result["group"]["title"],
                status="joined",
                is_joined=True,
                joined_at=datetime.utcnow()
            )
            db.add(group)

        await db.commit()

    return result


@app.get("/api/groups")
async def get_groups(
    filter: Optional[str] = Query(None),  # all, joined, pending, failed
    user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    stmt = select(Group)

    if filter == "joined":
        stmt = stmt.where(Group.status == "joined")
    elif filter == "pending":
        stmt = stmt.where(Group.status == "pending")
    elif filter == "failed":
        stmt = stmt.where(Group.status == "failed")

    stmt = stmt.order_by(Group.added_at.desc())
    result = await db.execute(stmt)
    groups = result.scalars().all()

    return [
        {
            "id": g.id,
            "telegram_id": g.telegram_id,
            "link": g.link,
            "title": g.title,
            "city": g.city,
            "address": g.address,
            "status": g.status,
            "is_joined": g.is_joined,
            "join_error": g.join_error,
            "join_attempts": g.join_attempts,
            "source": g.source,
            "added_at": g.added_at.isoformat(),
            "joined_at": g.joined_at.isoformat() if g.joined_at else None
        }
        for g in groups
    ]


@app.get("/api/groups/stats")
async def get_groups_stats(
    user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Статистика по группам"""
    stats = {}
    for status in ["pending", "joining", "joined", "failed"]:
        stmt = select(func.count(Group.id)).where(Group.status == status)
        stats[status] = (await db.execute(stmt)).scalar() or 0

    stmt = select(func.count(Group.id))
    stats["total"] = (await db.execute(stmt)).scalar() or 0

    return stats


@app.post("/api/groups/add")
async def add_group(
    request: GroupRequest,
    user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Добавить группу без вступления (из диалогов)"""
    group = Group(
        link=request.link,
        status="joined",
        is_joined=True
    )
    db.add(group)
    await db.commit()
    await db.refresh(group)

    return {"status": "success", "group_id": group.id}


@app.delete("/api/groups/{group_id}")
async def delete_group(
    group_id: int,
    user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Удалить группу"""
    stmt = select(Group).where(Group.id == group_id)
    group = (await db.execute(stmt)).scalar_one_or_none()

    if not group:
        raise HTTPException(status_code=404, detail="Group not found")

    await db.delete(group)
    await db.commit()

    return {"status": "deleted"}


# ========== Join Worker Endpoints ==========

@app.post("/api/groups/start-joining")
async def start_joining(
    request: StartJoiningRequest,
    user=Depends(get_current_user)
):
    """Запустить процесс вступления в группы"""
    result = await join_worker.start(
        request.phone,
        limit=request.limit,
        delay_min=request.delay_min,
        delay_max=request.delay_max
    )
    return result


@app.post("/api/groups/stop-joining")
async def stop_joining(user=Depends(get_current_user)):
    """Остановить процесс вступления"""
    result = await join_worker.stop()
    return result


@app.get("/api/groups/joining-status")
async def get_joining_status(user=Depends(get_current_user)):
    """Получить статус процесса вступления"""
    return await join_worker.get_status()


# ========== Posts Endpoints ==========

@app.post("/api/posts/send")
async def send_post(
    phone: str = Form(...),
    group_ids: str = Form(...),  # comma-separated IDs
    caption: str = Form(""),
    delay_seconds: int = Form(5),
    photo: UploadFile = File(...),
    user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    # Сохраняем файл
    file_ext = os.path.splitext(photo.filename)[1]
    file_name = f"{uuid.uuid4()}{file_ext}"
    file_path = os.path.join("data", "uploads", file_name)

    async with aiofiles.open(file_path, "wb") as f:
        content = await photo.read()
        await f.write(content)

    # Создаем запись о рассылке
    group_id_list = [int(x.strip()) for x in group_ids.split(",") if x.strip()]

    # Находим аккаунт
    stmt = select(TelegramAccount).where(TelegramAccount.phone == phone)
    account = (await db.execute(stmt)).scalar_one_or_none()

    if not account:
        raise HTTPException(status_code=404, detail="Account not found")

    post = Post(
        account_id=account.id,
        caption=caption,
        photo_path=file_path,
        status="in_progress",
        delay_seconds=delay_seconds
    )
    db.add(post)
    await db.commit()
    await db.refresh(post)

    # Отправляем в каждую группу
    results = []
    success_count = 0
    fail_count = 0

    import asyncio

    for idx, group_id in enumerate(group_id_list):
        # Задержка между отправками (кроме первой)
        if idx > 0 and delay_seconds > 0:
            await asyncio.sleep(delay_seconds)

        # Получаем группу из БД
        stmt = select(Group).where(Group.id == group_id)
        group = (await db.execute(stmt)).scalar_one_or_none()

        if not group:
            continue

        # Создаем запись результата
        post_result = PostResult(
            post_id=post.id,
            group_id=group.id,
            status="sending"
        )
        db.add(post_result)
        await db.commit()
        await db.refresh(post_result)

        # Отправляем
        send_result = await tg.send_photo_to_group(
            phone,
            group.telegram_id,
            file_path,
            caption
        )

        if send_result["status"] == "success":
            post_result.status = "success"
            post_result.sent_at = datetime.utcnow()

            # Получаем message_id и формируем ссылку
            if "message_id" in send_result:
                post_result.message_id = send_result["message_id"]
                # Формируем ссылку на сообщение
                chat_id = str(group.telegram_id).replace("-100", "")
                post_result.message_link = f"https://t.me/c/{chat_id}/{send_result['message_id']}"

            success_count += 1
        else:
            post_result.status = "failed"
            post_result.error_message = send_result.get("message", "Unknown error")
            fail_count += 1

        await db.commit()

        results.append({
            "group_id": group.id,
            "group_title": group.title,
            "status": post_result.status,
            "error": post_result.error_message,
            "message_link": post_result.message_link
        })

    # Обновляем статус рассылки
    post.status = "completed"
    post.completed_at = datetime.utcnow()
    await db.commit()

    return {
        "status": "completed",
        "post_id": post.id,
        "success_count": success_count,
        "fail_count": fail_count,
        "results": results
    }


@app.get("/api/posts")
async def get_posts(
    user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    stmt = select(Post).order_by(Post.created_at.desc()).limit(50)
    result = await db.execute(stmt)
    posts = result.scalars().all()

    posts_data = []
    for p in posts:
        # Получаем результаты
        stmt = select(PostResult).where(PostResult.post_id == p.id)
        results = (await db.execute(stmt)).scalars().all()

        success = sum(1 for r in results if r.status == "success")
        failed = sum(1 for r in results if r.status == "failed")

        posts_data.append({
            "id": p.id,
            "caption": p.caption[:50] + "..." if p.caption and len(p.caption) > 50 else p.caption,
            "status": p.status,
            "created_at": p.created_at.isoformat(),
            "completed_at": p.completed_at.isoformat() if p.completed_at else None,
            "success_count": success,
            "fail_count": failed,
            "total_groups": len(results)
        })

    return posts_data


@app.get("/api/posts/{post_id}")
async def get_post_detail(
    post_id: int,
    user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    stmt = select(Post).where(Post.id == post_id)
    post = (await db.execute(stmt)).scalar_one_or_none()

    if not post:
        raise HTTPException(status_code=404, detail="Post not found")

    stmt = select(PostResult).where(PostResult.post_id == post_id)
    results = (await db.execute(stmt)).scalars().all()

    results_data = []
    for r in results:
        stmt = select(Group).where(Group.id == r.group_id)
        group = (await db.execute(stmt)).scalar_one_or_none()

        results_data.append({
            "group_id": r.group_id,
            "group_title": group.title if group else "Unknown",
            "status": r.status,
            "error": r.error_message,
            "message_id": r.message_id,
            "message_link": r.message_link,
            "sent_at": r.sent_at.isoformat() if r.sent_at else None
        })

    return {
        "id": post.id,
        "caption": post.caption,
        "photo_path": post.photo_path,
        "status": post.status,
        "created_at": post.created_at.isoformat(),
        "completed_at": post.completed_at.isoformat() if post.completed_at else None,
        "results": results_data
    }


@app.get("/api/stats")
async def get_stats(
    user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    # Количество аккаунтов
    stmt = select(func.count(TelegramAccount.id))
    accounts_count = (await db.execute(stmt)).scalar() or 0

    # Количество групп
    stmt = select(func.count(Group.id))
    groups_count = (await db.execute(stmt)).scalar() or 0

    # Количество групп с joined
    stmt = select(func.count(Group.id)).where(Group.status == "joined")
    joined_count = (await db.execute(stmt)).scalar() or 0

    # Количество рассылок
    stmt = select(func.count(Post.id))
    posts_count = (await db.execute(stmt)).scalar() or 0

    # Успешных отправок
    stmt = select(func.count(PostResult.id)).where(PostResult.status == "success")
    success_count = (await db.execute(stmt)).scalar() or 0

    return {
        "accounts": accounts_count,
        "groups": groups_count,
        "groups_joined": joined_count,
        "posts": posts_count,
        "successful_sends": success_count
    }


# ========== Messages Endpoints (Фаза 1-2) ==========

@app.post("/api/messages")
async def create_message(
    name: str = Form(""),
    caption: str = Form(""),
    photo: UploadFile = File(None),
    user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Создать новое сообщение"""
    photo_path = None

    if photo:
        file_ext = os.path.splitext(photo.filename)[1]
        file_name = f"{uuid.uuid4()}{file_ext}"
        photo_path = os.path.join("data", "uploads", file_name)

        async with aiofiles.open(photo_path, "wb") as f:
            content = await photo.read()
            await f.write(content)

    message = Message(
        name=name or f"Сообщение {datetime.now().strftime('%d.%m %H:%M')}",
        caption=caption,
        photo_path=photo_path,
        status="ready"
    )
    db.add(message)
    await db.commit()
    await db.refresh(message)

    return {
        "id": message.id,
        "name": message.name,
        "caption": message.caption,
        "photo_path": message.photo_path,
        "status": message.status
    }


@app.get("/api/messages")
async def get_messages(
    user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Получить список сообщений"""
    stmt = select(Message).order_by(Message.created_at.desc())
    result = await db.execute(stmt)
    messages = result.scalars().all()

    messages_data = []
    for m in messages:
        # Считаем статистику отправок
        stmt = select(func.count(MessageSend.id)).where(MessageSend.message_id == m.id)
        total = (await db.execute(stmt)).scalar() or 0

        stmt = select(func.count(MessageSend.id)).where(
            MessageSend.message_id == m.id,
            MessageSend.status == "sent"
        )
        sent = (await db.execute(stmt)).scalar() or 0

        stmt = select(func.count(MessageSend.id)).where(
            MessageSend.message_id == m.id,
            MessageSend.status == "failed"
        )
        failed = (await db.execute(stmt)).scalar() or 0

        messages_data.append({
            "id": m.id,
            "name": m.name,
            "caption": m.caption[:100] + "..." if m.caption and len(m.caption) > 100 else m.caption,
            "photo_path": m.photo_path,
            "status": m.status,
            "created_at": m.created_at.isoformat(),
            "stats": {
                "total": total,
                "sent": sent,
                "failed": failed,
                "pending": total - sent - failed
            }
        })

    return messages_data


@app.get("/api/messages/{message_id}")
async def get_message(
    message_id: int,
    user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Получить сообщение с деталями отправок"""
    stmt = select(Message).where(Message.id == message_id)
    message = (await db.execute(stmt)).scalar_one_or_none()

    if not message:
        raise HTTPException(status_code=404, detail="Message not found")

    # Получаем все отправки
    stmt = select(MessageSend).where(MessageSend.message_id == message_id)
    sends = (await db.execute(stmt)).scalars().all()

    sends_data = []
    for s in sends:
        stmt = select(Group).where(Group.id == s.group_id)
        group = (await db.execute(stmt)).scalar_one_or_none()

        sends_data.append({
            "id": s.id,
            "group_id": s.group_id,
            "group_title": group.title if group else "Unknown",
            "group_link": group.link if group else None,
            "status": s.status,
            "error": s.error_message,
            "message_link": s.message_link,
            "sent_at": s.sent_at.isoformat() if s.sent_at else None
        })

    return {
        "id": message.id,
        "name": message.name,
        "caption": message.caption,
        "photo_path": message.photo_path,
        "status": message.status,
        "created_at": message.created_at.isoformat(),
        "sends": sends_data
    }


@app.delete("/api/messages/{message_id}")
async def delete_message(
    message_id: int,
    user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Удалить сообщение"""
    stmt = select(Message).where(Message.id == message_id)
    message = (await db.execute(stmt)).scalar_one_or_none()

    if not message:
        raise HTTPException(status_code=404, detail="Message not found")

    # Удаляем фото если есть
    if message.photo_path and os.path.exists(message.photo_path):
        os.remove(message.photo_path)

    await db.delete(message)
    await db.commit()

    return {"status": "deleted"}


@app.get("/api/messages/{message_id}/groups")
async def get_message_groups(
    message_id: int,
    user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Получить группы со статусом отправки для сообщения"""
    # Получаем все joined группы
    stmt = select(Group).where(Group.status == "joined").order_by(Group.title)
    groups = (await db.execute(stmt)).scalars().all()

    # Получаем отправки для этого сообщения
    stmt = select(MessageSend).where(MessageSend.message_id == message_id)
    sends = (await db.execute(stmt)).scalars().all()
    sends_map = {s.group_id: s for s in sends}

    groups_data = []
    for g in groups:
        send = sends_map.get(g.id)
        groups_data.append({
            "id": g.id,
            "title": g.title or g.address or g.link,
            "link": g.link,
            "city": g.city,
            "address": g.address,
            "send_status": send.status if send else None,
            "message_link": send.message_link if send else None,
            "error": send.error_message if send else None,
            "sent_at": send.sent_at.isoformat() if send and send.sent_at else None
        })

    return groups_data


@app.post("/api/messages/{message_id}/send")
async def send_message_to_groups(
    message_id: int,
    phone: str = Form(...),
    group_ids: str = Form(...),
    delay_seconds: int = Form(5),
    user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Отправить сообщение в выбранные группы"""
    import asyncio

    # Получаем сообщение
    stmt = select(Message).where(Message.id == message_id)
    message = (await db.execute(stmt)).scalar_one_or_none()

    if not message:
        raise HTTPException(status_code=404, detail="Message not found")

    if not message.photo_path:
        raise HTTPException(status_code=400, detail="Message has no photo")

    group_id_list = [int(x.strip()) for x in group_ids.split(",") if x.strip()]

    if not group_id_list:
        raise HTTPException(status_code=400, detail="No groups selected")

    # Обновляем статус сообщения
    message.status = "sending"
    await db.commit()

    results = []
    success_count = 0
    fail_count = 0

    for idx, group_id in enumerate(group_id_list):
        # Задержка между отправками (кроме первой)
        if idx > 0 and delay_seconds > 0:
            await asyncio.sleep(delay_seconds)

        # Получаем группу
        stmt = select(Group).where(Group.id == group_id)
        group = (await db.execute(stmt)).scalar_one_or_none()

        if not group or not group.telegram_id:
            continue

        # Проверяем есть ли уже отправка
        stmt = select(MessageSend).where(
            MessageSend.message_id == message_id,
            MessageSend.group_id == group_id
        )
        existing = (await db.execute(stmt)).scalar_one_or_none()

        if existing:
            # Обновляем существующую
            send = existing
            send.status = "sending"
            send.error_message = None
        else:
            # Создаем новую
            send = MessageSend(
                message_id=message_id,
                group_id=group_id,
                status="sending"
            )
            db.add(send)

        await db.commit()
        await db.refresh(send)

        # Отправляем
        send_result = await tg.send_photo_to_group(
            phone,
            group.telegram_id,
            message.photo_path,
            message.caption or ""
        )

        if send_result["status"] == "success":
            send.status = "sent"
            send.sent_at = datetime.utcnow()

            if "message_id" in send_result:
                send.telegram_message_id = send_result["message_id"]
                chat_id = str(group.telegram_id).replace("-100", "")
                send.message_link = f"https://t.me/c/{chat_id}/{send_result['message_id']}"

            success_count += 1
        else:
            send.status = "failed"
            send.error_message = send_result.get("message", "Unknown error")
            fail_count += 1

        await db.commit()

        results.append({
            "group_id": group.id,
            "group_title": group.title,
            "group_link": group.link,
            "status": send.status,
            "error": send.error_message,
            "message_link": send.message_link
        })

    # Обновляем статус сообщения
    message.status = "completed" if fail_count == 0 else "ready"
    await db.commit()

    return {
        "status": "completed",
        "success_count": success_count,
        "fail_count": fail_count,
        "results": results
    }


@app.get("/api/messages/{message_id}/sending-status")
async def get_sending_status(
    message_id: int,
    user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Получить текущий статус отправки (для polling)"""
    stmt = select(Message).where(Message.id == message_id)
    message = (await db.execute(stmt)).scalar_one_or_none()

    if not message:
        raise HTTPException(status_code=404, detail="Message not found")

    # Статистика
    stmt = select(MessageSend).where(MessageSend.message_id == message_id)
    sends = (await db.execute(stmt)).scalars().all()

    stats = {"pending": 0, "sending": 0, "sent": 0, "failed": 0}
    latest_sends = []

    for s in sends:
        stats[s.status] = stats.get(s.status, 0) + 1

    # Последние 10 отправок
    stmt = select(MessageSend).where(
        MessageSend.message_id == message_id
    ).order_by(MessageSend.sent_at.desc()).limit(10)
    recent = (await db.execute(stmt)).scalars().all()

    for s in recent:
        stmt = select(Group).where(Group.id == s.group_id)
        group = (await db.execute(stmt)).scalar_one_or_none()

        latest_sends.append({
            "group_id": s.group_id,
            "group_title": group.title if group else "Unknown",
            "group_link": group.link if group else None,
            "status": s.status,
            "message_link": s.message_link
        })

    return {
        "message_status": message.status,
        "stats": stats,
        "is_sending": message.status == "sending",
        "recent_sends": latest_sends
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8002, reload=True)
