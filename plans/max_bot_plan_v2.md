# План создания MAX-бота для `lgzt_registry` (v2 - Улучшенный)

Этот план основан на `plans/max_bot_plan.md` и дополнен результатами исследования API MAX, а также архитектурными улучшениями для безопасной миграции и долгосрочной поддержки.

## Ключевые изменения относительно v1
1.  **Стратегия склейки (Matching Strategy):** Детально прописан алгоритм объединения профилей Telegram и MAX через нормализацию телефона и проверку ФИО+ДР.
2.  **Notification Service:** Абстракция отправки уведомлений, чтобы бизнес-логика не зависела от конкретного мессенджера.
3.  **Refactoring Facade:** Плавная миграция `functions.py` через паттерн Facade, вместо рискованного полного переписывания.
4.  **Configuration:** Использование `pydantic-settings` для строгой типизации конфигов.

---

## 1. Архитектура данных (Identity Layer)

### Проблема
Текущая БД жестко привязана к `tg_id`. Прямое добавление `max_id` в таблицу `User` приведет к дублированию и сложности поддержки.

### Решение: Таблица Identity
Создать промежуточную таблицу для связи внешних идентификаторов с внутренним `User.id`.

#### Новая схема БД (SQLAlchemy)

```python
class UserIdentity(Base):
    __tablename__ = 'user_identity'
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('user.id'), nullable=False)
    provider = Column(String(50), nullable=False)  # 'telegram', 'max'
    external_id = Column(String(100), nullable=False) # tg_id или user_id из MAX
    
    # Метаданные для удобства (не для логики)
    username = Column(String(255), nullable=True)
    first_name = Column(String(255), nullable=True)
    last_name = Column(String(255), nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    last_seen_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint('provider', 'external_id', name='uq_provider_external_id'),
    )
```

**Миграция данных:**
1. Создать таблицу `user_identity`.
2. Написать скрипт, который пройдет по всем `User` с заполненным `tg_id` и создаст для них записи в `user_identity` с `provider='telegram'`.

---

## 2. Сервисный слой (Service Layer)

Вместо монолитного `functions.py` и размазанной логики в ботах, вводим сервисы.

### 2.1. IdentityService
Отвечает за распознавание пользователя.

*   `get_user_by_identity(provider, external_id) -> User | None`
*   `link_identity(user_id, provider, external_id, metadata)`
*   `update_last_seen(provider, external_id)`

### 2.2. AuthService & Matching Strategy (Алгоритм склейки)
Как понять, что пользователь MAX — это тот же `User`, что и в Telegram?

**Алгоритм при входе через MAX:**
1.  **Поиск по Identity:** Проверяем, есть ли уже запись в `user_identity` для `(provider='max', external_id=...)`.
    *   *Есть:* Авторизуем пользователя.
    *   *Нет:* Запускаем сценарий регистрации/входа.
2.  **Запрос телефона:** Просим пользователя нажать "Поделиться контактом" (MAX `request_contact` button).
3.  **Поиск по телефону:**
    *   Нормализуем полученный телефон (удаляем `+`, `(`, `)`, `-`, пробелы; приводим `8` к `7` в начале).
    *   Ищем в таблице `User` по `phone_number` (тоже нормализованному).
    *   *Найдено:* Создаем новую запись в `user_identity` (связываем MAX-аккаунт с найденным `User`). **Пользователь залогинен.**
4.  **Поиск по ФИО + ДР (Fallback):** Если телефона нет или он изменился.
    *   Просим ввести Фамилию и Дату Рождения.
    *   Ищем в `User` (у нас есть уникальный констрейнт `last_name` + `date_of_birth`).
    *   *Найдено:* Предлагаем подтвердить (например, через SMS на старый номер или просто связываем, если политика безопасности позволяет).
5.  **Регистрация:** Если ничего не найдено — создаем нового `User` и `Identity`.

### 2.3. NotificationService
Абстрагирует отправку сообщений. Бизнес-логика не должна знать про Telegram или MAX.

*   `send_to_user(user_id: int, text: str, file: IO = None)`
    *   Получает все `identities` для `user_id`.
    *   Для каждого identity вызывает соответствующий адаптер (`TelegramAdapter.send`, `MaxAdapter.send`).
*   `send_to_admins(text: str)`
    *   Читает список админов (теперь это роли, привязанные к `User`, а не хардкод ID).
    *   Рассылает всем.

---

## 3. План рефакторинга `functions.py` (Facade Pattern)

Не нужно переписывать `functions.py` сразу. Это опасно.

