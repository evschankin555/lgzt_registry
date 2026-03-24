# План создания MAX-бота для `lgzt_registry` (v3 - после ревью)

## Дата
2026-03-24

## Статус
Версия после технического ревью `plans/max_bot_plan_v2.md`.

Эта версия исправляет ключевые риски v2:
- убирает опасную автосклейку аккаунтов только по телефону
- сохраняет текущую бизнес-модель проекта: регистрация только предзагруженных пользователей
- расширяет identity-слой не только на `User`, но и на волонтёров, блокировки и роли
- добавляет обязательное общее persistent state storage
- уточняет, что notification fan-out не должен использоваться по умолчанию
- сохраняет текущий env-контракт проекта (`DATABASE_URL`, `ALEMBIC_DATABASE_URL`)

---

## 1. Цель

Сделать отдельного бота для MAX, который:
- работает параллельно с Telegram-ботом
- использует ту же PostgreSQL базу
- использует ту же бизнес-логику регистрации
- не ломает текущий Telegram production
- не дублирует данные пользователей, волонтёров и админов

Целевая архитектура:
- `Telegram bot`
- `MAX bot`
- `registry-dashboard`
- одна общая БД

---

## 2. Рабочий порядок по фазам

Работа идёт строго по фазам. Следующую фазу начинаем только после завершения артефактов и проверки предыдущей.

### Статус фаз
- `[x]` План согласован
- `[ ]` Фаза 0. Безопасность и technical spike
- `[ ]` Фаза 1. Data foundation
- `[ ]` Фаза 2. Shared services
- `[ ]` Фаза 3. Telegram compatibility migration
- `[ ]` Фаза 4. MAX MVP
- `[ ]` Фаза 5. MAX admin parity
- `[ ]` Фаза 6. Stabilization

### Текущая активная фаза
- `Фаза 0. Безопасность и technical spike`

### Правило перехода между фазами
Переход к следующей фазе разрешён только если:
- собраны артефакты текущей фазы
- выполнены базовые проверки текущей фазы
- нет блокирующих вопросов по архитектуре

---

## 3. Базовые решения, которые считаем утверждёнными

### 2.1. Не заменяем Telegram-бота
MAX-бот внедряется как второй клиент поверх общей доменной логики.

### 2.2. Не разрешаем свободную self-signup регистрацию
Текущий продукт работает так:
- люди сначала загружаются в БД из Excel
- бот не создаёт произвольного нового пользователя
- бот дооформляет уже существующую запись

Это поведение сохраняется и для MAX MVP.

Следствие:
- пункт “если не найдено, создаем нового `User`” из v2 исключается
- создание новых пользователей вне предзагруженного списка возможно только как отдельное продуктовое решение в будущем

### 2.3. Не линковать MAX identity к пользователю только по совпавшему телефону
Телефон используется только как кандидат на совпадение, но не как достаточное основание.

Следствие:
- автологин по одному совпадению `phone_number` запрещён
- нужен дополнительный шаг подтверждения

### 2.4. Roles / identities / volunteers / blocked events должны стать мультиплатформенными
Нельзя переносить только `User.tg_id`, игнорируя:
- `User_volunteer.tg_id`
- `User_who_blocked.tg_id`
- `admin_ids`
- `superadmin_ids`
- `developer_ids`

### 2.5. Persistent state обязателен
MAX нельзя строить поверх текущего in-memory state хранения.

---

## 4. Что есть сейчас в проекте

### Текущие ограничения кода
- пользовательская привязка завязана на `User.tg_id`
- волонтёры завязаны на `User_volunteer.tg_id`
- блокировки завязаны на `User_who_blocked.tg_id`
- роли админов и разработчика захардкожены списками ID в `vars.py`
- состояние диалога хранится в `StateMemoryStorage()`

### Практический вывод
Чтобы MAX и Telegram работали с одной БД без конфликтов, нужно сначала вынести идентичность и состояние в платформенно-независимый слой.

---

## 5. Целевая модель данных

## 4.1. UserIdentity
Связь внутреннего `User.id` с внешним аккаунтом мессенджера.

Пример структуры:

```python
class UserIdentity(Base):
    __tablename__ = "user_identity"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("user.id"), nullable=False)
    provider = Column(String(32), nullable=False)  # telegram, max
    external_user_id = Column(String(128), nullable=False)
    external_chat_id = Column(String(128), nullable=True)

    username = Column(String(255), nullable=True)
    first_name = Column(String(255), nullable=True)
    last_name = Column(String(255), nullable=True)

    created_at = Column(DateTime, nullable=False)
    last_seen_at = Column(DateTime, nullable=True)

    __table_args__ = (
        UniqueConstraint("provider", "external_user_id", name="uq_user_identity_provider_external"),
    )
```

