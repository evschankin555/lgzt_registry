# Registry Dashboard

Веб-дашборд для управления базой данных Registry Bot.

## 🎯 Функции

- 📊 Статистика (общая, за период)
- 👥 Управление пользователями (просмотр, редактирование, удаление, фильтры, поиск)
- 🙋 Управление волонтерами (изменение имени, удаление)
- 🏢 Просмотр компаний и статистики по ним
- 📥 Экспорт всех данных в Excel

## 📁 Структура

```
registry_dashboard/
├── backend/              # FastAPI (порт 8112)
│   ├── main.py          # API эндпоинты
│   ├── auth.py          # JWT авторизация
│   ├── config.py        # Настройки
│   └── requirements.txt
├── frontend/            # React + TypeScript + Vite
│   ├── src/
│   │   ├── pages/       # Страницы
│   │   ├── App.tsx
│   │   └── api.ts
│   └── package.json
└── deploy/              # Файлы деплоя
    ├── nginx-registry.conf
    ├── registry-dashboard.service
    └── deploy.sh
```

## 🚀 Локальный запуск

### Backend

```bash
cd registry_dashboard/backend
python -m venv venv
source venv/bin/activate  # Linux/Mac
# venv\Scripts\activate  # Windows

pip install -r requirements.txt

# Создать .env
cp .env.example .env
# Отредактировать .env

python main.py
# API доступен на http://localhost:8112
```

### Frontend

```bash
cd registry_dashboard/frontend
npm install
npm run dev
# Dashboard на http://localhost:3112
```

## 🌐 Деплой на сервер

### Автоматический деплой

```bash
chmod +x deploy.sh
./deploy.sh
```

Скрипт автоматически:
1. Соберет frontend
2. Загрузит на сервер
3. Установит backend dependencies
4. Настроит systemd сервис
5. Обновит nginx конфигурацию

### Ручной деплой

1. Собрать frontend:
```bash
cd registry_dashboard/frontend
npm install
npm run build
```

2. Загрузить на сервер:
```bash
rsync -avz registry_dashboard/ root@188.225.11.147:/var/www/lgzt_registry/registry_dashboard/
```

3. На сервере:
```bash
ssh root@188.225.11.147

# Backend
cd /var/www/lgzt_registry/registry_dashboard/backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# Отредактировать .env

# Systemd сервис
sudo cp deploy/registry-dashboard.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable registry-dashboard
sudo systemctl start registry-dashboard

# Nginx
sudo cp deploy/nginx-registry.conf /etc/nginx/sites-available/lgzt-registry
sudo ln -sf /etc/nginx/sites-available/lgzt-registry /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

## 🔐 Доступ

- **URL**: https://lgzt.developing-site.ru/registry/
- **Пароль**: `admin2026` (или из .env: `REGISTRY_ADMIN_PASSWORD`)

## 📝 API Эндпоинты

| Метод | URL | Описание |
|-------|-----|----------|
| POST | /api/login | Авторизация |
| GET | /api/stats | Статистика |
| GET | /api/users | Список пользователей |
| GET | /api/users/{id} | Пользователь по ID |
| PATCH | /api/users/{id} | Обновить пользователя |
| DELETE | /api/users/{id} | Удалить пользователя |
| GET | /api/companies | Список компаний |
| GET | /api/volunteers | Список волонтеров |
| PATCH | /api/volunteers/{id} | Обновить волонтера |
| DELETE | /api/volunteers/{id} | Удалить волонтера |
| GET | /api/export/excel | Экспорт в Excel |

## 🔧 Управление на сервере

```bash
# Логи
journalctl -u registry-dashboard -f

# Статус
systemctl status registry-dashboard

# Перезапуск
sudo systemctl restart registry-dashboard

# Остановка
sudo systemctl stop registry-dashboard

# Запуск
sudo systemctl start registry-dashboard
```

## 🛠️ Разработка

### Добавление нового эндпоинта

1. Добавить в `backend/main.py`:
```python
@app.get(f"{API_PREFIX}/new-endpoint")
async def new_endpoint(current_user: dict = Depends(get_current_user)):
    return {"data": "value"}
```

2. Добавить в `frontend/src/api.ts`:
```typescript
export const getNewData = async () => {
  const response = await api.get('/new-endpoint');
  return response.data;
};
```

3. Использовать в компоненте:
```typescript
const data = await getNewData();
```

## 📦 Переменные окружения

### Backend (.env)

```env
REGISTRY_SECRET_KEY=your-secret-key
REGISTRY_ADMIN_PASSWORD=admin2026
```

## ❓ Troubleshooting

### Backend не запускается
```bash
# Проверить логи
journalctl -u registry-dashboard -n 50

# Проверить что БД существует
ls -la /var/www/lgzt_registry/app.db

# Проверить порт
netstat -tlnp | grep 8112
```

### Frontend не собирается
```bash
# Очистить кэш
cd registry_dashboard/frontend
rm -rf node_modules dist
npm install
npm run build
```

### Nginx 502 Bad Gateway
```bash
# Проверить что backend работает
systemctl status registry-dashboard

# Проверить логи nginx
tail -f /var/log/nginx/registry_error.log
```

## 📄 Лицензия

Приватный проект
