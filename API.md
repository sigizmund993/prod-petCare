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
| 403 | `Email not verified` при логине; в сообществах — нет прав (`Not a member`, `Only the owner can do this` и т.п.) |
| 404 | объект не найден **или чужой** (`User not found`, `Pet not found`, `Prop not found`, `Notification not found`, `Community not found`, `Message not found`, `Member not found`) |
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
  "email_verified": true,
  "telegram_linked": false
}
```
`phone_number` может быть `null`. `telegram_linked` — подключены ли уведомления в Telegram.

### Pet
```json
{
  "id": 1,
  "name": "Барсик",
  "type": "кошка",
  "breed": "британская",
  "birth_date": "2020-05-17",
  "own_ids": [1, 2],
  "prop_ids": [5, 7],
  "has_picture": true
}
```
- `type` — вид животного, `breed` — порода; обе строки необязательны (`null`).
- `birth_date` — дата рождения в формате `YYYY-MM-DD`, необязательна (`null`). Дата из будущего — 422 с `loc: ["body", "birth_date"]`.
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
  "own_ids": [1],
  "category": "vaccination",
  "liked": null,
  "suitable": null,
  "reactions": []
}
```
- `msg`, `text` — необязательные строки (`null`).
- `rep` — булево, по умолчанию `false`.
- `date` — дата и время в ISO 8601, лучше передавать с часовым поясом (`Z` или `+03:00`).
- `own_ids` — пользователи, которые видят запись.
- `category` — тип записи, по умолчанию `reminder`:

  | Значение | Что это |
  |---|---|
  | `reminder` | обычное напоминание |
  | `food` | запись о корме (журнал питания) |
  | `vaccination` | вакцинация |
  | `parasites` | обработка от паразитов |
  | `vet_visit` | посещение ветеринара, заключение — в `text` |
  | `medication` | приём препарата |

- Только для `category: "food"` (для других типов — 422):
  - `liked` — понравилось (`true`) / не понравилось (`false`) / не оценено (`null`);
  - `suitable` — подошло (`true`) / не подошло (`false`) / не оценено (`null`);
  - `reactions` — нежелательные реакции: `gi` (ЖКТ), `allergy` (аллергия), `other`. Повторы убираются.
