from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

DATABASE_URI = "sqlite+aiosqlite:///app.db"

engine = create_async_engine(DATABASE_URI, echo=False, future=True)

# scoped_session so you can safely use it in multi‑threaded contexts
SessionLocal = async_sessionmaker(
    bind=engine,
    expire_on_commit=False,
    class_=AsyncSession,
)