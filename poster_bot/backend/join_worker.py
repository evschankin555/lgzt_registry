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
            "next_attempt_in": 0,
            "joined_this_session": 0,
            "limit": 0
        }
        self.delay_min = 30  # Минимальная задержка между вступлениями (сек)
        self.delay_max = 60  # Максимальная задержка
        self.max_attempts = 3  # Максимум попыток на группу
        self.limit = 0  # Лимит на сессию (0 = без лимита)
        self.joined_this_session = 0  # Счётчик вступлений в текущей сессии

    async def start(self, phone: str, limit: int = 0, delay_min: int = 30, delay_max: int = 60):
        """Запустить воркер"""
        if self.is_running:
            return {"status": "already_running"}

        self.is_running = True
        self.limit = limit
        self.delay_min = delay_min
        self.delay_max = delay_max
        self.joined_this_session = 0
        self.stats["joined_this_session"] = 0
        self.stats["limit"] = limit
        self.current_task = asyncio.create_task(self._run(phone))
        return {"status": "started", "limit": limit, "delay_min": delay_min, "delay_max": delay_max}

    async def stop(self):
        """Остановить воркер"""
        self.is_running = False
        if self.current_task:
            self.current_task.cancel()
            try:
                await self.current_task
            except asyncio.CancelledError:
                pass
        return {"status": "stopped", "joined_this_session": self.joined_this_session}

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

        self.stats["joined_this_session"] = self.joined_this_session
        self.stats["limit"] = self.limit

        return {
            "is_running": self.is_running,
            "stats": self.stats
        }

    async def _run(self, phone: str):
        """Основной цикл воркера"""
        import random
        import re

        while self.is_running:
            # Проверяем лимит
            if self.limit > 0 and self.joined_this_session >= self.limit:
                print(f"JoinWorker: достигнут лимит {self.limit} групп")
                self.is_running = False
                self.stats["current_group"] = None
                break

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
                        # Нет групп для вступления - останавливаемся
                        print("JoinWorker: нет групп для вступления")
                        self.stats["current_group"] = None
                        self.is_running = False
                        break

                    # Обновляем статус
                    group.status = "joining"
                    group.join_attempts += 1
                    group.last_attempt_at = datetime.utcnow()
                    self.stats["current_group"] = group.link
                    await db.commit()

                    # Пробуем вступить
                    result = await self._join_group(phone, group.link)

                    join_success = False
                    if result["status"] == "success":
                        group.status = "joined"
                        group.is_joined = True
                        group.joined_at = datetime.utcnow()
                        group.telegram_id = str(result.get("group_id", ""))
                        group.title = result.get("title", "")
                        group.join_error = None
                        self.joined_this_session += 1
                        self.stats["joined_this_session"] = self.joined_this_session
                        join_success = True
                    else:
                        error_msg = result.get("error", "Unknown error")

                        # Проверяем FloodWait
                        flood_match = re.search(r'wait of (\d+) second', error_msg.lower())
                        if flood_match:
                            wait_seconds = int(flood_match.group(1))
                            # Возвращаем в pending, не помечаем как failed
                            group.status = "pending"
                            group.join_error = error_msg
                            print(f"FloodWait: ждём {wait_seconds}с для {group.link}")
                            await db.commit()

                            # Ждём N + 10 секунд
                            total_wait = wait_seconds + 10
                            self.stats["next_attempt_in"] = total_wait
                            for i in range(total_wait):
                                if not self.is_running:
                                    break
                                self.stats["next_attempt_in"] = total_wait - i
                                await asyncio.sleep(1)
                            continue
                        else:
                            # Другие ошибки — помечаем как failed
                            group.status = "failed"
                            group.join_error = error_msg

                    await db.commit()

                # После успеха — полная задержка 30-60 сек, после ошибки — 5 сек
                if join_success:
                    delay = random.randint(max(30, self.delay_min), max(30, self.delay_max))
                else:
                    delay = 5

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
