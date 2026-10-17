from datetime import date, timedelta


def test_create_pet_with_only_name(client, register):
    user, headers = register()
    r = client.post("/pet/add", json={"name": "Барсик"}, headers=headers)
    assert r.status_code == 201
    pet = r.json()
    assert pet["name"] == "Барсик"
    assert pet["type"] is None and pet["breed"] is None and pet["birth_date"] is None
    assert pet["own_ids"] == [user["id"]]


def test_create_full_pet_card(client, register):
    _, headers = register()
    body = {"name": "Барсик", "type": "кошка", "breed": "британская", "birth_date": "2020-05-17"}
    pet = client.post("/pet/add", json=body, headers=headers).json()
    assert {k: pet[k] for k in body} == body

    got = client.get("/pet/get", params={"pet_id": pet["id"]}, headers=headers).json()
    assert got == pet


def test_birth_date_today_allowed(client, register):
    _, headers = register()
    today = date.today().isoformat()
    r = client.post("/pet/add", json={"name": "Малыш", "birth_date": today}, headers=headers)
    assert r.status_code == 201
    assert r.json()["birth_date"] == today


def test_birth_date_in_future_rejected(client, register):
    _, headers = register()
    tomorrow = (date.today() + timedelta(days=1)).isoformat()
    r = client.post("/pet/add", json={"name": "Барсик", "birth_date": tomorrow}, headers=headers)
    assert r.status_code == 422
    assert r.json()["detail"][0]["loc"] == ["body", "birth_date"]


def test_birth_date_invalid_format_rejected(client, register):
    _, headers = register()
    r = client.post("/pet/add", json={"name": "Барсик", "birth_date": "17.05.2020"}, headers=headers)
    assert r.status_code == 422


def test_name_is_required(client, register):
    _, headers = register()
    r = client.post("/pet/add", json={"type": "кошка"}, headers=headers)
    assert r.status_code == 422
    assert r.json()["detail"][0]["loc"] == ["body", "name"]


def test_list_shows_only_own_pets(client, register):
    _, alice_h = register("alice@example.com")
    _, bob_h = register("bob@example.com")
    client.post("/pet/add", json={"name": "Барсик"}, headers=alice_h)
    client.post("/pet/add", json={"name": "Мурка"}, headers=alice_h)
    client.post("/pet/add", json={"name": "Шарик"}, headers=bob_h)

    names = [p["name"] for p in client.get("/pet/list", headers=alice_h).json()]
    assert names == ["Барсик", "Мурка"]


def test_foreign_pet_not_found(client, register):
    _, alice_h = register("alice@example.com")
    _, bob_h = register("bob@example.com")
    pet = client.post("/pet/add", json={"name": "Барсик"}, headers=alice_h).json()

    params = {"pet_id": pet["id"]}
    assert client.get("/pet/get", params=params, headers=bob_h).status_code == 404
    assert client.put("/pet/edit", params=params, json={"name": "X"}, headers=bob_h).status_code == 404
    assert client.delete("/pet/del", params=params, headers=bob_h).status_code == 404


def test_edit_is_full_replace(client, register):
    _, headers = register()
    pet = client.post(
        "/pet/add", json={"name": "Барсик", "breed": "британская", "birth_date": "2020-05-17"}, headers=headers
    ).json()
    r = client.put("/pet/edit", params={"pet_id": pet["id"]}, json={"name": "Барс"}, headers=headers)
    assert r.status_code == 200
    assert r.json()["name"] == "Барс"
    assert r.json()["breed"] is None and r.json()["birth_date"] is None


def test_shared_pet_visible_to_co_owner(client, register):
    alice, alice_h = register("alice@example.com")
    bob, bob_h = register("bob@example.com")
    pet = client.post("/pet/add", json={"name": "Барсик", "own_ids": [bob["id"]]}, headers=alice_h).json()
    assert set(pet["own_ids"]) == {alice["id"], bob["id"]}
    assert client.get("/pet/get", params={"pet_id": pet["id"]}, headers=bob_h).status_code == 200


def test_creator_always_stays_owner(client, register):
    alice, alice_h = register("alice@example.com")
    bob, _ = register("bob@example.com")
    pet = client.post("/pet/add", json={"name": "Барсик"}, headers=alice_h).json()
    r = client.put("/pet/edit", params={"pet_id": pet["id"]}, json={"name": "Барсик", "own_ids": [bob["id"]]}, headers=alice_h)
    assert alice["id"] in r.json()["own_ids"]


def test_unknown_owner_rejected(client, register):
    _, headers = register()
    r = client.post("/pet/add", json={"name": "Барсик", "own_ids": [9999]}, headers=headers)
    assert r.status_code == 400
    assert r.json()["detail"] == "Unknown user in own_ids"
    pet = client.post("/pet/add", json={"name": "Барсик"}, headers=headers).json()
    r = client.put("/pet/edit", params={"pet_id": pet["id"]}, json={"name": "Барсик", "own_ids": [9999]}, headers=headers)
    assert r.status_code == 400


def test_foreign_prop_cannot_be_attached(client, register):
    _, alice_h = register("alice@example.com")
    _, bob_h = register("bob@example.com")
    prop = client.post("/prop/add", json={"name": "Прививка", "date": "2026-01-01T12:00:00Z"}, headers=bob_h).json()
    r = client.post("/pet/add", json={"name": "Барсик", "prop_ids": [prop["id"]]}, headers=alice_h)
    assert r.status_code == 400
    assert r.json()["detail"] == "Unknown prop in prop_ids"


def test_delete_pet(client, register):
    _, headers = register()
    pet = client.post("/pet/add", json={"name": "Барсик"}, headers=headers).json()
    assert client.delete("/pet/del", params={"pet_id": pet["id"]}, headers=headers).status_code == 204
    assert client.get("/pet/get", params={"pet_id": pet["id"]}, headers=headers).status_code == 404
    assert client.get("/pet/list", headers=headers).json() == []
