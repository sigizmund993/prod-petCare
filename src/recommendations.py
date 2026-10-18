from datetime import date

# Свойства товаров и предрасположенности пород — общий словарь тегов
TAG_LABELS = {
    "hypoallergenic": "гипоаллергенный",
    "sensitive_digestion": "чувствительное пищеварение",
    "weight_control": "контроль веса",
    "sterilised": "для стерилизованных",
    "urinary": "здоровье мочевыводящих путей",
    "renal": "поддержка почек",
    "dental": "здоровье зубов",
    "joint": "здоровье суставов",
    "hairball": "вывод шерсти",
    "skin_coat": "кожа и шерсть",
    "long_coat": "уход за длинной шерстью",
    "brachycephalic": "для коротких морд",
    "active": "активные игры",
    "intellectual": "развивающие",
    "chewer": "для любителей грызть",
}

INGREDIENT_LABELS = {
    "chicken": "курица",
    "turkey": "индейка",
    "beef": "говядина",
    "lamb": "ягнёнок",
    "fish": "рыба",
    "grain": "злаки",
    "rice": "рис",
    "dairy": "молочное",
}

AGE_LABELS = {"baby": "малыш", "adult": "взрослый", "senior": "пожилой"}

# pets.type — свободный текст, приводим его к виду из каталога
_SPECIES = {
    "cat": {"кошка", "кот", "котёнок", "котенок", "кошечка", "cat"},
    "dog": {"собака", "пёс", "пес", "щенок", "собачка", "dog"},
}
# С какого возраста животное считается пожилым
_SENIOR_FROM = {"cat": 10, "dog": 7}

# Баллы за совпадения: рекомендация врача важнее предрасположенности породы
VET_SCORE = 3
BREED_SCORE = 2
GI_SCORE = 2
TRIED_SCORE = 2
AGE_SCORE = 1
# Товар сделан именно для этого возраста, а не для нескольких
AGE_ONLY_SCORE = 2


def species_of(pet_type: str | None) -> str | None:
    value = (pet_type or "").strip().lower()
    return next((species for species, names in _SPECIES.items() if value in names), None)


def age_group(birth_date: date | None, species: str, today: date) -> str | None:
    if birth_date is None:
        return None
    years = today.year - birth_date.year - ((today.month, today.day) < (birth_date.month, birth_date.day))
    if years < 1:
        return "baby"
    return "senior" if years >= _SENIOR_FROM[species] else "adult"


def vet_advice(props: list[dict]) -> dict | None:
    # Действуют рекомендации последнего визита, где врач их оставил: более поздний визит отменяет прежние
    visits = [p for p in props if p["category"] == "vet_visit" and (p["diet_tags"] or p["diet_exclude"])]
    return max(visits, key=lambda p: p["date"]) if visits else None


def _fits(product: dict, species: str, age: str | None, size: str | None) -> bool:
    if product["species"] and species not in product["species"]:
        return False
    if age and product["age_groups"] and age not in product["age_groups"]:
        return False
    return not (size and product["sizes"] and size not in product["sizes"])


def recommend(pet: dict, products: list[dict], props: list[dict], breed: dict | None, today: date, limit: int) -> list[dict]:
    """Подбирает товары для питомца: жёсткий отбор, затем баллы с причинами.

    pet — питомец, products — каталог одного раздела (корма или товары), props — записи питомца,
    breed — найденная порода или None.
    """
    species = species_of(pet["type"])
    age = age_group(pet["birth_date"], species, today)
    size = breed["size"] if breed else None
    advice = vet_advice(props)
    vet_tags = set(advice["diet_tags"]) if advice else set()
    vet_exclude = set(advice["diet_exclude"]) if advice else set()

    # История питания: какие корма из каталога питомец уже пробовал и как
    foods = [p for p in props if p["category"] == "food"]
    rejected = {p["name"].strip().lower() for p in foods if p["suitable"] is False or "allergy" in p["reactions"]}
    allergic_names = {p["name"].strip().lower() for p in foods if "allergy" in p["reactions"]}
    allergens = {i for product in products if product["name"].strip().lower() in allergic_names for i in product["ingredients"]}
    had_gi = any("gi" in p["reactions"] for p in foods)
    good = {p["name"].strip().lower() for p in foods if p["suitable"] and p["liked"] is not False}

    result = []
    for product in products:
        name = product["name"].strip().lower()
        if not _fits(product, species, age, size) or name in rejected:
            continue
        ingredients = set(product["ingredients"])
        if ingredients & (vet_exclude | allergens):
            continue

        tags = set(product["tags"])
        score, reasons = 0, []
        for tag in sorted(tags & vet_tags):
            score += VET_SCORE
            reasons.append(f"рекомендовано ветеринаром: {TAG_LABELS[tag]}")
        if breed:
            for tag in sorted(tags & set(breed["tags"])):
                score += BREED_SCORE
                reasons.append(f"для породы {breed['name']}: {TAG_LABELS[tag]}")
        if had_gi and "sensitive_digestion" in tags:
            score += GI_SCORE
            reasons.append("были проблемы с ЖКТ: чувствительное пищеварение")
        if name in good:
            score += TRIED_SCORE
            reasons.append("уже подошёл питомцу")
        if age and product["age_groups"] == [age]:
            score += AGE_ONLY_SCORE
            reasons.append(f"специально для возраста: {AGE_LABELS[age]}")
        elif age and age in product["age_groups"]:
            score += AGE_SCORE
            reasons.append(f"по возрасту: {AGE_LABELS[age]}")
        if vet_exclude and ingredients:
            reasons.append("без исключённого врачом: " + ", ".join(INGREDIENT_LABELS[i] for i in sorted(vet_exclude)))
        if allergens and ingredients:
            reasons.append("без ингредиентов, на которые была аллергия: " + ", ".join(INGREDIENT_LABELS[i] for i in sorted(allergens)))

        result.append({**product, "score": score, "reasons": reasons})

    result.sort(key=lambda r: (-r["score"], r["name"]))
    return result[:limit]
