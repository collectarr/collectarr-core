-- One-way Anime and TV release-to-Catalog-Item backfills.
-- Run only against a reviewed, non-live copy of the pinned Core baseline.
-- Legacy sources remain unchanged until App and Sync migrate.

BEGIN;

CREATE TABLE IF NOT EXISTS anime_items (
    id uuid PRIMARY KEY, title varchar(255) NOT NULL, sort_key varchar(255),
    barcode varchar(100), catalog_number varchar(100), details jsonb NOT NULL,
    revision integer NOT NULL DEFAULT 1, created_at timestamptz NOT NULL,
    updated_at timestamptz NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_anime_items_title ON anime_items (title);
CREATE INDEX IF NOT EXISTS ix_anime_items_sort_key ON anime_items (sort_key);
CREATE INDEX IF NOT EXISTS ix_anime_items_barcode ON anime_items (barcode);
CREATE INDEX IF NOT EXISTS ix_anime_items_catalog_number ON anime_items (catalog_number);
CREATE TABLE IF NOT EXISTS anime_item_media (
    id uuid PRIMARY KEY, anime_item_id uuid NOT NULL REFERENCES anime_items(id) ON DELETE CASCADE,
    position integer NOT NULL, media_number integer, details jsonb NOT NULL,
    created_at timestamptz NOT NULL, updated_at timestamptz NOT NULL,
    CONSTRAINT uq_anime_item_media_position UNIQUE (anime_item_id, position)
);
CREATE INDEX IF NOT EXISTS ix_anime_item_media_number ON anime_item_media (anime_item_id, media_number);
CREATE TABLE IF NOT EXISTS anime_item_episodes (
    id uuid PRIMARY KEY, anime_item_id uuid NOT NULL REFERENCES anime_items(id) ON DELETE CASCADE,
    position integer NOT NULL, episode_number integer, title varchar(255), details jsonb NOT NULL,
    created_at timestamptz NOT NULL, updated_at timestamptz NOT NULL,
    CONSTRAINT uq_anime_item_episode_position UNIQUE (anime_item_id, position)
);
CREATE INDEX IF NOT EXISTS ix_anime_item_episodes_number ON anime_item_episodes (anime_item_id, episode_number);
CREATE TABLE IF NOT EXISTS anime_item_identifiers (
    id uuid PRIMARY KEY, anime_item_id uuid NOT NULL REFERENCES anime_items(id) ON DELETE CASCADE,
    identifier_type varchar(64) NOT NULL, value varchar(255) NOT NULL,
    normalized_value varchar(255) NOT NULL, is_primary boolean NOT NULL DEFAULT false,
    created_at timestamptz NOT NULL, updated_at timestamptz NOT NULL,
    CONSTRAINT uq_anime_item_identifier_normalized UNIQUE (anime_item_id, identifier_type, normalized_value)
);
CREATE INDEX IF NOT EXISTS ix_anime_item_identifiers_type_value ON anime_item_identifiers (identifier_type, normalized_value);
CREATE TABLE IF NOT EXISTS anime_item_legacy_identity_map (
    old_entity_type text NOT NULL, old_entity_id uuid NOT NULL,
    catalog_item_id uuid NOT NULL REFERENCES anime_items(id) ON DELETE CASCADE,
    resolution text NOT NULL, PRIMARY KEY (old_entity_type, old_entity_id, catalog_item_id)
);
CREATE TABLE IF NOT EXISTS anime_item_episode_identity_map (
    old_episode_id uuid NOT NULL, anime_item_id uuid NOT NULL REFERENCES anime_items(id) ON DELETE CASCADE,
    new_episode_id uuid NOT NULL REFERENCES anime_item_episodes(id) ON DELETE CASCADE,
    resolution text NOT NULL, PRIMARY KEY (old_episode_id, anime_item_id)
);
CREATE TABLE IF NOT EXISTS anime_item_migration_review (
    snapshot_id bigserial PRIMARY KEY, catalog_item_id uuid REFERENCES anime_items(id) ON DELETE SET NULL,
    source_table text NOT NULL, source_id uuid NOT NULL, legacy_payload jsonb NOT NULL
);

CREATE TABLE IF NOT EXISTS tv_items (
    id uuid PRIMARY KEY, title varchar(255) NOT NULL, sort_key varchar(255),
    barcode varchar(100), catalog_number varchar(100), details jsonb NOT NULL,
    revision integer NOT NULL DEFAULT 1, created_at timestamptz NOT NULL,
    updated_at timestamptz NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_tv_items_title ON tv_items (title);
CREATE INDEX IF NOT EXISTS ix_tv_items_sort_key ON tv_items (sort_key);
CREATE INDEX IF NOT EXISTS ix_tv_items_barcode ON tv_items (barcode);
CREATE INDEX IF NOT EXISTS ix_tv_items_catalog_number ON tv_items (catalog_number);
CREATE TABLE IF NOT EXISTS tv_item_seasons (
    id uuid PRIMARY KEY, tv_item_id uuid NOT NULL REFERENCES tv_items(id) ON DELETE CASCADE,
    season_number integer NOT NULL, title varchar(255), details jsonb NOT NULL,
    created_at timestamptz NOT NULL, updated_at timestamptz NOT NULL,
    CONSTRAINT uq_tv_item_season_number UNIQUE (tv_item_id, season_number)
);
CREATE TABLE IF NOT EXISTS tv_item_media (
    id uuid PRIMARY KEY, tv_item_id uuid NOT NULL REFERENCES tv_items(id) ON DELETE CASCADE,
    position integer NOT NULL, media_number integer, details jsonb NOT NULL,
    created_at timestamptz NOT NULL, updated_at timestamptz NOT NULL,
    CONSTRAINT uq_tv_item_media_position UNIQUE (tv_item_id, position)
);
CREATE INDEX IF NOT EXISTS ix_tv_item_media_number ON tv_item_media (tv_item_id, media_number);
CREATE TABLE IF NOT EXISTS tv_item_episodes (
    id uuid PRIMARY KEY, tv_item_id uuid NOT NULL REFERENCES tv_items(id) ON DELETE CASCADE,
    position integer NOT NULL, season_number integer, episode_number integer,
    title varchar(255), details jsonb NOT NULL, created_at timestamptz NOT NULL,
    updated_at timestamptz NOT NULL,
    CONSTRAINT uq_tv_item_episode_position UNIQUE (tv_item_id, position)
);
CREATE INDEX IF NOT EXISTS ix_tv_item_episodes_coordinates ON tv_item_episodes (tv_item_id, season_number, episode_number);
CREATE TABLE IF NOT EXISTS tv_item_identifiers (
    id uuid PRIMARY KEY, tv_item_id uuid NOT NULL REFERENCES tv_items(id) ON DELETE CASCADE,
    identifier_type varchar(64) NOT NULL, value varchar(255) NOT NULL,
    normalized_value varchar(255) NOT NULL, is_primary boolean NOT NULL DEFAULT false,
    created_at timestamptz NOT NULL, updated_at timestamptz NOT NULL,
    CONSTRAINT uq_tv_item_identifier_normalized UNIQUE (tv_item_id, identifier_type, normalized_value)
);
CREATE INDEX IF NOT EXISTS ix_tv_item_identifiers_type_value ON tv_item_identifiers (identifier_type, normalized_value);
CREATE TABLE IF NOT EXISTS tv_item_legacy_identity_map (
    old_entity_type text NOT NULL, old_entity_id uuid NOT NULL,
    catalog_item_id uuid NOT NULL REFERENCES tv_items(id) ON DELETE CASCADE,
    resolution text NOT NULL, PRIMARY KEY (old_entity_type, old_entity_id, catalog_item_id)
);
CREATE TABLE IF NOT EXISTS tv_item_season_identity_map (
    old_season_id uuid NOT NULL, tv_item_id uuid NOT NULL REFERENCES tv_items(id) ON DELETE CASCADE,
    new_season_id uuid NOT NULL REFERENCES tv_item_seasons(id) ON DELETE CASCADE,
    resolution text NOT NULL, PRIMARY KEY (old_season_id, tv_item_id)
);
CREATE TABLE IF NOT EXISTS tv_item_episode_identity_map (
    old_episode_id uuid NOT NULL, tv_item_id uuid NOT NULL REFERENCES tv_items(id) ON DELETE CASCADE,
    new_episode_id uuid NOT NULL REFERENCES tv_item_episodes(id) ON DELETE CASCADE,
    resolution text NOT NULL, PRIMARY KEY (old_episode_id, tv_item_id)
);
CREATE TABLE IF NOT EXISTS tv_item_migration_review (
    snapshot_id bigserial PRIMARY KEY, catalog_item_id uuid REFERENCES tv_items(id) ON DELETE SET NULL,
    source_table text NOT NULL, source_id uuid NOT NULL, legacy_payload jsonb NOT NULL
);

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM anime_items) OR EXISTS (SELECT 1 FROM anime_item_media)
       OR EXISTS (SELECT 1 FROM anime_item_episodes) OR EXISTS (SELECT 1 FROM anime_item_identifiers)
       OR EXISTS (SELECT 1 FROM anime_item_legacy_identity_map)
       OR EXISTS (SELECT 1 FROM anime_item_episode_identity_map)
       OR EXISTS (SELECT 1 FROM anime_item_migration_review)
       OR EXISTS (SELECT 1 FROM tv_items) OR EXISTS (SELECT 1 FROM tv_item_seasons)
       OR EXISTS (SELECT 1 FROM tv_item_media) OR EXISTS (SELECT 1 FROM tv_item_episodes)
       OR EXISTS (SELECT 1 FROM tv_item_identifiers)
       OR EXISTS (SELECT 1 FROM tv_item_legacy_identity_map)
       OR EXISTS (SELECT 1 FROM tv_item_season_identity_map)
       OR EXISTS (SELECT 1 FROM tv_item_episode_identity_map)
       OR EXISTS (SELECT 1 FROM tv_item_migration_review) THEN
        RAISE EXCEPTION 'Anime/TV Catalog Item destinations must be empty';
    END IF;
    IF EXISTS (SELECT 1 FROM anime_releases r LEFT JOIN anime_series s ON s.id = r.work_id WHERE s.id IS NULL)
       OR EXISTS (SELECT 1 FROM tv_releases r LEFT JOIN tv_series s ON s.id = r.series_id WHERE s.id IS NULL) THEN
        RAISE EXCEPTION 'Anime/TV Catalog Item backfill found a release without a series';
    END IF;
    IF EXISTS (
        SELECT 1 FROM anime_series s WHERE NOT EXISTS (SELECT 1 FROM anime_releases r WHERE r.work_id = s.id)
          AND EXISTS (SELECT 1 FROM anime_releases r WHERE r.id = s.id)
    ) OR EXISTS (
        SELECT 1 FROM tv_series s WHERE NOT EXISTS (SELECT 1 FROM tv_releases r WHERE r.series_id = s.id)
          AND EXISTS (SELECT 1 FROM tv_releases r WHERE r.id = s.id)
    ) THEN
        RAISE EXCEPTION 'Anime/TV Catalog Item backfill found a root ID collision';
    END IF;
END $$;

CREATE TEMP TABLE _anime_item_roots ON COMMIT DROP AS
SELECT r.id AS item_id, r.work_id AS series_id, r.id AS release_id, r.created_at, r.updated_at
FROM anime_releases r
UNION ALL
SELECT s.id, s.id, NULL::uuid, s.created_at, s.updated_at
FROM anime_series s WHERE NOT EXISTS (SELECT 1 FROM anime_releases r WHERE r.work_id = s.id);

INSERT INTO anime_items (id, title, sort_key, barcode, catalog_number, details, revision, created_at, updated_at)
SELECT a.item_id, COALESCE(NULLIF(r.title, ''), s.title), COALESCE(r.sort_title, s.sort_title),
       r.barcode, r.catalog_number,
       jsonb_strip_nulls(jsonb_build_object(
           'title', COALESCE(NULLIF(r.title, ''), s.title),
           'sort_key', COALESCE(r.sort_title, s.sort_title),
           'original_title', s.title,
           'edition_title', r.title,
           'description', COALESCE(r.description, s.description),
           'release_date', COALESCE(to_jsonb(r.release_date_parts), to_jsonb(r.release_date),
                                    to_jsonb(s.original_air_date_parts), to_jsonb(s.original_air_date)),
           'release_date_parts', COALESCE(r.release_date_parts, s.original_air_date_parts),
           'release_status', COALESCE(r.release_status, s.status),
           'publisher', COALESCE(r.publisher, r.distributor),
           'country', r.region_code,
           'language', COALESCE(r.language_audio[1], s.original_language),
           'barcode', r.barcode,
           'catalog_number', r.catalog_number,
           'physical_format', r.format,
           'cover_image_url', r.cover_image_url,
           'thumbnail_image_url', r.cover_image_url,
           'episodes', '[]'::jsonb,
           'media', '[]'::jsonb,
           'discs', '[]'::jsonb
       )), 1, a.created_at, a.updated_at
FROM _anime_item_roots a
JOIN anime_series s ON s.id = a.series_id
LEFT JOIN anime_releases r ON r.id = a.release_id;

INSERT INTO anime_item_media (id, anime_item_id, position, media_number, details, created_at, updated_at)
SELECT m.id, m.release_id, row_number() OVER (PARTITION BY m.release_id ORDER BY m.media_number, m.id)::integer - 1,
       m.media_number,
       jsonb_strip_nulls(jsonb_build_object(
           'media_number', m.media_number, 'media_type', m.media_type, 'title', m.title,
           'episode_count', m.episode_count, 'runtime_minutes', m.runtime_minutes,
           'region_code', m.region_code, 'encoding', m.encoding, 'aspect_ratio', m.aspect_ratio,
           'audio_tracks', m.audio_tracks, 'subtitles', m.subtitles,
           'resolution', m.resolution, 'hdr_format', m.hdr_format
       )), m.created_at, m.updated_at
FROM anime_release_media m;

INSERT INTO anime_item_episodes (id, anime_item_id, position, episode_number, title, details, created_at, updated_at)
SELECT md5('anime-item-episode:' || roots.item_id::text || ':' || ep.id::text)::uuid,
       roots.item_id,
       row_number() OVER (PARTITION BY roots.item_id ORDER BY ep.episode_number NULLS LAST, ep.id)::integer - 1,
       ep.episode_number, ep.episode_title,
       jsonb_strip_nulls(jsonb_build_object(
           'episode_number', ep.episode_number, 'episode_title', ep.episode_title,
           'title', ep.episode_title, 'air_date', ep.air_date_parts,
           'description', ep.description, 'runtime_minutes', ep.runtime_minutes
       )), roots.created_at, roots.updated_at
FROM _anime_item_roots roots
JOIN anime_episodes ep ON ep.series_id = roots.series_id
WHERE roots.release_id IS NULL
   OR EXISTS (SELECT 1 FROM anime_release_episode_map m WHERE m.release_id = roots.release_id AND m.episode_id = ep.id);

INSERT INTO anime_item_episode_identity_map (old_episode_id, anime_item_id, new_episode_id, resolution)
SELECT source_episode.id, roots.item_id, child.id,
       CASE WHEN copies.item_count = 1 THEN 'exact' ELSE 'copied_to_multiple_items' END
FROM _anime_item_roots roots
JOIN anime_episodes source_episode ON source_episode.series_id = roots.series_id
JOIN anime_item_episodes child
  ON child.anime_item_id = roots.item_id
 AND child.id = md5('anime-item-episode:' || roots.item_id::text || ':' || source_episode.id::text)::uuid
JOIN LATERAL (
    SELECT count(*) AS item_count
    FROM _anime_item_roots candidate_roots
    WHERE candidate_roots.series_id = source_episode.series_id
      AND (candidate_roots.release_id IS NULL OR EXISTS (
          SELECT 1 FROM anime_release_episode_map map
          WHERE map.release_id = candidate_roots.release_id
            AND map.episode_id = source_episode.id
      ))
) copies ON true;

INSERT INTO anime_item_identifiers (id, anime_item_id, identifier_type, value, normalized_value, is_primary, created_at, updated_at)
SELECT md5('anime-item-identifier:' || roots.item_id::text || ':' || ids.identifier_type || ':' || ids.normalized_value)::uuid,
       roots.item_id, ids.identifier_type, ids.value, ids.normalized_value, ids.is_primary,
       roots.created_at, roots.updated_at
FROM _anime_item_roots roots
JOIN LATERAL (
    SELECT i.identifier_type, i.value, i.normalized_value, i.is_primary
    FROM anime_release_identifiers i
    WHERE i.release_id = roots.release_id AND i.source_provider IS NULL
    UNION ALL
    SELECT i.identifier_type, i.value, i.normalized_value, i.is_primary
    FROM anime_identifiers i
    WHERE i.series_id = roots.series_id AND i.source_provider IS NULL
) ids ON true
ON CONFLICT (anime_item_id, identifier_type, normalized_value) DO NOTHING;

INSERT INTO anime_item_legacy_identity_map (old_entity_type, old_entity_id, catalog_item_id, resolution)
SELECT 'anime_release', a.release_id, a.item_id, 'exact' FROM _anime_item_roots a WHERE a.release_id IS NOT NULL
UNION ALL
SELECT 'anime_series', a.series_id, a.item_id,
       CASE WHEN counts.item_count = 1 THEN 'exact' ELSE 'ambiguous_series_items' END
FROM _anime_item_roots a
JOIN LATERAL (SELECT count(*) item_count FROM _anime_item_roots x WHERE x.series_id = a.series_id) counts ON true;

INSERT INTO anime_item_migration_review (catalog_item_id, source_table, source_id, legacy_payload)
SELECT a.item_id, 'anime_series', s.id, to_jsonb(s) FROM _anime_item_roots a JOIN anime_series s ON s.id = a.series_id
UNION ALL SELECT a.item_id, 'anime_releases', r.id, to_jsonb(r) FROM _anime_item_roots a JOIN anime_releases r ON r.id = a.release_id
UNION ALL SELECT a.item_id, 'anime_episodes', e.id, to_jsonb(e)
FROM _anime_item_roots a JOIN anime_episodes e ON e.series_id = a.series_id
WHERE a.release_id IS NULL OR EXISTS (SELECT 1 FROM anime_release_episode_map m WHERE m.release_id = a.release_id AND m.episode_id = e.id)
UNION ALL SELECT a.item_id, 'anime_release_media', m.id, to_jsonb(m) FROM _anime_item_roots a JOIN anime_release_media m ON m.release_id = a.release_id
UNION ALL SELECT a.item_id, 'anime_release_episode_map', m.id, to_jsonb(m) FROM _anime_item_roots a JOIN anime_release_episode_map m ON m.release_id = a.release_id
UNION ALL SELECT a.item_id, 'anime_release_contributions', c.id, to_jsonb(c) FROM _anime_item_roots a JOIN anime_release_contributions c ON c.release_id = a.release_id
UNION ALL SELECT a.item_id, 'anime_contributions', c.id, to_jsonb(c) FROM _anime_item_roots a JOIN anime_contributions c ON c.series_id = a.series_id OR c.episode_id IN (SELECT e.id FROM anime_episodes e WHERE e.series_id = a.series_id)
UNION ALL SELECT a.item_id, 'anime_identifiers', i.id, to_jsonb(i) FROM _anime_item_roots a JOIN anime_identifiers i ON i.series_id = a.series_id
UNION ALL SELECT a.item_id, 'anime_release_identifiers', i.id, to_jsonb(i) FROM _anime_item_roots a JOIN anime_release_identifiers i ON i.release_id = a.release_id
UNION ALL SELECT a.item_id, 'anime_character_appearances', c.id, to_jsonb(c) FROM _anime_item_roots a JOIN anime_character_appearances c ON c.series_id = a.series_id
UNION ALL SELECT NULL, 'anime_episodes', e.id, to_jsonb(e) FROM anime_episodes e
WHERE NOT EXISTS (
    SELECT 1 FROM _anime_item_roots a WHERE a.series_id = e.series_id
      AND (a.release_id IS NULL OR EXISTS (
          SELECT 1 FROM anime_release_episode_map m WHERE m.release_id = a.release_id AND m.episode_id = e.id
      ))
)
UNION ALL SELECT NULL, 'external_provider_ids', p.id, to_jsonb(p) FROM external_provider_ids p WHERE p.entity_type LIKE 'anime_%'
UNION ALL SELECT NULL, 'entity_aliases', a.id, to_jsonb(a) FROM entity_aliases a WHERE a.entity_type LIKE 'anime_%'
UNION ALL SELECT NULL, 'entity_links', l.id, to_jsonb(l) FROM entity_links l WHERE l.entity_type LIKE 'anime_%'
UNION ALL SELECT NULL, 'entity_persons', p.id, to_jsonb(p) FROM entity_persons p WHERE p.entity_type LIKE 'anime_%'
UNION ALL SELECT NULL, 'entity_organizations', o.id, to_jsonb(o) FROM entity_organizations o WHERE o.entity_type LIKE 'anime_%'
UNION ALL SELECT NULL, 'entity_tags', t.id, to_jsonb(t) FROM entity_tags t WHERE t.entity_type LIKE 'anime_%'
UNION ALL SELECT NULL, 'image_assets', i.id, to_jsonb(i) FROM image_assets i WHERE i.entity_type LIKE 'anime_%';

CREATE TEMP TABLE _tv_item_roots ON COMMIT DROP AS
SELECT r.id AS item_id, r.series_id, r.id AS release_id, r.created_at, r.updated_at
FROM tv_releases r
UNION ALL
SELECT s.id, s.id, NULL::uuid, s.created_at, s.updated_at
FROM tv_series s WHERE NOT EXISTS (SELECT 1 FROM tv_releases r WHERE r.series_id = s.id);

INSERT INTO tv_items (id, title, sort_key, barcode, catalog_number, details, revision, created_at, updated_at)
SELECT t.item_id, COALESCE(NULLIF(r.title, ''), s.title), COALESCE(r.sort_title, s.sort_title),
       NULL::varchar, r.sku,
       jsonb_strip_nulls(jsonb_build_object(
           'title', COALESCE(NULLIF(r.title, ''), s.title),
           'sort_key', COALESCE(r.sort_title, s.sort_title),
           'original_title', s.original_title,
           'edition_title', r.title,
           'description', COALESCE(r.description, s.overview),
           'release_date', COALESCE(to_jsonb(r.release_date_parts), to_jsonb(r.release_date),
                                    to_jsonb(s.first_air_date_parts), to_jsonb(s.first_air_date)),
           'release_date_parts', COALESCE(r.release_date_parts, s.first_air_date_parts),
           'release_status', COALESCE(r.release_status, s.status),
           'publisher', COALESCE(r.publisher, s.network),
           'country', s.country,
           'language', COALESCE(r.language_audio[1], s.original_language),
           'barcode', NULL,
           'catalog_number', r.sku,
           'physical_format', COALESCE(r.case_type, r.format),
           'runtime_minutes', r.runtime_minutes,
           'age_rating', r.content_rating,
           'cover_image_url', COALESCE(r.cover_image_url, s.poster_url),
           'thumbnail_image_url', COALESCE(r.cover_image_url, s.poster_url),
           'episodes', '[]'::jsonb, 'media', '[]'::jsonb, 'discs', '[]'::jsonb
       )), 1, t.created_at, t.updated_at
FROM _tv_item_roots t JOIN tv_series s ON s.id = t.series_id
LEFT JOIN tv_releases r ON r.id = t.release_id;

INSERT INTO tv_item_seasons (id, tv_item_id, season_number, title, details, created_at, updated_at)
SELECT md5('tv-item-season:' || t.item_id::text || ':' || s.id::text)::uuid,
       t.item_id, s.season_number, s.title,
       jsonb_strip_nulls(jsonb_build_object(
           'season_number', s.season_number, 'title', s.title,
           'description', s.overview, 'air_date', s.air_date_parts,
           'episode_count', s.episode_count
       )), t.created_at, t.updated_at
FROM _tv_item_roots t
JOIN tv_seasons s ON s.series_id = t.series_id
WHERE t.release_id IS NULL OR EXISTS (
    SELECT 1 FROM tv_episodes e
    WHERE e.season_id = s.id AND (
        e.release_id = t.release_id OR EXISTS (
            SELECT 1 FROM tv_release_episode_map m
            WHERE m.release_id = t.release_id AND m.episode_id = e.id
        )
    )
);

INSERT INTO tv_item_season_identity_map (old_season_id, tv_item_id, new_season_id, resolution)
SELECT source_season.id, roots.item_id, child.id,
       CASE WHEN copies.item_count = 1 THEN 'exact' ELSE 'copied_to_multiple_items' END
FROM _tv_item_roots roots
JOIN tv_seasons source_season ON source_season.series_id = roots.series_id
JOIN tv_item_seasons child
  ON child.tv_item_id = roots.item_id
 AND child.id = md5('tv-item-season:' || roots.item_id::text || ':' || source_season.id::text)::uuid
JOIN LATERAL (
    SELECT count(*) AS item_count
    FROM _tv_item_roots candidate_roots
    WHERE candidate_roots.series_id = source_season.series_id
      AND (candidate_roots.release_id IS NULL OR EXISTS (
          SELECT 1 FROM tv_episodes episode
          WHERE episode.season_id = source_season.id
            AND (episode.release_id = candidate_roots.release_id OR EXISTS (
                SELECT 1 FROM tv_release_episode_map map
                WHERE map.release_id = candidate_roots.release_id AND map.episode_id = episode.id
            ))
      ))
) copies ON true;

INSERT INTO tv_item_media (id, tv_item_id, position, media_number, details, created_at, updated_at)
SELECT m.id, m.release_id,
       row_number() OVER (PARTITION BY m.release_id ORDER BY m.media_number, m.id)::integer - 1,
       m.media_number,
       jsonb_strip_nulls(jsonb_build_object(
           'media_number', m.media_number, 'media_type', m.media_type, 'title', m.title,
           'episode_count', m.episode_count, 'runtime_minutes', m.runtime_minutes,
           'region_code', m.region_code, 'encoding', m.encoding, 'aspect_ratio', m.aspect_ratio,
           'color', m.color, 'audio_tracks', m.audio_tracks, 'subtitles', m.subtitles,
           'layers', m.layers, 'frame_rate', m.frame_rate, 'bit_depth', m.bit_depth,
           'resolution', m.resolution, 'hdr_format', m.hdr_format
       )), m.created_at, m.updated_at
FROM tv_release_media m;

INSERT INTO tv_item_episodes (id, tv_item_id, position, season_number, episode_number, title, details, created_at, updated_at)
SELECT md5('tv-item-episode:' || t.item_id::text || ':' || e.id::text)::uuid,
       t.item_id,
       row_number() OVER (PARTITION BY t.item_id ORDER BY e.season_number, e.episode_number, e.id)::integer - 1,
       e.season_number, e.episode_number, e.title,
       jsonb_strip_nulls(jsonb_build_object(
           'season_number', e.season_number, 'episode_number', e.episode_number,
           'episode_title', e.title, 'title', e.title, 'description', e.overview,
           'air_date', e.original_air_date_parts, 'runtime_minutes', (e.duration_seconds / 60),
           'position', row_number() OVER (PARTITION BY t.item_id ORDER BY e.season_number, e.episode_number, e.id)::integer - 1
       )), t.created_at, t.updated_at
FROM _tv_item_roots t
JOIN tv_episodes e ON e.series_id = t.series_id
WHERE t.release_id IS NULL OR e.release_id = t.release_id OR EXISTS (
    SELECT 1 FROM tv_release_episode_map m WHERE m.release_id = t.release_id AND m.episode_id = e.id
);

INSERT INTO tv_item_episode_identity_map (old_episode_id, tv_item_id, new_episode_id, resolution)
SELECT source_episode.id, roots.item_id, child.id,
       CASE WHEN copies.item_count = 1 THEN 'exact' ELSE 'copied_to_multiple_items' END
FROM _tv_item_roots roots
JOIN tv_episodes source_episode ON source_episode.series_id = roots.series_id
JOIN tv_item_episodes child
  ON child.tv_item_id = roots.item_id
 AND child.id = md5('tv-item-episode:' || roots.item_id::text || ':' || source_episode.id::text)::uuid
JOIN LATERAL (
    SELECT count(*) AS item_count
    FROM _tv_item_roots candidate_roots
    WHERE candidate_roots.series_id = source_episode.series_id
      AND (candidate_roots.release_id IS NULL OR source_episode.release_id = candidate_roots.release_id OR EXISTS (
          SELECT 1 FROM tv_release_episode_map map
          WHERE map.release_id = candidate_roots.release_id
            AND map.episode_id = source_episode.id
      ))
) copies ON true;

INSERT INTO tv_item_identifiers (id, tv_item_id, identifier_type, value, normalized_value, is_primary, created_at, updated_at)
SELECT md5('tv-item-identifier:' || t.item_id::text || ':' || i.identifier_type || ':' || COALESCE(i.normalized_value, i.value))::uuid,
       t.item_id, i.identifier_type, i.value,
       COALESCE(i.normalized_value, regexp_replace(lower(i.value), '[^a-z0-9]', '', 'g')),
       i.is_primary, t.created_at, t.updated_at
FROM _tv_item_roots t JOIN tv_release_identifiers i ON i.release_id = t.release_id AND i.source_provider IS NULL
ON CONFLICT (tv_item_id, identifier_type, normalized_value) DO NOTHING;

INSERT INTO tv_item_legacy_identity_map (old_entity_type, old_entity_id, catalog_item_id, resolution)
SELECT 'tv_release', t.release_id, t.item_id, 'exact' FROM _tv_item_roots t WHERE t.release_id IS NOT NULL
UNION ALL
SELECT 'tv_series', t.series_id, t.item_id,
       CASE WHEN counts.item_count = 1 THEN 'exact' ELSE 'ambiguous_series_items' END
FROM _tv_item_roots t JOIN LATERAL (SELECT count(*) item_count FROM _tv_item_roots x WHERE x.series_id = t.series_id) counts ON true;

INSERT INTO tv_item_migration_review (catalog_item_id, source_table, source_id, legacy_payload)
SELECT t.item_id, 'tv_series', s.id, to_jsonb(s) FROM _tv_item_roots t JOIN tv_series s ON s.id = t.series_id
UNION ALL SELECT t.item_id, 'tv_releases', r.id, to_jsonb(r) FROM _tv_item_roots t JOIN tv_releases r ON r.id = t.release_id
UNION ALL SELECT t.item_id, 'tv_seasons', s.id, to_jsonb(s)
FROM _tv_item_roots t JOIN tv_seasons s ON s.series_id = t.series_id
WHERE t.release_id IS NULL OR EXISTS (
    SELECT 1 FROM tv_episodes e
    WHERE e.season_id = s.id AND (
        e.release_id = t.release_id OR EXISTS (
            SELECT 1 FROM tv_release_episode_map m
            WHERE m.release_id = t.release_id AND m.episode_id = e.id
        )
    )
)
UNION ALL SELECT t.item_id, 'tv_episodes', e.id, to_jsonb(e)
FROM _tv_item_roots t JOIN tv_episodes e ON e.series_id = t.series_id
WHERE t.release_id IS NULL OR e.release_id = t.release_id OR EXISTS (
    SELECT 1 FROM tv_release_episode_map m WHERE m.release_id = t.release_id AND m.episode_id = e.id
)
UNION ALL SELECT t.item_id, 'tv_release_media', m.id, to_jsonb(m) FROM _tv_item_roots t JOIN tv_release_media m ON m.release_id = t.release_id
UNION ALL SELECT t.item_id, 'tv_release_episode_map', m.id, to_jsonb(m) FROM _tv_item_roots t JOIN tv_release_episode_map m ON m.release_id = t.release_id
UNION ALL SELECT t.item_id, 'tv_release_identifiers', i.id, to_jsonb(i) FROM _tv_item_roots t JOIN tv_release_identifiers i ON i.release_id = t.release_id
UNION ALL SELECT t.item_id, 'tv_episode_identifiers', i.id, to_jsonb(i) FROM _tv_item_roots t JOIN tv_episodes e ON e.series_id = t.series_id JOIN tv_episode_identifiers i ON i.episode_id = e.id
UNION ALL SELECT t.item_id, 'tv_episode_contributions', c.id, to_jsonb(c) FROM _tv_item_roots t JOIN tv_episodes e ON e.series_id = t.series_id JOIN tv_episode_contributions c ON c.episode_id = e.id
UNION ALL SELECT t.item_id, 'tv_release_contributions', c.id, to_jsonb(c) FROM _tv_item_roots t JOIN tv_release_contributions c ON c.release_id = t.release_id
UNION ALL SELECT NULL, 'tv_episodes', e.id, to_jsonb(e) FROM tv_episodes e
WHERE NOT EXISTS (
    SELECT 1 FROM _tv_item_roots t WHERE t.series_id = e.series_id
      AND (t.release_id IS NULL OR e.release_id = t.release_id OR EXISTS (
          SELECT 1 FROM tv_release_episode_map m WHERE m.release_id = t.release_id AND m.episode_id = e.id
      ))
)
UNION ALL SELECT NULL, 'tv_seasons', s.id, to_jsonb(s) FROM tv_seasons s
WHERE NOT EXISTS (
    SELECT 1 FROM _tv_item_roots t WHERE t.series_id = s.series_id
      AND (t.release_id IS NULL OR EXISTS (
          SELECT 1 FROM tv_episodes e WHERE e.season_id = s.id
            AND (e.release_id = t.release_id OR EXISTS (
                SELECT 1 FROM tv_release_episode_map m
                WHERE m.release_id = t.release_id AND m.episode_id = e.id
            ))
      ))
)
UNION ALL SELECT NULL, 'external_provider_ids', p.id, to_jsonb(p) FROM external_provider_ids p WHERE p.entity_type LIKE 'tv_%'
UNION ALL SELECT NULL, 'entity_aliases', a.id, to_jsonb(a) FROM entity_aliases a WHERE a.entity_type LIKE 'tv_%'
UNION ALL SELECT NULL, 'entity_links', l.id, to_jsonb(l) FROM entity_links l WHERE l.entity_type LIKE 'tv_%'
UNION ALL SELECT NULL, 'entity_persons', p.id, to_jsonb(p) FROM entity_persons p WHERE p.entity_type LIKE 'tv_%'
UNION ALL SELECT NULL, 'entity_organizations', o.id, to_jsonb(o) FROM entity_organizations o WHERE o.entity_type LIKE 'tv_%'
UNION ALL SELECT NULL, 'entity_tags', t.id, to_jsonb(t) FROM entity_tags t WHERE t.entity_type LIKE 'tv_%'
UNION ALL SELECT NULL, 'image_assets', i.id, to_jsonb(i) FROM image_assets i WHERE i.entity_type LIKE 'tv_%';

DO $$
BEGIN
    IF (SELECT count(*) FROM _anime_item_roots) <> (SELECT count(*) FROM anime_items) THEN
        RAISE EXCEPTION 'Anime Catalog Item root count mismatch';
    END IF;
    IF (SELECT count(*) FROM _tv_item_roots) <> (SELECT count(*) FROM tv_items) THEN
        RAISE EXCEPTION 'TV Catalog Item root count mismatch';
    END IF;
    IF EXISTS (
        SELECT 1 FROM anime_releases r LEFT JOIN anime_items i ON i.id = r.id WHERE i.id IS NULL
    ) OR EXISTS (
        SELECT 1 FROM tv_releases r LEFT JOIN tv_items i ON i.id = r.id WHERE i.id IS NULL
    ) THEN
        RAISE EXCEPTION 'Anime/TV Catalog Item migration lost a release identity';
    END IF;
    IF (SELECT count(*) FROM anime_release_media) <> (SELECT count(*) FROM anime_item_media)
       OR (SELECT count(*) FROM anime_item_episodes) <> (SELECT count(*) FROM anime_item_episode_identity_map)
       OR (SELECT count(*) FROM tv_release_media) <> (SELECT count(*) FROM tv_item_media)
       OR (SELECT count(*) FROM tv_item_seasons) <> (SELECT count(*) FROM tv_item_season_identity_map)
       OR (SELECT count(*) FROM tv_item_episodes) <> (SELECT count(*) FROM tv_item_episode_identity_map) THEN
        RAISE EXCEPTION 'Anime/TV Catalog Item contained-row identity count mismatch';
    END IF;
    IF (SELECT count(DISTINCT old_entity_type || ':' || old_entity_id::text) FROM anime_item_legacy_identity_map)
       <> (SELECT count(*) FROM anime_series) + (SELECT count(*) FROM anime_releases)
       OR (SELECT count(DISTINCT old_entity_type || ':' || old_entity_id::text) FROM tv_item_legacy_identity_map)
       <> (SELECT count(*) FROM tv_series) + (SELECT count(*) FROM tv_releases) THEN
        RAISE EXCEPTION 'Anime/TV Catalog Item legacy identity-map count mismatch';
    END IF;
END $$;

COMMIT;
