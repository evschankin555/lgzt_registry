#!/usr/bin/env python3
"""
Простой webhook сервер для автоматического деплоя при push в GitHub
Запускает git pull в /var/www/lgzt_registry при получении webhook от GitHub
"""

import hmac
import hashlib
import json
import subprocess
import logging
import os
from http.server import HTTPServer, BaseHTTPRequestHandler

# Настройка
# ВАЖНО: Это шаблон! Плейсхолдеры "", 4561, "lgzt_registry-webhook" 
# заменяются генератором WebhookGenerator перед использованием
WEBHOOK_SECRET = ""  # type: ignore  # noqa: F821
PROJECT_DIR = "/var/www/lgzt_registry"
BRANCH = "main"
PORT = 4561  # type: ignore  # noqa: F821
SSH_KEY_PATH = "/var/www/.ssh/id_ed25519"
SERVICE_NAME = "lgzt_registry-webhook"  # type: ignore  # noqa: F821
BOT_SERVICE_NAME = "lgzt_registry-bot"  # Сервис бота для перезапуска после деплоя

# Логирование
LOG_PATH = "/var/www/lgzt_registry/logs/webhook.log"
# Создаем директорию для логов (если не существует)
# Директория должна быть создана заранее с правильными правами
log_dir = os.path.dirname(LOG_PATH)
if log_dir:
    try:
        os.makedirs(log_dir, exist_ok=True)
    except PermissionError:
        # Если нет прав, логируем только в stdout/stderr
        LOG_PATH = None
# Настройка логирования
handlers = [logging.StreamHandler()]
if LOG_PATH:
    try:
        handlers.append(logging.FileHandler(LOG_PATH))
    except (PermissionError, OSError):
        # Если не удалось создать файл логов, используем только stdout
        pass

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=handlers
)
logger = logging.getLogger(__name__)


def run_command(command, cwd=None):
    """Выполнить команду с учетом SSH ключа для git команд"""
    try:
        env = os.environ.copy()
        
        # Настройка SSH для git команд
        if command.startswith('git') and os.path.exists(SSH_KEY_PATH):
            git_ssh_command = f'ssh -i /var/www/.ssh/id_ed25519 -o StrictHostKeyChecking=no -o UserKnownHostsFile=/var/www/.ssh/known_hosts'
            env['GIT_SSH_COMMAND'] = git_ssh_command
            env['GIT_SSH'] = git_ssh_command
        
        process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            shell=True,
            cwd=cwd or PROJECT_DIR,
            env=env
        )
        output, error = process.communicate()
        output_str = output.decode('utf-8')
        error_str = error.decode('utf-8')
        
        if process.returncode != 0:
            logger.error(f"Command failed: {command}")
            logger.error(f"Error: {error_str}")
        else:
            logger.info(f"Command success: {command}")
            if output_str:
                logger.info(f"Output: {output_str}")
        
        return output_str, error_str, process.returncode
    except Exception as e:
        logger.error(f"Exception in run_command: {str(e)}")
        return '', str(e), 1


class WebhookHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        """Обработка POST запроса от GitHub"""
        # Логируем все POST запросы для отладки (как в рабочем скрипте)
        logger.info(f"Получен POST запрос на {self.path} от {self.client_address[0]}")
        logger.info(f"Headers: {dict(self.headers)}")
        
        # Проверяем путь
        if self.path != '/webhook':
            logger.warning(f"Неверный путь: {self.path}, ожидается /webhook")
            self.send_response(404)
            self.end_headers()
            return

        try:
            content_length = int(self.headers.get('Content-Length', 0))
            payload = self.rfile.read(content_length)
            logger.info(f"Размер payload: {content_length} байт")
        except (ValueError, TypeError) as e:
            logger.error(f"Ошибка чтения payload: {e}")
            self.send_response(400)
            self.end_headers()
            return

        # Проверка подписи (если установлен секрет)
        if WEBHOOK_SECRET:
            signature = self.headers.get('X-Hub-Signature-256', '')
            if signature:
                expected = hmac.new(
                    WEBHOOK_SECRET.encode(),
                    payload,
                    hashlib.sha256
                ).hexdigest()
                if not hmac.compare_digest(f"sha256={expected}", signature):
                    logger.warning("Неверная подпись webhook")
                    self.send_response(401)
                    self.end_headers()
                    return

        # Парсинг события
        try:
            event = json.loads(payload.decode('utf-8'))
            ref = event.get('ref', '')
            
            # Проверка ветки
            if f'refs/heads/main' in ref:
                logger.info(f"Получен push в ветку main, запуск деплоя...")
                
                try:
                    # Получаем текущий хеш коммита
                    current_output, _, code = run_command('git rev-parse HEAD')
                    if code != 0:
                        logger.error("Не удалось получить текущий коммит")
                        raise Exception("Failed to get current commit")
                    current_hash = current_output.strip()
                    logger.info(f"Текущий коммит: {current_hash}")
                    
                    # Получаем обновления
                    logger.info("Получение обновлений из репозитория...")
                    run_command(f'git fetch origin main')
                    
                    # Получаем хеш последнего коммита
                    origin_output, _, code = run_command(f'git rev-parse origin/main')
                    if code != 0:
                        logger.error("Не удалось получить коммит из origin")
                        raise Exception("Failed to get origin commit")
                    origin_hash = origin_output.strip()
                    logger.info(f"Коммит в origin: {origin_hash}")
                    
                    # Если есть новые коммиты
                    if current_hash != origin_hash:
                        logger.info("Обнаружены обновления, выполнение git pull...")
                        
                        # Выполнение git pull
                        output, error, code = run_command(f'git reset --hard origin/main')
                        if code != 0:
                            raise Exception(f"Git pull failed: {error}")
                        
                        # Обновление прав на файлы (кроме .git директории)
                        logger.info("Обновление прав на файлы...")
                        run_command('find . -path ./.git -prune -o -exec chown www-data:www-data {} +')
                        
                        # Перезапуск сервиса бота после деплоя (ПЕРЕД перезапуском webhook!)
                        if BOT_SERVICE_NAME:
                            logger.info(f"Перезапуск сервиса бота {BOT_SERVICE_NAME}...")
                            output, error, code = run_command(f"systemctl restart {BOT_SERVICE_NAME}")
                            if code != 0:
                                logger.error(f"Не удалось перезапустить сервис бота: {error}")
                        
                        # Перезапуск сервиса webhook (если указан) - в конце, асинхронно
                        if SERVICE_NAME:
                            logger.info(f"Перезапуск сервиса {SERVICE_NAME}...")
                            # Используем subprocess.Popen для асинхронного перезапуска,
                            # чтобы не прерывать выполнение до отправки ответа
                            try:
                                subprocess.Popen(['systemctl', 'restart', SERVICE_NAME], 
                                                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                                logger.info(f"Команда перезапуска webhook отправлена")
                            except Exception as e:
                                logger.error(f"Ошибка при перезапуске webhook: {e}")
                        
                        logger.info("Деплой успешно завершен!")
                    else:
                        logger.info("Нет новых обновлений")
                    
                    self.send_response(200)
                    self.send_header('Content-type', 'application/json')
                    self.end_headers()
                    self.wfile.write(json.dumps({'status': 'ok', 'message': 'Deployed'}).encode())
                except Exception as e:
                    logger.error(f"Ошибка деплоя: {str(e)}")
                    self.send_response(500)
                    self.end_headers()
            else:
                logger.info(f"Игнорирование push в ветку: {ref}")
                self.send_response(200)
                self.end_headers()
                
        except Exception as e:
            logger.error(f"Ошибка обработки webhook: {str(e)}")
            self.send_response(500)
            self.end_headers()

    def do_GET(self):
        """Проверка работоспособности"""
        # Разрешаем GET только для проверки работоспособности
        if self.path == '/webhook' or self.path == '/':
            self.send_response(200)
            self.send_header('Content-type', 'text/plain')
            self.end_headers()
            self.wfile.write(b'Webhook server is running')
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, format, *args):
        """Переопределение логирования"""
        logger.info(f"{self.address_string()} - {format % args}")


def main():
    """Запуск webhook сервера"""
    server = HTTPServer(('0.0.0.0', PORT), WebhookHandler)
    logger.info(f"Webhook сервер запущен на порту 4561")
    logger.info(f"Ожидание webhook от GitHub для деплоя в /var/www/lgzt_registry")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        logger.info("Остановка webhook сервера...")
        server.shutdown()


if __name__ == '__main__':
    main()

