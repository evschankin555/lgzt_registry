# seed_companies.py
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from models import Base, Company
import openpyxl

def seed_companies(sqlite_url: str = "sqlite:///app.db"):
    engine = create_engine(sqlite_url, echo=False, future=True)
    
    # Ensure tables exist
    Base.metadata.create_all(engine)
    
    # Load companies from Excel
    wb = openpyxl.load_workbook('Список предприятий.xlsx')
    ws = wb.worksheets[0]
    
    comp_list = [i[0] for i in ws.values if i[0] is not None]
    del comp_list[0]  # Remove header
    
    print(f"Найдено предприятий в файле: {len(comp_list)}")
    
    with Session(engine, future=True) as session:
        existing_companies = {c.name for c in session.query(Company).all()}
        
        new_companies = []
        updated_count = 0
        
        for name in comp_list:
            if name in existing_companies:
                updated_count += 1
            else:
                new_companies.append(Company(name=name))
        
        if new_companies:
            session.bulk_save_objects(new_companies)
            session.commit()
            print(f"Добавлено новых предприятий: {len(new_companies)}")
        
        if updated_count > 0:
            print(f"Уже существующих предприятий (пропущено): {updated_count}")
        
        total = session.query(Company).count()
        print(f"Всего предприятий в БД: {total}")

if __name__ == "__main__":
    seed_companies()