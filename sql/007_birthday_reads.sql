-- В какой день рождения питомца пользователь уже прочитал уведомление
CREATE TABLE IF NOT EXISTS birthday_reads (
    user_id   BIGINT NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    pet_id    BIGINT NOT NULL REFERENCES pets (id) ON DELETE CASCADE,
    read_date DATE NOT NULL,
    PRIMARY KEY (user_id, pet_id)
);
