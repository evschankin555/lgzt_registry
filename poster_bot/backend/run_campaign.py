"""
Полный скрипт управления рассылкой:
1. Выход из групп где успешно отправили
2. Вступление в новые группы
3. Отправка сообщений
4. Генерация CSV отчета
"""
import requests
import csv
import time
import sys
from datetime import datetime

API_BASE = "https://lgzt.developing-site.ru/api"
PASSWORD = "admin2026" + chr(36) + "rassilka"

# Лимит времени - 21:00 МСК (UTC+3)
DEADLINE_HOUR = 21


class PosterBot:
    def __init__(self):
        self.token = None
        self.phone = None

    def auth(self):
        r = requests.post(f"{API_BASE}/login", json={"password": PASSWORD})
        r.raise_for_status()
        self.token = r.json()["access_token"]

    def h(self):
        return {"Authorization": f"Bearer {self.token}"}

    def get(self, path):
        r = requests.get(f"{API_BASE}{path}", headers=self.h())
        r.raise_for_status()
        return r.json()

    def post(self, path, data=None, json_data=None):
        r = requests.post(f"{API_BASE}{path}", data=data, json=json_data, headers=self.h())
        r.raise_for_status()
        return r.json()

    def init(self):
        self.auth()
        accounts = self.get("/telegram/accounts")
        self.phone = accounts[0]["phone"]
        print(f"[OK] Auth: {self.phone}")
        return self


def step1_leave_groups(bot):
    """Шаг 1: Выход из групп где успешно отправили"""
    print("\n" + "="*50)
    print("ШАГ 1: ВЫХОД ИЗ ГРУПП")
    print("="*50)

    groups = bot.get("/groups?filter=joined")
    to_leave = [g for g in groups if g.get("can_leave")]
    print(f"Joined групп: {len(groups)}")
    print(f"Для выхода (can_leave): {len(to_leave)}")

    if not to_leave:
        print("Нет групп для выхода")
        return 0

    total_left = 0
    batch_size = 30

    for i in range(0, len(to_leave), batch_size):
        batch = to_leave[i:i+batch_size]
        ids = ",".join(str(g["id"]) for g in batch)

        print(f"\nВыходим из {i+1}-{min(i+batch_size, len(to_leave))} / {len(to_leave)}...")

        try:
            result = bot.post("/groups/leave-batch", data={
                "phone": bot.phone,
                "group_ids": ids
            })
            total_left += result["success_count"]
            print(f"  OK: {result['success_count']}, Errors: {result['fail_count']}")
        except Exception as e:
            print(f"  ERROR: {e}")

        # Пауза между батчами
        if i + batch_size < len(to_leave):
            print("  Пауза 5 сек...")
            time.sleep(5)

    print(f"\nВсего вышли из {total_left} групп")
    return total_left


