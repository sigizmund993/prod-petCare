# petCare backend

```
db/       подключение к БД и запросы
sql/      миграции (монтируются в postgres как docker-entrypoint-initdb.d)
src/      FastAPI приложение и хендлеры
```

Запуск: `make run-dev` → http://localhost:8080/docs

## Деплой (Spirit GitLab)

`push` в `master` → `build:image` (Kaniko, prod-стадия Dockerfile → Spirit Registry) → `setup:vm` (ставит `dp`) → `deploy:vm` (ssh + `docker compose` из `deploy/docker-compose.yml`).
В merge request выполняется только `build:image`.

CI-переменные (Spirit → Код → Репозитории → репозиторий → CI-переменные):

| Ключ | Тип | Значение |
|---|---|---|
| `SPIRIT_DOCKER_SA_KEY` | Файл | `key.json` сервис-аккаунта (создаёт Project lead) |
| `DEPLOY_KEY` | Файл | приватный SSH-ключ к ВМ (с переводом строки в конце) |
| `DEPLOY_HOST` | Переменная | адрес ВМ |
| `POSTGRES_PASSWORD` | Переменная, защищённая | пароль БД (без `@ : / ?` — он подставляется в `DATABASE_URL`) |
| `JWT_SECRET` | Переменная, защищённая | секрет для JWT |
| `DEPLOY_USER`, `APP_PORT`, `POSTGRES_USER`, `POSTGRES_DB`, `CORS_ORIGIN` | Переменная, необязательно | по умолчанию `root`, `8080`, `petcare`, `petcare`, `http://localhost` |

На ВМ всё лежит в `~/app` (`docker-compose.yml`, `sql/`, `.env`). Миграции из `sql/` применяются только при первом создании тома `pgdata`.