## 4.2. VolunteerIdentity
Связь `User_volunteer.id` с внешним аккаунтом платформы.

```python
class VolunteerIdentity(Base):
    __tablename__ = "volunteer_identity"

    id = Column(Integer, primary_key=True)
    volunteer_id = Column(Integer, ForeignKey("user_volunteer.id"), nullable=False)
    provider = Column(String(32), nullable=False)
    external_user_id = Column(String(128), nullable=False)
    display_name = Column(String(255), nullable=True)
    created_at = Column(DateTime, nullable=False)

    __table_args__ = (
        UniqueConstraint("provider", "external_user_id", name="uq_volunteer_identity_provider_external"),
    )
```

## 4.3. PlatformRole
Хранение ролей не в коде, а в БД.

```python
class PlatformRole(Base):
    __tablename__ = "platform_role"

    id = Column(Integer, primary_key=True)
    provider = Column(String(32), nullable=False)  # telegram, max, any
    external_user_id = Column(String(128), nullable=False)
    role = Column(String(32), nullable=False)      # admin, superadmin, developer
    created_at = Column(DateTime, nullable=False)

    __table_args__ = (
        UniqueConstraint("provider", "external_user_id", "role", name="uq_platform_role"),
    )
```

Примечание:
- если захотим роли, независимые от провайдера, можно добавить `provider='any'`
- на первом этапе допустимо хранить роли и в БД, и параллельно поддерживать старый Telegram fallback

## 4.4. BlockedIdentityEvent

```python
class BlockedIdentityEvent(Base):
    __tablename__ = "blocked_identity_event"

    id = Column(Integer, primary_key=True)
    provider = Column(String(32), nullable=False)
    external_user_id = Column(String(128), nullable=False)
    linked_user_id = Column(Integer, ForeignKey("user.id"), nullable=True)
    blocked_at = Column(DateTime, nullable=False)
```

## 4.5. ConversationState
Общее хранилище состояний диалога.

```python
class ConversationState(Base):
    __tablename__ = "conversation_state"

    id = Column(Integer, primary_key=True)
    provider = Column(String(32), nullable=False)
    external_user_id = Column(String(128), nullable=False)
    external_chat_id = Column(String(128), nullable=True)
    state = Column(String(100), nullable=False)
    payload_json = Column(JSON, nullable=True)
    updated_at = Column(DateTime, nullable=False)

    __table_args__ = (
        UniqueConstraint("provider", "external_user_id", name="uq_conversation_state_provider_external"),
    )
```

---

## 6. Политика склейки аккаунтов

## 5.1. Что запрещено
Запрещено автоматически линковать MAX identity к `User` только по совпадению телефона.

Причины:
- телефон в модели не уникален
- телефон мог смениться
- номер может быть общим / служебным / переиспользованным
- это создаёт риск захвата чужого профиля

## 5.2. Безопасная стратегия matching

### Шаг 1. Проверка identity
- ищем `(provider='max', external_user_id=...)`
- если найдено, пользователь уже привязан

### Шаг 2. Получаем кандидата
Допустимые способы:
- через `request_contact`
- через ввод фамилии + даты рождения

### Шаг 3. Ищем кандидатов в БД

#### По телефону
Телефон даёт только список кандидатов или одного кандидата, но не финальную авторизацию.

#### По фамилии + дате рождения
Работает лучше, потому что текущая бизнес-модель уже построена на этом сценарии.

### Шаг 4. Обязательное подтверждение
Если кандидат найден, линковка выполняется только после подтверждения.

Допустимые safe-варианты:
- SMS на номер, уже записанный у кандидата
- повторный ввод DOB + SMS
- ручное подтверждение через админа

### Рекомендуемый вариант для MVP
Для MAX MVP:
1. пользователь вводит фамилию
2. пользователь вводит дату рождения
3. если запись найдена и статус позволяет, продолжаем текущий flow
4. на этапе телефона отправляем SMS на введённый номер
5. только после успешного SMS подтверждения создаём `UserIdentity(provider='max', ...)`

Это максимально близко к текущей Telegram-модели и не добавляет новый канал захвата профиля.

---

## 7. Что меняем в бизнес-логике, а что сохраняем

## 6.1. Сохраняем
- регистрация по шагам
- проверка фамилии
- проверка даты рождения
- SMS-подтверждение
- выбор предприятия
- профиль пользователя
- работа волонтёров
- админские функции

