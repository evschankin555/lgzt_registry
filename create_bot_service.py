#!/usr/bin/env python3
"""
Скрипт для создания systemd сервиса для Telegram бота lgzt_registry
Использует подход из проекта langgraph
"""

import subprocess
import sys
import os

def run_command(command, use_sudo=False):
    """Выполнить команду"""
    if use_sudo:
        command = f"sudo {command}"
    
    try:
        result = subprocess.run(
            command,
            shell=True,
            check=True,
            capture_output=True,
            text=True
        )
        return True, result.stdout, result.stderr
    except subprocess.CalledProcessError as e:
        return False, e.stdout, e.stderr

def create_bot_service():
    """Создает systemd сервис для бота"""
    
    service_name = "lgzt_registry-bot"
    project_dir = "/var/www/lgzt_registry"
    bot_script = f"{project_dir}/main.py"
    user = "www-data"
    
    service_content = f"""[Unit]
Description=lgzt_registry Telegram Bot
After=network.target
Wants=network.target

[Service]
Type=simple
User={user}
Group={user}
WorkingDirectory={project_dir}
Environment="PATH=/usr/bin"
ExecStart=/usr/bin/python3 {bot_script}
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
"""
    
    service_file_path = f"/etc/systemd/system/{service_name}.service"
    
    print(f"Создание systemd сервиса: {service_name}")
    print(f"Файл: {service_file_path}")
    
    # Записываем файл
    try:
        with open(service_file_path, 'w') as f:
            f.write(service_content)
        print(f"✓ Файл сервиса создан: {service_file_path}")
    except PermissionError:
        print("✗ Ошибка: нет прав для записи. Запустите с sudo или выполните:")
        print(f"  sudo tee {service_file_path} << 'EOF'")
        print(service_content)
        print("EOF")
        return False
    
    # Устанавливаем права
    success, stdout, stderr = run_command(f"chmod 644 {service_file_path}", use_sudo=True)
    if not success:
        print(f"✗ Ошибка установки прав: {stderr}")
        return False
    
    # Перезагружаем systemd
    success, stdout, stderr = run_command("systemctl daemon-reload", use_sudo=True)
    if not success:
        print(f"✗ Ошибка перезагрузки systemd: {stderr}")
        return False
    print("✓ systemd перезагружен")
    
    # Включаем автозапуск
    success, stdout, stderr = run_command(f"systemctl enable {service_name}", use_sudo=True)
    if not success:
        print(f"✗ Ошибка включения сервиса: {stderr}")
        return False
    print(f"✓ Сервис {service_name} включен для автозапуска")
    
    # Запускаем сервис
    success, stdout, stderr = run_command(f"systemctl start {service_name}", use_sudo=True)
    if not success:
        print(f"✗ Ошибка запуска сервиса: {stderr}")
        return False
    print(f"✓ Сервис {service_name} запущен")
    
    # Проверяем статус
    success, stdout, stderr = run_command(f"systemctl status {service_name}", use_sudo=True)
    if success:
        print("\n" + "="*60)
        print("СТАТУС СЕРВИСА:")
        print("="*60)
        print(stdout)
    
    print("\n" + "="*60)
    print("СЕРВИС УСПЕШНО СОЗДАН И ЗАПУЩЕН!")
    print("="*60)
    print(f"\nПолезные команды:")
    print(f"  Просмотр логов в реальном времени:")
    print(f"    sudo journalctl -u {service_name} -f")
    print(f"\n  Проверка статуса:")
    print(f"    sudo systemctl status {service_name}")
    print(f"\n  Перезапуск:")
    print(f"    sudo systemctl restart {service_name}")
    print(f"\n  Остановка:")
    print(f"    sudo systemctl stop {service_name}")
    
    return True

if __name__ == "__main__":
    if os.geteuid() != 0:
        print("ВНИМАНИЕ: Скрипт требует прав root для создания systemd сервиса")
        print("Запустите с sudo:")
        print("  sudo python3 create_bot_service.py")
        sys.exit(1)
    
    success = create_bot_service()
    sys.exit(0 if success else 1)
