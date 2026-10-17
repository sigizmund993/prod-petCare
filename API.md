# PetCare API

- **Base URL (prod):** `http://139.100.200.207:8080`
- **Локально:** `http://localhost:8080` (`make run-dev`)
- **Swagger:** `<base>/docs`. Там можно потыкать все ручки, схема OpenAPI лежит в `<base>/openapi.json`

Все запросы и ответы в JSON (`Content-Type: application/json`).

## Авторизация

Защищённые ручки требуют заголовок:

```
Authorization: Bearer <access_token>
```

Токен выдают `POST /user/login` и `POST /user/verify`, он живёт 24 часа. Обновления токена нет: когда приходит 401, отправляйте пользователя на логин.

### Флоу регистрации

```
POST /user/add  ──►  на почту приходит 6-значный код
       │
       ▼
экран «введите код»  ──►  POST /user/verify  ──►  токен, пользователь залогинен
       │
       └── «отправить ещё раз»  ──►  POST /user/verify/resend
```

- Пока почта не подтверждена, `POST /user/login` отвечает **403** `{"detail": "Email not verified"}`. В этом случае покажите экран ввода кода (и можно сразу вызвать `/user/verify/resend`).
- Код действует **15 минут**, на ввод даётся **5 попыток**, повторно отправить можно **не чаще раза в минуту**.
- Если сменить почту в `PUT /user/edit`, она снова становится неподтверждённой, и код уходит на новый адрес.

## Ошибки

Все ошибки имеют вид `{"detail": "..."}`.

| Код | Когда |
|---|---|
| 400 | неверные ссылки (`Unknown user in own_ids`, `Unknown prop in prop_ids`), неверный или просроченный код |
| 401 | нет токена, токен неверный или просрочен (без заголовка `Authorization` может прийти 403 `Not authenticated`) |
| 403 | `Email not verified` при логине |
| 404 | объект не найден **или чужой** (`User not found`, `Pet not found`, `Prop not found`, `Notification not found`) |
| 409 | `Email already registered` или `Phone number already registered` |
| 422 | тело или параметры не прошли валидацию; `detail` в этом случае — массив с описанием полей |

## Модели

### User
```json
{
  "id": 1,
  "email": "user@example.com",
  "phone_number": "+79990000000",
  "name": "Иван",
  "email_verified": true
}
```
`phone_number` может быть `null`.

### Pet
```json
{
  "id": 1,
  "name": "Барсик",
  "type": "кошка",
  "breed": "британская",
  "own_ids": [1, 2],
  "prop_ids": [5, 7],
  "has_picture": true
}
```
- `type` — вид животного, `breed` — порода; обе строки необязательны (`null`).
- `has_picture` — загружена ли картинка. Саму картинку отдаёт `GET /pets/{pet_id}/photo`, в `Pet` её нет. Только для чтения: в `PetIn` не передаётся.
- `own_ids` — id пользователей-владельцев.
- `prop_ids` — id записей (Prop), привязанных к питомцу.

### Prop
```json
{
  "id": 5,
  "name": "Прививка",
  "msg": "Не забыть паспорт",
  "text": null,
  "rep": false,
  "date": "2026-10-20T12:00:00Z",
  "own_ids": [1]
}
```
- `msg`, `text` — необязательные строки (`null`).
- `rep` — булево, по умолчанию `false`.
- `date` — дата и время в ISO 8601, лучше передавать с часовым поясом (`Z` или `+03:00`).
- `own_ids` — пользователи, которые видят запись.

### Доступ и владельцы
- Пользователь видит только тех питомцев и те записи, где его `id` есть в `own_ids`. На чужие объекты API отвечает 404.
- Текущий пользователь **всегда** добавляется в `own_ids` сам, передавать его не обязательно.
- Все `id` в `own_ids` должны существовать, иначе будет 400.
- В `prop_ids` питомца можно указывать только записи, которые видит текущий пользователь, иначе будет 400.
- Чтобы привязать запись к питомцу, сначала создайте Prop, потом добавьте его `id` в `prop_ids` питомца через `PUT /pet/edit`.

## Ручки

`id` объекта передаётся **query-параметром**: `?pet_id=1`, `?prop_id=5`.

`edit` — это **полная замена**: передавайте все поля, а не только изменённые. Поля, которые не передали, сбросятся в значения по умолчанию.

### User

| Метод | Путь | Авторизация | Тело | Ответ |
|---|---|---|---|---|
| POST | `/user/add` | — | `UserIn` | 201 `User` |
| POST | `/user/verify` | — | `{"email", "code"}` | 200 `Token` |
| POST | `/user/verify/resend` | — | `{"email"}` | 204 |
| POST | `/user/login` | — | `{"email", "passwd"}` | 200 `Token` |
| GET | `/user/me` | да | — | 200 `User` |
| PUT | `/user/edit` | да | `UserIn` | 200 `User` |
| DELETE | `/user/del` | да | — | 204 |

`UserIn`:
```json
{
  "email": "user@example.com",
  "passwd": "secret",
  "name": "Иван",
  "phone_number": "+79990000000"
}
```
`phone_number` необязателен и уникален: два пользователя не могут указать один номер. Пустая строка считается отсутствием номера (`null`).

`Token`:
```json
{ "access_token": "eyJ...", "token_type": "bearer" }
```

Примечания:
- **`PUT /user/edit` требует `passwd` всегда**: пароль перезаписывается тем, что пришёл. Если пользователь не меняет пароль, всё равно попросите его ввести текущий.
- `/user/verify/resend` всегда отвечает 204, даже если почта не зарегистрирована или уже подтверждена. Показывайте нейтральное «если адрес зарегистрирован, мы отправили код».
- `/user/verify` на любую проблему с кодом (неверный, просрочен, попытки кончились) отвечает 400 `Wrong or expired code`. Предложите отправить код ещё раз.
- `DELETE /user/del` убирает пользователя из всех `own_ids`. Питомцы и записи, у которых не осталось владельцев, удаляются.

