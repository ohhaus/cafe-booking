# Проект бронирования столов в кафе

Сервис управления бронированием мест в кафе, просмотр меню и действующих акций.

## Основной функционал

- Управление пользователями (создание, редактирование, блокировка и разблокировка)
- Авторизация пользователей
- Бронирование столов в кафе с выбором даты и времени
- Предоставление информации о действующих акциях
- Предоставление информации о доступных блюдах
- Управление бронированием
- Напоминание о бронировании
- Уведомление администратора о бронировании и изменении бронирования

## Технологический стек

<details>
<summary>Показать технологический стек</summary>

```md
### Основные технологии
**Язык и платформа**
- Python `3.12`

**API (веб-сервис)**
- FastAPI `0.124.2`
- Starlette `0.50.0`
- Uvicorn `0.38.0`

**Данные и хранение**
- PostgreSQL `17`
- SQLAlchemy `2.0.45`
- Alembic `1.17.2`
- asyncpg `0.31.0`

**Валидация и конфигурация**
- Pydantic `2.12.5`
- pydantic-settings `2.12.0`
- pydantic-extra-types `2.10.6`
- email-validator `2.3.0`
- phonenumbers `9.0.20`

**Фоновые задачи**
- Celery `5.6.0`
- Redis (broker/backend) `7.1.0`
- Flower `2.0.1`
- kombu `5.6.1`, amqp `5.3.1`

**HTTP и аутентификация**
- HTTPX `0.28.1`
- PyJWT `2.8.0`

**Тестирование**
- pytest `9.0.2`
- pytest-asyncio `1.3.0`

**Качество кода**
- ruff `0.14.8`
- pre-commit `4.5.0`

***Безопасность и криптография***
- cryptography `46.0.3`
```
</details>

## Quickstart (Docker)

> Требования: установлен Docker и Docker Compose.

```bash
# 1) Склонировать репозиторий
git clone git@github.com:ohhaus/cafe-booking.git
cd cafe-booking

# 2) Создать .env
cp .env.example .env

# 3) Собрать и запустить контейнеры
docker compose -f infra/docker-compose.yml up -d --build

# 4) Применить миграции
docker compose -f infra/docker-compose.yml exec app alembic upgrade head
```

### Проверка
- API: http://localhost:8000
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## Установка и запуск проекта

- Основной способ запуска — через Docker Compose (инфраструктура и приложение).
- Локальная установка (venv) может быть полезна для разработки/линтинга/тестов.

### Клонирование удаленного репозитория на локальную машину

```bash
git clone git@github.com:ohhaus/cafe-booking.git
```

### Активация виртуального окружения

```bash
# Создание и активация виртуального окружения

# Windows:
python -m venv venv
. venv/Scripts/activate

# Linux и macOS:
python3 -m venv venv
source venv/bin/activate
```

### Установка зависимостей

```bash
# Обновить пакетный менеджер:

# Для Windows:
python -m pip install --upgrade pip

# Для Linux и macOS:
python3 -m pip install --upgrade pip

# Установить зависимости
pip install -r src/requirements.txt
```

### Конфигурация окружения

