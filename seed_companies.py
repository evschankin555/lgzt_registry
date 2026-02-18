# seed_companies.py
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from models import Base, Company, User
import openpyxl

def seed_companies(sqlite_url: str = "sqlite:///app.db"):
    engine = create_engine(sqlite_url, echo=False, future=True)

    # Ensure tables exist
    Base.metadata.create_all(engine)

    # Load companies from Excel (column 2 = company name)
    wb = openpyxl.load_workbook('Список предприятий.xlsx')
    ws = wb.worksheets[0]

    # Read company names from second column (index 1), strip whitespace, skip empty
    comp_list = [row[1].strip() for row in ws.values if row[1] and str(row[1]).strip()]

    print(f"Найдено предприятий в файле: {len(comp_list)}")

    with Session(engine, future=True) as session:
        # Get all existing companies
        existing_companies = {c.name: c for c in session.query(Company).all()}
        excel_companies_set = set(comp_list)

        # Find companies to delete (in DB but not in Excel)
        to_delete = []
        for name, company in existing_companies.items():
            if name not in excel_companies_set:
                # Check if any users are assigned to this company
                user_count = session.query(User).filter(User.company_id == company.id).count()
                if user_count > 0:
                    print(f"⚠️  Не могу удалить '{name}' - к ней привязано {user_count} пользователей")
                else:
                    to_delete.append(company)

        # Delete companies
        if to_delete:
            for company in to_delete:
                session.delete(company)
            session.commit()
            print(f"Удалено предприятий: {len(to_delete)}")
            for c in to_delete:
                print(f"  - {c.name}")

        # Find companies to add (in Excel but not in DB)
        new_companies = []
        kept_count = 0

        for name in comp_list:
            if name in existing_companies:
                kept_count += 1
            else:
                new_companies.append(Company(name=name))

        # Add new companies
        if new_companies:
            session.bulk_save_objects(new_companies)
            session.commit()
            print(f"Добавлено новых предприятий: {len(new_companies)}")
            for c in new_companies:
                print(f"  + {c.name}")

        if kept_count > 0:
            print(f"Оставлено существующих предприятий: {kept_count}")

        total = session.query(Company).count()
        print(f"\nВсего предприятий в БД: {total}")

if __name__ == "__main__":
    seed_companies()