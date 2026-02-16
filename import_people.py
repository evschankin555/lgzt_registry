# import_users.py
import pathlib
from datetime import datetime
import asyncio

import pandas as pd
from sqlalchemy import select

from models import Base, User
from db import SessionLocal, engine

async def load_users_from_excel(excel_path):

    """
    Read users from an Excel file and insert/update them in the SQLite database.
    """

    # Читаем Excel файл с нормальными заголовками
    df = pd.read_excel(excel_path)

    print(f"Columns: {df.columns.tolist()}")
    print(f"Total rows: {len(df)}")

    # Очищаем и конвертируем дату рождения
    df["Дата рождения"] = pd.to_datetime(df["Дата рождения"], errors="coerce").dt.date

    async with SessionLocal() as session:
        imported = 0
        updated = 0

        for idx, row in enumerate(df.to_dict(orient="records"), 1):

            # Убираем NaN значения
            cleaned = {k: (None if pd.isna(v) else v) for k, v in row.items()}

            # Проверяем существование пользователя по фамилии + дате рождения
            stmt = select(User).where(
                User.last_name == cleaned["Фамилия"],
                User.date_of_birth == cleaned["Дата рождения"]
            )
            result = await session.execute(stmt)
            existing = result.scalars().one_or_none()

            if existing:
                # Обновляем базовые поля
                existing.first_name = cleaned["Имя"]
                existing.last_name = cleaned["Фамилия"]
                existing.father_name = cleaned.get("Отчество")
                existing.date_of_birth = cleaned["Дата рождения"]
                existing.counter = cleaned["№ п/п"]
                updated += 1
            else:
                user = User(
                    first_name=cleaned["Имя"],
                    last_name=cleaned["Фамилия"],
                    father_name=cleaned.get("Отчество"),
                    passport_number=None,  # Паспорта нет в новой базе
                    date_of_birth=cleaned["Дата рождения"],
                    counter=cleaned["№ п/п"]
                )
                session.add(user)
                imported += 1

            # Коммитим батчами по 1000 записей
            if idx % 1000 == 0:
                await session.commit()
                print(f"  Обработано: {idx}/{len(df)} записей...")

        await session.commit()
    print(f"\nOK: Import zavershen - dobavleno {imported}, obnovleno {updated} polzovateley")


if __name__ == "__main__":
    asyncio.run(load_users_from_excel("data/База.xlsx"))