from datetime import UTC, date, datetime, timedelta
from typing import get_args

import pytest

from src.recommendations import INGREDIENT_LABELS, TAG_LABELS, age_group, species_of, vet_advice
from src.schemas import DietTag, Ingredient

TODAY = date.today()
ADULT = date(TODAY.year - 3, 1, 1).isoformat()
KITTEN = (TODAY - timedelta(days=90)).isoformat()
SENIOR = date(TODAY.year - 12, 1, 1).isoformat()


def at(days: int) -> str:
    return (datetime.now(UTC) + timedelta(days=days)).isoformat()


def add_pet(client, headers, **body):
    return client.post("/pet/add", json={"name": "Барсик", **body}, headers=headers).json()


def add_record(client, headers, pet, **body):
    prop = client.post("/prop/add", json={"date": at(-1), **body}, headers=headers)
    assert prop.status_code == 201, prop.json()
    pet["prop_ids"].append(prop.json()["id"])
    r = client.put("/pet/edit", params={"pet_id": pet["id"]}, json={k: pet[k] for k in ("name", "type", "breed", "birth_date", "prop_ids")}, headers=headers)
    assert r.status_code == 200
    return prop.json()


def food(client, headers, pet_id, **params):
    r = client.get("/recommendation/food", params={"pet_id": pet_id, **params}, headers=headers)
    assert r.status_code == 200, r.json()
    return r.json()


def goods(client, headers, pet_id, **params):
    r = client.get("/recommendation/goods", params={"pet_id": pet_id, **params}, headers=headers)
    assert r.status_code == 200, r.json()
    return r.json()


def names(items):
    return [i["name"] for i in items]


# ---------- правила ----------

def test_species_from_free_text():
    assert species_of(" Кошка ") == "cat" and species_of("кот") == "cat"
    assert species_of("Собака") == "dog" and species_of("щенок") == "dog"
    assert species_of("попугай") is None and species_of(None) is None


@pytest.mark.parametrize(
    "born, species, group",
    [
        (date(2026, 1, 1), "cat", "baby"),
        (date(2024, 10, 18), "cat", "adult"),
        (date(2016, 10, 19), "cat", "adult"),
        (date(2016, 10, 18), "cat", "senior"),
        (date(2019, 10, 18), "dog", "senior"),
        (None, "dog", None),
    ],
)
def test_age_group(born, species, group):
    assert age_group(born, species, date(2026, 10, 18)) == group


def test_latest_vet_advice_wins():
    old = {"category": "vet_visit", "date": datetime(2026, 1, 1, tzinfo=UTC), "diet_tags": ["hypoallergenic"], "diet_exclude": []}
    new = {"category": "vet_visit", "date": datetime(2026, 6, 1, tzinfo=UTC), "diet_tags": ["renal"], "diet_exclude": []}
    empty = {"category": "vet_visit", "date": datetime(2026, 9, 1, tzinfo=UTC), "diet_tags": [], "diet_exclude": []}
    assert vet_advice([old, new, empty]) is new
    assert vet_advice([empty]) is None


def test_labels_cover_api_vocabulary():
    assert set(TAG_LABELS) == set(get_args(DietTag))
    assert set(INGREDIENT_LABELS) == set(get_args(Ingredient))


def test_catalog_uses_known_tags(sql):
    tags = {t for (row,) in sql("SELECT tags FROM products UNION ALL SELECT tags FROM breeds") for t in row}
    ingredients = {i for (row,) in sql("SELECT ingredients FROM products") for i in row}
    assert tags <= set(TAG_LABELS)
    assert ingredients <= set(INGREDIENT_LABELS)


# ---------- корма ----------

def test_food_fits_species_age_and_breed(client, register):
    _, headers = register()
    pet = add_pet(client, headers, type="кошка", breed="Британская", birth_date=ADULT)
    items = food(client, headers, pet["id"])

    assert items and all(i["kind"] == "food" for i in items)
    assert "Корм для котят с курицей" not in names(items)
    assert not any("собак" in n or "щенк" in n for n in names(items))
    # Британцы склонны к лишнему весу и проблемам с суставами — такие корма наверху и с объяснением
    assert any(r.startswith("для породы Британская короткошёрстная") for r in items[0]["reasons"])
    assert any("weight_control" in i["tags"] for i in items[:2])
    assert any("joint" in i["tags"] for i in items[:2])
    assert [i["score"] for i in items] == sorted((i["score"] for i in items), reverse=True)