def step2_join_and_send(bot):
    """Шаг 2: Вступление в новые группы и отправка"""
    print("\n" + "="*50)
    print("ШАГ 2: ВСТУПЛЕНИЕ И ОТПРАВКА")
    print("="*50)

    # Получаем активное сообщение
    messages = bot.get("/messages")
    if not messages:
        print("Нет сообщений для рассылки!")
        return 0, 0

    active_msg = messages[0]  # Берем последнее сообщение
    msg_id = active_msg["id"]
    print(f"Активное сообщение: {active_msg['name']} (ID: {msg_id})")

    # Получаем все группы для этого сообщения
    all_groups = bot.get(f"/messages/{msg_id}/all-groups")

    # Группы pending (не вошли) и included
    pending_groups = [g for g in all_groups if g["group_status"] == "pending" and g.get("included", True)]
    # Группы joined но не отправлено
    joined_not_sent = [g for g in all_groups
                       if g["group_status"] == "joined"
                       and g.get("send_status") in [None, "pending", "waiting"]
                       and g.get("included", True)]

    print(f"Pending групп (не вошли): {len(pending_groups)}")
    print(f"Joined но не отправлено: {len(joined_not_sent)}")

    joined_count = 0
    sent_count = 0

    # Сначала отправляем в уже joined группы
    if joined_not_sent:
        print(f"\nОтправляем в {len(joined_not_sent)} уже joined групп...")
        group_ids = ",".join(str(g["id"]) for g in joined_not_sent)

        try:
            result = bot.post(f"/messages/{msg_id}/send", data={
                "phone": bot.phone,
                "group_ids": group_ids,
                "delay_seconds": 5
            })
            sent_count += result.get("success_count", 0)
            print(f"  Отправлено: {result.get('success_count', 0)}, Ошибок: {result.get('fail_count', 0)}")
        except Exception as e:
            print(f"  ERROR: {e}")

    # Теперь вступаем в pending группы и отправляем
    if pending_groups:
        print(f"\nВступаем в {len(pending_groups)} новых групп и отправляем...")

        # Запускаем join worker
        try:
            result = bot.post("/groups/start-joining", json_data={
                "phone": bot.phone,
                "limit": min(len(pending_groups), 50),
                "delay_min": 15,
                "delay_max": 25
            })
            print(f"Join worker запущен: {result}")
        except Exception as e:
            print(f"  ERROR запуска join worker: {e}")
            return joined_count, sent_count

        # Мониторим прогресс и отправляем по мере вступления
        last_check_joined = 0
        while True:
            # Проверяем время
            now_hour = (datetime.utcnow().hour + 3) % 24  # МСК
            now_min = datetime.utcnow().minute
            if now_hour >= DEADLINE_HOUR:
                print(f"\n[STOP] Достигнут дедлайн {DEADLINE_HOUR}:00 МСК")
                # Останавливаем join worker
                try:
                    bot.post("/groups/stop-joining")
                except:
                    pass
                break

            # Проверяем статус join worker
            try:
                status = bot.get("/groups/joining-status")
            except:
                time.sleep(10)
                continue

            is_running = status.get("is_running", False)
            stats = status.get("stats", {})
            joined_session = stats.get("joined_this_session", 0)

            print(f"\r  Join: {joined_session} joined, pending: {stats.get('pending', 0)}, "
                  f"current: {stats.get('current_group', 'N/A')}, "
                  f"next in: {stats.get('next_attempt_in', 0)}s", end="", flush=True)

            # Если есть новые joined группы - отправляем
            if joined_session > last_check_joined:
                last_check_joined = joined_session
                joined_count += (joined_session - last_check_joined + (joined_session - last_check_joined))

                # Получаем свежий список joined но не отправленных
                all_groups_fresh = bot.get(f"/messages/{msg_id}/all-groups")
                new_joined = [g for g in all_groups_fresh
                              if g["group_status"] == "joined"
                              and g.get("send_status") in [None, "pending", "waiting"]
                              and g.get("included", True)]

                if new_joined:
                    print(f"\n  Отправляем в {len(new_joined)} новых групп...")
                    group_ids = ",".join(str(g["id"]) for g in new_joined[:10])  # По 10 за раз

                    try:
                        result = bot.post(f"/messages/{msg_id}/send", data={
                            "phone": bot.phone,
                            "group_ids": group_ids,
                            "delay_seconds": 5
                        })
                        sent_count += result.get("success_count", 0)
                        print(f"  Отправлено: {result.get('success_count', 0)}")
                    except Exception as e:
                        print(f"  ERROR отправки: {e}")

            if not is_running:
                print(f"\n  Join worker остановлен")
                break

            time.sleep(15)

        # Финальная отправка в оставшиеся joined группы
        all_groups_final = bot.get(f"/messages/{msg_id}/all-groups")
        remaining = [g for g in all_groups_final
                     if g["group_status"] == "joined"
                     and g.get("send_status") in [None, "pending", "waiting"]
                     and g.get("included", True)]

        if remaining:
            print(f"\nФинальная отправка в {len(remaining)} групп...")
            group_ids = ",".join(str(g["id"]) for g in remaining)

            try:
                result = bot.post(f"/messages/{msg_id}/send", data={
                    "phone": bot.phone,
                    "group_ids": group_ids,
                    "delay_seconds": 5
                })
                sent_count += result.get("success_count", 0)
                print(f"  Отправлено: {result.get('success_count', 0)}")
            except Exception as e:
                print(f"  ERROR: {e}")

    print(f"\nИтого: вступили в {joined_count}, отправили в {sent_count}")
    return joined_count, sent_count


