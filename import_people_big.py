# import_users_optimized.py
import pandas as pd
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from models import Base, User

def load_users_from_excel(excel_path, sqlite_url: str = "sqlite:///app.db", batch_size: int = 5000):
    """
    Load users from Excel into the SQLite database efficiently.
    """

    engine = create_engine(sqlite_url, echo=False, future=True)

    # Ensure tables exist
    Base.metadata.create_all(engine)

    # Load the Excel file
    df = pd.read_excel(excel_path, usecols=[0, 1, 2, 3, 4, 5])

    # Rename columns to simpler keys (optional but cleaner)
    df.columns = ["passport_num", "counter", "last_name", "first_name", "father_name", "dob"]

    # Convert DOB to proper date objects
    df["dob"] = pd.to_datetime(df["dob"], errors="coerce").dt.date

    # Drop completely invalid rows
    df = df.dropna(subset=["passport_num", "first_name", "last_name", "dob"])

    print(f"Read {len(df)} users from Excel")

    with Session(engine, future=True) as session:
        # Load all existing passport numbers once
        existing_passports = set(x for (x,) in session.execute(select(User.passport_number)).all())
        print(f"{len(existing_passports)} existing users in the database")

        to_insert = []
        updated = 0

        for i, row in enumerate(df.to_dict(orient="records"), start=1):
            passport = row["passport_num"]

            if passport in existing_passports:
                # Optional: batch update existing users if you need
                session.query(User).filter_by(passport_number=passport).update({
                    "first_name": row["first_name"],
                    "last_name": row["last_name"],
                    "father_name": row["father_name"],
                    "date_of_birth": row["dob"],
                    "counter": int(row["counter"]),
                })
                updated += 1
            else:
                to_insert.append(
                    User(
                        passport_number=passport,
                        first_name=row["first_name"],
                        last_name=row["last_name"],
                        father_name=row.get("father_name"),
                        date_of_birth=row["dob"],
                        counter=int(row["counter"]),
                    )
                )

            # Batch insert every N rows
            if len(to_insert) >= batch_size:
                session.bulk_save_objects(to_insert)
                session.commit()
                existing_passports.update(u.passport_number for u in to_insert)

                to_insert.clear()
                print(f"Processed {i} rows...")

        # Insert remaining users
        if to_insert:
            session.bulk_save_objects(to_insert)
            session.commit()

        print(f"✅ Import complete: inserted {len(df) - updated} new, updated {updated} users.")

if __name__ == "__main__":
    load_users_from_excel("data/База.xlsx")