def test_kitten_gets_kitten_food(client, register):
    _, headers = register()
    pet = add_pet(client, headers, type="котёнок", birth_date=KITTEN)
    result = names(food(client, headers, pet["id"]))
    assert result == ["Корм для котят с курицей"]


def test_senior_cat(client, register):
    _, headers = register()
    pet = add_pet(client, headers, type="кошка", birth_date=SENIOR)
    items = food(client, headers, pet["id"])
    assert items[0]["name"] == "Корм для пожилых кошек с рыбой"
    assert "специально для возраста: пожилой" in items[0]["reasons"]


def test_small_dog_does_not_get_large_breed_food(client, register):
    _, headers = register()
    pet = add_pet(client, headers, type="собака", breed="чихуахуа", birth_date=ADULT)
    result = names(food(client, headers, pet["id"]))
    assert "Корм для взрослых собак крупных пород" not in result
    assert result[0] == "Корм для взрослых собак мелких пород"  # мелкая гранула для зубов — предрасположенность породы


def test_vet_advice_ranks_first_and_excludes_ingredients(client, register):
    _, headers = register()
    pet = add_pet(client, headers, type="кошка", breed="британская", birth_date=ADULT)
    add_record(client, headers, pet, name="Дерматолог", category="vet_visit", text="Аллергия на курицу",
               diet_tags=["hypoallergenic"], diet_exclude=["chicken"])

    items = food(client, headers, pet["id"])
    assert items[0]["name"] == "Гипоаллергенный корм с ягнёнком для кошек"
    assert "рекомендовано ветеринаром: гипоаллергенный" in items[0]["reasons"]
    assert "без исключённого врачом: курица" in items[0]["reasons"]
    assert all("chicken" not in i["ingredients"] for i in items)


def test_newer_vet_visit_replaces_old_advice(client, register):
    _, headers = register()
    pet = add_pet(client, headers, type="кошка", birth_date=ADULT)
    add_record(client, headers, pet, name="Визит 1", category="vet_visit", date=at(-30), diet_exclude=["chicken"])
    add_record(client, headers, pet, name="Визит 2", category="vet_visit", date=at(-1), diet_tags=["urinary"])

    items = food(client, headers, pet["id"])
    assert items[0]["name"] == "Корм для профилактики мочекаменной болезни"
    assert any("chicken" in i["ingredients"] for i in items)  # запрет из старого визита больше не действует


def test_food_history_excludes_unsuitable_and_allergens(client, register):
    _, headers = register()
    pet = add_pet(client, headers, type="собака", birth_date=ADULT)
    add_record(client, headers, pet, name="Корм для взрослых собак средних пород с говядиной", category="food", suitable=False)
    add_record(client, headers, pet, name="корм для собак с контролем веса", category="food", reactions=["allergy"])

    items = food(client, headers, pet["id"])
    result = names(items)
    assert "Корм для взрослых собак средних пород с говядиной" not in result
    # Аллергия была на корм с индейкой и рисом — всё с этими ингредиентами исключено
    assert all(not {"turkey", "rice"} & set(i["ingredients"]) for i in items)
    assert any("аллергия: рис, индейка" in r for r in items[0]["reasons"])


def test_gi_reactions_boost_sensitive_digestion(client, register):
    _, headers = register()
    pet = add_pet(client, headers, type="собака", birth_date=ADULT)
    add_record(client, headers, pet, name="Какой-то корм из магазина", category="food", reactions=["gi"])
    top = food(client, headers, pet["id"])[0]
    assert "sensitive_digestion" in top["tags"]
    assert "были проблемы с ЖКТ: чувствительное пищеварение" in top["reasons"]


def test_tried_and_suitable_food_is_boosted(client, register):
    _, headers = register()
    pet = add_pet(client, headers, type="кошка", birth_date=ADULT)
    add_record(client, headers, pet, name="Корм для вывода шерсти", category="food", suitable=True, liked=True)
    top = food(client, headers, pet["id"])[0]
    assert top["name"] == "Корм для вывода шерсти" and "уже подошёл питомцу" in top["reasons"]


def test_unknown_breed_and_age_still_recommends(client, register, sql):
    _, headers = register()
    pet = add_pet(client, headers, type="кошка", breed="дворовая")
    items = food(client, headers, pet["id"], limit=50)
    cat_foods = sql("SELECT count(*) FROM products WHERE kind = 'food' AND 'cat' = ANY(species)")[0][0]
    # Без возраста и породы — все кошачьи корма, без баллов и выдуманных причин
    assert len(items) == cat_foods
    assert all(i["score"] == 0 and i["reasons"] == [] for i in items)


