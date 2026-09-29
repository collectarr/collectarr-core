-- Install before creating the flattened catalog GIN indexes below.
CREATE EXTENSION IF NOT EXISTS pg_trgm;

CREATE INDEX IF NOT EXISTS ix_anime_items_title_trgm
    ON anime_items USING gin (title gin_trgm_ops);
CREATE INDEX IF NOT EXISTS ix_anime_items_sort_key_trgm
    ON anime_items USING gin (sort_key gin_trgm_ops);

CREATE INDEX IF NOT EXISTS ix_boardgame_items_title_trgm
    ON boardgame_items USING gin (title gin_trgm_ops);
CREATE INDEX IF NOT EXISTS ix_boardgame_items_sort_key_trgm
    ON boardgame_items USING gin (sort_key gin_trgm_ops);

CREATE INDEX IF NOT EXISTS ix_book_items_title_trgm
    ON book_items USING gin (title gin_trgm_ops);
CREATE INDEX IF NOT EXISTS ix_book_items_sort_key_trgm
    ON book_items USING gin (sort_key gin_trgm_ops);

CREATE INDEX IF NOT EXISTS ix_comic_items_title_trgm
    ON comic_items USING gin (title gin_trgm_ops);
CREATE INDEX IF NOT EXISTS ix_comic_items_sort_key_trgm
    ON comic_items USING gin (sort_key gin_trgm_ops);

CREATE INDEX IF NOT EXISTS ix_game_items_title_trgm
    ON game_items USING gin (title gin_trgm_ops);
CREATE INDEX IF NOT EXISTS ix_game_items_sort_key_trgm
    ON game_items USING gin (sort_key gin_trgm_ops);

CREATE INDEX IF NOT EXISTS ix_manga_items_title_trgm
    ON manga_items USING gin (title gin_trgm_ops);
CREATE INDEX IF NOT EXISTS ix_manga_items_sort_key_trgm
    ON manga_items USING gin (sort_key gin_trgm_ops);

CREATE INDEX IF NOT EXISTS ix_movie_items_title_trgm
    ON movie_items USING gin (title gin_trgm_ops);
CREATE INDEX IF NOT EXISTS ix_movie_items_sort_key_trgm
    ON movie_items USING gin (sort_key gin_trgm_ops);

CREATE INDEX IF NOT EXISTS ix_music_items_title_trgm
    ON music_items USING gin (title gin_trgm_ops);
CREATE INDEX IF NOT EXISTS ix_music_items_sort_title_trgm
    ON music_items USING gin (sort_title gin_trgm_ops);
CREATE INDEX IF NOT EXISTS ix_music_items_artist_trgm
    ON music_items USING gin (artist gin_trgm_ops);
CREATE INDEX IF NOT EXISTS ix_music_items_label_trgm
    ON music_items USING gin (label gin_trgm_ops);

CREATE INDEX IF NOT EXISTS ix_tv_items_title_trgm
    ON tv_items USING gin (title gin_trgm_ops);
CREATE INDEX IF NOT EXISTS ix_tv_items_sort_key_trgm
    ON tv_items USING gin (sort_key gin_trgm_ops);