## 6.2. Меняем
- поиск пользователя по платформе делаем через identity
- роли админов/суперадминов/разработчиков перестают зависеть только от Telegram ID
- request correction перестаёт зависеть от `admin_ids[0]` как единственного канала
- состояние диалога уходит из Telegram memory storage в общую таблицу

## 6.3. Не меняем на MVP
- продуктовую логику набора пользователей из Excel
- SMS-провайдера
- web dashboard как основной административный веб-интерфейс

---

## 8. Сервисный слой

## 7.1. IdentityService
Функции:
- `get_user_by_identity(provider, external_user_id)`
- `link_user_identity(user_id, provider, external_user_id, metadata)`
- `get_volunteer_by_identity(provider, external_user_id)`
- `link_volunteer_identity(volunteer_id, provider, external_user_id, metadata)`
- `touch_identity(provider, external_user_id)`

## 7.2. RegistrationService
Функции:
- старт регистрации
- проверка фамилии
- проверка даты рождения
- проверка волонтёра
- сохранение телефона
- генерация и проверка SMS
- назначение предприятия
- завершение регистрации

Ключевое правило:
- `RegistrationService` не должен знать, пришёл пользователь из Telegram или MAX

## 7.3. RoleService
Функции:
- `is_admin(provider, external_user_id)`
- `is_superadmin(provider, external_user_id)`
- `is_developer(provider, external_user_id)`

## 7.4. ConversationStateService
Функции:
- `get_state(provider, external_user_id)`
- `set_state(provider, external_user_id, state, payload)`
- `clear_state(provider, external_user_id)`
- `touch_state(provider, external_user_id)`

## 7.5. NotificationService
Исправление относительно v2:

### Нельзя делать по умолчанию
- слать любой ответ во все identity пользователя

### Нужно делать
- обычный ответ возвращается только в текущий канал/текущий чат
- fan-out используется только для специальных системных уведомлений

Рекомендуемый интерфейс:
- `reply_current(context, text, file=None)`
- `notify_all_identities(user_id, text, file=None)` для редких системных кейсов
- `notify_admins(text)` через role/identity lookup

## 7.6. CorrectionRequestService
Запросы на исправление данных лучше хранить в БД, а не считать доставку в Telegram единственным способом.

MVP-вариант:
- записываем correction request в таблицу
- dashboard показывает список запросов
- при наличии настроенных админских identity можно ещё дублировать уведомление в Telegram/MAX

---

## 9. Persistent state обязателен

## Почему
Текущий `StateMemoryStorage()` подходит только для одного Telegram-процесса и не переживает рестарт.

Для мультиплатформенности это блокер, потому что:
- MAX будет отдельным сервисом
- после рестарта флоу регистрации не должен исчезать
- нужна одинаковая модель состояний для обеих платформ

## Решение
Внедрить `ConversationState` как обязательный фундамент до MAX MVP.

## Порядок
1. сделать таблицу
2. реализовать сервис
3. перевести Telegram на новое state storage
4. только после этого строить MAX flow

---

## 10. Конфигурация

Используем `pydantic-settings`, но не ломаем текущий контракт env.

### Что должно остаться
- `DATABASE_URL`
- `ALEMBIC_DATABASE_URL`
- текущий `.env` подход для systemd и dashboard

### Что добавится
- `TELEGRAM_BOT_TOKEN`
- `MAX_BOT_TOKEN`
- `MAX_WEBHOOK_SECRET`
- `MAX_WEBHOOK_URL`
- при необходимости `MAX_API_BASE_URL`

### Чего не делаем
- не переводим проект на `DB_HOST/DB_PORT/...`, если это не нужно отдельно

---

## 11. MAX transport layer

## 10.1. Базовый вариант внедрения
На первом этапе MAX webhook встраивается в уже существующий `registry-dashboard` backend.

Внешний маршрут:
- `/registry-api/max/*`

Внутренний FastAPI маршрут:
- `/api/max/*`

Почему:
- уже есть рабочий FastAPI backend
- уже есть домен и nginx-контур
- быстрее поднять webhook и собрать реальные payload samples
- меньше инфраструктурных изменений на ранних фазах

Отдельный сервис для MAX допустим позже, если:
- появится отдельная фоновая обработка
- понадобится отдельный lifecycle и scaling
- нагрузка на webhook контур вырастет

## 10.2. Реализация

### В существующем backend
FastAPI endpoints:
- `GET /api/max/health`
- `POST /api/max/webhook`

