from datetime import UTC, datetime, timedelta


def at(delta: timedelta) -> str:
    return (datetime.now(UTC) + delta).isoformat()


def add_prop(client, headers, name, delta, **extra):
    return client.post("/prop/add", json={"name": name, "date": at(delta), **extra}, headers=headers).json()


def count(client, headers) -> int:
    return client.get("/notification/count", headers=headers).json()["count"]


def test_only_due_props_are_notifications(client, register):
    _, headers = register()
    past = add_prop(client, headers, "Прививка", -timedelta(hours=1))
    add_prop(client, headers, "Обработка", timedelta(days=3))

    items = client.get("/notification/list", headers=headers).json()
    assert [n["id"] for n in items] == [past["id"]]
    assert count(client, headers) == 1


def test_list_newest_first(client, register):
    _, headers = register()
    add_prop(client, headers, "Давно", -timedelta(days=2))
    add_prop(client, headers, "Недавно", -timedelta(minutes=5))
    names = [n["name"] for n in client.get("/notification/list", headers=headers).json()]
    assert names == ["Недавно", "Давно"]


def test_read_hides_notification(client, register):
    _, headers = register()
    prop = add_prop(client, headers, "Прививка", -timedelta(hours=1))

    assert client.post("/notification/read", params={"prop_id": prop["id"]}, headers=headers).status_code == 204
    assert count(client, headers) == 0
    # Повторно прочитать нечего
    assert client.post("/notification/read", params={"prop_id": prop["id"]}, headers=headers).status_code == 404


def test_cannot_read_future_or_foreign(client, register):
    _, alice_h = register("alice@example.com")
    _, bob_h = register("bob@example.com")
    future = add_prop(client, alice_h, "Позже", timedelta(days=1))
    due = add_prop(client, alice_h, "Сейчас", -timedelta(hours=1))

    assert client.post("/notification/read", params={"prop_id": future["id"]}, headers=alice_h).status_code == 404
    assert client.post("/notification/read", params={"prop_id": due["id"]}, headers=bob_h).status_code == 404
    assert count(client, alice_h) == 1


def test_read_all(client, register):
    _, headers = register()
    add_prop(client, headers, "Первая", -timedelta(hours=2))
    add_prop(client, headers, "Вторая", -timedelta(hours=1))
    upcoming = add_prop(client, headers, "Будущая", timedelta(hours=1))

    assert client.post("/notification/read_all", headers=headers).status_code == 204
    assert count(client, headers) == 0
    # Будущая запись не помечается прочитанной заранее
    assert client.get("/prop/get", params={"prop_id": upcoming["id"]}, headers=headers).status_code == 200


def test_read_is_per_owner(client, register):
    _, alice_h = register("alice@example.com")
    bob, bob_h = register("bob@example.com")
    prop = add_prop(client, alice_h, "Прививка", -timedelta(hours=1), own_ids=[bob["id"]])

    client.post("/notification/read", params={"prop_id": prop["id"]}, headers=alice_h)
    assert count(client, alice_h) == 0
    assert count(client, bob_h) == 1


def test_moving_date_forward_rearms_notification(client, register, sql):
    _, headers = register()
    prop = add_prop(client, headers, "Прививка", -timedelta(hours=1))
    client.post("/notification/read", params={"prop_id": prop["id"]}, headers=headers)

    # Дату перенесли на «позже», и она снова наступила
    sql("UPDATE props SET date = now() - interval '1 minute' WHERE id = %s", (prop["id"],))
    assert count(client, headers) == 1


def test_repeating_prop_fires_again_next_day(client, register, sql):
    _, headers = register()
    prop = add_prop(client, headers, "Таблетка", -timedelta(days=3, hours=1), rep=True)

    item = client.get("/notification/list", headers=headers).json()[0]
    # Показывается последнее срабатывание (сегодняшнее), а не исходная дата
    occurred = datetime.fromisoformat(item["date"])
    assert timedelta(0) <= datetime.now(UTC) - occurred < timedelta(days=1)

    client.post("/notification/read", params={"prop_id": prop["id"]}, headers=headers)
    assert count(client, headers) == 0

    # Прошли сутки: прочитанное срабатывание стало вчерашним
    sql("UPDATE notification_reads SET read_date = read_date - interval '1 day'")
    assert count(client, headers) == 1


def test_deleting_prop_removes_notification(client, register):
    _, headers = register()
    prop = add_prop(client, headers, "Прививка", -timedelta(hours=1))
    client.post("/notification/read", params={"prop_id": prop["id"]}, headers=headers)
    assert client.delete("/prop/del", params={"prop_id": prop["id"]}, headers=headers).status_code == 204
    assert client.get("/notification/list", headers=headers).json() == []


def test_requires_auth(client):
    assert client.get("/notification/list").status_code in (401, 403)
