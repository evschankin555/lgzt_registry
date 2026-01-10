# modules/auto_migrate.py
"""
Автоматическая миграция БД при старте бота.
Проверяет наличие новых полей и добавляет их если отсутствуют.
"""

import logging
from sqlalchemy import text, inspect
from db import engine

logger = logging.getLogger(__name__)


async def check_and_migrate():
    """
    Проверить и применить миграции при старте бота.
    Безопасно добавляет недостающие колонки.
    """
    logger.info("Checking database migrations...")

    async with engine.begin() as conn:
        # Получаем инспектор для проверки структуры таблиц
        def get_columns(connection, table_name):
            inspector = inspect(connection)
            try:
                columns = inspector.get_columns(table_name)
                return {col['name'] for col in columns}
            except Exception:
                return set()

        # Проверяем таблицу user_volunteer
        existing_columns = await conn.run_sync(
            lambda sync_conn: get_columns(sync_conn, 'user_volunteer')
        )

        if existing_columns:  # Таблица существует
            migrations_applied = []

            # Проверяем и добавляем поле name
            if 'name' not in existing_columns:
                await conn.execute(text(
                    "ALTER TABLE user_volunteer ADD COLUMN name VARCHAR(255)"
                ))
                migrations_applied.append('name')
                logger.info("Added column 'name' to user_volunteer")

            # Проверяем и добавляем поле added_at
            if 'added_at' not in existing_columns:
                await conn.execute(text(
                    "ALTER TABLE user_volunteer ADD COLUMN added_at DATETIME"
                ))
                migrations_applied.append('added_at')
                logger.info("Added column 'added_at' to user_volunteer")

            # Проверяем и добавляем поле added_by
            if 'added_by' not in existing_columns:
                await conn.execute(text(
                    "ALTER TABLE user_volunteer ADD COLUMN added_by INTEGER"
                ))
                migrations_applied.append('added_by')
                logger.info("Added column 'added_by' to user_volunteer")

            if migrations_applied:
                logger.info(f"Migrations applied: {migrations_applied}")
            else:
                logger.info("No migrations needed")
        else:
            logger.info("Table user_volunteer not found, will be created by SQLAlchemy")

    logger.info("Database migration check complete")
