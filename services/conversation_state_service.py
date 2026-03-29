from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError

from db import SessionLocal
from models import ConversationState
from services.platform import _raise_schema_unavailable


def build_storage_key(
    chat_id: int,
    user_id: int,
    prefix: str,
    separator: str,
    business_connection_id: str | None = None,
    message_thread_id: int | None = None,
    bot_id: int | None = None,
) -> str:
    params = [prefix]
    if bot_id:
        params.append(str(bot_id))
    if business_connection_id:
        params.append(business_connection_id)
    if message_thread_id:
        params.append(str(message_thread_id))
    params.append(str(chat_id))
    params.append(str(user_id))
    return separator.join(params)


class ConversationStateService:
    def __init__(
        self,
        provider: str = "telegram",
        session_factory=SessionLocal,
        prefix: str = "telebot",
        separator: str = ":",
    ) -> None:
        self.provider = provider
        self.session_factory = session_factory
        self.prefix = prefix
        self.separator = separator

    def make_storage_key(
        self,
        chat_id: int,
        user_id: int,
        business_connection_id: str | None = None,
        message_thread_id: int | None = None,
        bot_id: int | None = None,
    ) -> str:
        return build_storage_key(
            chat_id=chat_id,
            user_id=user_id,
            prefix=self.prefix,
            separator=self.separator,
            business_connection_id=business_connection_id,
            message_thread_id=message_thread_id,
            bot_id=bot_id,
        )

    async def _get_record(self, session, storage_key: str) -> ConversationState | None:
        stmt = select(ConversationState).where(ConversationState.storage_key == storage_key)
        result = await session.execute(stmt)
        return result.scalars().first()

    async def set_state(
        self,
        chat_id: int,
        user_id: int,
        state: Any,
        business_connection_id: str | None = None,
        message_thread_id: int | None = None,
        bot_id: int | None = None,
    ) -> bool:
        if hasattr(state, "name"):
            state = state.name

        storage_key = self.make_storage_key(
            chat_id=chat_id,
            user_id=user_id,
            business_connection_id=business_connection_id,
            message_thread_id=message_thread_id,
            bot_id=bot_id,
        )
        now = datetime.utcnow()

        async with self.session_factory() as session:
            try:
                record = await self._get_record(session, storage_key)
                if record is None:
                    record = ConversationState(
                        storage_key=storage_key,
                        provider=self.provider,
                        external_user_id=str(user_id),
                        chat_id=str(chat_id),
                        business_connection_id=business_connection_id,
                        message_thread_id=message_thread_id,
                        bot_id=bot_id,
                        state=state,
                        data={},
                        created_at=now,
                        updated_at=now,
                    )
                    session.add(record)
                else:
                    record.state = state
                    record.updated_at = now

                await session.commit()
                return True
            except SQLAlchemyError as exc:
                await session.rollback()
                _raise_schema_unavailable(exc, "conversation state write")

    async def get_state(
        self,
        chat_id: int,
        user_id: int,
        business_connection_id: str | None = None,
        message_thread_id: int | None = None,
        bot_id: int | None = None,
    ) -> str | None:
        storage_key = self.make_storage_key(
            chat_id=chat_id,
            user_id=user_id,
            business_connection_id=business_connection_id,
            message_thread_id=message_thread_id,
            bot_id=bot_id,
        )

        async with self.session_factory() as session:
            try:
                record = await self._get_record(session, storage_key)
                return record.state if record else None
            except SQLAlchemyError as exc:
                _raise_schema_unavailable(exc, "conversation state read")

    async def delete_state(
        self,
        chat_id: int,
        user_id: int,
        business_connection_id: str | None = None,
        message_thread_id: int | None = None,
        bot_id: int | None = None,
    ) -> bool:
        storage_key = self.make_storage_key(
            chat_id=chat_id,
            user_id=user_id,
            business_connection_id=business_connection_id,
            message_thread_id=message_thread_id,
            bot_id=bot_id,
        )

        async with self.session_factory() as session:
            try:
                record = await self._get_record(session, storage_key)
                if record is None:
                    return False
                await session.delete(record)
                await session.commit()
                return True
            except SQLAlchemyError as exc:
                await session.rollback()
                _raise_schema_unavailable(exc, "conversation state delete")

    async def get_data(
        self,
        chat_id: int,
        user_id: int,
        business_connection_id: str | None = None,
        message_thread_id: int | None = None,
        bot_id: int | None = None,
    ) -> dict:
        storage_key = self.make_storage_key(
            chat_id=chat_id,
            user_id=user_id,
            business_connection_id=business_connection_id,
            message_thread_id=message_thread_id,
            bot_id=bot_id,
        )

        async with self.session_factory() as session:
            try:
                record = await self._get_record(session, storage_key)
                return dict(record.data or {}) if record else {}
            except SQLAlchemyError as exc:
                _raise_schema_unavailable(exc, "conversation data read")

    async def set_data(
        self,
        chat_id: int,
        user_id: int,
        key: str,
        value: Any,
        business_connection_id: str | None = None,
        message_thread_id: int | None = None,
        bot_id: int | None = None,
    ) -> bool:
        storage_key = self.make_storage_key(
            chat_id=chat_id,
            user_id=user_id,
            business_connection_id=business_connection_id,
            message_thread_id=message_thread_id,
            bot_id=bot_id,
        )

        async with self.session_factory() as session:
            try:
                record = await self._get_record(session, storage_key)
                if record is None:
                    raise RuntimeError(f"ConversationState: key {storage_key} does not exist.")
                payload = dict(record.data or {})
                payload[key] = value
                record.data = payload
                record.updated_at = datetime.utcnow()
                await session.commit()
                return True
            except SQLAlchemyError as exc:
                await session.rollback()
                _raise_schema_unavailable(exc, "conversation data write")

    async def reset_data(
        self,
        chat_id: int,
        user_id: int,
        business_connection_id: str | None = None,
        message_thread_id: int | None = None,
        bot_id: int | None = None,
    ) -> bool:
        storage_key = self.make_storage_key(
            chat_id=chat_id,
            user_id=user_id,
            business_connection_id=business_connection_id,
            message_thread_id=message_thread_id,
            bot_id=bot_id,
        )

        async with self.session_factory() as session:
            try:
                record = await self._get_record(session, storage_key)
                if record is None:
                    return False
                record.data = {}
                record.updated_at = datetime.utcnow()
                await session.commit()
                return True
            except SQLAlchemyError as exc:
                await session.rollback()
                _raise_schema_unavailable(exc, "conversation data reset")

    async def save(
        self,
        chat_id: int,
        user_id: int,
        data: dict,
        business_connection_id: str | None = None,
        message_thread_id: int | None = None,
        bot_id: int | None = None,
    ) -> bool:
        storage_key = self.make_storage_key(
            chat_id=chat_id,
            user_id=user_id,
            business_connection_id=business_connection_id,
            message_thread_id=message_thread_id,
            bot_id=bot_id,
        )

        async with self.session_factory() as session:
            try:
                record = await self._get_record(session, storage_key)
                if record is None:
                    return False
                record.data = dict(data or {})
                record.updated_at = datetime.utcnow()
                await session.commit()
                return True
            except SQLAlchemyError as exc:
                await session.rollback()
                _raise_schema_unavailable(exc, "conversation data save")
