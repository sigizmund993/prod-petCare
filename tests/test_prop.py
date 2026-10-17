VACCINE = {"name": "Прививка", "msg": "Не забыть паспорт", "date": "2026-10-20T12:00:00Z"}


def test_create_and_get_prop(client, register):
    user, headers = register()
    r = client.post("/prop/add", json=VACCINE, headers=headers)
    assert r.status_code == 201
    prop = r.json()
    assert prop["name"] == "Прививка" and prop["msg"] == "Не забыть паспорт"
    assert prop["text"] is None and prop["rep"] is False
    assert prop["own_ids"] == [user["id"]]

    got = client.get("/prop/get", params={"prop_id": prop["id"]}, headers=headers).json()
    assert got == prop


def test_name_and_date_required(client, register):
    _, headers = register()
    assert client.post("/prop/add", json={"name": "Прививка"}, headers=headers).status_code == 422
    assert client.post("/prop/add", json={"date": VACCINE["date"]}, headers=headers).status_code == 422


def test_list_sorted_by_date(client, register):
    _, headers = register()
    client.post("/prop/add", json={"name": "Поздняя", "date": "2026-12-01T00:00:00Z"}, headers=headers)
    client.post("/prop/add", json={"name": "Ранняя", "date": "2026-01-01T00:00:00Z"}, headers=headers)
    names = [p["name"] for p in client.get("/prop/list", headers=headers).json()]
    assert names == ["Ранняя", "Поздняя"]


def test_list_by_pet(client, register):
    _, headers = register()
    vaccine = client.post("/prop/add", json=VACCINE, headers=headers).json()
    client.post("/prop/add", json={"name": "Другое", "date": VACCINE["date"]}, headers=headers)
    pet = client.post("/pet/add", json={"name": "Барсик", "prop_ids": [vaccine["id"]]}, headers=headers).json()

    props = client.get("/prop/list", params={"pet_id": pet["id"]}, headers=headers).json()
    assert [p["id"] for p in props] == [vaccine["id"]]


def test_list_by_foreign_pet_not_found(client, register):
    _, alice_h = register("alice@example.com")
    _, bob_h = register("bob@example.com")
    pet = client.post("/pet/add", json={"name": "Барсик"}, headers=alice_h).json()
    assert client.get("/prop/list", params={"pet_id": pet["id"]}, headers=bob_h).status_code == 404


def test_edit_prop(client, register):
    _, headers = register()
    prop = client.post("/prop/add", json=VACCINE, headers=headers).json()
    r = client.put(
        "/prop/edit", params={"prop_id": prop["id"]}, json={"name": "Ревакцинация", "date": VACCINE["date"], "rep": True}, headers=headers
    )
    assert r.status_code == 200
    assert r.json()["name"] == "Ревакцинация" and r.json()["rep"] is True
    assert r.json()["msg"] is None  # полная замена


def test_foreign_prop_not_found(client, register):
    _, alice_h = register("alice@example.com")
    _, bob_h = register("bob@example.com")
    prop = client.post("/prop/add", json=VACCINE, headers=alice_h).json()
    params = {"prop_id": prop["id"]}
    assert client.get("/prop/get", params=params, headers=bob_h).status_code == 404
    assert client.put("/prop/edit", params=params, json=VACCINE, headers=bob_h).status_code == 404
    assert client.delete("/prop/del", params=params, headers=bob_h).status_code == 404


def test_delete_prop_detaches_from_pet(client, register):
    _, headers = register()
    prop = client.post("/prop/add", json=VACCINE, headers=headers).json()
    pet = client.post("/pet/add", json={"name": "Барсик", "prop_ids": [prop["id"]]}, headers=headers).json()

    assert client.delete("/prop/del", params={"prop_id": prop["id"]}, headers=headers).status_code == 204
    assert client.get("/pet/get", params={"pet_id": pet["id"]}, headers=headers).json()["prop_ids"] == []


def test_unknown_owner_rejected(client, register):
    _, headers = register()
    prop = client.post("/prop/add", json=VACCINE, headers=headers).json()
    bad = {**VACCINE, "own_ids": [9999]}
    assert client.post("/prop/add", json=bad, headers=headers).status_code == 400
    assert client.put("/prop/edit", params={"prop_id": prop["id"]}, json=bad, headers=headers).status_code == 400
