ALTER TABLE users ADD COLUMN IF NOT EXISTS email_verified BOOLEAN NOT NULL DEFAULT FALSE;

-- Один активный код подтверждения на пользователя; храним только хэш
CREATE TABLE IF NOT EXISTS email_codes (
    user_id    BIGINT PRIMARY KEY REFERENCES users (id) ON DELETE CASCADE,
    code_hash  TEXT NOT NULL,
    expires_at TIMESTAMPTZ NOT NULL,
    sent_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    attempts   INT NOT NULL DEFAULT 0
);