```env
# Создайте файл .env на основе примера:

cp .env.example .env

# ==================================================
# DATABASE
# ==================================================
DATABASE_URL=postgresql+asyncpg://postgres:postgres@postgres:5432/postgres
DATABASE_POOL_TIMEOUT=30
DATABASE_POOL_RECYCLE=1800
DATABASE_POOL_SIZE=20
DATABASE_MAX_OVERFLOW=30
DATABASE_POOL_PING=true
DATABASE_ECHO_SQL=false
DATABASE_USER=postgres
DATABASE_PASSWORD=postgres
DATABASE_PORT=5432
DATABASE_HOST=postgres

# ==================================================
# REDIS
# ==================================================
REDIS_URL=redis://redis:6379/0
REDIS_PASSWORD=password
REDIS_SOCKET_CONNECTION_TIMEOUT=5
REDIS_SOCKET_TIMEOUT=5
REDIS_RETRY_ON_TIMEOUT=true
REDIS_MAX_CONNECTIONS=10

# ==================================================
# CELERY
# ==================================================
CELERY_BROKER_DB=1
CELERY_RESULT_DB=2
CELERY_TIMEZONE=Europe/Moscow
CELERY_ENABLE_UTC=true
CELERY_TASK_SERIALIZER=json
CELERY_RESULT_SERIALIZER=json
CELERY_ACCEPT_CONTENT=["json"]
CELERY_TASK_IGNORE_RESULT=false
CELERY_TASK_TRACK_STARTED=true
CELERY_BROKER_CONNECTION_RETRY_ON_STARTUP=true
CELERY_TASK_TIME_LIMIT=300
CELERY_TASK_SOFT_TIME_LIMIT=240

# ==================================================
# AUTH / JWT
# ==================================================
AUTH_SECRET_KEY=super_ultra_secret_key_min_64_chars_change_me
AUTH_ACCESS_TOKEN_EXPIRE_MINUTES=6000
AUTH_ALGORITHM=HS256

# ==================================================
# CACHE
# ==================================================
CACHE_TTL_CAFES_LIST=600
CACHE_TTL_CAFE_BY_ID=1800
CACHE_TTL_CAFE_ACTIVE=300
CACHE_TTL_DISHES_LIST=900
CACHE_TTL_DISH_BY_ID=1800
CACHE_TTL_ACTIONS_LIST=300
CACHE_TTL_ACTION_BY_ID=900
CACHE_TTL_CAFE_TABLES=120
CACHE_TTL_CAFE_TABLE=300
CACHE_TTL_CAFE_TABLE_ACTIVE=300
CACHE_TTL_CAFE_SLOTS=120
CACHE_TTL_CAFE_SLOT=300
CACHE_TTL_CAFE_SLOT_ACTIVE=300
CACHE_TTL_MEDIA=3600
CACHE_TTL_MANAGER_CUD_CAFE=120
CACHE_TTL_CAFE_META=120

# ==================================================
# MAIL
# ==================================================
MAIL_SERVER=smtp.example.com
MAIL_PORT=465
MAIL_SSL=true
MAIL_TLS=false
MAIL_USERNAME=your_email@example.com
MAIL_PASSWORD=your_smtp_password
MAIL_FROM=your_email@example.com
MAIL_FROM_NAME=Cafe Booking
MAIL_USE_CREDENTIALS=true
MAIL_VALIDATE_CREDS=true

# ==================================================
# SUPERUSER
# ==================================================
SUPERUSER_USERNAME=admin
SUPERUSER_EMAIL=admin@example.com
SUPERUSER_PHONE=+79999999999
SUPERUSER_PASSWORD=ChangeMe123!
SUPERUSER_TG_ID=123456789
```

### Запуск проекта

Сервис запускается в контейнерах, миграции выполняются отдельной командой

```bash
# Запуск контейнера из корневой папки проекта:
# Тихий режим (без логов в терминале):
docker compose -f infra/docker-compose.yml up -d --build
# Режим с выводом логов в терминале:
docker compose -f infra/docker-compose.yml up --build
```

### Миграции

Применение миграций (при запущенных контейнерах):

```bash
docker compose -f infra/docker-compose.yml exec app alembic upgrade head
```

Создание новой миграции (если нужно):

```bash
docker compose -f infra/docker-compose.yml exec app alembic revision --autogenerate -m "describe_change"
```

### Полезные команды Docker

```bash
# список контейнеров и их статус
docker compose -f infra/docker-compose.yml ps

# Вывод логов в терминал (для режима -d)
docker compose -f infra/docker-compose.yml logs -f
# Остановить просмотр логов: Ctrl + C
```

## Документация API

После запуска сервиса:
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

Если порт отличается — проверь `infra/docker-compose.yml`.

## Роли и доступы

В проекте используется ролевая модель доступа. Роль пользователя хранится в поле `role`:

