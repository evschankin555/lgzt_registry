# Poster Bot - Автопостинг в Telegram группы

Дашборд для автоматической публикации фото в Telegram группы от имени пользователя.

## Деплой

### Сервер
- **IP:** 188.225.11.147
- **Домен:** lgzt.developing-site.ru
- **SSH алиас:** `poster-dev`
- **Web root:** `/var/www/poster-bot/`

### SSH конфигурация (добавить в ~/.ssh/config)
```
Host poster-dev
    HostName 188.225.11.147
    User root
    Port 22
```

### Первоначальная настройка
```bash
# Один раз - настройка сервера
./deploy.sh setup
```

### Команды деплоя
```bash
# Деплой (git push + автосборка)
./deploy.sh

# Логи backend
./deploy.sh logs

# Статус сервиса
./deploy.sh status

# Перезапуск
./deploy.sh restart

# Получить SSL
./deploy.sh ssl
```

## Структура проекта

```
poster_bot/
├── backend/              # FastAPI + Telethon
│   ├── main.py          # API эндпоинты (порт 8001)
│   ├── telegram_client.py # Работа с TG
│   ├── auth.py          # JWT авторизация
│   ├── models.py        # SQLAlchemy модели
│   ├── config.py        # Настройки
│   ├── database.py      # БД
│   ├── .env             # Конфигурация (не в git!)
│   └── requirements.txt
├── frontend/            # React + Vite
│   ├── src/
│   │   ├── pages/
│   │   │   ├── Login.tsx
│   │   │   └── Dashboard.tsx
│   │   ├── App.tsx
│   │   └── api.ts
│   ├── package.json
│   └── vite.config.ts
├── deploy/              # Файлы деплоя
│   ├── nginx-poster-http.conf
│   ├── poster-bot.service
│   └── deploy.sh (старый)
├── server/              # Серверные скрипты
│   └── post-receive     # Git hook автодеплоя
├── deploy.sh            # Основной скрипт деплоя
└── CLAUDE.md            # Этот файл
```

## Технологии

### Backend
- Python 3.10+
- FastAPI - REST API
- Telethon - Telegram Client API (userbot)
- SQLAlchemy + aiosqlite - БД
- JWT - авторизация дашборда

### Frontend
- React 18
- TypeScript
- Vite - сборка
- Axios - HTTP клиент

## API Эндпоинты

| Метод | URL | Описание |
|-------|-----|----------|
| POST | /api/login | Авторизация (пароль) |
| POST | /api/telegram/send-code | Отправить код на телефон |
| POST | /api/telegram/verify-code | Подтвердить код |
| GET | /api/telegram/accounts | Список TG аккаунтов |
| GET | /api/telegram/dialogs/{phone} | Группы из TG |
| GET | /api/groups | Сохранённые группы |
| POST | /api/posts/send | Отправить фото |
| GET | /api/posts | История рассылок |
| GET | /api/stats | Статистика |

## Переменные окружения (.env)

```env
ADMIN_PASSWORD=admin2026$rassilka
SECRET_KEY=your-secret-key
TELEGRAM_API_ID=20279706
TELEGRAM_API_HASH=506f03c7787a0daa1df776a2ba15e95c
DATABASE_URL=sqlite+aiosqlite:///./data/poster.db
```

## Доступ к дашборду

- **URL:** https://lgzt.developing-site.ru
- **Пароль:** `admin2026$rassilka`

## Git правила

### Формат коммитов
```
тип: краткое описание
```

### Типы
- `feat:` - новая функция
- `fix:` - исправление
- `docs:` - документация
- `refactor:` - рефакторинг
- `chore:` - рутина

## Важно

- Telegram сессии хранятся в `backend/data/sessions/`
- Загруженные фото в `backend/data/uploads/`
- Логи: `journalctl -u poster-bot -f`
- После изменений просто: `./deploy.sh`
