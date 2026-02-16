"""
FastAPI backend для Registry Dashboard
"""
from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime, timedelta, timezone
import sys
from pathlib import Path

# Добавляем корневую директорию проекта в путь
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from sqlalchemy import select, func, update, delete
from db import SessionLocal
from models import User, Company, User_volunteer
from auth import create_access_token, verify_password, get_current_user
from config import API_PREFIX, CORS_ORIGINS

app = FastAPI(title="Registry Dashboard API")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ===== МОДЕЛИ ЗАПРОСОВ =====

class LoginRequest(BaseModel):
    password: str

class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"

class VolunteerUpdate(BaseModel):
    name: str

class UserUpdate(BaseModel):
    company_id: Optional[int] = None
    status: Optional[str] = None

# ===== АВТОРИЗАЦИЯ =====

@app.post(f"{API_PREFIX}/login", response_model=LoginResponse)
async def login(request: LoginRequest):
    """Авторизация по паролю"""
    if not verify_password(request.password):
        raise HTTPException(status_code=401, detail="Invalid password")

    token = create_access_token({"sub": "admin"})
    return LoginResponse(access_token=token)

# ===== СТАТИСТИКА =====

@app.get(f"{API_PREFIX}/stats")
async def get_stats(current_user: dict = Depends(get_current_user)):
    """Получить статистику"""
    async with SessionLocal() as session:
        now = datetime.now(timezone.utc)

        # Общее количество
        total_stmt = select(func.count(User.id))
        total = (await session.execute(total_stmt)).scalar()

        # По статусам
        registered_stmt = select(func.count(User.id)).where(User.status == 'registered')
        registered = (await session.execute(registered_stmt)).scalar()

        # За сегодня
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        today_stmt = select(func.count(User.id)).where(
            User.status == 'registered',
            User.registered_at >= today_start
        )
        today = (await session.execute(today_stmt)).scalar()

        # За неделю
        week_start = now - timedelta(days=7)
        week_stmt = select(func.count(User.id)).where(
            User.status == 'registered',
            User.registered_at >= week_start
        )
        week = (await session.execute(week_stmt)).scalar()

        # За месяц
        month_start = now - timedelta(days=30)
        month_stmt = select(func.count(User.id)).where(
            User.status == 'registered',
            User.registered_at >= month_start
        )
        month = (await session.execute(month_stmt)).scalar()

        # Компании
        companies_stmt = select(func.count(Company.id))
        companies = (await session.execute(companies_stmt)).scalar()

        # Волонтеры
        volunteers_stmt = select(func.count(User_volunteer.id))
        volunteers = (await session.execute(volunteers_stmt)).scalar()

        return {
            "total": total,
            "registered": registered,
            "today": today,
            "week": week,
            "month": month,
            "companies": companies,
            "volunteers": volunteers
        }

# ===== ПОЛЬЗОВАТЕЛИ =====

@app.get(f"{API_PREFIX}/users")
async def get_users(
    page: int = 0,
    limit: int = 20,
    status: Optional[str] = None,
    search: Optional[str] = None,
    current_user: dict = Depends(get_current_user)
):
    """Получить список пользователей с пагинацией"""
    async with SessionLocal() as session:
        # Базовый запрос
        base_query = select(User).join(Company, User.company_id == Company.id, isouter=True)
        count_query = select(func.count(User.id))

        # Фильтры
        if status:
            base_query = base_query.where(User.status == status)
            count_query = count_query.where(User.status == status)

        if search:
            search_filter = f"%{search}%"
            base_query = base_query.where(
                (User.last_name.ilike(search_filter)) |
                (User.first_name.ilike(search_filter)) |
                (User.phone_number.ilike(search_filter))
            )
            count_query = count_query.where(
                (User.last_name.ilike(search_filter)) |
                (User.first_name.ilike(search_filter)) |
                (User.phone_number.ilike(search_filter))
            )

        # Общее количество
        total = (await session.execute(count_query)).scalar()

        # Пользователи с пагинацией
        stmt = base_query.order_by(User.id.desc()).offset(page * limit).limit(limit)
        result = await session.execute(stmt)
        users = result.scalars().all()

        # Получаем компании для пользователей
        users_data = []
        for user in users:
            company_name = None
            if user.company_id:
                company = await session.get(Company, user.company_id)
                if company:
                    company_name = company.name

            users_data.append({
                "id": user.id,
                "last_name": user.last_name,
                "first_name": user.first_name,
                "father_name": user.father_name,
                "phone_number": user.phone_number,
                "date_of_birth": user.date_of_birth.isoformat() if user.date_of_birth else None,
                "address": user.address,
                "status": user.status,
                "company_id": user.company_id,
                "company_name": company_name,
                "registered_at": user.registered_at.isoformat() if user.registered_at else None,
                "tg_id": user.tg_id
            })

        return {
            "users": users_data,
            "total": total,
            "page": page,
            "limit": limit,
            "pages": (total + limit - 1) // limit
        }

