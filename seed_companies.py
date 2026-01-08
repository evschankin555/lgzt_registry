# seed_companies.py
from db import SessionLocal
from models import Company
import openpyxl

wb = openpyxl.load_workbook('Список предприятий.xlsx')

ws = wb.worksheets[0]

comp_list = [i[0] for i in ws.values if i[0] is not None]

del comp_list[0]

def seed_companies():
    db = SessionLocal()
    try:
        db.bulk_save_objects([Company(name=n) for n in comp_list])
        db.commit()
    finally:
        db.close()

if __name__ == "__main__":
    seed_companies()