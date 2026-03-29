import asyncio
import logging

from telebot.asyncio_storage import StateMemoryStorage
from telebot.asyncio_storage.base_storage import StateDataContext, StateStorageBase

from services.conversation_state_service import ConversationStateService
from services.platform import PlatformSchemaUnavailable

logger = logging.getLogger(__name__)


class DbStateStorage(StateStorageBase):
    """DB-backed storage with in-memory fallback until the schema is ready."""

    def __init__(
        self,
        provider: str = "telegram",
        prefix: str = "telebot",
        separator: str = ":",
    ) -> None:
        self.provider = provider
        self.prefix = prefix
        self.separator = separator
        self.lock = asyncio.Lock()
        self.memory = StateMemoryStorage(separator=separator, prefix=prefix)
        self.service = ConversationStateService(
            provider=provider,
            prefix=prefix,
            separator=separator,
        )
        self._fallback_logged = False

    def _log_fallback(self, exc: Exception) -> None:
        if self._fallback_logged:
            return
        logger.warning(
            "ConversationState DB storage is not ready, falling back to memory: %s",
            exc,
        )
        self._fallback_logged = True

    async def _reseed_db_record(
        self,
        chat_id,
        user_id,
        business_connection_id=None,
        message_thread_id=None,
        bot_id=None,
    ) -> bool:
        state = await self.memory.get_state(
            chat_id=chat_id,
            user_id=user_id,
            business_connection_id=business_connection_id,
            message_thread_id=message_thread_id,
            bot_id=bot_id,
        )
        if state is None:
            return False

        try:
            return await self.service.set_state(
                chat_id=chat_id,
                user_id=user_id,
                state=state,
                business_connection_id=business_connection_id,
                message_thread_id=message_thread_id,
                bot_id=bot_id,
            )
        except PlatformSchemaUnavailable as exc:
            self._log_fallback(exc)
            return False

    async def set_state(
        self,
        chat_id,
        user_id,
        state,
        business_connection_id=None,
        message_thread_id=None,
        bot_id=None,
    ) -> bool:
        async with self.lock:
            await self.memory.set_state(
                chat_id=chat_id,
                user_id=user_id,
                state=state,
                business_connection_id=business_connection_id,
                message_thread_id=message_thread_id,
                bot_id=bot_id,
            )
            try:
                return await self.service.set_state(
                    chat_id=chat_id,
                    user_id=user_id,
                    state=state,
                    business_connection_id=business_connection_id,
                    message_thread_id=message_thread_id,
                    bot_id=bot_id,
                )
            except PlatformSchemaUnavailable as exc:
                self._log_fallback(exc)
                return True

    async def get_state(
        self,
        chat_id,
        user_id,
        business_connection_id=None,
        message_thread_id=None,
        bot_id=None,
    ):
        try:
            db_state = await self.service.get_state(
                chat_id=chat_id,
                user_id=user_id,
                business_connection_id=business_connection_id,
                message_thread_id=message_thread_id,
                bot_id=bot_id,
            )
        except PlatformSchemaUnavailable as exc:
            self._log_fallback(exc)
            db_state = None

        if db_state is not None:
            return db_state

        return await self.memory.get_state(
            chat_id=chat_id,
            user_id=user_id,
            business_connection_id=business_connection_id,
            message_thread_id=message_thread_id,
            bot_id=bot_id,
        )

    async def delete_state(
        self,
        chat_id,
        user_id,
        business_connection_id=None,
        message_thread_id=None,
        bot_id=None,
    ) -> bool:
        async with self.lock:
            memory_deleted = await self.memory.delete_state(
                chat_id=chat_id,
                user_id=user_id,
                business_connection_id=business_connection_id,
                message_thread_id=message_thread_id,
                bot_id=bot_id,
            )
            try:
                db_deleted = await self.service.delete_state(
                    chat_id=chat_id,
                    user_id=user_id,
                    business_connection_id=business_connection_id,
                    message_thread_id=message_thread_id,
                    bot_id=bot_id,
                )
                return db_deleted or memory_deleted
            except PlatformSchemaUnavailable as exc:
                self._log_fallback(exc)
                return memory_deleted

    async def set_data(
        self,
        chat_id,
        user_id,
        key,
        value,
        business_connection_id=None,
        message_thread_id=None,
        bot_id=None,
    ) -> bool:
        async with self.lock:
            await self.memory.set_data(
                chat_id=chat_id,
                user_id=user_id,
                key=key,
                value=value,
                business_connection_id=business_connection_id,
                message_thread_id=message_thread_id,
                bot_id=bot_id,
            )
            try:
                return await self.service.set_data(
                    chat_id=chat_id,
                    user_id=user_id,
                    key=key,
                    value=value,
                    business_connection_id=business_connection_id,
                    message_thread_id=message_thread_id,
                    bot_id=bot_id,
                )
            except RuntimeError:
                reseeded = await self._reseed_db_record(
                    chat_id=chat_id,
                    user_id=user_id,
                    business_connection_id=business_connection_id,
                    message_thread_id=message_thread_id,
                    bot_id=bot_id,
                )
                if reseeded:
                    return await self.service.set_data(
                        chat_id=chat_id,
                        user_id=user_id,
                        key=key,
                        value=value,
                        business_connection_id=business_connection_id,
                        message_thread_id=message_thread_id,
                        bot_id=bot_id,
                    )
                raise
            except PlatformSchemaUnavailable as exc:
                self._log_fallback(exc)
                return True

    async def get_data(
        self,
        chat_id,
        user_id,
        business_connection_id=None,
        message_thread_id=None,
        bot_id=None,
    ) -> dict:
        try:
            db_data = await self.service.get_data(
                chat_id=chat_id,
                user_id=user_id,
                business_connection_id=business_connection_id,
                message_thread_id=message_thread_id,
                bot_id=bot_id,
            )
        except PlatformSchemaUnavailable as exc:
            self._log_fallback(exc)
            db_data = {}

        if db_data:
            return db_data

        return await self.memory.get_data(
            chat_id=chat_id,
            user_id=user_id,
            business_connection_id=business_connection_id,
            message_thread_id=message_thread_id,
            bot_id=bot_id,
        )

    async def reset_data(
        self,
        chat_id,
        user_id,
        business_connection_id=None,
        message_thread_id=None,
        bot_id=None,
    ) -> bool:
        async with self.lock:
            memory_reset = await self.memory.reset_data(
                chat_id=chat_id,
                user_id=user_id,
                business_connection_id=business_connection_id,
                message_thread_id=message_thread_id,
                bot_id=bot_id,
            )
            try:
                db_reset = await self.service.reset_data(
                    chat_id=chat_id,
                    user_id=user_id,
                    business_connection_id=business_connection_id,
                    message_thread_id=message_thread_id,
                    bot_id=bot_id,
                )
                return db_reset or memory_reset
            except PlatformSchemaUnavailable as exc:
                self._log_fallback(exc)
                return memory_reset

    def get_interactive_data(
        self,
        chat_id,
        user_id,
        business_connection_id=None,
        message_thread_id=None,
        bot_id=None,
    ):
        return StateDataContext(
            self,
            chat_id=chat_id,
            user_id=user_id,
            business_connection_id=business_connection_id,
            message_thread_id=message_thread_id,
            bot_id=bot_id,
        )

    async def save(
        self,
        chat_id,
        user_id,
        data,
        business_connection_id=None,
        message_thread_id=None,
        bot_id=None,
    ) -> bool:
        async with self.lock:
            await self.memory.save(
                chat_id=chat_id,
                user_id=user_id,
                data=data,
                business_connection_id=business_connection_id,
                message_thread_id=message_thread_id,
                bot_id=bot_id,
            )
            try:
                saved = await self.service.save(
                    chat_id=chat_id,
                    user_id=user_id,
                    data=data,
                    business_connection_id=business_connection_id,
                    message_thread_id=message_thread_id,
                    bot_id=bot_id,
                )
                if saved:
                    return True
                reseeded = await self._reseed_db_record(
                    chat_id=chat_id,
                    user_id=user_id,
                    business_connection_id=business_connection_id,
                    message_thread_id=message_thread_id,
                    bot_id=bot_id,
                )
                if reseeded:
                    return await self.service.save(
                        chat_id=chat_id,
                        user_id=user_id,
                        data=data,
                        business_connection_id=business_connection_id,
                        message_thread_id=message_thread_id,
                        bot_id=bot_id,
                    )
                return False
            except PlatformSchemaUnavailable as exc:
                self._log_fallback(exc)
                return True
