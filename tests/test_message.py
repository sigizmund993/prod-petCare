import pytest


@pytest.fixture
def chat(client, register):
    # Алиса — владелец, Боб — участник, Ева — не участник
    alice, alice_h = register("alice@example.com", name="Алиса")
    bob, bob_h = register("bob@example.com", name="Боб")
    _, eve_h = register("eve@example.com", name="Ева")
    c = client.post("/community/add", json={"name": "Кошатники"}, headers=alice_h).json()
    client.post("/community/join", params={"community_id": c["id"]}, headers=bob_h)
    return {"id": c["id"], "alice": (alice, alice_h), "bob": (bob, bob_h), "eve_h": eve_h}


def send(client, chat, headers, text):
    return client.post("/message/add", params={"community_id": chat["id"]}, json={"text": text}, headers=headers)


def messages(client, chat, headers, **params):
    return client.get("/message/list", params={"community_id": chat["id"], **params}, headers=headers)


def test_send_and_list(client, chat):
    bob, bob_h = chat["bob"]
    r = send(client, chat, bob_h, "  Привет!  ")
    assert r.status_code == 201
    m = r.json()
    assert m["text"] == "Привет!" and m["community_id"] == chat["id"]
    assert m["from_id"] == bob["id"] and m["from_name"] == "Боб"
    assert m["created_at"] and m["edited_at"] is None
    assert messages(client, chat, chat["alice"][1]).json() == [m]


def test_empty_or_too_long_text_rejected(client, chat):
    _, bob_h = chat["bob"]
    assert send(client, chat, bob_h, "   ").status_code == 422
    assert send(client, chat, bob_h, "x" * 4001).status_code == 422


def test_non_member_cannot_read_or_write(client, chat):
    assert send(client, chat, chat["eve_h"], "Я тут").status_code == 403
    assert messages(client, chat, chat["eve_h"]).status_code == 403
    assert client.get("/message/list", params={"community_id": 999}, headers=chat["eve_h"]).status_code == 404


def test_pagination(client, chat):
    _, bob_h = chat["bob"]
    ids = [send(client, chat, bob_h, f"m{i}").json()["id"] for i in range(5)]

    assert [m["id"] for m in messages(client, chat, bob_h, limit=2).json()] == ids[3:]
    assert [m["id"] for m in messages(client, chat, bob_h, limit=2, before_id=ids[3]).json()] == ids[1:3]
    assert [m["id"] for m in messages(client, chat, bob_h, after_id=ids[2]).json()] == ids[3:]
    assert messages(client, chat, bob_h, after_id=ids[4]).json() == []
    assert messages(client, chat, bob_h, before_id=ids[3], after_id=ids[1]).status_code == 400
    assert messages(client, chat, bob_h, limit=101).status_code == 422


def test_only_author_edits(client, chat):
    _, alice_h = chat["alice"]
    _, bob_h = chat["bob"]
    m = send(client, chat, bob_h, "Опечатка").json()
    p = {"message_id": m["id"]}

    assert client.put("/message/edit", params=p, json={"text": "Чужое"}, headers=alice_h).status_code == 403
    assert client.put("/message/edit", params=p, json={"text": "x"}, headers=chat["eve_h"]).status_code == 404

    r = client.put("/message/edit", params=p, json={"text": "Исправил"}, headers=bob_h)
    assert r.status_code == 200
    assert r.json()["text"] == "Исправил" and r.json()["edited_at"] is not None
    assert r.json()["created_at"] == m["created_at"]


def test_delete_by_author_or_owner(client, chat):
    _, alice_h = chat["alice"]
    _, bob_h = chat["bob"]
    by_alice = send(client, chat, alice_h, "От владельца").json()
    by_bob_1 = send(client, chat, bob_h, "Раз").json()
    by_bob_2 = send(client, chat, bob_h, "Два").json()

    assert client.delete("/message/del", params={"message_id": by_alice["id"]}, headers=bob_h).status_code == 403
    assert client.delete("/message/del", params={"message_id": by_bob_1["id"]}, headers=chat["eve_h"]).status_code == 404
    assert client.delete("/message/del", params={"message_id": by_bob_1["id"]}, headers=bob_h).status_code == 204
    assert client.delete("/message/del", params={"message_id": by_bob_2["id"]}, headers=alice_h).status_code == 204
    assert [m["id"] for m in messages(client, chat, alice_h).json()] == [by_alice["id"]]