### MAX client module
Методы:
- `send_message`
- `edit_message`
- `answer_callback`
- `send_file`
- `set_webhook`
- `delete_webhook`
- `get_updates` для dev-режима

### Безопасность webhook
Приоритет:
1. проверка официально поддерживаемого secret/header, если MAX это даёт
2. fallback: secret в path только если официального механизма нет

### Обязательное требование
На dev-этапе логировать сырые входящие payload, особенно для:
- `bot_started`
- `message_created`
- `message_callback`
- `request_contact`

---

## 12. Telegram migration strategy

## 11.1. Facade подход остаётся правильным
Не переписывать весь старый бот сразу.

## 11.2. Но scope facade должен быть шире, чем в v2
Недостаточно заменить только `find_user_by_tg_id`.

Нужно поэтапно переводить:
- `find_user_by_tg_id`
- `register_user`
- `record_block`
- `is_volunteer`
- `add_volunteer`
- `update_volunteer_tg_name`
- lookup ролей админа

## 11.3. Legacy поля остаются временно
Не удалять сразу:
- `User.tg_id`
- `User_volunteer.tg_id`
- `User_who_blocked.tg_id`

Но новая логика должна постепенно перестать от них зависеть.

---

## 13. Фазы реализации

## Фаза 0. Безопасность и design spike
1. перевыпустить MAX токен
2. завести `MAX_WEBHOOK_SECRET`
3. поднять минимальный dev webhook endpoint
4. получить реальные payload samples от MAX
5. зафиксировать findings по `request_contact`, callback и file sending

Результат:
- снимаем риски предположений о MAX API до основной разработки

## Фаза 1. Data foundation
1. создать `user_identity`
2. создать `volunteer_identity`
3. создать `platform_role`
4. создать `blocked_identity_event`
5. создать `conversation_state`
6. сделать backfill для Telegram user identities
7. сделать backfill для volunteer identities
8. перенести роли админов/разработчиков в БД или подготовить dual-read

Результат:
- база готова к мультиплатформенности

## Фаза 2. Shared services
1. реализовать `IdentityService`
2. реализовать `RoleService`
3. реализовать `ConversationStateService`
4. реализовать `RegistrationService`
5. реализовать `CorrectionRequestService`
6. подготовить `NotificationService` с `reply_current()`

Результат:
- доменная логика отвязана от конкретного мессенджера

## Фаза 3. Telegram compatibility migration
1. перевести `find_user_by_tg_id` на `IdentityService`
2. перевести volunteer lookup
3. перевести role lookup
4. перевести block events
5. перевести state flow на `ConversationState`
6. прогнать регрессию Telegram-бота

Результат:
- текущий бот продолжает работать, но уже сидит на новой архитектуре

## Фаза 4. MAX MVP
1. расширить existing backend routes и обработку MAX update
2. реализовать `MaxClient`
3. реализовать старт и routing
4. реализовать registration flow
5. реализовать SMS подтверждение
6. реализовать выбор предприятия
7. реализовать профиль
8. реализовать базовый admin menu

Результат:
- MAX пользователь может пройти основной сценарий

## Фаза 5. MAX admin parity
1. пользователи
2. предприятия
3. волонтёры
4. correction requests
5. Excel
6. role-aware notifications

## Фаза 6. Stabilization
1. журналирование
2. rate limiting
3. retry/backoff
4. health checks
5. dashboard updates for identities
6. cleanup legacy dependencies

---

## 14. Артефакты и проверки по фазам

## Фаза 0. Безопасность и technical spike

### Артефакты
- `registry_dashboard/backend/main.py` MAX endpoints
- `registry_dashboard/backend/config.py` MAX config
- nginx/service deployment updates для env и public prefix
- env placeholders для MAX
- папка для фиксации payload samples

### Что считаем готовым
- есть минимальный webhook endpoint
- endpoint валидирует secret
- endpoint логирует raw payload
- локальный импорт и запуск каркаса проходят без ошибок

### Проверки
- импорт `registry_dashboard/backend/main.py` проходит
- health endpoint отвечает
- POST на webhook без секрета отклоняется
- POST на webhook с секретом принимается

## Фаза 1. Data foundation

### Артефакты
- Alembic migration для identity/state/roles
- backfill script для Telegram identities
- backfill script для volunteer identities

### Что считаем готовым
- новые таблицы созданы
- существующие Telegram данные мигрированы
- rollback сценарий понятен

### Проверки
- уникальность identity работает
- существующие Telegram пользователи находятся через new identity lookup
- старая функциональность не ломается

## Фаза 2. Shared services

