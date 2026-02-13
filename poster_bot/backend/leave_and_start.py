"""
Скрипт для выхода из групп где успешно отправили и запуска автоматического режима
"""
import requests
import time
from datetime import datetime

API_BASE = "https://lgzt.developing-site.ru/api"
PASSWORD = "admin2026$rassilka"


class PosterBotController:
    def __init__(self):
        self.token = None
        self.phone = None

    def authenticate(self):
        """Авторизация"""
        response = requests.post(
            f"{API_BASE}/login",
            json={"password": PASSWORD}
        )
        response.raise_for_status()
        self.token = response.json()["access_token"]
        print(f"[OK] Авторизован")

    def headers(self):
        return {"Authorization": f"Bearer {self.token}"}

    def get_accounts(self):
        """Получить список аккаунтов"""
        response = requests.get(f"{API_BASE}/telegram/accounts", headers=self.headers())
        response.raise_for_status()
        accounts = response.json()
        if accounts:
            self.phone = accounts[0]['phone']
        return accounts

    def get_groups(self, filter_status=None):
        """Получить список групп"""
        url = f"{API_BASE}/groups"
        if filter_status:
            url += f"?filter={filter_status}"
        response = requests.get(url, headers=self.headers())
        response.raise_for_status()
        return response.json()

    def leave_groups_batch(self, group_ids: list):
        """Выйти из нескольких групп"""
        if not self.phone:
            self.get_accounts()

        group_ids_str = ",".join(str(gid) for gid in group_ids)
        data = {
            "phone": self.phone,
            "group_ids": group_ids_str
        }
        response = requests.post(
            f"{API_BASE}/groups/leave-batch",
            data=data,
            headers=self.headers()
        )
        response.raise_for_status()
        return response.json()

    def get_settings(self):
        """Получить настройки"""
        response = requests.get(f"{API_BASE}/settings", headers=self.headers())
        response.raise_for_status()
        return response.json()

    def start_auto_mode(self):
        """Запустить автоматический режим"""
        if not self.phone:
            self.get_accounts()

        data = {"phone": self.phone}
        response = requests.post(
            f"{API_BASE}/auto/start",
            data=data,
            headers=self.headers()
        )
        response.raise_for_status()
        return response.json()

    def stop_auto_mode(self):
        """Остановить автоматический режим"""
        response = requests.post(
            f"{API_BASE}/auto/stop",
            headers=self.headers()
        )
        response.raise_for_status()
        return response.json()

    def get_auto_status(self):
        """Статус автоматического режима"""
        response = requests.get(f"{API_BASE}/auto/status", headers=self.headers())
        response.raise_for_status()
        return response.json()


def main():
    controller = PosterBotController()

    try:
        # Авторизация
        controller.authenticate()

        # Получаем аккаунты
        accounts = controller.get_accounts()
        print(f"\n[INFO] Используем аккаунт: {controller.phone}")

        # Получаем joined группы
        joined_groups = controller.get_groups(filter_status="joined")
        print(f"\n[INFO] Всего joined групп: {len(joined_groups)}")

        # Фильтруем группы где can_leave=True (успешно отправили)
        groups_to_leave = [g for g in joined_groups if g.get("can_leave")]
        print(f"[INFO] Групп для выхода (can_leave=True): {len(groups_to_leave)}")

        if groups_to_leave:
            # Выходим батчами по 50 групп
            batch_size = 50
            total_left = 0

            for i in range(0, len(groups_to_leave), batch_size):
                batch = groups_to_leave[i:i+batch_size]
                batch_ids = [g["id"] for g in batch]

                print(f"\n[ACTION] Выходим из групп {i+1}-{min(i+batch_size, len(groups_to_leave))} из {len(groups_to_leave)}...")

                result = controller.leave_groups_batch(batch_ids)
                total_left += result["success_count"]

                print(f"[OK] Успешно вышли: {result['success_count']}")
                print(f"[ERROR] Ошибок: {result['fail_count']}")

                # Пауза между батчами
                if i + batch_size < len(groups_to_leave):
                    print(f"[INFO] Пауза 10 секунд...")
                    time.sleep(10)

            print(f"\n[OK] Всего вышли из {total_left} групп")
        else:
            print(f"[INFO] Нет групп для выхода")

        # Проверяем настройки
        settings = controller.get_settings()
        print(f"\n[INFO] Настройки:")
        print(f"  - Активное сообщение ID: {settings.get('active_message_id')}")
        print(f"  - Время отправки: {settings.get('send_start_hour')}:00 - {settings.get('send_end_hour')}:00")
        print(f"  - Дневной лимит: {settings.get('daily_limit')}")

        # Проверяем текущий статус автоматического режима
        auto_status = controller.get_auto_status()
        print(f"\n[INFO] Автоматический режим:")
        print(f"  - Запущен: {auto_status['is_running']}")

        if not auto_status['is_running']:
            # Запускаем автоматический режим
            print(f"\n[ACTION] Запускаем автоматический режим...")
            result = controller.start_auto_mode()
            print(f"[OK] Автоматический режим запущен: {result}")

            # Ждем немного и проверяем статус
            time.sleep(3)
            auto_status = controller.get_auto_status()
            print(f"\n[INFO] Статус после запуска:")
            print(f"  - Режим: {auto_status['status']['mode']}")
            print(f"  - Текущее действие: {auto_status['status'].get('current_action')}")
            print(f"  - Сегодня вступлений: {auto_status['status']['today_joins']}")
            print(f"  - Сегодня отправок: {auto_status['status']['today_sends']}")
        else:
            print(f"[INFO] Автоматический режим уже запущен")
            print(f"  - Режим: {auto_status['status']['mode']}")
            print(f"  - Текущее действие: {auto_status['status'].get('current_action')}")

        print(f"\n[INFO] Бот будет работать до 21:00 МСК")
        print(f"[INFO] Текущее время: {datetime.now().strftime('%H:%M:%S')}")

    except Exception as e:
        print(f"\n[ERROR] Ошибка: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
