# Создание пользователя с правами администратора

Это руководство описывает процесс создания пользователя с правами администратора путем прямого обращения к базе данных. Это может быть полезно для первоначальной настройки системы или в целях тестирования.

## Шаг 1: Создание пользователя в базе данных

Выполните следующую команду для создания записи администратора в базе данных:

```bash
docker compose -f infra/docker-compose.yml exec db psql -U postgres -d postgres -c "INSERT INTO \"user\" (id, username, email, phone, role, hashed_password, active, created_at, updated_at) VALUES ('00000000-0000-0000-0000-000000000001', 'admin', 'admin@example.com', '+375290000000', 2, '\$2b\$12\$example_hashed_password', true, NOW(), NOW());"
```

## Шаг 2: Обновление данных пользователя

После создания записи обновите данные пользователя, установив корректный хэшированный пароль:

```bash
docker compose -f infra/docker-compose.yml exec db psql -U postgres -d postgres -c "UPDATE \"user\" SET username = 'admin_user', phone = '+375291111112', hashed_password = '\$argon2id\$v=19\$m=65536,t=3,p=4\$uak5OcO7RA1wGiUDwxr2uA\$eGWZKxE/8e1o9wCG5IvR7InoBGg/GKfKYjfNI8BFmZg' WHERE id = '00000000-0000-0000-0000-000000000001';"
```

## Шаг 3: Аутентификация через API

После создания пользователя вы можете аутентифицироваться через API с использованием следующих учетных данных:

```bash
curl -X POST "http://localhost:8000/auth/login" \
  -H "Content-Type: application/json" \
  -d '{"login": "admin@example.com", "password": "Adminpassword123!"}'
```

## Генерация хэшированного пароля (опционально)

Если вы хотите использовать свой собственный пароль, вы можете сгенерировать для него хэш следующей командой:

```bash
docker compose -f infra/docker-compose.yml exec app python -c "from src.users.security import get_password_hash; print(get_password_hash('Ваш_Пароль_Здесь'))"
```

Замените `'Ваш_Пароль_Здесь'` на желаемый пароль.

## Проверка доступа

После аутентификации вы можете использовать полученный токен для доступа к административным эндпоинтам:

- Получение списка всех пользователей: `GET /users/`
- Получение конкретного пользователя: `GET /users/{user_id}`
- Обновление данных пользователя: `PATCH /users/{user_id}`