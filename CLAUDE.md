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
- `vars.py` - Bot initialization, state definitions (`MyStates`), keyboard markups, admin IDs
- `functions.py` - Business logic (DB queries, SMS sending, Excel export, user registration)
- `models.py` - SQLAlchemy models: `User`, `Company`, `User_who_blocked`, `User_volunteer`
- `db.py` - Async database engine and session factory

### Data Flow
1. User sends `/start` -> bot checks if admin/volunteer/regular user
2. Registration flow: surname -> DOB -> name + patronymic -> phone (SMS verification) -> address -> NDA -> company selection
3. State machine (`MyStates`) tracks user progress through multi-step registration
4. User data stored with status: `not registered`, `registered`, `blocked`, `deleted`

### Admin Features (IDs in `vars.py`)
- User statistics (daily/weekly/monthly registrations)
- Company statistics
- Full Excel export of all data
- Edit user company / delete user
- Add volunteers (can register others)

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
