#!/bin/bash
# Скрипт деплоя Registry Dashboard на сервер
set -e

SERVER="root@188.225.11.147"
PROJECT_DIR="/var/www/lgzt_registry"
BACKEND_DIR="$PROJECT_DIR/registry_dashboard/backend"
FRONTEND_DIR="$PROJECT_DIR/registry_dashboard/frontend"

echo "🚀 Deploying Registry Dashboard..."

# 1. Сборка frontend локально
echo "📦 Building frontend..."
cd registry_dashboard/frontend
npm install
npm run build
cd ../..

# 2. Отправка на сервер
echo "📤 Uploading to server..."
rsync -avz --delete \
  --exclude 'node_modules' \
  --exclude '.git' \
  --exclude 'venv' \
  --exclude '__pycache__' \
  --exclude '*.pyc' \
  registry_dashboard/ \
  $SERVER:$PROJECT_DIR/registry_dashboard/

# 3. Установка backend на сервере
echo "⚙️  Setting up backend on server..."
ssh $SERVER << 'EOF'
cd /var/www/lgzt_registry/registry_dashboard/backend

# Создаем виртуальное окружение если нет
if [ ! -d "venv" ]; then
    python3 -m venv venv
fi

# Активируем и устанавливаем зависимости
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

# Создаем .env если нет
if [ ! -f ".env" ]; then
    cp .env.example .env
    echo "⚠️  Создан .env файл, проверьте настройки!"
fi

# Копируем systemd сервис
sudo cp /var/www/lgzt_registry/registry_dashboard/deploy/registry-dashboard.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable registry-dashboard
sudo systemctl restart registry-dashboard

echo "✅ Backend deployed and restarted"
EOF

# 4. Настройка nginx
echo "🌐 Configuring nginx..."
ssh $SERVER << 'EOF'
# Обновляем конфигурацию nginx
sudo cp /var/www/lgzt_registry/registry_dashboard/deploy/nginx-registry.conf /etc/nginx/sites-available/lgzt-registry
sudo ln -sf /etc/nginx/sites-available/lgzt-registry /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx

echo "✅ Nginx configured and reloaded"
EOF

echo ""
echo "🎉 Deployment completed!"
echo "Dashboard: https://lgzt.developing-site.ru/registry/"
echo ""
echo "Useful commands:"
echo "  - View logs: ssh $SERVER journalctl -u registry-dashboard -f"
echo "  - Restart backend: ssh $SERVER sudo systemctl restart registry-dashboard"
echo "  - Check status: ssh $SERVER sudo systemctl status registry-dashboard"
