# petCare backend

```
db/       подключение к БД и запросы
sql/      миграции (монтируются в postgres как docker-entrypoint-initdb.d)
src/      FastAPI приложение и хендлеры
```

Запуск: `make run-dev` → http://localhost:8080/docs