### Pet

| Метод | Путь | Тело | Ответ |
|---|---|---|---|
| POST | `/pet/add` | `PetIn` | 201 `Pet` |
| GET | `/pet/list` | — | 200 `Pet[]` (по `id`) |
| GET | `/pet/get?pet_id=1` | — | 200 `Pet` |
| PUT | `/pet/edit?pet_id=1` | `PetIn` | 200 `Pet` |
| DELETE | `/pet/del?pet_id=1` | — | 204 |
| POST | `/pets/1/photo` | `multipart/form-data`, поле `file` | 200 `{"pet_id": 1, "photo_url": "/pets/1/photo"}` |
| GET | `/pets/1/photo` | — | 200, байты картинки (404, если её нет) |
| DELETE | `/pets/1/photo` | — | 204 |

Все ручки требуют авторизации.

`PetIn`:
```json
{ "name": "Барсик", "type": "кошка", "breed": "британская", "own_ids": [2], "prop_ids": [5] }
```
Обязательно только `name`. `type` и `breed` по умолчанию `null`, `own_ids` и `prop_ids` — `[]`.

#### Фото питомца

Обратите внимание: у ручек фото **другая схема URL**, чем у остальных: `/pets/{pet_id}/photo` (id в пути, `pets` во множественном числе).

- У питомца одно фото. Новая загрузка заменяет старое, `PUT /pet/edit` фото не трогает.
- Форматы: **JPEG, PNG, WebP**, до **5 МБ**. Проверяется и `Content-Type` файла, и его содержимое. Иначе будет 400, слишком большой файл — 413.
- `GET /pets/{pet_id}/photo` требует токен, поэтому `<img src="/pets/1/photo">` напрямую **не сработает**: браузер не отправит заголовок `Authorization`. Загрузите картинку через `fetch` и покажите её через blob URL:

```js
// загрузка
const form = new FormData();
form.append("file", fileInput.files[0]);
await fetch(`${API}/pets/${petId}/photo`, {
  method: "POST",
  headers: { Authorization: `Bearer ${token}` }, // Content-Type не ставить: браузер сам добавит boundary
  body: form,
});

// показ
if (pet.has_picture) {
  const res = await fetch(`${API}/pets/${pet.id}/photo`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  img.src = URL.createObjectURL(await res.blob());
}
```

### Prop

| Метод | Путь | Тело | Ответ |
|---|---|---|---|
| POST | `/prop/add` | `PropIn` | 201 `Prop` |
| GET | `/prop/list` | — | 200 `Prop[]` — все записи пользователя, по `date` |
| GET | `/prop/list?pet_id=1` | — | 200 `Prop[]` — записи питомца, по `date` (404, если питомец чужой) |
| GET | `/prop/get?prop_id=5` | — | 200 `Prop` |
| PUT | `/prop/edit?prop_id=5` | `PropIn` | 200 `Prop` |
| DELETE | `/prop/del?prop_id=5` | — | 204 |

Все ручки требуют авторизации.

`PropIn`:
```json
{
  "name": "Прививка",
  "date": "2026-10-20T12:00:00Z",
  "msg": "Не забыть паспорт",
  "text": null,
  "rep": false,
  "own_ids": []
}
```
Обязательны `name` и `date`.

`DELETE /prop/del` сам убирает запись из `prop_ids` всех питомцев.

### Notification

Уведомление — это запись (Prop), у которой наступила `date`, а текущий пользователь её ещё не прочитал. Повторяющиеся записи (`rep: true`) срабатывают каждый день начиная с `date`, после прочтения уведомление снова появится на следующий день. «Прочитано» у каждого владельца своё.

| Метод | Путь | Тело | Ответ |
|---|---|---|---|
| GET | `/notification/list` | — | 200 `Prop[]` — непрочитанные уведомления, новые сверху; `date` — время срабатывания |
| GET | `/notification/count` | — | 200 `{"count": 3}` |
| POST | `/notification/read?prop_id=5` | — | 204 (404, если такого непрочитанного уведомления нет) |
| POST | `/notification/read_all` | — | 204 |

Все ручки требуют авторизации. Новые уведомления сервер не присылает сам: опрашивайте `/notification/count` раз в 30–60 секунд и при открытии приложения.

## Пример

```js
const API = "http://139.100.200.207:8080";

async function api(path, { method = "GET", body, token } = {}) {
  const res = await fetch(API + path, {
    method,
    headers: {
      "Content-Type": "application/json",
      ...(token && { Authorization: `Bearer ${token}` }),
    },
    body: body && JSON.stringify(body),
  });
  if (res.status === 204) return null;
  const data = await res.json();
  if (!res.ok) throw { status: res.status, detail: data.detail };
  return data;
}

await api("/user/add", { method: "POST", body: { email, passwd, name } });
const { access_token } = await api("/user/verify", { method: "POST", body: { email, code } });
const pets = await api("/pet/list", { token: access_token });
```

## CORS

- Фронт, запущенный на **`localhost` или `127.0.0.1` на любом порту** (`http://localhost:5173`, `http://localhost:3000` и т.д.), может ходить и в локальный бэкенд, и в прод `http://139.100.200.207:8080`, ничего настраивать не нужно.
- Для любого другого адреса фронта (домен, IP в локальной сети) сообщите его бэкендерам: его добавят в `CORS_ORIGIN`, иначе браузер заблокирует запросы.