def test_limit(client, register):
    _, headers = register()
    pet = add_pet(client, headers, type="собака")
    assert len(food(client, headers, pet["id"], limit=3)) == 3
    assert client.get("/recommendation/food", params={"pet_id": pet["id"], "limit": 0}, headers=headers).status_code == 422


# ---------- игрушки и другие товары ----------

def test_goods_for_active_chewer_dog(client, register):
    _, headers = register()
    pet = add_pet(client, headers, type="собака", breed="Лабрадор", birth_date=ADULT)
    items = goods(client, headers, pet["id"])
    assert {i["kind"] for i in items} <= {"toy", "accessory", "care"}
    assert items[0]["name"] == "Мяч-апорт" or "chewer" in items[0]["tags"]
    assert not any(i["name"] == "Удочка с пёрышками" for i in items)  # кошачья игрушка


def test_goods_filtered_by_kind(client, register):
    _, headers = register()
    pet = add_pet(client, headers, type="кошка", breed="мейн-кун", birth_date=ADULT)
    care = goods(client, headers, pet["id"], kind="care")
    assert care and all(i["kind"] == "care" for i in care)
    assert care[0]["name"] == "Пуходёрка для длинной шерсти"  # длинная шерсть и комки шерсти у мейн-куна
    toys = goods(client, headers, pet["id"], kind="toy")
    assert toys and all(i["kind"] == "toy" for i in toys)


def test_goods_follow_vet_advice(client, register):
    _, headers = register()
    pet = add_pet(client, headers, type="собака", birth_date=ADULT)
    add_record(client, headers, pet, name="Стоматолог", category="vet_visit", diet_tags=["dental"])
    top = goods(client, headers, pet["id"])[0]
    assert "dental" in top["tags"] and "рекомендовано ветеринаром: здоровье зубов" in top["reasons"]
    assert not any(r.startswith("без исключённого") for r in top["reasons"])


def test_brachycephalic_accessories(client, register):
    _, headers = register()
    pet = add_pet(client, headers, type="собака", breed="мопс", birth_date=ADULT)
    accessories = names(goods(client, headers, pet["id"], kind="accessory"))
    # Мопс — брахицефал (широкая миска, шлейка) и склонен к лишнему весу (миска с замедлением)
    assert set(accessories[:3]) == {"Широкая неглубокая миска", "Шлейка вместо ошейника", "Миска-кормушка с замедлением"}


# ---------- ошибки ----------

def test_pet_type_required(client, register):
    _, headers = register()
    for pet_type in (None, "попугай"):
        pet = add_pet(client, headers, type=pet_type)
        r = client.get("/recommendation/food", params={"pet_id": pet["id"]}, headers=headers)
        assert r.status_code == 400
        assert r.json()["detail"] == "Pet type must be cat or dog for recommendations"


def test_foreign_pet_not_found(client, register):
    _, alice = register("alice@example.com")
    _, bob = register("bob@example.com")
    pet = add_pet(client, alice, type="кошка")
    assert client.get("/recommendation/food", params={"pet_id": pet["id"]}, headers=bob).status_code == 404
    assert client.get("/recommendation/goods", params={"pet_id": pet["id"]}, headers=bob).status_code == 404


def test_invalid_goods_kind(client, register):
    _, headers = register()
    pet = add_pet(client, headers, type="кошка")
    assert client.get("/recommendation/goods", params={"pet_id": pet["id"], "kind": "food"}, headers=headers).status_code == 422


def test_diet_fields_only_for_vet_visit(client, register):
    _, headers = register()
    base = {"name": "Корм", "date": at(-1)}
    assert client.post("/prop/add", json={**base, "category": "food", "diet_tags": ["renal"]}, headers=headers).status_code == 422
    assert client.post("/prop/add", json={**base, "diet_exclude": ["fish"]}, headers=headers).status_code == 422
    assert client.post("/prop/add", json={**base, "category": "vet_visit", "diet_tags": ["magic"]}, headers=headers).status_code == 422
    r = client.post("/prop/add", json={**base, "category": "vet_visit", "diet_tags": ["renal", "renal"], "diet_exclude": ["fish"]}, headers=headers)
    assert r.status_code == 201
    assert r.json()["diet_tags"] == ["renal"] and r.json()["diet_exclude"] == ["fish"]
