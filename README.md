# petCare backend

```
db/       подключение к БД и запросы
sql/      миграции (монтируются в postgres как docker-entrypoint-initdb.d)
src/      FastAPI приложение и хендлеры
```

Запуск: `make run-dev` → http://localhost:8080/docs

## Подтверждение почты

1. `POST /user/add` — регистрация, на почту уходит 6-значный код (локально без SMTP — в лог: `docker compose logs app`).
2. `POST /user/verify` `{"email", "code"}` — подтверждает почту и сразу возвращает токен.
3. `POST /user/verify/resend` `{"email"}` — новый код (не чаще раза в минуту, ответ всегда 204).

Пока почта не подтверждена, `POST /user/login` отвечает 403 `Email not verified`. Код живёт 15 минут, даётся 5 попыток.
Смена почты в `PUT /user/edit` снова делает её неподтверждённой и отправляет код на новый адрес.

## Уведомления в Telegram

Бот работает через long polling (`getUpdates`), поэтому HTTPS и публичный адрес не нужны. Опрашивать бота может только один процесс: не запускайте uvicorn с `--workers` > 1 и не используйте прод-токен локально — заведите для разработки отдельного бота.

1. `POST /user/telegram/link` → ссылка `https://t.me/<бот>?start=<код>` (живёт 15 минут).
2. Пользователь жмёт Start — бот привязывает его `chat_id` к аккаунту. `/stop` в боте или `DELETE /user/telegram` отвязывают.
3. При `POST /prop/add` всем владельцам записи с подключённым Telegram приходит сообщение.

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
| `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_FROM`, `SMTP_TLS` | Переменная | SMTP-сервер для кодов подтверждения почты; `SMTP_TLS`: `starttls` (порт 587), `ssl` (465) или `none`. Без `SMTP_HOST` коды пишутся в лог приложения |
| `SMTP_PASSWORD` | Переменная, защищённая | пароль SMTP (для Яндекса/Mail.ru — пароль приложения) |
| `TELEGRAM_BOT_TOKEN` | Переменная, защищённая | токен бота от @BotFather. Без него Telegram-уведомления выключены |
| `TELEGRAM_BOT_USERNAME` | Переменная | имя бота без `@`, например `petcare_bot` |
| `DEPLOY_USER`, `APP_PORT`, `POSTGRES_USER`, `POSTGRES_DB`, `CORS_ORIGIN` | Переменная, необязательно | по умолчанию `root`, `8080`, `petcare`, `petcare`, `http://localhost` |

На ВМ всё лежит в `~/app` (`docker-compose.yml`, `sql/`, `.env`). Миграции из `sql/` применяются только при первом создании тома `pgdata`.
