from __future__ import annotations

import asyncio
import html
import json
import logging
import re
from dataclasses import dataclass
from datetime import datetime
from math import ceil
from random import randint
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from sqlalchemy import func, select

from db import SessionLocal
from models import Company, User, User_volunteer
from services.conversation_state_service import ConversationStateService
from services.platform import IdentityService, PlatformSchemaUnavailable

logger = logging.getLogger(__name__)

MAX_PROVIDER = "max"
MAX_API_BASE_URL = "https://platform-api.max.ru"
SMS_API_URL = "https://smsc.ru/sys/send.php"
SMS_LOGIN = "lgjt"
SMS_PASSWORD = "123456"
SMS_SENDER = "kotelnikiru"
COMPANIES_PER_PAGE = 5


class MaxState:
    WAIT_VOLUNTEER_ID = "wait_volunteer_id"
    WAIT_SURNAME = "wait_surname"
    WAIT_DOB = "wait_dob"
    WAIT_NAMES = "wait_names"
    WAIT_PHONE = "wait_phone"
    WAIT_SMS = "wait_sms"
    WAIT_ADDRESS = "wait_address"
    WAIT_NDA = "wait_nda"
    WAIT_COMPANY = "wait_company"
    WAIT_LINK_SMS = "wait_link_sms"


@dataclass(slots=True)
class MaxUser:
    user_id: int
    name: str | None = None
    username: str | None = None
    is_bot: bool = False


@dataclass(slots=True)
class MaxEvent:
    update_type: str
    chat_id: int | None
    user: MaxUser | None
    text: str | None = None
    callback_id: str | None = None
    callback_payload: str | None = None
    message_id: str | None = None
    attachments: list[dict[str, Any]] | None = None
    payload: dict[str, Any] | None = None


class MaxApiError(RuntimeError):
    pass


