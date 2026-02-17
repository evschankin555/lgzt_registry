"""
Добавление волонтёра в базу данных
"""
import asyncio
from datetime import datetime, timezone
from db import SessionLocal
from models import User_volunteer

async def add_volunteer(tg_id: int, name: str):
    async with SessionLocal() as session:
        # Проверяем есть ли уже такой волонтёр
        from sqlalchemy import select
        stmt = select(User_volunteer).where(User_volunteer.tg_id == tg_id)
        result = await session.execute(stmt)
        existing = result.scalar_one_or_none()

        if existing:
            print(f"[WARNING] Волонтёр с Telegram ID {tg_id} уже существует")
            print(f"  ID: {existing.id}")
            print(f"  Имя: {existing.name}")
            print(f"  Добавлен: {existing.added_at}")
            return

        # Создаём нового волонтёра
        volunteer = User_volunteer(
            tg_id=tg_id,
            name=name,
            added_at=datetime.now(timezone.utc),
            added_by=None  # Можно указать ID админа, который добавляет
        )

        session.add(volunteer)
        await session.commit()
        await session.refresh(volunteer)

        print(f"\n[OK] Волонтёр добавлен:")
        print(f"  ID: {volunteer.id}")
        print(f"  Telegram ID: {volunteer.tg_id}")
        print(f"  Имя: {volunteer.name}")
        print(f"  Добавлен: {volunteer.added_at}")

if __name__ == "__main__":
    import sys
    if len(sys.argv) < 3:
        print("Использование: python add_volunteer.py <TELEGRAM_ID> \"<Имя>\"")
        print("Пример: python add_volunteer.py 123456789 \"Иван Иванов\"")
        sys.exit(1)

    tg_id = int(sys.argv[1])
    name = sys.argv[2]
    asyncio.run(add_volunteer(tg_id, name))
