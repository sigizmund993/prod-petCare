from tests.conftest import code_from

USER = {"email": "ivan@example.com", "passwd": "secret", "name": "Иван"}


def test_registration_sends_code_and_verify_logs_in(client, mailbox):
    r = client.post("/user/add", json=USER)
    assert r.status_code == 201
    assert r.json()["email_verified"] is False
    assert "passwd" not in r.json()
    assert len(mailbox) == 1 and mailbox[0]["to"] == USER["email"]

    r = client.post("/user/verify", json={"email": USER["email"], "code": code_from(mailbox[0])})
    assert r.status_code == 200
    headers = {"Authorization": f"Bearer {r.json()['access_token']}"}

    me = client.get("/user/me", headers=headers).json()
    assert me["email"] == USER["email"] and me["email_verified"] is True


def test_login_requires_verified_email(client, mailbox):
    client.post("/user/add", json=USER)
    r = client.post("/user/login", json={"email": USER["email"], "passwd": USER["passwd"]})
    assert r.status_code == 403
    assert r.json()["detail"] == "Email not verified"


def test_login_after_verification(client, register):
    register(USER["email"], USER["passwd"])
    r = client.post("/user/login", json={"email": USER["email"], "passwd": USER["passwd"]})
    assert r.status_code == 200
    assert r.json()["token_type"] == "bearer"


def test_login_wrong_password_or_unknown_email(client, register):
    register(USER["email"], USER["passwd"])
    assert client.post("/user/login", json={"email": USER["email"], "passwd": "wrong"}).status_code == 401
    assert client.post("/user/login", json={"email": "nobody@example.com", "passwd": "x"}).status_code == 401


def test_duplicate_email_conflict(client, mailbox):
    client.post("/user/add", json=USER)
    r = client.post("/user/add", json=USER)
    assert r.status_code == 409
    assert r.json()["detail"] == "Email already registered"


def test_duplicate_phone_conflict(client, mailbox):
    client.post("/user/add", json={**USER, "phone_number": "+79990000000"})
    r = client.post("/user/add", json={**USER, "email": "other@example.com", "phone_number": "+79990000000"})
    assert r.status_code == 409
    assert r.json()["detail"] == "Phone number already registered"


def test_empty_phone_is_null_and_not_unique(client, mailbox):
    a = client.post("/user/add", json={**USER, "phone_number": ""})
    b = client.post("/user/add", json={**USER, "email": "other@example.com", "phone_number": ""})
    assert a.status_code == b.status_code == 201
    assert a.json()["phone_number"] is None and b.json()["phone_number"] is None


def test_registration_validation_error(client):
    r = client.post("/user/add", json={"email": "a@b.c"})
    assert r.status_code == 422


def test_wrong_code_rejected(client, mailbox):
    client.post("/user/add", json=USER)
    real = code_from(mailbox[0])
    wrong = "000000" if real != "000000" else "111111"
    r = client.post("/user/verify", json={"email": USER["email"], "code": wrong})
    assert r.status_code == 400


def test_code_blocked_after_max_attempts(client, mailbox):
    client.post("/user/add", json=USER)
    real = code_from(mailbox[0])
    wrong = "000000" if real != "000000" else "111111"
    for _ in range(5):
        client.post("/user/verify", json={"email": USER["email"], "code": wrong})
    # Попытки кончились — даже правильный код больше не принимается
    r = client.post("/user/verify", json={"email": USER["email"], "code": real})
    assert r.status_code == 400


def test_expired_code_rejected(client, mailbox, sql):
    client.post("/user/add", json=USER)
    sql("UPDATE email_codes SET expires_at = now() - interval '1 minute'")
    r = client.post("/user/verify", json={"email": USER["email"], "code": code_from(mailbox[0])})
    assert r.status_code == 400


def test_resend_is_rate_limited(client, mailbox, sql):
    client.post("/user/add", json=USER)
    assert client.post("/user/verify/resend", json={"email": USER["email"]}).status_code == 204
    assert len(mailbox) == 1  # прошло меньше минуты — новый код не отправлен

    sql("UPDATE email_codes SET sent_at = now() - interval '2 minutes'")
    client.post("/user/verify/resend", json={"email": USER["email"]})
    assert len(mailbox) == 2
    # Старый код после повторной отправки не работает (если случайно не совпал с новым)
    old, new = code_from(mailbox[0]), code_from(mailbox[1])
    if old != new:
        assert client.post("/user/verify", json={"email": USER["email"], "code": old}).status_code == 400
    assert client.post("/user/verify", json={"email": USER["email"], "code": new}).status_code == 200


def test_resend_does_not_reveal_unknown_email(client, mailbox):
    r = client.post("/user/verify/resend", json={"email": "nobody@example.com"})
    assert r.status_code == 204
    assert mailbox == []


def test_protected_endpoints_require_token(client):
    assert client.get("/user/me").status_code in (401, 403)
    assert client.get("/user/me", headers={"Authorization": "Bearer garbage"}).status_code == 401


def test_edit_email_resets_verification(client, register, mailbox):
    _, headers = register(USER["email"])
    new = {**USER, "email": "new@example.com"}
    r = client.put("/user/edit", json=new, headers=headers)
    assert r.status_code == 200
    assert r.json()["email_verified"] is False
    assert mailbox[-1]["to"] == "new@example.com"


def test_edit_same_email_keeps_verification(client, register):
    _, headers = register(USER["email"])
    r = client.put("/user/edit", json={**USER, "name": "Пётр"}, headers=headers)
    assert r.json()["name"] == "Пётр"
    assert r.json()["email_verified"] is True


def test_edit_to_taken_email_conflict(client, register):
    register("other@example.com")
    _, headers = register(USER["email"])
    r = client.put("/user/edit", json={**USER, "email": "other@example.com"}, headers=headers)
    assert r.status_code == 409


def test_delete_user_removes_only_orphaned_data(client, register):
    _, alice_h = register("alice@example.com")
    bob, bob_h = register("bob@example.com")
    shared = client.post("/pet/add", json={"name": "Общий", "own_ids": [bob["id"]]}, headers=alice_h).json()
    client.post("/pet/add", json={"name": "Только Алисы"}, headers=alice_h)
    own_prop = client.post("/prop/add", json={"name": "Прививка", "date": "2026-01-01T00:00:00Z"}, headers=alice_h).json()
    client.put("/pet/edit", params={"pet_id": shared["id"]}, json={"name": "Общий", "own_ids": [bob["id"]], "prop_ids": [own_prop["id"]]}, headers=alice_h)

    assert client.delete("/user/del", headers=alice_h).status_code == 204

    pets = client.get("/pet/list", headers=bob_h).json()
    assert [p["id"] for p in pets] == [shared["id"]]
    assert pets[0]["own_ids"] == [bob["id"]]
    assert pets[0]["prop_ids"] == []  # запись Алисы осталась без владельцев и удалена
    assert client.get("/user/me", headers=alice_h).status_code == 404
