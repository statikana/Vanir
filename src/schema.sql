CREATE TABLE IF NOT EXISTS starboard_data (
    guild_id BIGINT PRIMARY KEY NOT NULL, -- what guild the data belongs to
    channel_id BIGINT, -- the channel that the starboard is connected to, can be null
    threshold INT -- the number of stars needed to post a message in the starboard
);

CREATE TABLE IF NOT EXISTS starboard_posts (
    starboard_post_id BIGINT, -- the bot's post in the starboard channel - may be null if n_stars < threshold
    guild_id BIGINT NOT NULL,
    original_id BIGINT UNIQUE NOT NULL, -- id of the post which has the stars
    user_id BIGINT NOT NULL, -- the author of the original post
    n_stars INT NOT NULL DEFAULT 0, -- the number of stars the original post has
    FOREIGN KEY (guild_id) REFERENCES starboard_data(guild_id) ON DELETE CASCADE,
    PRIMARY KEY (original_id)
);

