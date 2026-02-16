# 🚀 Деплой Registry Dashboard - Инструкция

Код уже на сервере (через webhook). Теперь нужно задеплоить дашборд.

## Вариант 1: Автоматический (рекомендуется)

```bash
ssh root@188.225.11.147
cd /var/www/lgzt_registry/registry_dashboard
chmod +x deploy.sh
./deploy.sh
```

Скрипт автоматически:
- Соберет frontend (React)
- Установит Python зависимости
- Настроит systemd сервис
- Обновит nginx

## Вариант 2: Ручной (пошагово)

```bash
ssh root@188.225.11.147
cd /var/www/lgzt_registry/registry_dashboard

# 1. Backend
cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# Отредактировать .env если нужно
deactivate
cd ..

# 2. Frontend
cd frontend
npm install
npm run build
cd ..

# 3. Systemd сервис
sudo cp deploy/registry-dashboard.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable registry-dashboard
sudo systemctl start registry-dashboard

# 4. Nginx
sudo cp deploy/nginx-registry.conf /etc/nginx/sites-available/lgzt-registry
sudo ln -sf /etc/nginx/sites-available/lgzt-registry /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

## Проверка

После деплоя:

1. **Проверить backend:**
```bash
sudo systemctl status registry-dashboard
journalctl -u registry-dashboard -n 50
curl http://localhost:8112/health
```

2. **Открыть дашборд:**
https://lgzt.developing-site.ru/registry/

Логин: `admin2026`

## Если что-то пошло не так

### Backend не запускается
```bash
journalctl -u registry-dashboard -f
# Проверить БД
ls -la /var/www/lgzt_registry/app.db
```

### Nginx ошибка
```bash
sudo nginx -t
tail -f /var/log/nginx/registry_error.log
```

### Frontend не собрался
```bash
cd /var/www/lgzt_registry/registry_dashboard/frontend
rm -rf node_modules dist
npm install
npm run build
```

## Полезные команды

```bash
# Логи backend
journalctl -u registry-dashboard -f

# Перезапуск backend
sudo systemctl restart registry-dashboard

# Перезапуск nginx
sudo systemctl reload nginx

# Пересборка frontend
cd /var/www/lgzt_registry/registry_dashboard/frontend
npm run build
```
