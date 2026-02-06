# Poster Bot - Автопостинг в Telegram группы

Дашборд для автоматической публикации фото в Telegram группы от имени пользователя.

## Структура проекта

```
poster_bot/
├── backend/              # FastAPI + Telethon
│   ├── main.py          # API эндпоинты
│   ├── telegram_client.py # Telethon клиент
│   ├── auth.py          # JWT авторизация
│   ├── models.py        # SQLAlchemy модели
│   ├── database.py      # База данных
│   ├── config.py        # Настройки
│   └── requirements.txt
├── frontend/            # React + Vite
│   └── src/
│       ├── pages/
│       │   ├── Login.tsx
│       │   └── Dashboard.tsx
│       └── ...
├── deploy/              # Файлы деплоя
│   ├── nginx-poster.conf
│   ├── poster-bot.service
│   └── deploy.sh
└── data/                # Данные
    ├── sessions/        # Telegram сессии
    └── uploads/         # Загруженные фото
```

## Локальный запуск

### Backend

```bash
cd poster_bot/backend
python -m venv venv
source venv/bin/activate  # Linux/Mac
# или: venv\Scripts\activate  # Windows

pip install -r requirements.txt

# Создать .env из примера
cp .env.example .env
# Отредактировать .env - указать API credentials

python main.py
```

API будет доступен на http://localhost:8001

### Frontend

```bash
cd poster_bot/frontend
npm install
npm run dev
```

Дашборд будет доступен на http://localhost:3000

## Деплой на сервер

### Предварительные требования

- Python 3.10+
- Node.js 18+
- nginx
- certbot (для SSL)

### Шаги деплоя

1. **Настройка DNS** - добавить A-запись `lgzt.developing-site.ru` -> `188.225.11.147`

2. **Запуск скрипта деплоя**:
```bash
chmod +x deploy/deploy.sh
./deploy/deploy.sh
```

3. **SSL сертификат**:
```bash
ssh root@188.225.11.147
certbot --nginx -d lgzt.developing-site.ru
```

4. **Проверка сервисов**:
```bash
systemctl status poster-bot
systemctl status nginx
```

## Использование

### 1. Вход в дашборд
- Откройте https://lgzt.developing-site.ru
- Пароль: `admin2026$rassilka`

### 2. Авторизация Telegram
- Перейдите в раздел "Telegram аккаунт"
- Введите номер телефона в формате +7XXXXXXXXXX
- Введите код из Telegram
- При необходимости введите 2FA пароль

### 3. Загрузка групп
- Перейдите в раздел "Группы"
- Выберите авторизованный аккаунт
- Группы загрузятся автоматически из Telegram
- Нажмите "Добавить" для нужных групп

### 4. Отправка фото
- Перейдите в раздел "Отправить"
- Выберите аккаунт-отправитель
- Отметьте группы для рассылки
- Добавьте подпись (опционально)
- Загрузите фото
- Нажмите "Отправить"

### 5. История
- В разделе "История" отображаются все рассылки
- Статусы: success (успех), failed (ошибка), pending (ожидание)

## API Эндпоинты

| Метод | URL | Описание |
|-------|-----|----------|
| POST | /api/login | Авторизация в дашборде |
| POST | /api/telegram/send-code | Отправка кода на телефон |
| POST | /api/telegram/verify-code | Подтверждение кода |
| GET | /api/telegram/accounts | Список аккаунтов |
| GET | /api/telegram/dialogs/{phone} | Список групп из TG |
| GET | /api/groups | Сохранённые группы |
| POST | /api/posts/send | Отправить фото |
| GET | /api/posts | История рассылок |
| GET | /api/stats | Статистика |

## Безопасность

- Пароль дашборда хранится в .env
- JWT токены с истечением 24 часа
- Telegram сессии сохраняются локально
- Загруженные файлы хранятся на сервере
