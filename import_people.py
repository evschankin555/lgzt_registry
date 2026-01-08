# import_users.py
import pathlib
from datetime import datetime

import pandas as pd
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from models import Base, User  # reuse the models defined earlier

def load_users_from_excel(excel_path, sqlite_url: str = "sqlite:///app.db"):

    """
    Read users from an Excel file and insert/update them in the SQLite database.
    """


    engine = create_engine(sqlite_url, echo=False, future=True)

    # Ensure tables exist
    Base.metadata.create_all(engine)

    df = pd.read_excel(excel_path, usecols=[0,1,2,3,4,5])

    print(df.columns)

    # Clean and convert the date column
    df["Дата рождения"] = pd.to_datetime(df["Дата рождения"], errors="coerce").dt.date

    with Session(engine, future=True) as session:

        for row in df.to_dict(orient="records"):

            # Drop NaN values so SQLAlchemy receives None
            cleaned = {k: (None if pd.isna(v) else v) for k, v in row.items()}

            # Check if the user already exists using passport + country as the unique key
            existing = (
                session.query(User)
                .filter(
                    User.passport_number == cleaned["СЕРИЯ номер паспорта"],
                )
                .one_or_none()
            )

            if existing:
                # Update base fields; skip address/phone since users supply them later
                existing.first_name = cleaned["Имя"]
                existing.last_name = cleaned["Фамилия"]
                existing.date_of_birth = cleaned["Дата рождения"]
                existing.counter = cleaned["№ п/п"]
            else:
                user = User(
                    first_name=cleaned["Имя"],
                    last_name=cleaned["Фамилия"],
                    passport_number=cleaned["СЕРИЯ номер паспорта"],
                    date_of_birth=cleaned["Дата рождения"],
                    counter=cleaned["№ п/п"]
                )
                session.add(user)

        session.commit()
    print(f"Imported {len(df)} users into {sqlite_url}")


if __name__ == "__main__":
    load_users_from_excel("data/База.xlsx")