-- Привязка Telegram: chat_id приходит боту, когда пользователь жмёт Start по ссылке с сайта
ALTER TABLE users
    ADD COLUMN IF NOT EXISTS telegram_chat_id BIGINT UNIQUE,
    ADD COLUMN IF NOT EXISTS telegram_linked_at TIMESTAMPTZ;

-- Одноразовый код из ссылки t.me/<бот>?start=<код>; храним только хэш
CREATE TABLE IF NOT EXISTS telegram_link_codes (
    code_hash  TEXT PRIMARY KEY,
    user_id    BIGINT NOT NULL UNIQUE REFERENCES users (id) ON DELETE CASCADE,
    expires_at TIMESTAMPTZ NOT NULL
);

-- Какое срабатывание записи и какой день рождения уже отправлены в Telegram (как notification_reads и birthday_reads)
CREATE TABLE IF NOT EXISTS telegram_sent (
    user_id   BIGINT NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    prop_id   BIGINT NOT NULL REFERENCES props (id) ON DELETE CASCADE,
    sent_date TIMESTAMPTZ NOT NULL,
    PRIMARY KEY (user_id, prop_id)
);

CREATE TABLE IF NOT EXISTS telegram_birthday_sent (
    user_id   BIGINT NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    pet_id    BIGINT NOT NULL REFERENCES pets (id) ON DELETE CASCADE,
    sent_date DATE NOT NULL,
    PRIMARY KEY (user_id, pet_id)
);