**Этап 1: Внедрение Identity**
1.  Создать `IdentityService`.
2.  В `functions.py` переписать `find_user_by_tg_id`:
    ```python
    # functions.py
    async def find_user_by_tg_id(tg_id):
        # Старая логика: return session.query(User).filter(User.tg_id == tg_id).first().id
        # Новая логика (Facade):
        user = await identity_service.get_user_by_identity('telegram', tg_id)
        return user.id if user else None
    ```
3.  Остальной код бота продолжает использовать `find_user_by_tg_id`, не зная, что под капотом уже работает новая таблица.

**Этап 2: Вынос бизнес-логики**
Постепенно переносить функции регистрации и проверки данных из `functions.py` в `RegistrationService`, оставляя в `functions.py` только прокси-вызовы для совместимости со старым ботом, пока он не будет переведен на новые рельсы.

---

## 4. Конфигурация (Pydantic)

Использовать `pydantic-settings` для валидации переменных окружения.

```python
class Settings(BaseSettings):
    DB_HOST: str
    DB_PORT: int
    ...
    TELEGRAM_BOT_TOKEN: str
    MAX_BOT_TOKEN: str
    MAX_WEBHOOK_SECRET: str  # Для валидации входящих запросов
    MAX_WEBHOOK_URL: HttpUrl

    class Config:
        env_file = ".env"
```

---

## 5. Специфика MAX API (из исследования)

*   **Webhook Security:** MAX поддерживает HTTPS и самоподписанные сертификаты. Для защиты вебхука от подделки (если нет встроенной проверки подписи), рекомендуется использовать **Secret Token** в URL вебхука (например, `/max-bot/webhook/{SECRET_TOKEN}`) или проверять кастомный заголовок, если MAX позволяет его настроить при установке вебхука.
*   **Contact Button:** Кнопка `request_contact` возвращает объект контакта. Важно логировать сырой ответ на этапе dev-тестирования, чтобы корректно парсить телефон (форматы могут отличаться от Telegram).
*   **Файлы:** MAX поддерживает отправку файлов. Для Excel-отчетов нужно проверить лимиты на размер файла.
*   **RPS:** Лимит 30 RPS. Нужно внедрить очередь сообщений (или просто `asyncio.sleep` при массовых рассылках), чтобы не получить бан.

---

## 6. Детальный план работ (Step-by-Step)

### Фаза 1: Фундамент (БД и Сервисы)
1.  **Config:** Внедрить `pydantic-settings`.
2.  **Migration:** Создать таблицу `user_identity`.
3.  **Migration Script:** Наполнить `user_identity` данными из `User.tg_id`.
4.  **IdentityService:** Реализовать логику поиска/создания identity.
5.  **Refactor:** Обновить `functions.py` для использования `IdentityService` (сохраняя обратную совместимость).

### Фаза 2: MAX-бот (MVP)
1.  **Server:** Поднять FastAPI (или aiohttp) сервер для вебхука MAX.
2.  **Adapter:** Реализовать `MaxAdapter` (получение update -> преобразование в доменную команду).
3.  **Auth Flow:** Реализовать сценарий "Привет -> Дай контакт -> Поиск в БД -> Авторизация/Регистрация".
4.  **Menu:** Реализовать базовое меню (Профиль, Статус).

### Фаза 3: Интеграция и Бизнес-функции
1.  **NotificationService:** Реализовать отправку уведомлений.
2.  **Admin:** Адаптировать админские функции для MAX (используя `UserIdentity` для проверки прав).
3.  **Excel:** Протестировать отправку отчетов в MAX.

### Фаза 4: Чистка (Cleanup)
1.  Перевести Telegram-бота на прямую работу с сервисами (минуя старые функции `functions.py`, если возможно).
2.  Пометить поля `tg_id` в таблице `User` как deprecated (но не удалять сразу).

---

## Риски и Mitigation

1.  **Разные форматы телефонов:**
    *   *Mitigation:* Написать unit-тесты для нормализатора телефонов, покрывающие разные кейсы (+7, 8, 7, без плюса, с пробелами).
2.  **Дубликаты пользователей:**
    *   *Mitigation:* Жесткий UniqueConstraint на `(provider, external_id)` и логика поиска сначала по телефону, потом по ФИО+ДР.
3.  **Безопасность Вебхука:**
    *   *Mitigation:* Использовать `Secret Token` в URL пути вебхука, если заголовок `X-Max-Bot-Api-Secret` не поддерживается платформой явно.

Этот план минимизирует вмешательство в работающий Telegram-бот и создает надежную основу для мульти-платформенности.