| role | Название | Описание прав |
|------|----------|----------------|
| `0`  | Пользователь | Доступ к пользовательским операциям и своим данным (например, свои бронирования), просмотр активных сущностей |
| `1`  | Менеджер | Управление сущностями в рамках доступных кафе (по политике доступа) |
| `2`  | Администратор | Полный доступ к управлению системой (включая пользователей и кафе) |

> Точные ограничения по эндпоинтам см. в таблице “Основные запросы API” и в Swagger/ReDoc.

## Основные запросы API

| Endpoint | Method | Description | Access |
| --------------------------------------- | ----- | ---------------------------------------------------------------------------- | --------------------------- |
| `/auth/login`                           | POST  | Получение токена авторизации (логин + пароль)                                | Гость                       |
| `/users/`                               | POST  | Регистрация нового пользователя                                              | Гость                       |
| `/users/`                               | GET   | Получение списка пользователей                                               | Администратор / Менеджер    |
| `/users/me`                             | GET   | Получение профиля текущего пользователя                                      | Авторизованный пользователь |
| `/users/me`                             | PATCH | Обновление профиля текущего пользователя                                     | Авторизованный пользователь |
| `/users/{user_id}`                      | GET   | Получение пользователя по ID                                                 | Администратор / Менеджер    |
| `/users/{user_id}`                      | PATCH | Обновление пользователя по ID (например, роль)                               | Администратор / Менеджер    |
| `/cafes`                                | POST  | Создание нового кафе                                                         | Администратор               |
| `/cafes`                                | GET   | Получение списка кафе (для staff — все, для пользователей — только активные) | Авторизованный пользователь |
| `/cafes/{cafe_id}`                      | GET   | Получение информации о кафе по ID                                            | Авторизованный пользователь |
| `/cafes/{cafe_id}`                      | PATCH | Обновление кафе (в т.ч. активность и managers_id)                            | Администратор / Менеджер    |
| `/cafes/{cafe_id}/tables`               | GET   | Получение списка столов в кафе                                               | Авторизованный пользователь |
| `/cafes/{cafe_id}/tables`               | POST  | Создание нового стола в кафе                                                 | Администратор / Менеджер    |
| `/cafes/{cafe_id}/tables/{table_id}`    | GET   | Получение информации о столе по ID                                           | Авторизованный пользователь |
| `/cafes/{cafe_id}/tables/{table_id}`    | PATCH | Обновление стола по ID                                                       | Администратор / Менеджер    |
| `/cafes/{cafe_id}/time_slots`           | GET   | Получение списка временных слотов в кафе                                     | Авторизованный пользователь |
| `/cafes/{cafe_id}/time_slots`           | POST  | Создание временного слота в кафе                                             | Администратор / Менеджер    |
| `/cafes/{cafe_id}/time_slots/{slot_id}` | GET   | Получение временного слота по ID                                             | Авторизованный пользователь |
| `/cafes/{cafe_id}/time_slots/{slot_id}` | PATCH | Обновление временного слота по ID                                            | Администратор / Менеджер    |
| `/dishes/`                              | GET   | Получение списка блюд (staff — все, пользователь — активные)                 | Авторизованный пользователь |
| `/dishes/`                              | POST  | Создание нового блюда                                                        | Администратор / Менеджер    |
| `/dishes/{dish_id}`                     | GET   | Получение блюда по ID                                                        | Авторизованный пользователь |
| `/dishes/{dish_id}`                     | PATCH | Обновление блюда по ID                                                       | Администратор / Менеджер    |
| `/booking/`                             | POST  | Создать бронирование                                                         | Авторизованный пользователь |
| `/booking/`                             | GET   | Получение списка бронирований (пользователь — свои, staff — любые)           | Авторизованный пользователь |
| `/booking/{booking_id}`                 | GET   | Получение бронирования по ID                                                 | Авторизованный пользователь |
| `/booking/{booking_id}`                 | PATCH | Частичное обновление бронирования                                            | Авторизованный пользователь |
| `/media/`                               | POST  | Загрузить изображение                                                        | Администратор / Менеджер    |
| `/media/{image_id}`                     | GET   | Скачать изображение по ID (если активно)                                     | Гость                       |

