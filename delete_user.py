"""
Удаление регистрации пользователя (установка статуса deleted)
"""
import asyncio
from db import SessionLocal
from models import User

async def delete_user(user_id: int):
    async with SessionLocal() as session:
        user = await session.get(User, user_id)

        if not user:
            print(f"[ERROR] Пользователь с ID {user_id} не найден")
            return

        print(f"\n[INFO] Удаление пользователя ID {user_id}:")
        print(f"  ФИО: {user.last_name} {user.first_name} {user.father_name or ''}")
        print(f"  Статус: {user.status}")
        print(f"  Telegram ID: {user.tg_id or 'нет'}")

        # Устанавливаем статус deleted
        user.status = 'deleted'
        user.company_id = None

        await session.commit()

        print(f"\n[OK] Пользователь удалён (статус = deleted)")
        print(f"     Компания очищена")
        print(f"     Пользователь может зарегистрироваться снова через бота")

if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Использование: python delete_user.py <ID_пользователя>")
        print("Пример: python delete_user.py 10")
        sys.exit(1)

    user_id = int(sys.argv[1])
    asyncio.run(delete_user(user_id))
