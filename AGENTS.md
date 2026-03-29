# AGENTS.md

Оперативная памятка для агентных правок по проекту `lgzt_registry`.

## Что это за проект
- Telegram-бот регистрации (`main.py`)
- Веб-админка:
  - UI: `https://lgzt.developing-site.ru/registry/`
  - API: `https://lgzt.developing-site.ru/registry-api/*`

## Прод окружение
- Хост: `poster-dev` (root SSH)
- Код: `/var/www/lgzt_registry`
- Сервисы:
  - `lgzt_registry-bot` — бот
  - `registry-dashboard` — FastAPI backend админки
- БД в проде: PostgreSQL через `DATABASE_URL` из `/var/www/lgzt_registry/.env`

## Критичные технические договорённости
- `db.py` читает `DATABASE_URL` (SQLite только fallback для локалки)
- Для Alembic используется `ALEMBIC_DATABASE_URL`
- В проде datetime-фильтры для регистраций должны быть naive UTC (`datetime.utcnow()`), иначе ошибка с `TIMESTAMP WITHOUT TIME ZONE`
- Dashboard backend должен читать env через systemd `EnvironmentFile=/var/www/lgzt_registry/.env`
- В `registry_dashboard/backend` venv обязателен `asyncpg`
- Во фронте админки при `401` токен очищается и делается редирект на `/registry/login`
- В `Users` дефолтный фильтр: `registered`

## Быстрая проверка после правок
```bash
ssh poster-dev "systemctl is-active lgzt_registry-bot registry-dashboard"

# Логин и данные админки (должны приходить не пустые JSON)
TOKEN=$(curl -sS -X POST "https://lgzt.developing-site.ru/registry-api/login" \
  -H "Content-Type: application/json" \
  -d '{"password":"admin2026"}' | python -c "import sys,json;print(json.load(sys.stdin).get('access_token',''))")

curl -sS -H "Authorization: Bearer $TOKEN" "https://lgzt.developing-site.ru/registry-api/stats"
curl -sS -H "Authorization: Bearer $TOKEN" "https://lgzt.developing-site.ru/registry-api/users?page=0&limit=5&status=registered"
```

## Если жалоба "бот висит" / "админка пустая"
1. Проверить статус сервисов и последние логи (`journalctl -u ... -n 200`)
2. Проверить, что dashboard не ушёл в SQLite (признак: `no such table: user`)
3. Проверить токен/401 в `/registry-api/*`
4. Проверить фактический payload API, а не только HTTP 200
5. Для бота проверить ошибки SQL по datetime в логах

## Важные файлы
- `main.py`
- `modules/admin_ui.py`
- `functions.py`
- `db.py`
- `models.py`
- `registry_dashboard/backend/main.py`
- `registry_dashboard/backend/requirements.txt`
- `registry_dashboard/frontend/src/api.ts`
- `registry_dashboard/frontend/src/pages/Users.tsx`