Полный перечень моделей, входных и выходных параметров можно изучить в Swagger UI или ReDoc.

## Особенности API

### Синхронизация менеджеров кафе (`managers_id`)

При создании/обновлении кафе поле `managers_id` работает как **синхронизация списка менеджеров**, а не как “добавить одного”.

- **Семантика `replace` (полная замена):** переданный массив `managers_id` **полностью заменяет** текущий список менеджеров кафе.
  - Если передать только одного менеджера — все остальные будут удалены из связки с кафе.
  - Если передать пустой массив — у кафе станет `0` менеджеров (если это разрешено бизнес-логикой).
- **Атомарность:** обновление связей выполняется целиком (в транзакции): либо применяются все изменения, либо не применяется ничего.
- **Валидации (ожидаемое поведение):**
  - все `managers_id` должны быть валидными UUID;
  - пользователи должны существовать;
  - недопустимы дубли в списке;
  - (если предусмотрено) назначаемые пользователи должны иметь роль `manager`/`admin`.
- **Права доступа:** после синхронизации меняется набор пользователей, которые могут управлять конкретным кафе (и связанными ресурсами) — учитывайте это при интеграции.

## Postman

Коллекция и сценарии лежат в `postman_collection/`:
- `Cafe_booking.postman_collection.json` — коллекция Postman
- `README.md` — инструкция по использованию
- `10 Создание бронирования.md` — сценарий ручной проверки
- `20 Изменение бронирования.md` — сценарий ручной проверки

## Структура проекта

<details>
<summary>Показать дерево проекта</summary>

```text
├── .github
│   └── workflows
│       ├── style_check.yml
│       └── telegram-pr-notify.yml
├── infra
│   └── docker-compose.yml
├── logs
│   └── system
├── postman_collection
│   ├── 10 Создание бронирования.md
│   ├── 20 Изменение бронирования.md
│   ├── Cafe_booking.postman_collection.json
│   └── README.md
├── src
│   ├── actions
│   │   ├── __init__.py
│   │   ├── models.py
│   │   ├── responses.py
│   │   ├── schemas.py
│   │   ├── service.py
│   │   ├── validators.py
│   │   └── views.py
│   ├── auth
│   │   ├── __init__.py
│   │   ├── responses.py
│   │   └── views.py
│   ├── booking
│   │   ├── __init__.py
│   │   ├── constants.py
│   │   ├── crud.py
│   │   ├── dependencies.py
│   │   ├── enums.py
│   │   ├── lookup.py
│   │   ├── models.py
│   │   ├── schemas.py
│   │   ├── services.py
│   │   ├── validators.py
│   │   └── views.py
│   ├── cafes
│   │   ├── __init__.py
│   │   ├── cafe_scoped.py
│   │   ├── cafes_help_caches.py
│   │   ├── crud.py
│   │   ├── models.py
│   │   ├── responses.py
│   │   ├── schemas.py
│   │   ├── service.py
│   │   └── views.py
│   ├── celery
│   │   ├── tasks
│   │   │   ├── __init__.py
│   │   │   ├── admin_events.py
│   │   │   └── daily_reminders.py
│   │   ├── __init__.py
│   │   ├── asyncio_runner.py
│   │   ├── celery_app.py
│   │   ├── service.py
│   │   └── utils.py
│   ├── common
│   │   ├── logging
│   │   │   ├── logs
│   │   │   ├── __init__.py
│   │   │   ├── config.py
│   │   │   ├── decorators.py
│   │   │   ├── filters.py
│   │   │   ├── formatters.py
│   │   │   └── system_logger.py
│   │   ├── __init__.py
│   │   ├── exception_handlers.py
│   │   ├── exceptions.py
│   │   ├── responses.py
│   │   ├── schemas.py
│   │   └── super_user.py
│   ├── database
│   │   ├── revisions
│   │   │   ├── versions
│   │   │   │   └── 9a94f601510a_initial.py
│   │   │   ├── README
│   │   │   ├── env.py
│   │   │   └── script.py.mako
│   │   ├── __init__.py
│   │   ├── associations.py
│   │   ├── base.py
│   │   ├── models_imports.py
│   │   ├── service.py
│   │   └── sessions.py
│   ├── dishes
│   │   ├── __init__.py
│   │   ├── crud.py
│   │   ├── models.py
│   │   ├── router.py
│   │   ├── schemas.py
│   │   ├── services.py
│   │   ├── validators.py
│   │   └── views.py
│   ├── media
│   │   ├── __init__.py
│   │   ├── crud.py
│   │   ├── dependencies.py
│   │   ├── models.py
│   │   ├── responses.py
│   │   ├── schemas.py
│   │   ├── services.py
│   │   ├── validators.py
│   │   └── views.py
│   ├── slots
│   │   ├── __init__.py
│   │   ├── crud.py
│   │   ├── models.py
│   │   ├── responses.py
│   │   ├── schemas.py
│   │   └── views.py
│   ├── tables
│   │   ├── __init__.py
│   │   ├── crud.py
│   │   ├── models.py
│   │   ├── responses.py
│   │   ├── schemas.py
│   │   └── views.py
│   ├── users
│   │   ├── __init__.py
│   │   ├── dependencies.py
│   │   ├── models.py
│   │   ├── responses.py
│   │   ├── schemas.py
│   │   ├── security.py
│   │   ├── services.py
│   │   ├── validators.py
│   │   └── views.py
│   ├── Dockerfile
│   ├── __init__.py
│   ├── api.py
│   ├── config.py
│   ├── main.py
│   ├── models.py
│   └── requirements.txt
├── tests
│   ├── conftest.py
│   └── test_db_session.py
├── .env.example
├── .gitignore
├── .pre-commit-config.yaml
├── README.md
├── alembic.ini
├── pyproject.toml
└── requirements_style.txt
```
</details>


