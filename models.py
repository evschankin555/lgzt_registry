# models.py
from datetime import datetime
from sqlalchemy import (
    BigInteger, Column, Date, DateTime, Enum, ForeignKey, Integer,
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
    passport_number = Column(String(100), nullable=True)  # optional for new DBs
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
    tg_id = Column(BigInteger, nullable=True)
    company = relationship("Company", back_populates="users")
    identities = relationship(
        "UserIdentity",
        back_populates="user",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        UniqueConstraint("last_name", "date_of_birth", name="uq_user_identity"),
    )


class User_who_blocked(Base):

    __tablename__ = "user_who_blocked"

    id = Column(Integer, primary_key=True)
    tg_id = Column(BigInteger, nullable=True)
    blocked_at = Column(DateTime, nullable=True)


class User_volunteer(Base):

    __tablename__ = "user_volunteer"

    id = Column(Integer, primary_key=True)
    tg_id = Column(BigInteger, nullable=True)
    name = Column(String(255), nullable=True)
    name_manual = Column(Integer, default=0)
    added_at = Column(DateTime, nullable=True)
    added_by = Column(BigInteger, nullable=True)
    identities = relationship(
        "VolunteerIdentity",
        back_populates="volunteer",
        cascade="all, delete-orphan",
    )


class UserIdentity(Base):

    __tablename__ = "user_identity"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("user.id", ondelete="CASCADE"), nullable=False)
    provider = Column(String(50), nullable=False)
    external_user_id = Column(String(255), nullable=False)
    payload = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    last_seen_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    user = relationship("User", back_populates="identities")

    __table_args__ = (
        UniqueConstraint("provider", "external_user_id", name="uq_user_identity_provider_external"),
    )


class VolunteerIdentity(Base):

    __tablename__ = "volunteer_identity"

    id = Column(Integer, primary_key=True)
    volunteer_id = Column(Integer, ForeignKey("user_volunteer.id", ondelete="CASCADE"), nullable=False)
    provider = Column(String(50), nullable=False)
    external_user_id = Column(String(255), nullable=False)
    payload = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    last_seen_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    volunteer = relationship("User_volunteer", back_populates="identities")

    __table_args__ = (
        UniqueConstraint("provider", "external_user_id", name="uq_volunteer_identity_provider_external"),
    )


class PlatformRole(Base):

    __tablename__ = "platform_role"

    id = Column(Integer, primary_key=True)
    provider = Column(String(50), nullable=False)
    external_user_id = Column(String(255), nullable=False)
    role = Column(String(50), nullable=False)
    payload = Column(JSON, nullable=True)
    granted_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    __table_args__ = (
        UniqueConstraint("provider", "external_user_id", "role", name="uq_platform_role"),
    )


class BlockedIdentityEvent(Base):

    __tablename__ = "blocked_identity_event"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("user.id"), nullable=True)
    provider = Column(String(50), nullable=False)
    external_user_id = Column(String(255), nullable=False)
    blocked_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    payload = Column(JSON, nullable=True)


class ConversationState(Base):

    __tablename__ = "conversation_state"

    id = Column(Integer, primary_key=True)
    storage_key = Column(String(512), nullable=False)
    provider = Column(String(50), nullable=False)
    external_user_id = Column(String(255), nullable=False)
    chat_id = Column(String(255), nullable=False)
    business_connection_id = Column(String(255), nullable=True)
    message_thread_id = Column(BigInteger, nullable=True)
    bot_id = Column(BigInteger, nullable=True)
    state = Column(String(255), nullable=True)
    data = Column(JSON, nullable=False, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    __table_args__ = (
        UniqueConstraint("storage_key", name="uq_conversation_state_storage_key"),
    )
