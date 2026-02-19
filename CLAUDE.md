# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

A Russian-language Telegram bot for user registration in an organization. Users verify their identity by matching surname + date of birth against a pre-imported database, confirm via SMS code, and select their company affiliation. Admins can view statistics, export data to Excel, and manage user/company assignments.

## Tech Stack

- **Python 3** with async/await
- **pyTelebot** (async_telebot) for Telegram Bot API
- **SQLAlchemy** with async support (aiosqlite)
- **Alembic** for database migrations
- **SQLite** database (`app.db`)
- **SMSC.ru** for SMS verification

## Running the Bot

```bash
# Set up environment (creates .env from example.env if missing)
# Edit .env with your telegram_bot_api token

# Run the bot
python main.py
```

## Database Setup & Migrations

```bash
# Create initial database tables
python bootstrap.py

# Run migrations
alembic upgrade head

# Create new migration after model changes
alembic revision --autogenerate -m "description"

# Seed companies from Excel file
python seed_companies.py

# Import users from Excel
python import_people.py  # from data/База.xlsx
```

## Architecture

### Core Files
- `main.py` - Bot entry point, all message/callback handlers, state machine flow
- `vars.py` - Bot initialization, state definitions (`MyStates`), keyboard markups, admin IDs, `PRODUCTION_MODE` flag
- `functions.py` - Business logic (DB queries, SMS sending, Excel export, user registration, volunteer checks)
- `models.py` - SQLAlchemy models: `User`, `Company`, `User_who_blocked`, `User_volunteer`
- `db.py` - Async database engine and session factory

### Modules
- `modules/admin_ui.py` - Admin interface with pagination, user/company/volunteer cards, statistics, callback handlers
- `modules/user_ui.py` - User interface helpers (step messages, profile formatting, company selection)
- `modules/auto_migrate.py` - Automatic database migrations on startup (adds missing columns)
- `modules/auth.py` - Developer role checks and permissions
- `modules/logger.py` - Logging for admin actions (company changes, user deletions, role switches)
- `modules/error_handler.py` - Safe message sending/editing with error handling

### Data Flow
1. User sends `/start` -> bot checks if admin/volunteer/regular user
2. **Volunteer ID prompt** (optional) -> user can specify volunteer who helped them register
3. Registration flow: surname -> DOB -> name + patronymic -> phone (SMS verification) -> address -> NDA -> company selection
4. State machine (`MyStates`) tracks user progress through multi-step registration
5. User data stored with status: `not registered`, `registered`, `blocked`, `deleted`
6. SMS verification: code and timestamp saved to `sms_code` and `sms_confirmed_at` fields

### Admin Features (IDs in `vars.py`)
- User statistics (daily/weekly/monthly registrations)
- Company statistics
- Full Excel export of all data
- User management:
  - Edit user company
  - Delete user (sets status to `deleted`, unbinds Telegram)
  - Reset status to "not registered" (unbinds Telegram)
- Volunteer management:
  - Add/delete volunteers
  - Edit volunteer names (sets `name_manual=1` to prevent auto-overwrite)
  - View volunteer statistics (registration counts)
  - Auto-update volunteer names from Telegram on `/start` (if not manually set)
- Search users by name, ID, or phone

### Volunteer Features
- Can register other users
- Volunteer assignment tracked in `User.volunteer_id`
- Volunteer name auto-updates from Telegram first/last name on bot interaction
- Manual name edits protected from auto-overwrite via `name_manual` flag

### SMS Integration
- SMSC.ru API for sending verification codes
- Sender name: `kotelnikiru`
- 2-digit verification codes
- SMS confirmation tracked: `sms_code` and `sms_confirmed_at` stored in User model
- Displayed in admin user card for audit purposes

### Callback Routing (важно!)
В `main.py` есть два списка, определяющих какие callback'и попадают в `handle_admin_callback`:
- `admin_ui_callbacks` — точные совпадения (`admin_menu`, `admin_users`, etc.)
- `admin_ui_prefixes` — префиксы (`user_`, `delete_user_`, `reset_status_`, etc.)

**При добавлении нового callback в `admin_ui.py` обязательно добавить его префикс в `admin_ui_prefixes` в `main.py`, иначе callback не будет обработан.**

### Deployment
- `webhook.py` - GitHub webhook server for auto-deploy (systemd service)
- Auto-restarts `lgzt_registry-bot` service after git pull

## Environment Variables

Required in `.env`:
- `telegram_bot_api` - Telegram Bot API token

## Git Workflow

**ВАЖНО:** После каждого завершённого шага работы (исправление бага, добавление функции, рефакторинг) необходимо делать коммит и пуш:

```bash
git add .
git commit -m "Описание изменений"
git push
```

Это автоматически запустит деплой на сервер через webhook.
