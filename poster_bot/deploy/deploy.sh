#!/bin/bash
# Скрипт деплоя Poster Bot на сервер

set -e

echo "=== Poster Bot Deploy Script ==="

SERVER="root@188.225.11.147"
REMOTE_PATH="/var/www/poster-bot"

# 1. Создаём директории на сервере
echo "[1/7] Создание директорий..."
ssh $SERVER "mkdir -p $REMOTE_PATH/backend $REMOTE_PATH/frontend $REMOTE_PATH/backend/data/sessions $REMOTE_PATH/backend/data/uploads"

# 2. Копируем backend
echo "[2/7] Копирование backend..."
scp -r backend/* $SERVER:$REMOTE_PATH/backend/

# 3. Копируем frontend (нужно сначала собрать)
echo "[3/7] Сборка frontend..."
cd frontend
npm install
npm run build
cd ..

echo "[4/7] Копирование frontend..."
scp -r frontend/dist $SERVER:$REMOTE_PATH/frontend/

# 5. Настройка Python venv
echo "[5/7] Настройка Python окружения..."
ssh $SERVER "cd $REMOTE_PATH/backend && python3 -m venv venv && source venv/bin/activate && pip install -r requirements.txt"

# 6. Копируем и активируем systemd сервис
echo "[6/7] Настройка systemd сервиса..."
scp deploy/poster-bot.service $SERVER:/etc/systemd/system/
ssh $SERVER "systemctl daemon-reload && systemctl enable poster-bot && systemctl restart poster-bot"

# 7. Настройка nginx
echo "[7/7] Настройка nginx..."
scp deploy/nginx-poster.conf $SERVER:/etc/nginx/sites-available/poster-bot
ssh $SERVER "ln -sf /etc/nginx/sites-available/poster-bot /etc/nginx/sites-enabled/ && nginx -t && systemctl reload nginx"

echo ""
echo "=== Деплой завершён! ==="
echo "Сайт доступен: https://lgzt.developing-site.ru"
echo ""
echo "Не забудьте:"
echo "1. Получить SSL сертификат: certbot --nginx -d lgzt.developing-site.ru"
echo "2. Создать .env файл на сервере: $REMOTE_PATH/backend/.env"
