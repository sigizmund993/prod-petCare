-- Открытые сообщества: список виден всем, читать и писать сообщения могут только участники.
-- owner_id = NULL только на время удаления владельца: delete_user сразу передаёт сообщество
-- первому из оставшихся участников или удаляет его, если участников не осталось
CREATE TABLE IF NOT EXISTS communities (
    id          BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    name        TEXT NOT NULL,
    description TEXT,
    owner_id    BIGINT REFERENCES users (id) ON DELETE SET NULL,
    member_ids  BIGINT[] NOT NULL DEFAULT '{}',
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS communities_member_ids_idx ON communities USING GIN (member_ids);

-- Сообщения удалённого пользователя остаются, from_id становится NULL
CREATE TABLE IF NOT EXISTS messages (
    id           BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    text         TEXT NOT NULL,
    from_id      BIGINT REFERENCES users (id) ON DELETE SET NULL,
    community_id BIGINT NOT NULL REFERENCES communities (id) ON DELETE CASCADE,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    edited_at    TIMESTAMPTZ
);

-- Лента сообщества читается по id (курсоры before_id / after_id)
CREATE INDEX IF NOT EXISTS messages_community_id_idx ON messages (community_id, id);