@app.get(f"{API_PREFIX}/users/{{user_id}}")
async def get_user(user_id: int, current_user: dict = Depends(get_current_user)):
    """Получить пользователя по ID"""
    async with SessionLocal() as session:
        user = await session.get(User, user_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        company_name = None
        if user.company_id:
            company = await session.get(Company, user.company_id)
            if company:
                company_name = company.name

        return {
            "id": user.id,
            "last_name": user.last_name,
            "first_name": user.first_name,
            "father_name": user.father_name,
            "phone_number": user.phone_number,
            "date_of_birth": user.date_of_birth.isoformat() if user.date_of_birth else None,
            "address": user.address,
            "status": user.status,
            "company_id": user.company_id,
            "company_name": company_name,
            "registered_at": user.registered_at.isoformat() if user.registered_at else None,
            "tg_id": user.tg_id
        }

@app.patch(f"{API_PREFIX}/users/{{user_id}}")
async def update_user(
    user_id: int,
    update_data: UserUpdate,
    current_user: dict = Depends(get_current_user)
):
    """Обновить пользователя"""
    async with SessionLocal() as session:
        user = await session.get(User, user_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        if update_data.company_id is not None:
            company = await session.get(Company, update_data.company_id)
            if not company:
                raise HTTPException(status_code=404, detail="Company not found")
            user.company_id = update_data.company_id

        if update_data.status is not None:
            user.status = update_data.status

        await session.commit()
        return {"success": True}

@app.delete(f"{API_PREFIX}/users/{{user_id}}")
async def delete_user(user_id: int, current_user: dict = Depends(get_current_user)):
    """Удалить пользователя (установить статус deleted)"""
    async with SessionLocal() as session:
        user = await session.get(User, user_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        user.status = 'deleted'
        user.company_id = None
        await session.commit()
        return {"success": True}

# ===== КОМПАНИИ =====

@app.get(f"{API_PREFIX}/companies")
async def get_companies(current_user: dict = Depends(get_current_user)):
    """Получить список компаний со статистикой"""
    async with SessionLocal() as session:
        stmt = (
            select(
                Company.id,
                Company.name,
                func.count(User.id).label("user_count")
            )
            .outerjoin(User, (User.company_id == Company.id) & (User.status == 'registered'))
            .group_by(Company.id, Company.name)
            .order_by(Company.id)
        )
        result = await session.execute(stmt)
        companies = result.all()

        return {
            "companies": [
                {
                    "id": c.id,
                    "name": c.name,
                    "user_count": c.user_count
                }
                for c in companies
            ]
        }

# ===== ВОЛОНТЕРЫ =====

@app.get(f"{API_PREFIX}/volunteers")
async def get_volunteers(current_user: dict = Depends(get_current_user)):
    """Получить список волонтеров"""
    async with SessionLocal() as session:
        stmt = select(User_volunteer).order_by(User_volunteer.id.desc())
        result = await session.execute(stmt)
        volunteers = result.scalars().all()

        return {
            "volunteers": [
                {
                    "id": v.id,
                    "tg_id": v.tg_id,
                    "name": v.name,
                    "added_at": v.added_at.isoformat() if v.added_at else None,
                    "added_by": v.added_by
                }
                for v in volunteers
            ]
        }

@app.patch(f"{API_PREFIX}/volunteers/{{volunteer_id}}")
async def update_volunteer(
    volunteer_id: int,
    update_data: VolunteerUpdate,
    current_user: dict = Depends(get_current_user)
):
    """Обновить имя волонтера"""
    async with SessionLocal() as session:
        volunteer = await session.get(User_volunteer, volunteer_id)
        if not volunteer:
            raise HTTPException(status_code=404, detail="Volunteer not found")

        volunteer.name = update_data.name
        await session.commit()
        return {"success": True}

@app.delete(f"{API_PREFIX}/volunteers/{{volunteer_id}}")
async def delete_volunteer(volunteer_id: int, current_user: dict = Depends(get_current_user)):
    """Удалить волонтера"""
    async with SessionLocal() as session:
        volunteer = await session.get(User_volunteer, volunteer_id)
        if not volunteer:
            raise HTTPException(status_code=404, detail="Volunteer not found")

        await session.delete(volunteer)
        await session.commit()
        return {"success": True}

# ===== ЭКСПОРТ =====

@app.get(f"{API_PREFIX}/export/excel")
async def export_excel(current_user: dict = Depends(get_current_user)):
    """Экспортировать все данные в Excel"""
    from functions import generate_excel

    await generate_excel()

    return FileResponse(
        path="excel_dump.xlsx",
        filename="registry_export.xlsx",
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

# ===== HEALTHCHECK =====

@app.get("/health")
async def health():
    """Проверка работоспособности"""
    return {"status": "ok"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8002)