class MaxClient:
    def __init__(self, token: str, base_url: str = MAX_API_BASE_URL) -> None:
        self.token = (token or "").strip()
        self.base_url = base_url.rstrip("/")

    async def send_message(
        self,
        *,
        chat_id: int | None = None,
        user_id: int | None = None,
        text: str | None = None,
        attachments: list[dict[str, Any]] | None = None,
        notify: bool = True,
        fmt: str | None = "html",
    ) -> dict[str, Any]:
        return await self._request(
            method="POST",
            path="/messages",
            query={
                "chat_id": chat_id,
                "user_id": user_id,
            },
            body={
                "text": text,
                "attachments": attachments,
                "notify": notify,
                "format": fmt,
            },
        )

    async def edit_message(
        self,
        message_id: str,
        *,
        text: str | None = None,
        attachments: list[dict[str, Any]] | None = None,
        notify: bool = False,
        fmt: str | None = "html",
    ) -> dict[str, Any]:
        return await self._request(
            method="PUT",
            path="/messages",
            query={"message_id": message_id},
            body={
                "text": text,
                "attachments": attachments,
                "notify": notify,
                "format": fmt,
            },
        )

    async def answer_callback(
        self,
        callback_id: str,
        *,
        notification: str | None = None,
        message: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return await self._request(
            method="POST",
            path="/answers",
            query={"callback_id": callback_id},
            body={
                "notification": notification,
                "message": message,
            },
        )

    async def get_me(self) -> dict[str, Any]:
        return await self._request(method="GET", path="/me")

    async def _request(
        self,
        *,
        method: str,
        path: str,
        query: dict[str, Any] | None = None,
        body: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        if not self.token:
            raise MaxApiError("MAX_BOT_TOKEN is empty")
        return await asyncio.to_thread(
            self._request_sync,
            method,
            path,
            query or {},
            body,
        )

    def _request_sync(
        self,
        method: str,
        path: str,
        query: dict[str, Any],
        body: dict[str, Any] | None,
    ) -> dict[str, Any]:
        clean_query = {
            key: value
            for key, value in query.items()
            if value is not None
        }
        clean_body = None
        if body is not None:
            clean_body = {
                key: value
                for key, value in body.items()
                if value is not None
            }

        url = f"{self.base_url}{path}"
        if clean_query:
            url = f"{url}?{urlencode(clean_query)}"

        payload = None
        headers = {
            "Authorization": self.token,
            "Accept": "application/json",
        }
        if clean_body is not None:
            payload = json.dumps(clean_body).encode("utf-8")
            headers["Content-Type"] = "application/json"

        request = Request(url=url, data=payload, method=method.upper(), headers=headers)
        try:
            with urlopen(request, timeout=20) as response:
                raw = response.read().decode("utf-8")
        except HTTPError as exc:
            body_text = exc.read().decode("utf-8", errors="replace")
            logger.error(
                "MAX API error %s %s status=%s body=%s",
                method,
                path,
                exc.code,
                body_text,
            )
            raise MaxApiError(f"MAX API request failed with status {exc.code}") from exc
        except URLError as exc:
            logger.error("MAX API network error %s %s: %s", method, path, exc)
            raise MaxApiError("MAX API network error") from exc

        if not raw:
            return {}

        try:
            return json.loads(raw)
        except json.JSONDecodeError as exc:
            logger.error("MAX API returned invalid JSON for %s %s: %s", method, path, raw)
            raise MaxApiError("MAX API returned invalid JSON") from exc


class MaxConversationStore:
    def __init__(self) -> None:
        self._service = ConversationStateService(provider=MAX_PROVIDER, prefix="max")

    async def load(self, chat_id: int, user_id: int) -> tuple[str | None, dict[str, Any]]:
        state = await self._service.get_state(chat_id=chat_id, user_id=user_id)
        data = await self._service.get_data(chat_id=chat_id, user_id=user_id)
        return state, data

    async def save(self, chat_id: int, user_id: int, state: str | None, data: dict[str, Any]) -> None:
        await self._service.set_state(chat_id=chat_id, user_id=user_id, state=state)
        await self._service.save(chat_id=chat_id, user_id=user_id, data=data)

    async def clear(self, chat_id: int, user_id: int) -> None:
        await self._service.delete_state(chat_id=chat_id, user_id=user_id)


class MaxBotService:
    def __init__(self, client: MaxClient) -> None:
        self.client = client
        self.store = MaxConversationStore()

    async def handle_update(self, payload: dict[str, Any]) -> dict[str, Any]:
        event = parse_event(payload)
        if event is None or event.user is None or event.chat_id is None:
            logger.info("Skipping unsupported MAX update: %s", payload.get("update_type"))
            return {"handled": False, "reason": "unsupported_update"}

        if event.user.is_bot:
            return {"handled": False, "reason": "bot_message"}

        if event.update_type == "bot_started":
            await self._handle_start(event)
            return {"handled": True, "action": "bot_started"}

        if event.update_type == "message_callback":
            await self._handle_callback(event)
            return {"handled": True, "action": "callback"}

        if event.update_type != "message_created":
            return {"handled": False, "reason": event.update_type}

        await self._handle_message(event)
        return {"handled": True, "action": "message"}

    async def _handle_start(self, event: MaxEvent) -> None:
        await self.store.clear(event.chat_id, event.user.user_id)
        linked_user = await self._get_linked_user(event.user.user_id)
        if linked_user:
            await self._touch_identity(linked_user.id, event.user, event.chat_id)
            await self.send_text(
                event.chat_id,
                "Здравствуйте! Аккаунт MAX уже привязан к вашему профилю.",
                attachments=menu_keyboard(),
            )
            await self.send_profile(event.chat_id, linked_user.id)
            return

        await self.send_text(
            event.chat_id,
            (
                "Здравствуйте! Это MAX-бот регистрации актива.\n\n"
                "Можно пройти регистрацию, если вы уже есть в базе, или открыть свой профиль, "
                "если аккаунт MAX уже привязан."
            ),
            attachments=menu_keyboard(),
        )

    async def _handle_message(self, event: MaxEvent) -> None:
        text = (event.text or "").strip()
        command = normalize_command(text)

        if command in {"/start", "старт", "start", "меню", "menu"}:
            await self._handle_start(event)
            return

        if command in {"отмена", "cancel"}:
            await self.store.clear(event.chat_id, event.user.user_id)
            await self.send_text(
                event.chat_id,
                "Текущий сценарий остановлен. Можно начать заново.",
                attachments=menu_keyboard(),
            )
            return

        if command in {"мой профиль", "профиль", "статус", "profile"}:
            await self._handle_profile_request(event)
            return

        if command in {"регистрация", "registration"}:
            await self._start_registration(event)
            return

        state, data = await self.store.load(event.chat_id, event.user.user_id)

        if not state:
            await self.send_text(
                event.chat_id,
                "Не понял команду. Нажмите кнопку ниже или отправьте «Регистрация» / «Мой профиль».",
                attachments=menu_keyboard(),
            )
            return

        if state == MaxState.WAIT_VOLUNTEER_ID:
            await self._process_volunteer_step(event, data, text)
            return
        if state == MaxState.WAIT_SURNAME:
            await self._process_surname_step(event, data, text)
            return
        if state == MaxState.WAIT_DOB:
            await self._process_dob_step(event, data, text)
            return
        if state == MaxState.WAIT_NAMES:
            await self._process_names_step(event, data, text)
            return
        if state == MaxState.WAIT_PHONE:
            await self._process_phone_step(event, data, text)
            return
        if state == MaxState.WAIT_SMS:
            await self._process_sms_step(event, data, text)
            return
        if state == MaxState.WAIT_ADDRESS:
            await self._process_address_step(event, data, text)
            return
        if state == MaxState.WAIT_NDA:
            await self._process_nda_step(event, data, text)
            return
        if state == MaxState.WAIT_COMPANY:
            await self._process_company_text_step(event, data, text)
            return
        if state == MaxState.WAIT_LINK_SMS:
            await self._process_link_sms_step(event, data, text)
            return

        await self.send_text(
            event.chat_id,
            "Состояние сессии не распознано. Начните сценарий заново.",
            attachments=menu_keyboard(),
        )
        await self.store.clear(event.chat_id, event.user.user_id)

    async def _handle_callback(self, event: MaxEvent) -> None:
        payload = (event.callback_payload or "").strip()
        if not payload:
            await self._safe_answer_callback(event.callback_id, notification="Пустое действие")
            return

        if payload == "menu:register":
            await self._safe_answer_callback(event.callback_id, notification="Открываю регистрацию")
            await self._start_registration(event)
            return

        if payload == "menu:profile":
            await self._safe_answer_callback(event.callback_id, notification="Открываю профиль")
            await self._handle_profile_request(event)
            return

        if payload == "menu:cancel":
            await self._safe_answer_callback(event.callback_id, notification="Отменено")
            await self.store.clear(event.chat_id, event.user.user_id)
            await self.send_text(
                event.chat_id,
                "Сценарий остановлен.",
                attachments=menu_keyboard(),
            )
            return

        state, data = await self.store.load(event.chat_id, event.user.user_id)

        if payload == "reg:skip_volunteer":
            await self._safe_answer_callback(event.callback_id, notification="Пропускаем")
            await self._go_to_surname_step(event, data, volunteer_id=None)
            return

        if payload == "reg:agree_nda":
            await self._safe_answer_callback(event.callback_id, notification="Согласие принято")
            await self._show_company_selection(event, data, page=0, edit_message_id=event.message_id)
            return

        if payload.startswith("reg:comp_page:"):
            try:
                page = int(payload.rsplit(":", 1)[-1])
            except ValueError:
                await self._safe_answer_callback(event.callback_id, notification="Некорректная страница")
                return
            await self._safe_answer_callback(event.callback_id, notification="Обновляю список")
            await self._show_company_selection(event, data, page=page, edit_message_id=event.message_id)
            return

        if payload.startswith("reg:company:"):
            try:
                company_id = int(payload.rsplit(":", 1)[-1])
            except ValueError:
                await self._safe_answer_callback(event.callback_id, notification="Некорректный идентификатор")
                return
            await self._safe_answer_callback(event.callback_id, notification="Сохраняю выбор")
            await self._finalize_registration(event, data, company_id)
            return

        await self._safe_answer_callback(event.callback_id, notification="Неизвестное действие")

    async def _handle_profile_request(self, event: MaxEvent) -> None:
        linked_user = await self._get_linked_user(event.user.user_id)
        if not linked_user:
            await self.send_text(
                event.chat_id,
                "Профиль MAX пока не привязан. Нажмите «Регистрация», чтобы пройти идентификацию.",
                attachments=menu_keyboard(),
            )
            return

        await self._touch_identity(linked_user.id, event.user, event.chat_id)
        await self.send_profile(event.chat_id, linked_user.id)

    async def _start_registration(self, event: MaxEvent) -> None:
        linked_user = await self._get_linked_user(event.user.user_id)
        if linked_user and linked_user.status == "registered":
            await self._touch_identity(linked_user.id, event.user, event.chat_id)
            await self.send_text(
                event.chat_id,
                "Этот аккаунт MAX уже привязан к зарегистрированному профилю.",
                attachments=menu_keyboard(),
            )
            await self.send_profile(event.chat_id, linked_user.id)
            return

        data: dict[str, Any] = {
            "provider": MAX_PROVIDER,
            "max_user_id": event.user.user_id,
            "max_chat_id": event.chat_id,
        }
        await self.store.save(event.chat_id, event.user.user_id, MaxState.WAIT_VOLUNTEER_ID, data)
        await self.send_text(
            event.chat_id,
            (
                "Если регистрацию помогает пройти волонтёр, отправьте его номер.\n"
                "Если волонтёра нет, нажмите «Пропустить» или напишите «пропустить»."
            ),
            attachments=skip_volunteer_keyboard(),
        )

    async def _process_volunteer_step(self, event: MaxEvent, data: dict[str, Any], text: str) -> None:
        if normalize_command(text) in {"пропустить", "skip", "нет", "0", "-"}:
            await self._go_to_surname_step(event, data, volunteer_id=None)
            return

        try:
            volunteer_id = int(text)
        except (TypeError, ValueError):
            await self.send_text(
                event.chat_id,
                "Введите числовой номер волонтёра или нажмите «Пропустить».",
                attachments=skip_volunteer_keyboard(),
            )
            return

        if not await self._check_volunteer_exists(volunteer_id):
            await self.send_text(
                event.chat_id,
                "Волонтёр с таким номером не найден. Попробуйте ещё раз или пропустите шаг.",
                attachments=skip_volunteer_keyboard(),
            )
            return

        await self._go_to_surname_step(event, data, volunteer_id=volunteer_id)

    async def _go_to_surname_step(
        self,
        event: MaxEvent,
        data: dict[str, Any],
        volunteer_id: int | None,
    ) -> None:
        next_data = dict(data)
        next_data["volunteer_id"] = volunteer_id
        await self.store.save(event.chat_id, event.user.user_id, MaxState.WAIT_SURNAME, next_data)
        await self.send_text(
            event.chat_id,
            "Шаг 1 из 7. Отправьте вашу фамилию точно как в документах.",
        )

    async def _process_surname_step(self, event: MaxEvent, data: dict[str, Any], text: str) -> None:
        surname = normalize_name_piece(text)
        if not surname:
            await self.send_text(event.chat_id, "Фамилия пустая. Введите фамилию ещё раз.")
            return

        if not await self._surname_exists(surname):
            await self.send_text(
                event.chat_id,
                "Не вижу такую фамилию в базе. Проверьте написание и попробуйте снова.",
            )
            return

        next_data = dict(data)
        next_data["surname"] = surname
        await self.store.save(event.chat_id, event.user.user_id, MaxState.WAIT_DOB, next_data)
        await self.send_text(
            event.chat_id,
            "Шаг 2 из 7. Пришлите дату рождения в формате 01.01.2000.",
        )

    async def _process_dob_step(self, event: MaxEvent, data: dict[str, Any], text: str) -> None:
        dob = parse_dob(text)
        if dob is None:
            await self.send_text(
                event.chat_id,
                "Неверный формат даты. Используйте формат 01.01.2000.",
            )
            return

        surname = data.get("surname")
        candidate = await self._get_user_by_surname_and_dob(surname, dob)
        if candidate is None:
            await self.send_text(
                event.chat_id,
                "Пользователь с такой фамилией и датой рождения не найден. Проверьте данные и попробуйте снова.",
            )
            return

        if candidate.status == "blocked":
            await self.store.clear(event.chat_id, event.user.user_id)
            await self.send_text(
                event.chat_id,
                "Этот профиль заблокирован. Обратитесь к администратору.",
                attachments=menu_keyboard(),
            )
            return

        next_data = dict(data)
        next_data["dob"] = dob.isoformat()
        next_data["id"] = candidate.id

        if candidate.status == "registered":
            if not candidate.phone_number:
                await self.store.clear(event.chat_id, event.user.user_id)
                await self.send_text(
                    event.chat_id,
                    "Профиль уже зарегистрирован, но номер телефона для подтверждения не найден. Обратитесь к администратору.",
                    attachments=menu_keyboard(),
                )
                return

            code = await send_sms_code(candidate.phone_number)
            if not code:
                await self.send_text(
                    event.chat_id,
                    "Не удалось отправить SMS на номер из профиля. Попробуйте позже.",
                )
                return

            next_data["code"] = code
            next_data["link_phone_number"] = candidate.phone_number
            await self.store.save(event.chat_id, event.user.user_id, MaxState.WAIT_LINK_SMS, next_data)
            await self.send_text(
                event.chat_id,
                (
                    "Профиль уже зарегистрирован. Чтобы привязать MAX, отправили код подтверждения "
                    f"на номер {mask_phone(candidate.phone_number)}.\n\nВведите этот код."
                ),
            )
            return

        await self.store.save(event.chat_id, event.user.user_id, MaxState.WAIT_NAMES, next_data)
        await self.send_text(
            event.chat_id,
            "Шаг 3 из 7. Пришлите имя и отчество, например: Иван Иванович.",
        )

    async def _process_names_step(self, event: MaxEvent, data: dict[str, Any], text: str) -> None:
        parts = [piece for piece in text.split() if piece]
        if len(parts) < 2:
            await self.send_text(
                event.chat_id,
                "Нужно указать имя и отчество минимум из двух слов. Например: Иван Иванович.",
            )
            return

        first_name = normalize_name_piece(parts[0])
        father_name = " ".join(normalize_name_piece(piece) for piece in parts[1:]).strip()

        next_data = dict(data)
        next_data["name"] = first_name
        next_data["father_name"] = father_name
        await self.store.save(event.chat_id, event.user.user_id, MaxState.WAIT_PHONE, next_data)
        await self.send_text(
            event.chat_id,
            "Шаг 4 из 7. Пришлите номер телефона. Допустимы форматы 79271234567, +79271234567 или 89271234567.",
        )

    async def _process_phone_step(self, event: MaxEvent, data: dict[str, Any], text: str) -> None:
        phone = normalize_phone(text)
        if phone is None:
            phone = extract_phone_from_attachments(event.attachments)

        if phone is None:
            await self.send_text(
                event.chat_id,
                "Номер телефона не распознан. Отправьте 11 цифр, например 79271234567.",
            )
            return

        code = await send_sms_code(phone)
        if not code:
            await self.send_text(
                event.chat_id,
                "Не удалось отправить код подтверждения. Попробуйте ещё раз через минуту.",
            )
            return

        next_data = dict(data)
        next_data["phone_number"] = phone
        next_data["code"] = code
        await self.store.save(event.chat_id, event.user.user_id, MaxState.WAIT_SMS, next_data)
        await self.send_text(
            event.chat_id,
            f"Шаг 5 из 7. Отправили код подтверждения на номер {mask_phone(phone)}. Введите его.",
        )

    async def _process_sms_step(self, event: MaxEvent, data: dict[str, Any], text: str) -> None:
        expected_code = str(data.get("code") or "").strip()
        provided_code = re.sub(r"\D+", "", text or "")
        if not expected_code or provided_code != expected_code:
            await self.send_text(
                event.chat_id,
                "Код не совпадает. Проверьте SMS и попробуйте снова.",
            )
            return

        next_data = dict(data)
        next_data["sms_code"] = provided_code
        next_data["sms_confirmed_at"] = datetime.utcnow().isoformat()
        await self.store.save(event.chat_id, event.user.user_id, MaxState.WAIT_ADDRESS, next_data)
        await self.send_text(
            event.chat_id,
            "Шаг 6 из 7. Пришлите адрес проживания.",
        )

    async def _process_address_step(self, event: MaxEvent, data: dict[str, Any], text: str) -> None:
        address = (text or "").strip()
        if len(address) < 5:
            await self.send_text(
                event.chat_id,
                "Адрес выглядит слишком коротким. Укажите адрес подробнее.",
            )
            return

        next_data = dict(data)
        next_data["home_address"] = address
        await self.store.save(event.chat_id, event.user.user_id, MaxState.WAIT_NDA, next_data)
        await self.send_text(
            event.chat_id,
            (
                f"Ваш ID в базе: <code>{html.escape(str(next_data.get('id')))}</code>\n\n"
                "Перед выбором предприятия подтвердите согласие с правилами неразглашения. "
                "Нажмите кнопку «Подтверждаю» или отправьте слово «согласен»."
            ),
            attachments=nda_keyboard(),
        )

    async def _process_nda_step(self, event: MaxEvent, data: dict[str, Any], text: str) -> None:
        if normalize_command(text) not in {"согласен", "подтверждаю", "agree"}:
            await self.send_text(
                event.chat_id,
                "Чтобы продолжить, нажмите кнопку «Подтверждаю» или отправьте слово «согласен».",
                attachments=nda_keyboard(),
            )
            return

        await self._show_company_selection(event, data, page=0)

    async def _show_company_selection(
        self,
        event: MaxEvent,
        data: dict[str, Any],
        *,
        page: int,
        edit_message_id: str | None = None,
    ) -> None:
        companies, total_pages = await self._get_companies_page(page)
        if not companies:
            await self.send_text(event.chat_id, "Список предприятий пуст.")
            return

        next_data = dict(data)
        next_data["company_page"] = page
        await self.store.save(event.chat_id, event.user.user_id, MaxState.WAIT_COMPANY, next_data)

        lines = [
            "Шаг 7 из 7. Выберите предприятие кнопкой ниже или отправьте его ID сообщением.",
            "",
            f"Страница {page + 1} из {total_pages}",
            "",
        ]
        for company in companies:
            lines.append(f"{company['id']} — {html.escape(company['name'])}")

        text = "\n".join(lines)
        attachments = company_keyboard(companies, page, total_pages)

        if edit_message_id:
            try:
                await self.client.edit_message(
                    edit_message_id,
                    text=text,
                    attachments=attachments,
                    notify=False,
                )
                return
            except MaxApiError:
                logger.warning("Failed to edit MAX company selection message, sending a new one instead")

        await self.send_text(event.chat_id, text, attachments=attachments)

    async def _process_company_text_step(self, event: MaxEvent, data: dict[str, Any], text: str) -> None:
        try:
            company_id = int((text or "").strip())
        except (TypeError, ValueError):
            await self.send_text(
                event.chat_id,
                "Отправьте числовой ID предприятия или выберите кнопку из списка.",
            )
            return

        await self._finalize_registration(event, data, company_id)

    async def _finalize_registration(self, event: MaxEvent, data: dict[str, Any], company_id: int) -> None:
        company = await self._get_company(company_id)
        if company is None:
            await self.send_text(
                event.chat_id,
                "Предприятие с таким номером не найдено. Выберите значение из списка.",
            )
            return

        user_id = data.get("id")
        if not user_id:
            await self.store.clear(event.chat_id, event.user.user_id)
            await self.send_text(
                event.chat_id,
                "Сессия регистрации устарела. Начните регистрацию заново.",
                attachments=menu_keyboard(),
            )
            return

        success = await self._register_max_user(
            user_id=int(user_id),
            company_id=company.id,
            data=data,
            max_user=event.user,
            chat_id=event.chat_id,
        )
        if not success:
            await self.send_text(
                event.chat_id,
                "Не удалось завершить регистрацию. Попробуйте ещё раз позже.",
            )
            return

        await self.store.clear(event.chat_id, event.user.user_id)
        await self.send_text(
            event.chat_id,
            "Регистрация завершена успешно.",
            attachments=menu_keyboard(),
        )
        await self.send_profile(event.chat_id, int(user_id))

    async def _process_link_sms_step(self, event: MaxEvent, data: dict[str, Any], text: str) -> None:
        expected_code = str(data.get("code") or "").strip()
        provided_code = re.sub(r"\D+", "", text or "")
        if not expected_code or provided_code != expected_code:
            await self.send_text(
                event.chat_id,
                "Код не совпадает. Проверьте SMS и попробуйте снова.",
            )
            return

        user_id = data.get("id")
        if not user_id:
            await self.store.clear(event.chat_id, event.user.user_id)
            await self.send_text(
                event.chat_id,
                "Сессия привязки устарела. Начните заново.",
                attachments=menu_keyboard(),
            )
            return

        await self._link_identity(int(user_id), event.user, event.chat_id)
        await self.store.clear(event.chat_id, event.user.user_id)
        await self.send_text(
            event.chat_id,
            "Аккаунт MAX успешно привязан к вашему профилю.",
            attachments=menu_keyboard(),
        )
        await self.send_profile(event.chat_id, int(user_id))

    async def send_profile(self, chat_id: int, user_id: int) -> None:
        profile = await self._build_profile_text(user_id)
        if profile is None:
            await self.send_text(chat_id, "Не удалось загрузить профиль.")
            return
        await self.send_text(chat_id, profile, attachments=menu_keyboard())

    async def send_text(
        self,
        chat_id: int,
        text: str,
        *,
        attachments: list[dict[str, Any]] | None = None,
        notify: bool = True,
    ) -> None:
        await self.client.send_message(
            chat_id=chat_id,
            text=text,
            attachments=attachments,
            notify=notify,
            fmt="html",
        )

    async def _safe_answer_callback(
        self,
        callback_id: str | None,
        *,
        notification: str | None = None,
    ) -> None:
        if not callback_id:
            return
        try:
            await self.client.answer_callback(callback_id, notification=notification)
        except MaxApiError:
            logger.warning("Failed to answer MAX callback %s", callback_id, exc_info=True)

    async def _get_linked_user(self, max_user_id: int) -> User | None:
        async with SessionLocal() as session:
            try:
                return await IdentityService.get_user_by_identity(session, MAX_PROVIDER, max_user_id)
            except PlatformSchemaUnavailable:
                logger.warning("MAX identity lookup skipped: platform schema is unavailable")
                return None

    async def _touch_identity(self, user_id: int, max_user: MaxUser, chat_id: int) -> None:
        try:
            async with SessionLocal() as session:
                await IdentityService.link_user_identity(
                    session=session,
                    user_id=user_id,
                    provider=MAX_PROVIDER,
                    external_user_id=max_user.user_id,
                    payload=build_identity_payload(max_user, chat_id),
                )
                await session.commit()
        except PlatformSchemaUnavailable:
            logger.warning("MAX identity touch skipped: platform schema is unavailable")

    async def _link_identity(self, user_id: int, max_user: MaxUser, chat_id: int) -> None:
        await self._touch_identity(user_id, max_user, chat_id)

    async def _surname_exists(self, surname: str) -> bool:
        async with SessionLocal() as session:
            stmt = select(func.count(User.id)).where(User.last_name == surname)
            return bool((await session.scalar(stmt)) or 0)

    async def _get_user_by_surname_and_dob(self, surname: str | None, dob) -> User | None:
        if not surname:
            return None
        async with SessionLocal() as session:
            stmt = (
                select(User)
                .where(User.last_name == surname)
                .where(User.date_of_birth == dob)
            )
            result = await session.execute(stmt)
            return result.scalars().first()

    async def _check_volunteer_exists(self, volunteer_id: int) -> bool:
        async with SessionLocal() as session:
            volunteer = await session.get(User_volunteer, volunteer_id)
            return volunteer is not None

    async def _get_company(self, company_id: int) -> Company | None:
        async with SessionLocal() as session:
            return await session.get(Company, company_id)

    async def _get_companies_page(self, page: int) -> tuple[list[dict[str, Any]], int]:
        safe_page = max(page, 0)
        async with SessionLocal() as session:
            total_count = await session.scalar(select(func.count(Company.id)))
            total_count = int(total_count or 0)
            total_pages = max(1, ceil(total_count / COMPANIES_PER_PAGE)) if total_count else 1
            safe_page = min(safe_page, total_pages - 1)

            stmt = (
                select(Company)
                .order_by(Company.name.asc())
                .offset(safe_page * COMPANIES_PER_PAGE)
                .limit(COMPANIES_PER_PAGE)
            )
            result = await session.execute(stmt)
            companies = result.scalars().all()
            return (
                [{"id": company.id, "name": company.name} for company in companies],
                total_pages,
            )

    async def _register_max_user(
        self,
        *,
        user_id: int,
        company_id: int,
        data: dict[str, Any],
        max_user: MaxUser,
        chat_id: int,
    ) -> bool:
        async with SessionLocal() as session:
            user = await session.get(User, user_id)
            if user is None:
                return False

            company = await session.get(Company, company_id)
            if company is None:
                return False

            user.status = "registered"
            user.first_name = str(data.get("name") or "").strip()
            user.father_name = str(data.get("father_name") or "").strip()
            user.phone_number = str(data.get("phone_number") or "").strip()
            user.address = str(data.get("home_address") or "").strip()
            user.registered_at = datetime.utcnow()
            user.company = company
            user.volunteer_id = data.get("volunteer_id")
            user.sms_code = data.get("sms_code")

            sms_confirmed_at = data.get("sms_confirmed_at")
            if sms_confirmed_at:
                user.sms_confirmed_at = datetime.fromisoformat(str(sms_confirmed_at))

            try:
                await IdentityService.link_user_identity(
                    session=session,
                    user_id=user.id,
                    provider=MAX_PROVIDER,
                    external_user_id=max_user.user_id,
                    payload=build_identity_payload(max_user, chat_id),
                )
            except PlatformSchemaUnavailable:
                logger.warning("MAX identity link skipped during registration: schema unavailable")

            await session.commit()
            return True

    async def _build_profile_text(self, user_id: int) -> str | None:
        async with SessionLocal() as session:
            user = await session.get(User, user_id)
            if user is None:
                return None

            company_name = "Не назначено"
            if user.company_id:
                company = await session.get(Company, user.company_id)
                if company:
                    company_name = company.name

            volunteer_name = None
            if user.volunteer_id:
                volunteer = await session.get(User_volunteer, user.volunteer_id)
                if volunteer:
                    volunteer_name = volunteer.name or f"#{volunteer.id}"

            fio = " ".join(
                part for part in [user.last_name, user.first_name, user.father_name] if part
            ).strip() or "Не указано"

            lines = [
                "<b>Мой профиль</b>",
                "",
                f"<b>ID:</b> {user.id}",
                f"<b>ФИО:</b> {html.escape(fio)}",
                f"<b>Дата рождения:</b> {html.escape(format_date(user.date_of_birth))}",
                f"<b>Телефон:</b> {html.escape(format_phone_readable(user.phone_number))}",
                f"<b>Адрес:</b> {html.escape(user.address or 'Не указан')}",
                f"<b>Предприятие:</b> {html.escape(company_name)}",
                f"<b>Статус:</b> {html.escape(user.status or 'Не указан')}",
            ]

            if user.registered_at:
                lines.append(
                    f"<b>Дата регистрации:</b> {html.escape(format_datetime(user.registered_at))}"
                )

            if volunteer_name:
                lines.append(f"<b>Волонтёр:</b> {html.escape(volunteer_name)}")

            return "\n".join(lines)


def parse_event(payload: dict[str, Any]) -> MaxEvent | None:
    update_type = str(payload.get("update_type") or payload.get("type") or "")
    if not update_type:
        return None

    if update_type == "bot_started":
        user = build_user(payload.get("user"))
        return MaxEvent(
            update_type=update_type,
            chat_id=to_int(payload.get("chat_id")),
            user=user,
            payload=payload,
        )

    if update_type == "message_created":
        message = payload.get("message") or {}
        body = message.get("body") or {}
        recipient = message.get("recipient") or {}
        return MaxEvent(
            update_type=update_type,
            chat_id=to_int(recipient.get("chat_id")),
            user=build_user(message.get("sender")),
            text=body.get("text"),
            message_id=body.get("mid"),
            attachments=body.get("attachments"),
            payload=payload,
        )

    if update_type == "message_callback":
        callback = payload.get("callback") or {}
        message = payload.get("message") or {}
        body = message.get("body") or {}
        recipient = message.get("recipient") or {}
        return MaxEvent(
            update_type=update_type,
            chat_id=to_int(recipient.get("chat_id")),
            user=build_user(callback.get("user")),
            callback_id=callback.get("callback_id"),
            callback_payload=callback.get("payload"),
            message_id=body.get("mid"),
            attachments=body.get("attachments"),
            payload=payload,
        )

    return None


def build_user(raw: dict[str, Any] | None) -> MaxUser | None:
    if not raw:
        return None
    user_id = to_int(raw.get("user_id"))
    if user_id is None:
        return None
    return MaxUser(
        user_id=user_id,
        name=raw.get("name"),
        username=raw.get("username"),
        is_bot=bool(raw.get("is_bot")),
    )


def build_identity_payload(max_user: MaxUser, chat_id: int) -> dict[str, Any]:
    return {
        "chat_id": str(chat_id),
        "name": max_user.name,
        "username": max_user.username,
        "is_bot": max_user.is_bot,
    }


def to_int(value: Any) -> int | None:
    try:
        if value is None:
            return None
        return int(value)
    except (TypeError, ValueError):
        return None


def normalize_command(value: str | None) -> str:
    return " ".join((value or "").strip().lower().split())


def normalize_name_piece(value: str | None) -> str:
    cleaned = " ".join((value or "").strip().split())
    if not cleaned:
        return ""
    return cleaned[:1].upper() + cleaned[1:].lower()


def parse_dob(value: str | None):
    try:
        return datetime.strptime((value or "").strip(), "%d.%m.%Y").date()
    except ValueError:
        return None


def normalize_phone(value: str | None) -> str | None:
    digits = re.sub(r"\D+", "", value or "")
    if len(digits) == 10:
        digits = f"7{digits}"
    elif len(digits) == 11 and digits.startswith("8"):
        digits = f"7{digits[1:]}"

    if len(digits) != 11 or not digits.startswith("7"):
        return None
    return digits


def mask_phone(phone: str | None) -> str:
    normalized = normalize_phone(phone)
    if not normalized:
        return "неизвестный номер"
    return f"+7 *** ***-{normalized[-4:-2]}-{normalized[-2:]}"


def format_phone_readable(phone: str | None) -> str:
    normalized = normalize_phone(phone)
    if not normalized:
        return phone or "Не указан"
    return f"+7 {normalized[1:4]} {normalized[4:7]}-{normalized[7:9]}-{normalized[9:11]}"


def format_date(value) -> str:
    if not value:
        return "Не указана"
    return value.strftime("%d.%m.%Y")


def format_datetime(value: datetime) -> str:
    if not value:
        return "Не указано"
    return value.strftime("%d.%m.%Y %H:%M")


def extract_phone_from_attachments(attachments: list[dict[str, Any]] | None) -> str | None:
    if not attachments:
        return None

    for attachment in attachments:
        if attachment.get("type") != "contact":
            continue

        payload = attachment.get("payload") or {}
        phone = normalize_phone(payload.get("vcf_phone"))
        if phone:
            return phone

        vcf_info = payload.get("vcf_info") or ""
        match = re.search(r"TEL[^:]*:([+\d\-\s()]+)", vcf_info)
        if match:
            phone = normalize_phone(match.group(1))
            if phone:
                return phone
    return None


def callback_button(text: str, payload: str, intent: str | None = None) -> dict[str, Any]:
    button = {
        "type": "callback",
        "text": text,
        "payload": payload,
    }
    if intent:
        button["intent"] = intent
    return button


def inline_keyboard(button_rows: list[list[dict[str, Any]]]) -> list[dict[str, Any]]:
    return [
        {
            "type": "inline_keyboard",
            "payload": {
                "buttons": button_rows,
            },
        }
    ]


def menu_keyboard() -> list[dict[str, Any]]:
    return inline_keyboard(
        [
            [
                callback_button("Регистрация", "menu:register"),
                callback_button("Мой профиль", "menu:profile"),
            ]
        ]
    )


def skip_volunteer_keyboard() -> list[dict[str, Any]]:
    return inline_keyboard(
        [
            [callback_button("Пропустить", "reg:skip_volunteer")],
            [callback_button("Отмена", "menu:cancel", intent="negative")],
        ]
    )


def nda_keyboard() -> list[dict[str, Any]]:
    return inline_keyboard(
        [
            [callback_button("Подтверждаю", "reg:agree_nda", intent="positive")],
            [callback_button("Отмена", "menu:cancel", intent="negative")],
        ]
    )


def company_keyboard(
    companies: list[dict[str, Any]],
    page: int,
    total_pages: int,
) -> list[dict[str, Any]]:
    rows: list[list[dict[str, Any]]] = []
    for company in companies:
        rows.append([callback_button(company["name"], f"reg:company:{company['id']}")])

    navigation: list[dict[str, Any]] = []
    if page > 0:
        navigation.append(callback_button("Назад", f"reg:comp_page:{page - 1}"))
    if page < total_pages - 1:
        navigation.append(callback_button("Дальше", f"reg:comp_page:{page + 1}"))
    if navigation:
        rows.append(navigation)

    rows.append([callback_button("Отмена", "menu:cancel", intent="negative")])
    return inline_keyboard(rows)


async def send_sms_code(phone_number: str) -> str | None:
    code = str(randint(10, 99))
    message = f"Ваш код для подтверждения: {code}"

    params = urlencode(
        {
            "login": SMS_LOGIN,
            "psw": SMS_PASSWORD,
            "phones": phone_number,
            "mes": message,
            "sender": SMS_SENDER,
        }
    )
    request = Request(
        url=f"{SMS_API_URL}?{params}",
        method="POST",
    )

    try:
        response_text = await asyncio.to_thread(_read_sms_response, request)
    except Exception:
        logger.exception("SMS provider request failed for phone %s", phone_number)
        return None

    if not response_text:
        return None

    logger.info("SMS provider response for %s: %s", phone_number, response_text)
    return code


def _read_sms_response(request: Request) -> str:
    with urlopen(request, timeout=15) as response:
        return response.read().decode("utf-8", errors="replace").strip()