def step3_report(bot, left_count, joined_count, sent_count):
    """Шаг 3: Генерация CSV отчета"""
    print("\n" + "="*50)
    print("ШАГ 3: ГЕНЕРАЦИЯ ОТЧЕТА")
    print("="*50)

    # Получаем все данные
    messages = bot.get("/messages")
    all_groups = bot.get("/groups")
    groups_stats = bot.get("/groups/stats")

    # Собираем данные по отправкам
    successful_sends = []
    failed_sends = []

    for msg in messages:
        msg_detail = bot.get(f"/messages/{msg['id']}")
        for send in msg_detail.get("sends", []):
            entry = {
                "message_name": msg["name"],
                "group_title": send.get("group_title", "N/A"),
                "group_link": send.get("group_link", "N/A"),
                "message_link": send.get("message_link", ""),
                "sent_at": send.get("sent_at", ""),
                "status": send.get("status", ""),
                "error": send.get("error", "")
            }
            if send["status"] == "sent":
                successful_sends.append(entry)
            elif send["status"] == "failed":
                failed_sends.append(entry)

    # Группы куда не вошли
    failed_groups = [g for g in all_groups if g["status"] == "failed"]
    pending_groups = [g for g in all_groups if g["status"] == "pending"]

    # Записываем CSV
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"poster_report_{timestamp}.csv"

    with open(filename, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f, delimiter=";")

        # Сводка
        writer.writerow(["СВОДКА"])
        writer.writerow(["Дата отчета", datetime.now().strftime("%d.%m.%Y %H:%M")])
        writer.writerow(["Всего групп", groups_stats["total"]])
        writer.writerow(["Вошли (joined)", groups_stats["joined"]])
        writer.writerow(["Вышли (left)", groups_stats["left"]])
        writer.writerow(["Не вошли (failed)", groups_stats["failed"]])
        writer.writerow(["Ожидают (pending)", groups_stats["pending"]])
        writer.writerow(["Успешных отправок", len(successful_sends)])
        writer.writerow(["Неудачных отправок", len(failed_sends)])
        writer.writerow(["Вышли за сессию", left_count])
        writer.writerow(["Вступили за сессию", joined_count])
        writer.writerow(["Отправили за сессию", sent_count])
        writer.writerow([])

        # Успешные отправки
        writer.writerow(["УСПЕШНЫЕ ОТПРАВКИ"])
        writer.writerow(["Сообщение", "Группа", "Ссылка на группу", "Ссылка на сообщение", "Дата отправки"])
        for item in successful_sends:
            writer.writerow([
                item["message_name"],
                item["group_title"],
                item["group_link"],
                item["message_link"] or "",
                item["sent_at"] or ""
            ])
        writer.writerow([])

        # Неудачные отправки
        writer.writerow(["НЕУДАЧНЫЕ ОТПРАВКИ"])
        writer.writerow(["Сообщение", "Группа", "Ссылка на группу", "Ошибка"])
        for item in failed_sends:
            writer.writerow([
                item["message_name"],
                item["group_title"],
                item["group_link"],
                item["error"]
            ])
        writer.writerow([])

        # Группы куда не вошли (failed)
        writer.writerow(["ГРУППЫ КУДА НЕ ВОШЛИ (ОШИБКА)"])
        writer.writerow(["Ссылка", "Город", "Адрес", "Ошибка", "Попыток"])
        for g in failed_groups:
            writer.writerow([
                g["link"],
                g.get("city", ""),
                g.get("address", ""),
                g.get("join_error", ""),
                g.get("join_attempts", 0)
            ])
        writer.writerow([])

        # Группы pending (ещё не пробовали)
        writer.writerow(["ГРУППЫ В ОЧЕРЕДИ (PENDING)"])
        writer.writerow(["Ссылка", "Город", "Адрес"])
        for g in pending_groups:
            writer.writerow([
                g["link"],
                g.get("city", ""),
                g.get("address", "")
            ])

    print(f"Отчет сохранен: {filename}")
    print(f"  Успешных отправок: {len(successful_sends)}")
    print(f"  Неудачных отправок: {len(failed_sends)}")
    print(f"  Групп failed: {len(failed_groups)}")
    print(f"  Групп pending: {len(pending_groups)}")

    return filename


def main():
    bot = PosterBot().init()

    # Шаг 1: Выход из групп
    left_count = step1_leave_groups(bot)

    # Шаг 2: Вступление и отправка
    joined_count, sent_count = step2_join_and_send(bot)

    # Шаг 3: Отчет
    report = step3_report(bot, left_count, joined_count, sent_count)

    print("\n" + "="*50)
    print("ГОТОВО!")
    print(f"  Вышли из: {left_count} групп")
    print(f"  Вступили в: {joined_count} групп")
    print(f"  Отправили в: {sent_count} групп")
    print(f"  Отчет: {report}")
    print("="*50)


if __name__ == "__main__":
    main()
