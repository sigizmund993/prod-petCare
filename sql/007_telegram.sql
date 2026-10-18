-- Привязка Telegram: chat_id приходит боту, когда пользователь жмёт Start по ссылке с сайта
ALTER TABLE users ADD COLUMN IF NOT EXISTS telegram_chat_id BIGINT UNIQUE;

-- Одноразовый код из ссылки t.me/<бот>?start=<код>; храним только хэш
CREATE TABLE IF NOT EXISTS telegram_link_codes (
    code_hash  TEXT PRIMARY KEY,
    user_id    BIGINT NOT NULL UNIQUE REFERENCES users (id) ON DELETE CASCADE,
    expires_at TIMESTAMPTZ NOT NULL
);
