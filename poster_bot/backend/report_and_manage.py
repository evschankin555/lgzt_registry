"""
Скрипт для управления рассылкой и генерации отчета
- Проверяет текущее состояние
- Выходит из групп где успешно отправили
- Входит в новые группы и отправляет сообщения
- Генерирует CSV отчет
"""
import requests
import csv
import json
from datetime import datetime
from typing import List, Dict

API_BASE = "https://lgzt.developing-site.ru/api"
PASSWORD = "admin2026$rassilka"


class PosterBotManager:
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
        return response.json()

    def get_messages(self):
        """Получить список сообщений"""
        response = requests.get(f"{API_BASE}/messages", headers=self.headers())
        response.raise_for_status()
        return response.json()

    def get_message_detail(self, message_id: int):
        """Получить детали сообщения"""
        response = requests.get(f"{API_BASE}/messages/{message_id}", headers=self.headers())
        response.raise_for_status()
        return response.json()

    def get_groups(self, filter_status=None):
        """Получить список групп"""
        url = f"{API_BASE}/groups"
        if filter_status:
            url += f"?filter={filter_status}"
        response = requests.get(url, headers=self.headers())
        response.raise_for_status()
        return response.json()

    def get_groups_stats(self):
        """Статистика по группам"""
        response = requests.get(f"{API_BASE}/groups/stats", headers=self.headers())
        response.raise_for_status()
        return response.json()

    def get_auto_status(self):
        """Статус автоматического режима"""
        response = requests.get(f"{API_BASE}/auto/status", headers=self.headers())
        response.raise_for_status()
        return response.json()

    def leave_group(self, phone: str, group_telegram_id: str):
        """Выйти из группы через Telegram API"""
        # Используем прямой вызов к telegram_client через API
        # Но в API нет прямого эндпоинта для leave, нужно использовать auto_worker
        # Или добавить эндпоинт
        pass

    def generate_report(self, output_file="report.csv"):
        """Генерация отчета"""
        print("\n=== Генерация отчета ===")

        # Получаем все сообщения
        messages = self.get_messages()

        # Собираем данные для отчета
        successful_sends = []
        failed_groups = []

        for msg in messages:
            msg_detail = self.get_message_detail(msg["id"])

            for send in msg_detail.get("sends", []):
                if send["status"] == "sent":
                    successful_sends.append({
                        "message_id": msg["id"],
                        "message_name": msg["name"],
                        "group_title": send["group_title"],
                        "group_link": send["group_link"],
                        "message_link": send["message_link"],
                        "sent_at": send["sent_at"]
                    })
                elif send["status"] == "failed":
                    failed_groups.append({
                        "group_title": send["group_title"],
                        "group_link": send["group_link"],
                        "error": send["error"]
                    })

        # Получаем группы со статусом failed (не смогли войти)
        failed_join_groups = self.get_groups(filter_status="failed")

        # Записываем в CSV
        with open(output_file, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.writer(f)

            # Успешные отправки
            writer.writerow(["=== УСПЕШНЫЕ ОТПРАВКИ ==="])
            writer.writerow(["Название сообщения", "Группа", "Ссылка на группу", "Ссылка на сообщение", "Дата отправки"])
            for item in successful_sends:
                writer.writerow([
                    item["message_name"],
                    item["group_title"],
                    item["group_link"],
                    item["message_link"] or "N/A",
                    item["sent_at"] or "N/A"
                ])

            writer.writerow([])
            writer.writerow([f"Всего успешных отправок: {len(successful_sends)}"])

            # Группы куда не вошли
            writer.writerow([])
            writer.writerow(["=== ГРУППЫ КУДА НЕ ВОШЛИ ==="])
            writer.writerow(["Название", "Ссылка", "Ошибка"])
            for group in failed_join_groups:
                writer.writerow([
                    group.get("title", "N/A"),
                    group["link"],
                    group.get("join_error", "N/A")
                ])

            writer.writerow([])
            writer.writerow([f"Всего групп куда не вошли: {len(failed_join_groups)}"])

            # Группы где не удалось отправить
            writer.writerow([])
            writer.writerow(["=== ГРУППЫ ГДЕ НЕ УДАЛОСЬ ОТПРАВИТЬ ==="])
            writer.writerow(["Название", "Ссылка", "Ошибка"])
            for item in failed_groups:
                writer.writerow([
                    item["group_title"],
                    item["group_link"],
                    item["error"]
                ])

        print(f"[OK] Отчет сохранен: {output_file}")
        print(f"  - Успешных отправок: {len(successful_sends)}")
        print(f"  - Групп куда не вошли: {len(failed_join_groups)}")
        print(f"  - Групп где не удалось отправить: {len(failed_groups)}")

        return output_file

    def show_current_state(self):
        """Показать текущее состояние"""
        print("\n=== ТЕКУЩЕЕ СОСТОЯНИЕ ===")

        # Аккаунты
        accounts = self.get_accounts()
        print(f"\nАккаунты: {len(accounts)}")
        for acc in accounts:
            print(f"  - {acc['phone']} ({acc['first_name']} {acc['last_name']})")
            if not self.phone:
                self.phone = acc['phone']

        # Статистика групп
        stats = self.get_groups_stats()
        print(f"\nГруппы:")
        print(f"  - Всего: {stats['total']}")
        print(f"  - Pending (не вошли): {stats['pending']}")
        print(f"  - Joining (в процессе): {stats['joining']}")
        print(f"  - Joined (вошли): {stats['joined']}")
        print(f"  - Failed (ошибка входа): {stats['failed']}")
        print(f"  - Left (вышли): {stats['left']}")

        # Сообщения
        messages = self.get_messages()
        print(f"\nСообщения: {len(messages)}")
        for msg in messages:
            print(f"  - {msg['name']}: sent={msg['stats']['sent']}, failed={msg['stats']['failed']}, pending={msg['stats']['pending']}")

        # Статус автоматического режима
        auto_status = self.get_auto_status()
        print(f"\nАвтоматический режим:")
        print(f"  - Запущен: {auto_status['is_running']}")
        if auto_status['is_running']:
            status = auto_status['status']
            print(f"  - Режим: {status['mode']}")
            print(f"  - Текущее действие: {status.get('current_action', 'N/A')}")
            print(f"  - Сегодня вступлений: {status['today_joins']}")
            print(f"  - Сегодня отправок: {status['today_sends']}")
            print(f"  - Сегодня выходов: {status['today_leaves']}")


def main():
    manager = PosterBotManager()

    try:
        # Авторизация
        manager.authenticate()

        # Показать текущее состояние
        manager.show_current_state()

        # Генерация отчета
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_file = f"poster_report_{timestamp}.csv"
        manager.generate_report(report_file)

        print(f"\n[OK] Готово! Отчет: {report_file}")

    except Exception as e:
        print(f"\n[ERROR] Ошибка: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
