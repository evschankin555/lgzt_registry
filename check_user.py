"""
Проверка пользователя и получение его Telegram ID
"""
import asyncio
from db import SessionLocal
from models import User

async def check_user(user_id: int):
    async with SessionLocal() as session:
        user = await session.get(User, user_id)

        if not user:
            print(f"[ERROR] Пользователь с ID {user_id} не найден")
            return

        print(f"\n[INFO] Пользователь ID {user_id}:")
        print(f"  ФИО: {user.last_name} {user.first_name} {user.father_name or ''}")
        print(f"  Телефон: {user.phone_number or 'не указан'}")
        print(f"  Telegram ID: {user.tg_id or 'НЕ ЗАРЕГИСТРИРОВАН В БОТЕ'}")
        print(f"  Статус: {user.status}")
        print(f"  Компания ID: {user.company_id}")

        if user.tg_id:
            print(f"\n[OK] Telegram ID для добавления в админы: {user.tg_id}")
        else:
            print(f"\n[WARNING] Пользователь ещё не зарегистрирован в боте!")
            print(f"   Попросите его написать боту /start")

if __name__ == "__main__":
    import sys
    user_id = int(sys.argv[1]) if len(sys.argv) > 1 else 10
    asyncio.run(check_user(user_id))
