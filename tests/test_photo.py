PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 16
JPEG = b"\xff\xd8\xff\xe0" + b"\x00" * 16


def _pet(client, headers) -> int:
    return client.post("/pet/add", json={"name": "Барсик"}, headers=headers).json()["id"]


def _upload(client, headers, pet_id, content=PNG, content_type="image/png"):
    return client.post(f"/pets/{pet_id}/photo", files={"file": ("p", content, content_type)}, headers=headers)


def test_upload_get_and_replace_photo(client, register):
    _, headers = register()
    pet_id = _pet(client, headers)
    assert client.get("/pet/get", params={"pet_id": pet_id}, headers=headers).json()["has_picture"] is False

    r = _upload(client, headers, pet_id)
    assert r.status_code == 200
    assert r.json() == {"pet_id": pet_id, "photo_url": f"/pets/{pet_id}/photo"}
    assert client.get("/pet/get", params={"pet_id": pet_id}, headers=headers).json()["has_picture"] is True

    got = client.get(f"/pets/{pet_id}/photo", headers=headers)
    assert got.status_code == 200
    assert got.content == PNG and got.headers["content-type"] == "image/png"

    # новая загрузка заменяет старую
    _upload(client, headers, pet_id, JPEG, "image/jpeg")
    got = client.get(f"/pets/{pet_id}/photo", headers=headers)
    assert got.content == JPEG and got.headers["content-type"] == "image/jpeg"


def test_edit_pet_keeps_photo(client, register):
    _, headers = register()
    pet_id = _pet(client, headers)
    _upload(client, headers, pet_id)
    pet = client.put("/pet/edit", params={"pet_id": pet_id}, json={"name": "Мурзик"}, headers=headers).json()
    assert pet["has_picture"] is True


def test_delete_photo(client, register):
    _, headers = register()
    pet_id = _pet(client, headers)
    _upload(client, headers, pet_id)
    assert client.delete(f"/pets/{pet_id}/photo", headers=headers).status_code == 204
    assert client.get(f"/pets/{pet_id}/photo", headers=headers).status_code == 404
    assert client.get("/pet/get", params={"pet_id": pet_id}, headers=headers).json()["has_picture"] is False


def test_photo_rejects_bad_files(client, register):
    _, headers = register()
    pet_id = _pet(client, headers)
    assert _upload(client, headers, pet_id, b"GIF89a", "image/gif").status_code == 400
    assert _upload(client, headers, pet_id, b"", "image/png").status_code == 400
    assert _upload(client, headers, pet_id, b"not a png", "image/png").status_code == 400
    assert _upload(client, headers, pet_id, PNG + b"\x00" * (5 * 1024 * 1024), "image/png").status_code == 413


def test_photo_of_foreign_pet_is_not_found(client, register):
    _, owner = register()
    _, stranger = register("stranger@example.com")
    pet_id = _pet(client, owner)
    _upload(client, owner, pet_id)
    assert _upload(client, stranger, pet_id).status_code == 404
    assert client.get(f"/pets/{pet_id}/photo", headers=stranger).status_code == 404
    assert client.delete(f"/pets/{pet_id}/photo", headers=stranger).status_code == 404


def test_photo_requires_token(client, register):
    _, headers = register()
    pet_id = _pet(client, headers)
    assert client.get(f"/pets/{pet_id}/photo").status_code in (401, 403)
