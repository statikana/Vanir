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

CREATE TABLE item_info (
    item_id BIGINT NOT NULL,
    item_name TEXT NOT NULL,
    asset_path TEXT NOT NULL,
    PRIMARY KEY (item_id)
);

CREATE TABLE inventory_data (
    item_id BIGINT NOT NULL,
    owner_id BIGINT NOT NULL,
    count BIGINT NOT NULL DEFAULT 0,
    FOREIGN KEY (owner_id) REFERENCES currency_data(user_id) ON DELETE CASCADE,
    FOREIGN KEY (item_id) REFERENCES item_info(item_id),
    PRIMARY KEY (item_id, owner_id)
);