CREATE TABLE starboard_data (
    guild_id BIGINT NOT NULL,
    channel_id BIGINT,
    threshold INT,
    PRIMARY KEY (guild_id)
);

CREATE TABLE starboard_posts (
    original_id BIGINT NOT NULL,
    starboard_post_id BIGINT,
    guild_id BIGINT NOT NULL,
    user_id BIGINT NOT NULL,
    n_stars INT NOT NULL DEFAULT 0,
    FOREIGN KEY (guild_id) REFERENCES starboard_data(guild_id) ON DELETE CASCADE,
    PRIMARY KEY (original_id)
);

CREATE TABLE currency_data (
    user_id BIGINT NOT NULL,
    balance BIGINT NOT NULL,
    CONSTRAINT positive_balance CHECK (balance >= 0),
    PRIMARY KEY (user_id)
);

CREATE TABLE todo_data (
    user_id BIGINT NOT NULL,
    title TEXT NOT NULL,
    completed BOOLEAN NOT NULL DEFAULT FALSE,
    timestamp_created TIMESTAMP NOT NULL DEFAULT current_timestamp,
    todo_id SERIAL,
    PRIMARY KEY (user_id, title)
);

CREATE TABLE tlinks (
    guild_id BIGINT NOT NULL,
    from_channel_id BIGINT NOT NULL,
    to_channel_id BIGINT NOT NULL,
    from_lang_code VARCHAR(2),
    to_lang_code VARCHAR(2) NOT NULL,
    PRIMARY KEY (from_channel_id, to_channel_id)
);

-- all completed status trackers
CREATE TABLE status_ranges (
    user_id BIGINT NOT NULL,
    status_type VARCHAR(8) NOT NULL,
    start_time TIMESTAMP NOT NULL,
    end_time TIMESTAMP NOT NULL,
    PRIMARY KEY (user_id, status_type, start_time)
);

-- user changed their status, but it is not yet comfirmed how long this
-- status will last
-- waiting for another change to complete it, then will be moved to status_ranges
-- with the end_time set
CREATE TABLE status_trackers (
    user_id BIGINT NOT NULL,
    status_type VARCHAR(8) NOT NULL,
    start_time TIMESTAMP NOT NULL,
    PRIMARY KEY (user_id, status_type, start_time)
);