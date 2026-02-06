"""
Join Worker - фоновый процесс для постепенного вступления в группы
"""
import asyncio
from datetime import datetime
from typing import Optional
from sqlalchemy import select, or_
from sqlalchemy.ext.asyncio import AsyncSession

from database import async_session
from models import Group, TelegramAccount
import telegram_client as tg


class JoinWorker:
    """Воркер для постепенного вступления в группы"""

    def __init__(self):
        self.is_running = False
        self.current_task: Optional[asyncio.Task] = None
        self.stats = {
            "pending": 0,
            "joining": 0,
            "joined": 0,
            "failed": 0,
            "current_group": None,
            "next_attempt_in": 0
        }
        self.delay_min = 30  # Минимальная задержка между вступлениями (сек)
        self.delay_max = 60  # Максимальная задержка
        self.max_attempts = 3  # Максимум попыток на группу

    async def start(self, phone: str):
        """Запустить воркер"""
        if self.is_running:
            return {"status": "already_running"}

        self.is_running = True
        self.current_task = asyncio.create_task(self._run(phone))
        return {"status": "started"}

    async def stop(self):
        """Остановить воркер"""
        self.is_running = False
        if self.current_task:
            self.current_task.cancel()
            try:
                await self.current_task
            except asyncio.CancelledError:
                pass
        return {"status": "stopped"}

    async def get_status(self) -> dict:
        """Получить текущий статус"""
        async with async_session() as db:
            # Подсчёт по статусам
            for status in ["pending", "joined", "failed"]:
                stmt = select(Group).where(Group.status == status)
                result = await db.execute(stmt)
                self.stats[status] = len(result.scalars().all())

            # Joining считаем отдельно
            stmt = select(Group).where(Group.status == "joining")
            result = await db.execute(stmt)
            self.stats["joining"] = len(result.scalars().all())

        return {
            "is_running": self.is_running,
            "stats": self.stats
        }

    async def _run(self, phone: str):
        """Основной цикл воркера"""
        import random

        while self.is_running:
            try:
                async with async_session() as db:
                    # Берём группу для вступления
                    stmt = select(Group).where(
                        or_(
                            Group.status == "pending",
                            # Retry failed с < max попыток
                            (Group.status == "failed") & (Group.join_attempts < self.max_attempts)
                        )
                    ).order_by(Group.added_at).limit(1)

                    result = await db.execute(stmt)
                    group = result.scalar_one_or_none()

                    if not group:
                        # Нет групп для вступления
                        self.stats["current_group"] = None
                        await asyncio.sleep(10)
                        continue

                    # Обновляем статус
                    group.status = "joining"
                    group.join_attempts += 1
                    group.last_attempt_at = datetime.utcnow()
                    self.stats["current_group"] = group.link
                    await db.commit()

                    # Пробуем вступить
                    result = await self._join_group(phone, group.link)

                    if result["status"] == "success":
                        group.status = "joined"
                        group.is_joined = True
                        group.joined_at = datetime.utcnow()
                        group.telegram_id = str(result.get("group_id", ""))
                        group.title = result.get("title", "")
                        group.join_error = None
                    else:
                        group.status = "failed"
                        group.join_error = result.get("error", "Unknown error")

                    await db.commit()

                # Случайная задержка
                delay = random.randint(self.delay_min, self.delay_max)
                self.stats["next_attempt_in"] = delay

                for i in range(delay):
                    if not self.is_running:
                        break
                    self.stats["next_attempt_in"] = delay - i
                    await asyncio.sleep(1)

            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"JoinWorker error: {e}")
                await asyncio.sleep(10)

    async def _join_group(self, phone: str, link: str) -> dict:
        """Вступить в группу"""
        try:
            result = await tg.join_group(phone, link)
            if result["status"] == "success":
                return {
                    "status": "success",
                    "group_id": result["group"].get("id"),
                    "title": result["group"].get("title")
                }
            else:
                return {
                    "status": "error",
                    "error": result.get("message", "Unknown error")
                }
        except Exception as e:
            return {
                "status": "error",
                "error": str(e)
            }


# Глобальный экземпляр воркера
join_worker = JoinWorker()
