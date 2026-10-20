# StudentWallet

Учёт расходов студента: анализ трат и бюджет на месяц. Быстрый ввод трат голосом через Siri/Shortcuts.

Состав команды и роли: [TEAM.md](TEAM.md). Полный план проекта (требования, backlog, ER-диаграмма, спринты): [docs/StudentWallet_project_plan.md](docs/StudentWallet_project_plan.md).

## Структура репозитория

```
backend/     FastAPI + SQLAlchemy (REST API, БД, тесты)
frontend/    React (появится в спринте 1-2)
docs/        Документация и отчёты по спринтам
design/      Макеты и wireframes
shortcuts/   Инструкции и скриншоты команд Siri/Shortcuts
postman/     Postman-коллекция
```

## Запуск backend

Нужен Python 3.10 или новее.

```bash
cd backend
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt

uvicorn app.main:app --reload
```

После запуска:
- Swagger-документация и тестирование запросов: http://127.0.0.1:8000/docs
- Проверка работы: http://127.0.0.1:8000/api/health

При первом запуске создаётся файл `studentwallet.db` (SQLite), роли `student` и `admin` и шесть глобальных категорий.

### Переменные окружения (необязательно)

| Переменная | Назначение |
|---|---|
| `DATABASE_URL` | Адрес БД. По умолчанию SQLite. Для PostgreSQL: `postgresql+psycopg2://user:pass@localhost:5432/studentwallet` (потребуется `pip install psycopg2-binary`) |
| `SECRET_KEY` | Ключ подписи JWT. На сервере обязательно задайте свой |
| `ADMIN_EMAIL`, `ADMIN_PASSWORD` | Если заданы, при запуске создаётся администратор |

Пример создания администратора:

```bash
ADMIN_EMAIL=admin@example.com ADMIN_PASSWORD=ChangeMe123 uvicorn app.main:app --reload
```

- Быстрый ввод фразой (история 5): `POST /api/ai/parse-expense` разбирает «lunch at canteen 2500» в сумму, дату, тип и категорию. Сумма и категория определяются правилами, модель подключается только если категорию правила не нашли
- Массовая смена категории: `POST /api/expenses/bulk-category` (в интерфейсе: «История» → «Выбрать несколько», есть поиск по описанию)
- Импорт выписки Kaspi Gold (PDF, английская версия): `POST /api/import/kaspi` (предпросмотр) и `POST /api/import/commit`. Категории подбираются по ключевым словам, повторная загрузка не создаёт дубликатов

## Развёртывание на сервере

Пошаговая инструкция (Nginx, systemd, SSH-туннель до Ollama): [deploy/DEPLOY.md](deploy/DEPLOY.md).

## Тесты

```bash
cd backend
pytest
```

## Что уже готово (спринты 1-2, backend)

- Регистрация, вход (JWT), профиль `/api/auth/me`
- Роли `student` и `admin`, защита маршрутов
- Категории: глобальные и личные
- Траты и доходы: создание, список с фильтрами, изменение, удаление (только своих)
- Месячный бюджет и `GET /api/budget/summary` (остаток, процент, дневной лимит)
- Админ: список пользователей, блокировка
- ИИ-ассистент WALL·E (интерфейс приложения полностью на английском): чат `POST /api/assistant/chat`, знает бюджет и траты пользователя, работает на локальной модели через Ollama (`OLLAMA_URL`, `OLLAMA_MODEL`)

## Что дальше

См. таблицу спринтов в плане проекта. Ближайшее: frontend (вход, регистрация, список трат), затем уведомления о лимите (80% и 100%), аналитика, цели, API-токены для Siri.

## Проверка запросов вручную (curl)

```bash
curl -X POST http://127.0.0.1:8000/api/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email":"me@example.com","password":"password123","full_name":"Me"}'

curl -X POST http://127.0.0.1:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"me@example.com","password":"password123"}'
```

Полученный `access_token` подставляйте в заголовок `Authorization: Bearer <токен>`.