- Записи `food` никогда не становятся уведомлениями — это история питания, а не напоминания.
- Только для `category: "vet_visit"` (для других типов — 422) — рекомендации врача, по ним работают [рекомендации](#recommendation):
  - `diet_tags` — что рекомендовано: `hypoallergenic`, `sensitive_digestion`, `weight_control`, `sterilised`, `urinary`, `renal`, `dental`, `joint`, `hairball`, `skin_coat`, `long_coat`, `brachycephalic`, `active`, `intellectual`, `chewer`;
  - `diet_exclude` — каких ингредиентов избегать: `chicken`, `turkey`, `beef`, `lamb`, `fish`, `grain`, `rice`, `dairy`.

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
| POST | `/user/telegram/link` | да | — | 200 `{"url", "expires_in"}` |
| DELETE | `/user/telegram` | да | — | 204 |

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

### Telegram

1. По кнопке «Подключить Telegram» вызовите `POST /user/telegram/link` и откройте `url` в новой вкладке. Ссылка одноразовая и живёт `expires_in` секунд.
2. Пользователь жмёт Start в боте, и аккаунт привязывается. Обновите `GET /user/me`: `telegram_linked` станет `true`.
3. `DELETE /user/telegram` отключает уведомления.

Если бот на сервере не настроен, `POST /user/telegram/link` отвечает 503 `Telegram is not configured`.

В Telegram приходят те же уведомления, что в `/notification/list`: запись с наступившей `date` (повторяющиеся — каждый день) и день рождения питомца (в 9:00 по Москве). Уже прочитанные на сайте и наступившие до подключения Telegram не приходят. Прочтение в Telegram на сайт не влияет: уведомление остаётся непрочитанным, пока его не прочитают на сайте.

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
{ "name": "Барсик", "type": "кошка", "breed": "британская", "birth_date": "2020-05-17", "own_ids": [2], "prop_ids": [5] }
```
Обязательно только `name`. `type`, `breed` и `birth_date` по умолчанию `null`, `own_ids` и `prop_ids` — `[]`.

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
| GET | `/prop/list?pet_id=1&category=food&suitable=true` | — | 200 `Prop[]` — с фильтрами, см. ниже |
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
  "own_ids": [],
  "category": "reminder"
}
```
Обязательны `name` и `date`.

Запись о корме:
```json
{
  "name": "Royal Canin Sterilised",
  "date": "2026-10-16T09:00:00Z",
  "category": "food",
  "liked": true,
  "suitable": false,
  "reactions": ["gi"],
  "text": "Мягкий стул на второй день"
}
```

Фильтры `GET /prop/list` (все необязательные, комбинируются с `pet_id` и между собой):
- `category` — тип записи: `?category=vaccination` — история вакцинаций;
- `liked`, `suitable` — `true`/`false`: `?pet_id=1&category=food&suitable=true` — корма, которые подошли питомцу.

`DELETE /prop/del` сам убирает запись из `prop_ids` всех питомцев.

### Notification

Уведомления бывают двух видов (поле `kind`):

- `prop` — запись (Prop), у которой наступила `date`. Повторяющиеся записи (`rep: true`) срабатывают каждый день начиная с `date`, после прочтения уведомление снова появится на следующий день. `id` — id записи.
- `birthday` — у питомца сегодня день рождения (по московскому времени, начиная с первой годовщины; родившиеся 29 февраля в невисокосный год — 28-го). Висит весь день, пока не прочитано, и вернётся через год. `id` и `pet_id` — id питомца.

«Прочитано» у каждого владельца своё.

```json
[
  {
    "kind": "birthday", "id": 1, "pet_id": 1,
    "name": "День рождения: Барсик", "msg": "Исполняется 3 года", "text": null,
    "rep": true, "date": "2026-10-16T21:00:00Z", "own_ids": [1]
  },
  {
    "kind": "prop", "id": 5, "pet_id": null,
    "name": "Прививка", "msg": "Не забыть паспорт", "text": null,
    "rep": false, "date": "2026-10-15T12:00:00Z", "own_ids": [1]
  }
]
```

| Метод | Путь | Тело | Ответ |
|---|---|---|---|
| GET | `/notification/list` | — | 200 `Notification[]` — непрочитанные, новые сверху; `date` — время срабатывания |
| GET | `/notification/count` | — | 200 `{"count": 3}` |
| POST | `/notification/read?prop_id=5` | — | 204 — прочитать уведомление о записи |
| POST | `/notification/read?pet_id=1` | — | 204 — прочитать уведомление о дне рождения |
| POST | `/notification/read_all` | — | 204 |

`read` принимает ровно один из `prop_id`/`pet_id` (иначе 400) и отвечает 404, если такого непрочитанного уведомления нет. Удобно брать параметр по `kind`: `kind === "birthday" ? {pet_id: n.id} : {prop_id: n.id}`.

Все ручки требуют авторизации. Новые уведомления сервер не присылает сам: опрашивайте `/notification/count` раз в 30–60 секунд и при открытии приложения.

### Community

Сообщества **открытые**: список, карточку и участников видит любой пользователь, вступить и выйти можно самому. Читать и писать сообщения могут только участники.

```json
{
  "id": 1,
  "name": "Любители котов",
  "description": "Всё о котах",
  "owner_id": 1,
  "member_ids": [1, 2],
  "created_at": "2026-10-18T12:00:00Z"
}
```
- `owner_id` — владелец: только он меняет название и описание, удаляет сообщество и выгоняет участников.
- `member_ids` — участники в порядке вступления, владелец среди них. «Я участник» — `member_ids.includes(me.id)`.

| Метод | Путь | Тело | Ответ |
|---|---|---|---|
| POST | `/community/add` | `CommunityIn` | 201 `Community` — создатель становится владельцем и участником |
| GET | `/community/list` | — | 200 `Community[]` — все сообщества, по `id` |
| GET | `/community/list?q=кот` | — | 200 `Community[]` — поиск по подстроке названия, без учёта регистра |
| GET | `/community/list?mine=true` | — | 200 `Community[]` — только мои (можно вместе с `q`) |
| GET | `/community/get?community_id=1` | — | 200 `Community` |
| PUT | `/community/edit?community_id=1` | `CommunityIn` | 200 `Community` — только владелец |
| DELETE | `/community/del?community_id=1` | — | 204 — только владелец, сообщения удаляются вместе с ним |
| POST | `/community/join?community_id=1` | — | 200 `Community` — повторное вступление ничего не меняет |
| POST | `/community/leave?community_id=1` | — | 204 (403, если вы не участник) |
| POST | `/community/kick?community_id=1&member_id=2` | — | 204 — только владелец; себя — 400, не участник — 404 |
| GET | `/community/members?community_id=1` | — | 200 `[{"id": 1, "name": "Иван"}]` — в порядке вступления |

Все ручки требуют авторизации.

`CommunityIn`:
```json
{ "name": "Любители котов", "description": "Всё о котах" }
```
`name` обязателен, от 1 до 100 символов (пробелы по краям обрезаются, пустое — 422). `description` необязательно (`null`).

- Если владелец выходит из сообщества или удаляет аккаунт, владельцем становится первый из оставшихся участников (`member_ids[0]`). Сообщество без участников удаляется.
- `members` отдаёт только `id` и имя: почту и телефон других пользователей API не показывает. Удобно, чтобы показать список участников и имена в сообщениях.

### Message

```json
{
  "id": 10,
  "text": "Чем вы кормите британцев?",
  "community_id": 1,
  "from_id": 2,
  "from_name": "Иван",
  "created_at": "2026-10-18T12:05:00Z",
  "edited_at": null
}
```
- `from_id` и `from_name` — автор. Оба `null`, если автор удалил аккаунт: покажите «Удалённый пользователь».
- `edited_at` — время последнего редактирования, `null` — сообщение не меняли (можно показать «изменено»).

| Метод | Путь | Тело | Ответ |
|---|---|---|---|
| POST | `/message/add?community_id=1` | `{"text"}` | 201 `Message` — только участник |
| GET | `/message/list?community_id=1` | — | 200 `Message[]` — последние 50 |
| GET | `/message/list?community_id=1&before_id=10` | — | 200 `Message[]` — 50 сообщений перед `id = 10` (подгрузка истории) |
| GET | `/message/list?community_id=1&after_id=42` | — | 200 `Message[]` — новые после `id = 42` (опрос) |
| PUT | `/message/edit?message_id=10` | `{"text"}` | 200 `Message` — только автор |
| DELETE | `/message/del?message_id=10` | — | 204 — автор или владелец сообщества |

Все ручки требуют авторизации. Читать сообщения может только участник, иначе 403. Сообщение из сообщества, где вы не участник, — 404.

- `text` — от 1 до 4000 символов, пробелы по краям обрезаются, пустое — 422.
- `list` всегда отдаёт сообщения **по возрастанию `id`** (старые сверху, как в чате). `limit` — от 1 до 100, по умолчанию 50. `before_id` и `after_id` вместе — 400.
- Новые сообщения сервер сам не присылает. Пока чат открыт, опрашивайте `after_id=<id последнего сообщения>` раз в 3–5 секунд. Если пришло ровно `limit` сообщений, запросите ещё раз с новым `after_id`.
- Историю подгружайте при прокрутке вверх с `before_id=<id самого старого показанного>`. Если пришло меньше `limit`, история кончилась.

```js
let messages = await api(`/message/list?community_id=${id}`, { token });
// опрос новых
const lastId = messages.at(-1)?.id ?? 0;
messages.push(...await api(`/message/list?community_id=${id}&after_id=${lastId}`, { token }));
// история при прокрутке вверх
const older = await api(`/message/list?community_id=${id}&before_id=${messages[0].id}`, { token });
messages = [...older, ...messages];
```

### Recommendation

Подбор для питомца по виду, возрасту, породе, рекомендациям врача (последний визит `vet_visit` с `diet_tags`/`diet_exclude`) и истории кормов. Вид берётся из `pet.type` (`кошка`, `кот`, `котёнок`, `собака`, `щенок` …), порода — из `pet.breed`, возраст — из `pet.birth_date`.

| Метод | Путь | Ответ |
|---|---|---|
| GET | `/recommendation/food?pet_id=1` | 200 `Recommendation[]` — корма |
| GET | `/recommendation/goods?pet_id=1` | 200 `Recommendation[]` — игрушки, аксессуары и уход |
| GET | `/recommendation/goods?pet_id=1&kind=toy` | только игрушки; `kind`: `toy`, `accessory`, `care` |

Параметр `limit` — сколько вернуть, 1–50, по умолчанию 10. Ошибки: 404 — питомец чужой или не найден; 400 `Pet type must be cat or dog for recommendations` — не указан или не распознан вид питомца (попросите указать «кошка» или «собака»).

```json
[
  {
    "id": 4,
    "kind": "food",
    "name": "Гипоаллергенный корм с ягнёнком для кошек",
    "description": "Один источник белка, без злаков",
    "tags": ["hypoallergenic", "skin_coat"],
    "ingredients": ["lamb"],
    "score": 3,
    "reasons": ["рекомендовано ветеринаром: гипоаллергенный", "без исключённого врачом: курица"]
  }
]
```

Отсортировано по `score`. `reasons` — готовые подписи для интерфейса: почему товар предложен. Корма, которые не подошли или вызвали аллергию, и корма с аллергенами из них в выдачу не попадают. Рядом с рекомендациями стоит показать «Не заменяет консультацию ветеринара».

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
