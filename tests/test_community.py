def make_community(client, headers, name="Любители котов", description="Всё о котах"):
    return client.post("/community/add", json={"name": name, "description": description}, headers=headers).json()


def test_create_community_owner_is_member(client, register):
    user, headers = register()
    r = client.post("/community/add", json={"name": "  Любители котов  "}, headers=headers)
    assert r.status_code == 201
    c = r.json()
    assert c["name"] == "Любители котов" and c["description"] is None
    assert c["owner_id"] == user["id"] and c["member_ids"] == [user["id"]]
    assert client.get("/community/get", params={"community_id": c["id"]}, headers=headers).json() == c


def test_empty_name_rejected(client, register):
    _, headers = register()
    assert client.post("/community/add", json={"name": "   "}, headers=headers).status_code == 422


def test_list_is_open_with_search_and_mine(client, register):
    _, alice_h = register("alice@example.com")
    _, bob_h = register("bob@example.com")
    cats = make_community(client, alice_h, "Любители КОТОВ")
    dogs = make_community(client, bob_h, "Собачники")

    assert [c["id"] for c in client.get("/community/list", headers=alice_h).json()] == [cats["id"], dogs["id"]]
    assert [c["id"] for c in client.get("/community/list", params={"q": "котов"}, headers=bob_h).json()] == [cats["id"]]
    assert [c["id"] for c in client.get("/community/list", params={"mine": True}, headers=bob_h).json()] == [dogs["id"]]


def test_join_is_idempotent_and_members_list(client, register):
    alice, alice_h = register("alice@example.com", name="Алиса")
    bob, bob_h = register("bob@example.com", name="Боб")
    c = make_community(client, alice_h)

    for _ in range(2):
        r = client.post("/community/join", params={"community_id": c["id"]}, headers=bob_h)
        assert r.status_code == 200
        assert r.json()["member_ids"] == [alice["id"], bob["id"]]

    members = client.get("/community/members", params={"community_id": c["id"]}, headers=bob_h).json()
    assert members == [{"id": alice["id"], "name": "Алиса"}, {"id": bob["id"], "name": "Боб"}]


def test_unknown_community_404(client, register):
    _, headers = register()
    for method, path in [("get", "/community/get"), ("post", "/community/join"), ("get", "/community/members")]:
        assert client.request(method, path, params={"community_id": 999}, headers=headers).status_code == 404


def test_only_owner_edits_and_deletes(client, register):
    _, alice_h = register("alice@example.com")
    _, bob_h = register("bob@example.com")
    c = make_community(client, alice_h)
    client.post("/community/join", params={"community_id": c["id"]}, headers=bob_h)
    p = {"community_id": c["id"]}

    assert client.put("/community/edit", params=p, json={"name": "Хак"}, headers=bob_h).status_code == 403
    assert client.delete("/community/del", params=p, headers=bob_h).status_code == 403

    r = client.put("/community/edit", params=p, json={"name": "Кошатники", "description": "Новое"}, headers=alice_h)
    assert r.status_code == 200 and r.json()["name"] == "Кошатники" and r.json()["description"] == "Новое"

    client.post("/message/add", params=p, json={"text": "Привет"}, headers=bob_h)
    assert client.delete("/community/del", params=p, headers=alice_h).status_code == 204
    assert client.get("/community/get", params=p, headers=alice_h).status_code == 404


def test_leave_passes_ownership_and_last_member_deletes(client, register):
    _, alice_h = register("alice@example.com")
    bob, bob_h = register("bob@example.com")
    c = make_community(client, alice_h)
    p = {"community_id": c["id"]}
    client.post("/community/join", params=p, headers=bob_h)

    assert client.post("/community/leave", params=p, headers=alice_h).status_code == 204
    got = client.get("/community/get", params=p, headers=bob_h).json()
    assert got["owner_id"] == bob["id"] and got["member_ids"] == [bob["id"]]

    assert client.post("/community/leave", params=p, headers=alice_h).status_code == 403  # уже не участник
    client.post("/community/leave", params=p, headers=bob_h)
    assert client.get("/community/get", params=p, headers=bob_h).status_code == 404


def test_kick(client, register):
    alice, alice_h = register("alice@example.com")
    bob, bob_h = register("bob@example.com")
    c = make_community(client, alice_h)
    p = {"community_id": c["id"]}
    client.post("/community/join", params=p, headers=bob_h)

    assert client.post("/community/kick", params={**p, "member_id": alice["id"]}, headers=bob_h).status_code == 403
    assert client.post("/community/kick", params={**p, "member_id": alice["id"]}, headers=alice_h).status_code == 400
    assert client.post("/community/kick", params={**p, "member_id": 999}, headers=alice_h).status_code == 404
    assert client.post("/community/kick", params={**p, "member_id": bob["id"]}, headers=alice_h).status_code == 204
    assert client.get("/community/get", params=p, headers=alice_h).json()["member_ids"] == [alice["id"]]
    assert client.get("/message/list", params=p, headers=bob_h).status_code == 403


def test_delete_user_passes_ownership_and_keeps_messages(client, register):
    _, alice_h = register("alice@example.com")
    bob, bob_h = register("bob@example.com")
    shared = make_community(client, alice_h, "Общее")
    alone = make_community(client, alice_h, "Только Алисы")
    p = {"community_id": shared["id"]}
    client.post("/community/join", params=p, headers=bob_h)
    client.post("/message/add", params=p, json={"text": "Пока!"}, headers=alice_h)

    assert client.delete("/user/del", headers=alice_h).status_code == 204

    got = client.get("/community/get", params=p, headers=bob_h).json()
    assert got["owner_id"] == bob["id"] and got["member_ids"] == [bob["id"]]
    assert client.get("/community/get", params={"community_id": alone["id"]}, headers=bob_h).status_code == 404
    [msg] = client.get("/message/list", params=p, headers=bob_h).json()
    assert msg["text"] == "Пока!" and msg["from_id"] is None and msg["from_name"] is None


def test_requires_token(client):
    assert client.get("/community/list").status_code in (401, 403)
