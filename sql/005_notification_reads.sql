-- Какое срабатывание записи пользователь уже прочитал (у каждого владельца своё)
CREATE TABLE IF NOT EXISTS notification_reads (
    user_id   BIGINT NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    prop_id   BIGINT NOT NULL REFERENCES props (id) ON DELETE CASCADE,
    read_date TIMESTAMPTZ NOT NULL,
    PRIMARY KEY (user_id, prop_id)
);