### Артефакты
- `IdentityService`
- `RoleService`
- `ConversationStateService`
- `RegistrationService`
- `CorrectionRequestService`
- `NotificationService`

### Что считаем готовым
- доменная логика больше не зависит от Telegram/MAX транспорта
- сервисы покрывают основной registration flow

### Проверки
- сервисы можно вызвать из изолированных unit/integration сценариев
- state flow сохраняется и восстанавливается

## Фаза 3. Telegram compatibility migration

### Артефакты
- facade/adapter слой для старых функций
- перевод Telegram-бота на identity/state services

### Что считаем готовым
- Telegram продолжает работать на новой архитектуре
- legacy поля ещё есть, но не являются единственным источником истины

### Проверки
- `/start`
- регистрация
- профиль
- волонтёры
- админ-меню
- correction request

## Фаза 4. MAX MVP

### Артефакты
- `MaxClient`
- routing updates
- registration flow
- profile flow
- basic admin menu

### Что считаем готовым
- MAX пользователь проходит основной сценарий без дублей в БД

### Проверки
- webhook update принимается
- user flow проходит до конца
- создаётся `UserIdentity(provider='max', ...)`

## Фаза 5. MAX admin parity

### Артефакты
- users
- companies
- volunteers
- correction requests
- excel/file sending

### Что считаем готовым
- ключевые административные функции доступны из MAX

### Проверки
- списки, карточки, действия и выгрузка работают

## Фаза 6. Stabilization

### Артефакты
- logging
- retry/backoff
- rate limiting
- health checks
- dashboard updates

### Что считаем готовым
- система устойчива к рестартам и рабочей нагрузке

### Проверки
- сервисы поднимаются
- health-check проходит
- ошибок по webhook/retry/rate-limit нет

---

## 15. Что входит в MAX MVP

### Входит
- старт
- регистрация через предзагруженного пользователя
- SMS подтверждение
- NDA
- выбор предприятия
- профиль
- базовое определение ролей
- базовое меню админа

### Не входит автоматически
- создание нового `User`, если в базе никто не найден
- полная fan-out доставка во все каналы
- удаление legacy Telegram полей

---

## 16. Риски и меры снижения

### Риск 1. Захват чужого профиля по телефону
Mitigation:
- не автолинковать по телефону
- обязательный confirmation step

### Риск 2. MAX payload по контакту отличается от ожиданий
Mitigation:
- design spike до реализации MVP
- логирование raw payload

### Риск 3. Сломаем Telegram при миграции
Mitigation:
- facade strategy
- dual-read / dual-write на переходном этапе
- отдельная regression-проверка Telegram после Фазы 3

### Риск 4. State flow потеряется при рестарте
Mitigation:
- persistent `ConversationState` до запуска MAX

### Риск 5. Роли останутся только Telegram-specific
Mitigation:
- вынос ролей в `platform_role`

### Риск 6. Correction requests потеряются между платформами
Mitigation:
- хранить запросы в БД
- канал уведомления считать вторичным, не основным

---

## 17. Критерии готовности

## Data layer готов
Если:
- identity tables созданы
- Telegram identities заполнены
- volunteer identities заполнены
- conversation state работает

## Telegram migration готов
Если:
- `/start` работает
- регистрация работает
- волонтёры работают
- админ-меню работает
- блокировки и correction request не сломаны

## MAX MVP готов
Если:
- пользователь из MAX проходит полный основной flow
- создаётся `UserIdentity(provider='max', ...)`
- обновляется тот же `User`, а не дубль
- профиль отображается
- базовое админ-меню работает

## Full dual-platform ready
Если:
- Telegram и MAX одновременно работают с одной БД
- dashboard корректно показывает пользователей независимо от платформы
- роли и волонтёры не привязаны жёстко к Telegram

---

## 18. Примерная оценка

### Фаза 0
0.5 дня

### Фаза 1
1-1.5 дня

### Фаза 2
1-2 дня

### Фаза 3
1 день

### Фаза 4
1.5-3 дня

### Фаза 5
1-2 дня

### Фаза 6
0.5-1 день

### Итого
Реалистично `5.5-11` рабочих дней.

---

## 19. Рекомендуемый следующий шаг

Следующим практическим шагом после согласования этого плана нужно делать не код всей системы, а короткий technical spike:

1. перевыпустить токен
2. поднять минимальный MAX webhook
3. принять реальные updates
4. зафиксировать payload samples
5. подтвердить модель `request_contact`
6. подтвердить отправку Excel/file

После этого можно переходить к Фазе 1 без риска проектировать вслепую.
