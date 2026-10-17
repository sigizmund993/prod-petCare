-- Пустой номер считаем отсутствующим, иначе пустые строки конфликтуют между собой
UPDATE users SET phone_number = NULL WHERE trim(phone_number) = '';

-- NULL не участвует в уникальности: пользователей без номера может быть сколько угодно
CREATE UNIQUE INDEX IF NOT EXISTS users_phone_number_key ON users (phone_number);
