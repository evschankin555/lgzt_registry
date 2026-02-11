"""
AutoWorker - автоматический постинг по расписанию
Новая логика: работа с MessageTarget (целевые группы сообщения)
"""
import asyncio
import random
from datetime import datetime, date, timedelta
from typing import Optional
from sqlalchemy import select, and_, func
from sqlalchemy.ext.asyncio import AsyncSession

from database import async_session
from models import Group, Message, MessageTarget, DailyStats, BotSettings
import telegram_client as tg


class AutoWorker:
    """Автоматический воркер с расписанием"""

    def __init__(self):
        self.is_running = False
        self.current_task: Optional[asyncio.Task] = None
        self.phone: Optional[str] = None
        self.status = {
            "mode": "idle",  # idle, joining, sending, sleeping
            "current_action": None,
            "next_action_in": 0,
            "today_joins": 0,
            "today_sends": 0,
            "today_leaves": 0,
            "daily_limit": 100,
            "session_joins": 0,
            "session_sends": 0,
        }

    async def start(self, phone: str):
        """Запустить автоматический режим"""
        if self.is_running:
            return {"status": "already_running"}

        self.is_running = True
        self.phone = phone
        self.status["session_joins"] = 0
        self.status["session_sends"] = 0
        self.current_task = asyncio.create_task(self._run())
        return {"status": "started"}

    async def stop(self):
        """Остановить автоматический режим"""
        self.is_running = False
        if self.current_task:
            self.current_task.cancel()
            try:
                await self.current_task
            except asyncio.CancelledError:
                pass
        self.status["mode"] = "idle"
        return {"status": "stopped"}

    async def get_status(self) -> dict:
        """Получить текущий статус"""
        await self._load_daily_stats()
        return {
            "is_running": self.is_running,
            "status": self.status
        }

    async def _load_daily_stats(self):
        """Загрузить статистику за сегодня"""
        async with async_session() as db:
            today = date.today()
            stmt = select(DailyStats).where(DailyStats.date == today)
            stats = (await db.execute(stmt)).scalar_one_or_none()

            if stats:
                self.status["today_joins"] = stats.joins_count
                self.status["today_sends"] = stats.sends_count
                self.status["today_leaves"] = stats.leaves_count
            else:
                self.status["today_joins"] = 0
                self.status["today_sends"] = 0
                self.status["today_leaves"] = 0

            # Загружаем настройки
            stmt = select(BotSettings).limit(1)
            settings = (await db.execute(stmt)).scalar_one_or_none()
            if settings:
                self.status["daily_limit"] = settings.daily_limit

    async def _get_settings(self, db: AsyncSession) -> BotSettings:
        """Получить или создать настройки"""
        stmt = select(BotSettings).limit(1)
        settings = (await db.execute(stmt)).scalar_one_or_none()

        if not settings:
            settings = BotSettings()
            db.add(settings)
            await db.commit()
            await db.refresh(settings)

        return settings

    async def _get_or_create_daily_stats(self, db: AsyncSession) -> DailyStats:
        """Получить или создать статистику за сегодня"""
        today = date.today()
        stmt = select(DailyStats).where(DailyStats.date == today)
        stats = (await db.execute(stmt)).scalar_one_or_none()

        if not stats:
            stats = DailyStats(date=today)
            db.add(stats)
            await db.commit()
            await db.refresh(stats)

        return stats

    async def _increment_stat(self, stat_type: str):
        """Увеличить счётчик статистики"""
        async with async_session() as db:
            stats = await self._get_or_create_daily_stats(db)
            if stat_type == "join":
                stats.joins_count += 1
                self.status["today_joins"] = stats.joins_count
                self.status["session_joins"] += 1
            elif stat_type == "send":
                stats.sends_count += 1
                self.status["today_sends"] = stats.sends_count
                self.status["session_sends"] += 1
            elif stat_type == "leave":
                stats.leaves_count += 1
                self.status["today_leaves"] = stats.leaves_count
            await db.commit()

    async def _can_do_action(self) -> bool:
        """Проверить можно ли выполнить действие (лимит)"""
        async with async_session() as db:
            settings = await self._get_settings(db)
            stats = await self._get_or_create_daily_stats(db)
            total = stats.joins_count + stats.sends_count
            return total < settings.daily_limit

    async def _run(self):
        """Основной цикл"""
        while self.is_running:
            try:
                async with async_session() as db:
                    settings = await self._get_settings(db)

                # Определяем текущий час (МСК = UTC+3)
                now = datetime.utcnow() + timedelta(hours=3)
                hour = now.hour

                # КРИТИЧНО: Строгая проверка времени - после 21:00 полная остановка
                if hour >= 21 or hour < 8:
                    self.status["mode"] = "sleeping"
                    self.status["current_action"] = f"Ночной режим (21:00-8:00). Сейчас {hour:02d}:00 МСК"
                    # Спать 5 минут между проверками
                    await asyncio.sleep(300)
                    continue

                if settings.join_start_hour <= hour < settings.join_end_hour:
                    # Режим вступления (8:00-16:00)
                    self.status["mode"] = "joining"
                    await self._do_joins(settings)

                elif settings.send_start_hour <= hour < settings.send_end_hour:
                    # Режим рассылки (16:00-21:00)
                    self.status["mode"] = "sending"
                    await self._do_sends(settings)

                else:
                    # Промежуточный режим (между вступлением и рассылкой)
                    self.status["mode"] = "sleeping"
                    self.status["current_action"] = f"Ожидание до {settings.send_start_hour}:00"
                    await asyncio.sleep(60)

                # Проверяем авто-выход
                if settings.auto_leave_enabled:
                    await self._check_leaves(settings)

            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"AutoWorker error: {e}")
                await asyncio.sleep(30)

    async def _do_joins(self, settings: BotSettings):
        """Вступление в группы из активного сообщения"""
        if not await self._can_do_action():
            self.status["current_action"] = "Дневной лимит достигнут"
            await asyncio.sleep(60)
            return

        if self.status["session_joins"] >= settings.join_limit_per_session:
            self.status["current_action"] = "Лимит сессии достигнут"
            await asyncio.sleep(60)
            return

        if not settings.active_message_id:
            self.status["current_action"] = "Нет активного сообщения"
            await asyncio.sleep(60)
            return

        async with async_session() as db:
            # УМНЫЙ ВЫХОД: проверяем лимит групп перед вступлением
            stmt = select(func.count(Group.id)).where(Group.status == "joined")
            joined_count = (await db.execute(stmt)).scalar() or 0

            TELEGRAM_GROUP_LIMIT = 500  # Лимит Telegram

            if joined_count >= TELEGRAM_GROUP_LIMIT - 10:
                # Освобождаем место - выходим из старых групп
                await self._leave_oldest_groups(db, count=10)
                self.status["current_action"] = f"Освобождаем место (вышло из групп: {joined_count}/{TELEGRAM_GROUP_LIMIT})"
                await asyncio.sleep(30)
                return

            # Ищем MessageTarget с included=True, где группа ещё не joined
            stmt = select(MessageTarget).join(Group).where(
                and_(
                    MessageTarget.message_id == settings.active_message_id,
                    MessageTarget.included == True,
                    MessageTarget.send_status == "pending",
                    Group.status == "pending"
                )
            ).limit(1)

            target = (await db.execute(stmt)).scalar_one_or_none()

            if not target:
                self.status["current_action"] = "Нет групп для вступления"
                await asyncio.sleep(60)
                return

            # Получаем группу
            stmt = select(Group).where(Group.id == target.group_id)
            group = (await db.execute(stmt)).scalar_one_or_none()

            if not group:
                return

            # Вступаем
            group.status = "joining"
            group.join_attempts += 1
            group.last_attempt_at = datetime.utcnow()
            self.status["current_action"] = f"Вступаем: {group.link}"
            await db.commit()

            result = await tg.join_group(self.phone, group.link)

            if result["status"] == "success":
                group.status = "joined"
                group.is_joined = True
                group.joined_at = datetime.utcnow()
                group.telegram_id = str(result["group"].get("id", ""))
                group.title = result["group"].get("title", "")
                group.join_error = None
                # Помечаем target как waiting (ждём перед отправкой)
                target.send_status = "waiting"
                await self._increment_stat("join")
                print(f"AutoWorker: вступили в {group.title}")
            else:
                group.status = "failed"
                group.join_error = result.get("message", "Unknown error")
                target.send_status = "failed"
                target.send_error = group.join_error
                print(f"AutoWorker: ошибка вступления {group.link}: {group.join_error}")

            await db.commit()

        # Задержка
        delay = random.randint(settings.join_delay_min, settings.join_delay_max)
        self.status["next_action_in"] = delay
        for i in range(delay):
            if not self.is_running:
                break
            self.status["next_action_in"] = delay - i
            await asyncio.sleep(1)

    async def _do_sends(self, settings: BotSettings):
        """Рассылка сообщений в группы из активного сообщения"""
        if not await self._can_do_action():
            self.status["current_action"] = "Дневной лимит достигнут"
            await asyncio.sleep(60)
            return

        if self.status["session_sends"] >= settings.send_limit_per_session:
            self.status["current_action"] = "Лимит сессии достигнут"
            await asyncio.sleep(60)
            return

        if not settings.active_message_id:
            self.status["current_action"] = "Нет активного сообщения"
            await asyncio.sleep(60)
            return

        async with async_session() as db:
            # Получаем активное сообщение
            stmt = select(Message).where(Message.id == settings.active_message_id)
            message = (await db.execute(stmt)).scalar_one_or_none()

            if not message or not message.photo_path:
                self.status["current_action"] = "Сообщение не найдено или без фото"
                await asyncio.sleep(60)
                return

            # Минимальное время после вступления
            min_joined_at = datetime.utcnow() - timedelta(hours=settings.wait_before_send_hours)

            # Ищем MessageTarget с included=True, send_status=waiting, группа joined и прошло время
            stmt = select(MessageTarget).join(Group).where(
                and_(
                    MessageTarget.message_id == settings.active_message_id,
                    MessageTarget.included == True,
                    MessageTarget.send_status == "waiting",
                    Group.status == "joined",
                    Group.joined_at != None,
                    Group.joined_at < min_joined_at
                )
            ).limit(1)

            target = (await db.execute(stmt)).scalar_one_or_none()

            if not target:
                # Также проверяем группы где уже joined (если вступали вручную ранее)
                stmt = select(MessageTarget).join(Group).where(
                    and_(
                        MessageTarget.message_id == settings.active_message_id,
                        MessageTarget.included == True,
                        MessageTarget.send_status == "pending",
                        Group.status == "joined",
                        Group.joined_at != None,
                        Group.joined_at < min_joined_at
                    )
                ).limit(1)
                target = (await db.execute(stmt)).scalar_one_or_none()

            if not target:
                self.status["current_action"] = "Нет групп для отправки"
                await asyncio.sleep(60)
                return

            # Получаем группу
            stmt = select(Group).where(Group.id == target.group_id)
            group = (await db.execute(stmt)).scalar_one_or_none()

            if not group or not group.telegram_id:
                target.send_status = "failed"
                target.send_error = "Группа не найдена или нет telegram_id"
                await db.commit()
                return

            # ЗАЩИТА ОТ ДУБЛИКАТОВ: проверяем через Telegram API, есть ли наш пост в чате
            check = await tg.check_already_posted(self.phone, group.telegram_id, hours=48)
            if check.get("posted"):
                target.send_status = "sent"
                target.send_error = None
                target.sent_at = datetime.utcnow()
                if check.get("message_id"):
                    target.telegram_message_id = check["message_id"]
                    chat_id = str(group.telegram_id).replace("-100", "")
                    target.message_link = f"https://t.me/c/{chat_id}/{check['message_id']}"
                group.can_leave = True
                group.last_message_sent_id = message.id
                group.last_sent_at = datetime.utcnow()
                await db.commit()
                print(f"AutoWorker: пропускаем {group.title} - пост уже есть в чате (msg #{check.get('message_id')})")
                return

            target.send_status = "sending"
            await db.commit()

            self.status["current_action"] = f"Отправляем в: {group.title or group.link}"

            # Отправляем
            result = await tg.send_photo_to_group(
                self.phone,
                group.telegram_id,
                message.photo_path,
                message.caption or ""
            )

            if result["status"] == "success":
                target.send_status = "sent"
                target.sent_at = datetime.utcnow()
                if "message_id" in result:
                    target.telegram_message_id = result["message_id"]
                    chat_id = str(group.telegram_id).replace("-100", "")
                    target.message_link = f"https://t.me/c/{chat_id}/{result['message_id']}"

                # Помечаем группу что можно выходить
                group.can_leave = True

                # Сохраняем что в эту группу отправили это сообщение (защита от дубликатов)
                group.last_message_sent_id = message.id
                group.last_sent_at = datetime.utcnow()

                await self._increment_stat("send")
                print(f"AutoWorker: отправлено в {group.title}")
            else:
                # Ошибка - но проверяем, может сообщение всё-таки доставилось
                verify = await tg.check_already_posted(self.phone, group.telegram_id, hours=1)
                if verify.get("posted"):
                    # Сообщение доставилось несмотря на ошибку!
                    target.send_status = "sent"
                    target.sent_at = datetime.utcnow()
                    target.send_error = None
                    if verify.get("message_id"):
                        target.telegram_message_id = verify["message_id"]
                        chat_id = str(group.telegram_id).replace("-100", "")
                        target.message_link = f"https://t.me/c/{chat_id}/{verify['message_id']}"
                    group.can_leave = True
                    group.last_message_sent_id = message.id
                    group.last_sent_at = datetime.utcnow()
                    await self._increment_stat("send")
                    print(f"AutoWorker: {group.title} - ошибка '{result.get('message')}', но пост доставлен (msg #{verify.get('message_id')})")
                else:
                    target.send_status = "failed"
                    target.send_error = result.get("message", "Unknown error")
                    print(f"AutoWorker: ошибка отправки в {group.title}: {target.send_error}")

            await db.commit()

        # Задержка
        delay = random.randint(settings.send_delay_min, settings.send_delay_max)
        self.status["next_action_in"] = delay
        for i in range(delay):
            if not self.is_running:
                break
            self.status["next_action_in"] = delay - i
            await asyncio.sleep(1)

    async def _check_leaves(self, settings: BotSettings):
        """Проверить нужно ли выйти из групп"""
        async with async_session() as db:
            # Считаем сколько pending targets в активном сообщении
            if not settings.active_message_id:
                return

            stmt = select(func.count(MessageTarget.id)).join(Group).where(
                and_(
                    MessageTarget.message_id == settings.active_message_id,
                    MessageTarget.included == True,
                    MessageTarget.send_status.in_(["pending", "waiting"]),
                    Group.status == "pending"
                )
            )
            pending_count = (await db.execute(stmt)).scalar() or 0

            if pending_count == 0:
                return  # Нет pending - выходить не нужно

            # Проверяем лимит
            stats = await self._get_or_create_daily_stats(db)
            total_actions = stats.joins_count + stats.sends_count

            if total_actions < settings.daily_limit:
                return  # Лимит не достигнут

            # Ищем группы для выхода (can_leave=True)
            stmt = select(Group).where(
                and_(
                    Group.can_leave == True,
                    Group.status == "joined"
                )
            ).order_by(Group.joined_at).limit(5)  # Выходим по 5 за раз

            groups_to_leave = (await db.execute(stmt)).scalars().all()

            for group in groups_to_leave:
                try:
                    result = await tg.leave_group(self.phone, group.telegram_id)
                    if result.get("status") == "success":
                        group.status = "left"
                        group.left_at = datetime.utcnow()
                        await self._increment_stat("leave")
                        print(f"AutoWorker: вышли из {group.title}")
                    await db.commit()
                    await asyncio.sleep(5)  # Небольшая пауза между выходами
                except Exception as e:
                    print(f"AutoWorker: ошибка выхода из {group.title}: {e}")

    async def _leave_oldest_groups(self, db: AsyncSession, count: int = 10):
        """Выйти из самых старых групп где can_leave=True"""
        stmt = select(Group).where(
            and_(
                Group.can_leave == True,
                Group.status == "joined"
            )
        ).order_by(Group.joined_at).limit(count)

        groups = (await db.execute(stmt)).scalars().all()

        for group in groups:
            try:
                result = await tg.leave_group(self.phone, group.telegram_id)
                if result.get("status") == "success":
                    group.status = "left"
                    group.left_at = datetime.utcnow()
                    await self._increment_stat("leave")
                    print(f"AutoWorker: освобождаем место - вышли из {group.title}")
                await db.commit()
                await asyncio.sleep(3)  # Пауза между выходами
            except Exception as e:
                print(f"AutoWorker: ошибка выхода из {group.title}: {e}")
                await db.commit()  # Коммитим даже при ошибке


# Глобальный экземпляр
auto_worker = AutoWorker()