## Команда разработки

Проект выполнен командой **Team 4** (Яндекс Практикум).


- **Михаил Ковалев** — Team Lead, Backend-разработчик (Настройка проекта, Разработка базовых классов для моделей БД, базовый CRUD, Настройка кэширования (Redis), Деплой на сервер, настройка CI/CD) — GitHub: [ohhaus](https://github.com/ohhaus) — Telegram: [@ohhaus](https://t.me/ohhaus)
- **Константин Клейников** — Backend-разработчик (Модуль Bookings, Настройка связей с модулями Slots и Tables, Формирование Postman collection) — GitHub: [kkleinikov](https://github.com/kkleinikov) — Telegram: [@kkleinikov](https://t.me/kkleinikov)
- **Никита Ефремчев** — Backend-разработчик (Модули Cafes, Slots, Tables, Алгоритм синхронизации связей менеджер-кафе, Настройка Celery и разработка логики отправки уведомлений) — GitHub: [StigTax](https://github.com/StigTax) — Telegram: [@Nik_efr](https://t.me/Nik_efr)
- **Владимир Игнатьев** — Backend-разработчик (Модуль Dishes, Кастомизация исключений) — GitHub: [Ignatev-V](https://github.com/Ignatev-V) — Telegram: [@V_Ignatev](https://t.me/V_Ignatev)
- **Евгений Бирюков** — Backend-разработчик (Модуль Users) — GitHub: [JinBir007](https://github.com/JinBir007) — Telegram: [@Yfg007](https://t.me/Yfg007)
- **Максим Быстрых** — Backend-разработчик (Логирование, модуль Actions) — GitHub: [pro100max1996](https://github.com/pro100max1996) — Telegram: [@pro100maksim1996](https://t.me/pro100maksim1996)
- **Сергей Гусев** — Backend-разработчик (Модуль Media) — GitHub: [SergeyGusev1](https://github.com/SergeyGusev1) — Telegram: [@magnatuch](https://t.me/magnatuch)
