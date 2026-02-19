# models.py
from datetime import datetime
from sqlalchemy import (
    Column, Date, DateTime, Enum, ForeignKey, Integer,
    JSON, String, UniqueConstraint
)
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()

class Company(Base):
    __tablename__ = "company"

    id = Column(Integer, primary_key=True)
    name = Column(String(255), unique=True, nullable=False)

    users = relationship("User", back_populates="company")

class User(Base):

    __tablename__ = "user"

    id = Column(Integer, primary_key=True)

    last_name = Column(String(100), nullable=False)
    first_name = Column(String(100), nullable=False)
    father_name = Column(String(100), nullable=True)
    passport_number = Column(String(100), nullable=True)  # Сделано опциональным для новой БД
    date_of_birth = Column(Date, nullable=False)
    counter = Column(Integer, nullable=False)
    address = Column(String(255))
    phone_number = Column(String(40))
    status = Column(Enum("registered", "not registered", "blocked", "deleted", name="user_status"), default="not registered")
    registered_at = Column(DateTime, nullable=True)
    blocked_at = Column(DateTime, nullable=True)
    sms_code = Column(String(10), nullable=True)
    sms_confirmed_at = Column(DateTime, nullable=True)
    company_id = Column(Integer, ForeignKey("company.id"), nullable=True)
    volunteer_id = Column(Integer, ForeignKey("user_volunteer.id"), nullable=True)
    tg_id = Column(Integer, nullable=True)
    company = relationship("Company", back_populates="users")

    __table_args__ = (
        UniqueConstraint("last_name", "date_of_birth", name="uq_user_identity"),
    )

class User_who_blocked(Base):

    __tablename__ = 'user_who_blocked'

    id = Column(Integer, primary_key=True)
    tg_id = Column(Integer, nullable=True)
    blocked_at = Column(DateTime, nullable=True)


class User_volunteer(Base):

    __tablename__ = 'user_volunteer'

    id = Column(Integer, primary_key=True)
    tg_id = Column(Integer, nullable=True)
    name = Column(String(255), nullable=True)
    name_manual = Column(Integer, default=0)  # 1 если имя задано вручную
    added_at = Column(DateTime, nullable=True)
    added_by = Column(Integer, nullable=True)
