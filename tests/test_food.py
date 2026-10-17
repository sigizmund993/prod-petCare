from datetime import UTC, datetime, timedelta

YESTERDAY = (datetime.now(UTC) - timedelta(days=1)).isoformat()


def add_food(client, headers, name, **extra):
    body = {"name": name, "date": YESTERDAY, "category": "food", **extra}
    return client.post("/prop/add", json=body, headers=headers)


def test_food_record_with_ratings_and_reactions(client, register):
    _, headers = register()
    r = add_food(client, headers, "Royal Canin", liked=True, suitable=False, reactions=["gi", "allergy"], text="Мягкий стул")
    assert r.status_code == 201
    food = r.json()
    assert food["category"] == "food"
    assert food["liked"] is True and food["suitable"] is False
    assert food["reactions"] == ["gi", "allergy"]
    assert client.get("/prop/get", params={"prop_id": food["id"]}, headers=headers).json() == food


def test_defaults_keep_old_clients_working(client, register):
    _, headers = register()
    prop = client.post("/prop/add", json={"name": "Прививка", "date": YESTERDAY}, headers=headers).json()
    assert prop["category"] == "reminder"
    assert prop["liked"] is None and prop["suitable"] is None and prop["reactions"] == []


def test_unrated_food(client, register):
    _, headers = register()
    food = add_food(client, headers, "Purina").json()
    assert food["liked"] is None and food["suitable"] is None and food["reactions"] == []


def test_duplicate_reactions_collapsed(client, register):
    _, headers = register()
    assert add_food(client, headers, "Purina", reactions=["gi", "gi"]).json()["reactions"] == ["gi"]


def test_invalid_category_or_reaction_rejected(client, register):
    _, headers = register()
    assert client.post("/prop/add", json={"name": "X", "date": YESTERDAY, "category": "walk"}, headers=headers).status_code == 422
    assert add_food(client, headers, "Purina", reactions=["sneeze"]).status_code == 422


def test_food_fields_only_for_food(client, register):
    _, headers = register()
    for extra in ({"liked": True}, {"suitable": False}, {"reactions": ["gi"]}):
        body = {"name": "Прививка", "date": YESTERDAY, "category": "vaccination", **extra}
        assert client.post("/prop/add", json=body, headers=headers).status_code == 422


def test_edit_food_rating(client, register):
    _, headers = register()
    food = add_food(client, headers, "Purina").json()
    body = {"name": "Purina", "date": YESTERDAY, "category": "food", "liked": False, "suitable": True}
    r = client.put("/prop/edit", params={"prop_id": food["id"]}, json=body, headers=headers)
    assert r.status_code == 200
    assert r.json()["liked"] is False and r.json()["suitable"] is True


def test_filter_pet_foods_that_suit(client, register):
    _, headers = register()
    good = add_food(client, headers, "Hills", liked=True, suitable=True).json()
    bad = add_food(client, headers, "Whiskas", liked=True, suitable=False, reactions=["allergy"]).json()
    other_pet_food = add_food(client, headers, "Felix", suitable=True).json()
    vaccine = client.post("/prop/add", json={"name": "Прививка", "date": YESTERDAY, "category": "vaccination"}, headers=headers).json()
    pet = client.post("/pet/add", json={"name": "Барсик", "prop_ids": [good["id"], bad["id"], vaccine["id"]]}, headers=headers).json()

    def ids(**params):
        r = client.get("/prop/list", params=params, headers=headers)
        assert r.status_code == 200
        return {p["id"] for p in r.json()}

    assert ids(pet_id=pet["id"], category="food") == {good["id"], bad["id"]}
    assert ids(pet_id=pet["id"], category="food", suitable=True) == {good["id"]}
    assert ids(pet_id=pet["id"], category="food", suitable=False) == {bad["id"]}
    assert ids(pet_id=pet["id"], category="vaccination") == {vaccine["id"]}
    assert ids(pet_id=pet["id"]) == {good["id"], bad["id"], vaccine["id"]}
    # Без pet_id — по всем записям пользователя
    assert ids(category="food", suitable=True) == {good["id"], other_pet_food["id"]}
    assert ids(liked=True) == {good["id"], bad["id"]}


def test_invalid_filter_rejected(client, register):
    _, headers = register()
    assert client.get("/prop/list", params={"category": "walk"}, headers=headers).status_code == 422


def test_food_records_are_not_notifications(client, register):
    _, headers = register()
    add_food(client, headers, "Royal Canin", liked=True)
    vaccine = client.post("/prop/add", json={"name": "Прививка", "date": YESTERDAY, "category": "vaccination"}, headers=headers).json()

    items = client.get("/notification/list", headers=headers).json()
    assert [n["id"] for n in items] == [vaccine["id"]]
    assert items[0]["category"] == "vaccination"
    assert client.get("/notification/count", headers=headers).json()["count"] == 1
    # read_all не трогает записи о кормах
    assert client.post("/notification/read_all", headers=headers).status_code == 204
    assert client.get("/notification/count", headers=headers).json()["count"] == 0
