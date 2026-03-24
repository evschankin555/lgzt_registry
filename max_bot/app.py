import json
import logging
from typing import Any

from fastapi import FastAPI, Header, HTTPException, Query, Request

from max_bot.config import get_max_settings

logger = logging.getLogger(__name__)

app = FastAPI(title="LGZT Registry MAX Bot")


def _extract_update_type(payload: dict[str, Any]) -> str:
    for key in ("update_type", "type", "event_type"):
        value = payload.get(key)
        if value:
            return str(value)
    return "unknown"


def _is_secret_valid(
    expected_secret: str,
    header_secret: str | None,
    query_secret: str | None,
) -> bool:
    if not expected_secret:
        return True
    return header_secret == expected_secret or query_secret == expected_secret


@app.get("/healthz")
async def healthz() -> dict[str, Any]:
    return {
        "ok": True,
        "service": "lgzt_registry_max_bot",
    }


@app.post("/max-bot/webhook")
async def max_webhook(
    request: Request,
    x_max_bot_api_secret: str | None = Header(default=None),
    secret: str | None = Query(default=None),
) -> dict[str, Any]:
    settings = get_max_settings()
    expected_secret = settings.max_webhook_secret.strip()

    if not _is_secret_valid(expected_secret, x_max_bot_api_secret, secret):
        raise HTTPException(status_code=403, detail="Invalid MAX webhook secret")

    body = await request.body()
    try:
        payload = json.loads(body.decode("utf-8") if body else "{}")
    except json.JSONDecodeError as exc:
        logger.warning("MAX webhook received invalid JSON: %s", exc)
        raise HTTPException(status_code=400, detail="Invalid JSON payload") from exc

    update_type = _extract_update_type(payload)

    if settings.max_debug_log_payloads:
        logger.info(
            "MAX webhook payload type=%s payload=%s",
            update_type,
            json.dumps(payload, ensure_ascii=False),
        )
    else:
        logger.info("MAX webhook payload type=%s", update_type)

    return {
        "ok": True,
        "update_type": update_type,
    }
