#!/usr/bin/env python3
"""
Скрипт экспорта постов из Telegram-канала.
Считывает сообщения, группирует мультимедийные посты, скачивает фото.

Запуск: python export_channel.py
"""

import os
import sys
import json
import asyncio
from datetime import datetime

# Добавляем backend в путь
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "backend"))

from telegram_client import get_client, get_session_path
from config import get_settings

# Настройки
CHANNEL_USERNAME = "zov_piter_furniture_for_life"
OUTPUT_DIR = os.path.join("data", "exports", "zov_piter")
PHOTOS_DIR = os.path.join(OUTPUT_DIR, "photos")
LIMIT = 500  # Количество сообщений для чтения


async def get_phone():
    """Получить номер телефона из существующих сессий"""
    sessions_dir = os.path.join("data", "sessions")
    if not os.path.exists(sessions_dir):
        print("Нет сессий. Запустите бота и авторизуйтесь.")
        return None

    sessions = [f.replace(".session", "") for f in os.listdir(sessions_dir) if f.endswith(".session")]
    if not sessions:
        print("Нет авторизованных сессий.")
        return None

    if len(sessions) == 1:
        phone = "+" + sessions[0]
        print(f"Используем сессию: {phone}")
        return phone

    print("Доступные сессии:")
    for i, s in enumerate(sessions):
        print(f"  {i+1}. +{s}")

    choice = input("Выберите номер сессии: ").strip()
    try:
        idx = int(choice) - 1
        phone = "+" + sessions[idx]
        return phone
    except (ValueError, IndexError):
        print("Неверный выбор.")
        return None


async def export_channel():
    phone = await get_phone()
    if not phone:
        return

    client = await get_client(phone)
    if not client.is_connected():
        await client.connect()

    if not await client.is_user_authorized():
        print("Клиент не авторизован!")
        return

    print(f"\nЧитаю канал @{CHANNEL_USERNAME}...")
    entity = await client.get_entity(CHANNEL_USERNAME)
    print(f"Канал: {entity.title}")

    # Считываем все сообщения
    all_messages = []
    count = 0
    async for message in client.iter_messages(entity, limit=LIMIT):
        count += 1
        msg_data = {
            "id": message.id,
            "date": message.date.isoformat() if message.date else None,
            "text": message.text or "",
            "grouped_id": str(message.grouped_id) if message.grouped_id else None,
            "has_photo": message.photo is not None,
            "views": message.views,
        }
        all_messages.append(msg_data)

        if count % 50 == 0:
            print(f"  Прочитано {count} сообщений...")

    print(f"Всего прочитано: {count} сообщений")

    # Группируем по grouped_id (мультимедийные посты)
    grouped = {}
    standalone = []

    for msg in all_messages:
        if msg["grouped_id"]:
            gid = msg["grouped_id"]
            if gid not in grouped:
                grouped[gid] = {
                    "messages": [],
                    "text": "",
                    "date": msg["date"],
                    "views": msg["views"],
                    "first_id": msg["id"],
                }
            grouped[gid]["messages"].append(msg)
            # Берём текст из сообщения с текстом (обычно последнее в группе)
            if msg["text"]:
                grouped[gid]["text"] = msg["text"]
            # first_id — минимальный id (первый пост группы)
            if msg["id"] < grouped[gid]["first_id"]:
                grouped[gid]["first_id"] = msg["id"]
        else:
            standalone.append(msg)

    # Формируем посты
    posts = []

    # Grouped posts
    for gid, group in grouped.items():
        photo_ids = [m["id"] for m in group["messages"] if m["has_photo"]]
        post = {
            "id": group["first_id"],
            "grouped_id": gid,
            "date": group["date"][:10] if group["date"] else None,
            "text": group["text"],
            "photos": [f"{pid}_0.jpg" for pid in sorted(photo_ids)],
            "views": group["views"],
            "link": f"https://t.me/{CHANNEL_USERNAME}/{group['first_id']}",
        }
        posts.append(post)

    # Standalone posts with photos
    for msg in standalone:
        if msg["has_photo"] or msg["text"]:
            post = {
                "id": msg["id"],
                "grouped_id": None,
                "date": msg["date"][:10] if msg["date"] else None,
                "text": msg["text"],
                "photos": [f"{msg['id']}_0.jpg"] if msg["has_photo"] else [],
                "views": msg["views"],
                "link": f"https://t.me/{CHANNEL_USERNAME}/{msg['id']}",
            }
            posts.append(post)

    # Сортируем по дате (новые первые)
    posts.sort(key=lambda p: p["date"] or "", reverse=True)

    print(f"\nСформировано постов: {len(posts)}")
    print(f"  Из них групповых: {len(grouped)}")
    print(f"  Одиночных: {len(posts) - len(grouped)}")

    # Сохраняем JSON
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    result = {
        "channel": CHANNEL_USERNAME,
        "exported_at": datetime.now().isoformat(),
        "total_messages": count,
        "total_posts": len(posts),
        "posts": posts,
    }

    json_path = os.path.join(OUTPUT_DIR, "messages.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(f"\nJSON сохранён: {json_path}")

    # Скачиваем фото
    print(f"\nСкачиваю фото в {PHOTOS_DIR}...")
    os.makedirs(PHOTOS_DIR, exist_ok=True)

    downloaded = 0
    skipped = 0
    photo_message_ids = set()

    # Собираем все ID сообщений с фото
    for post in posts:
        for photo_name in post["photos"]:
            msg_id = int(photo_name.split("_")[0])
            photo_message_ids.add(msg_id)

    print(f"Нужно скачать фото из {len(photo_message_ids)} сообщений")

    # Скачиваем
    async for message in client.iter_messages(entity, limit=LIMIT):
        if message.id in photo_message_ids and message.photo:
            filename = f"{message.id}_0.jpg"
            filepath = os.path.join(PHOTOS_DIR, filename)

            if os.path.exists(filepath):
                skipped += 1
                continue

            try:
                await client.download_media(message, file=filepath)
                downloaded += 1
                if downloaded % 10 == 0:
                    print(f"  Скачано {downloaded} фото...")
                await asyncio.sleep(0.5)  # Rate limit
            except Exception as e:
                print(f"  Ошибка скачивания {filename}: {e}")

    print(f"\nСкачано: {downloaded}, пропущено (уже есть): {skipped}")
    print(f"\nГотово! Результаты в {OUTPUT_DIR}/")


if __name__ == "__main__":
    asyncio.run(export_channel())
