-- One-way backfill from Movie Work -> Release to Catalog Item roots.
-- Run only against a reviewed non-live copy of the pinned Core baseline.
-- The source tables are intentionally left intact; dropping them is a later
-- coordinated step after App and Sync no longer consume the old graph.

BEGIN;

CREATE TABLE IF NOT EXISTS movie_items (
    id uuid PRIMARY KEY,
    title varchar(255) NOT NULL,
    sort_key varchar(255),
    barcode varchar(100),
    catalog_number varchar(100),
    details jsonb NOT NULL,
    revision integer NOT NULL DEFAULT 1,
    created_at timestamptz NOT NULL,
    updated_at timestamptz NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_movie_items_title ON movie_items (title);
CREATE INDEX IF NOT EXISTS ix_movie_items_sort_key ON movie_items (sort_key);
CREATE INDEX IF NOT EXISTS ix_movie_items_barcode ON movie_items (barcode);
CREATE INDEX IF NOT EXISTS ix_movie_items_catalog_number ON movie_items (catalog_number);

CREATE TABLE IF NOT EXISTS movie_item_media (
    id uuid PRIMARY KEY,
    movie_item_id uuid NOT NULL REFERENCES movie_items(id) ON DELETE CASCADE,
    media_number integer NOT NULL,
    media_type varchar(64),
    title varchar(255),
    aspect_ratio varchar(16),
    screen_ratio varchar(50),
    color varchar(64),
    num_discs integer,
    nr_layers integer,
    layers varchar(50),
    audio_tracks varchar(500),
    subtitles varchar(500),
    created_at timestamptz NOT NULL,
    updated_at timestamptz NOT NULL,
    CONSTRAINT uq_movie_item_media_number UNIQUE (movie_item_id, media_number)
);
CREATE INDEX IF NOT EXISTS ix_movie_item_media_item
    ON movie_item_media (movie_item_id, media_number);

CREATE TABLE IF NOT EXISTS movie_item_legacy_identity_map (
    old_entity_type text NOT NULL,
    old_entity_id uuid NOT NULL,
    catalog_item_id uuid NOT NULL REFERENCES movie_items(id) ON DELETE CASCADE,
    resolution text NOT NULL,
    PRIMARY KEY (old_entity_type, old_entity_id, catalog_item_id)
);
CREATE INDEX IF NOT EXISTS ix_movie_item_legacy_identity_map_old
    ON movie_item_legacy_identity_map (old_entity_type, old_entity_id);

CREATE TABLE IF NOT EXISTS movie_item_migration_review (
    catalog_item_id uuid NOT NULL REFERENCES movie_items(id) ON DELETE CASCADE,
    source_table text NOT NULL,
    source_id uuid NOT NULL,
    field_key text NOT NULL,
    legacy_payload jsonb NOT NULL,
    PRIMARY KEY (catalog_item_id, source_table, source_id, field_key)
);

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM movie_items) OR EXISTS (SELECT 1 FROM movie_item_media) THEN
        RAISE EXCEPTION 'Movie Catalog Item backfill destination is not empty';
    END IF;
    IF EXISTS (
        SELECT 1
        FROM movie_releases r
        JOIN movie_works w ON w.id = r.work_id
        JOIN movie_works collision ON collision.id = r.id
    ) THEN
        RAISE EXCEPTION 'Movie Catalog Item backfill found a release/work ID collision';
    END IF;
END $$;

INSERT INTO movie_items (
    id, title, sort_key, barcode, catalog_number, details, revision,
    created_at, updated_at
)
SELECT
    r.id,
    w.title,
    w.sort_title,
    r.barcode,
    r.sku,
    jsonb_strip_nulls(jsonb_build_object(
        'title', w.title,
        'sort_key', w.sort_title,
        'subtitle', w.subtitle,
        'original_title', w.original_title,
        'description', w.description,
        'release_date', r.release_date,
        'release_date_parts', r.release_date_parts,
        'release_status', r.release_type,
        'publisher', COALESCE(r.distributor, r.publisher),
        'country', r.region_code,
        'language', w.original_language,
        'barcode', r.barcode,
        'catalog_number', r.sku,
        'physical_format', r.format,
        'runtime_minutes', COALESCE(r.runtime_minutes, w.runtime_minutes),
        'age_rating', COALESCE(w.age_rating, r.certification),
        'audience_rating', w.audience_rating,
        'cover_image_url', COALESCE(r.cover_image_url, w.poster_image_url),
        'thumbnail_image_url', w.poster_image_url,
        'color', r.color,
        'nr_discs', r.media_count,
        'contributors', COALESCE((
            SELECT jsonb_agg(jsonb_strip_nulls(jsonb_build_object(
                'person_id', c.person_id,
                'name', p.name,
                'role', c.role,
                'role_id', c.role_id,
                'sequence', c.sequence
            )) ORDER BY c.sequence NULLS LAST, c.created_at)
            FROM movie_work_contributions c
            JOIN persons p ON p.id = c.person_id
            WHERE c.work_id = w.id
        ), '[]'::jsonb),
        'characters', COALESCE((
            SELECT jsonb_agg(jsonb_strip_nulls(jsonb_build_object(
                'character_id', ch.id,
                'name', ch.name,
                'role', ca.role,
                'description', ch.description,
                'image_url', ch.image_url
            )) ORDER BY ch.name, ca.id)
            FROM character_appearances ca
            JOIN characters ch ON ch.id = ca.character_id
            WHERE (ca.entity_type = 'movie_work' AND ca.entity_id = w.id)
               OR (ca.entity_type = 'movie_release' AND ca.entity_id = r.id)
        ), '[]'::jsonb),
        'external_links', COALESCE((
            SELECT jsonb_agg(jsonb_strip_nulls(jsonb_build_object(
                'url', l.url, 'site', l.site, 'name', l.name, 'kind', l.kind,
                'description', l.description, 'position', l.position
            )) ORDER BY l.position, l.created_at)
            FROM entity_links l
            WHERE l.link_type = 'external'
              AND ((l.entity_type = 'movie_work' AND l.entity_id = w.id)
                OR (l.entity_type = 'movie_release' AND l.entity_id = r.id))
        ), '[]'::jsonb),
        'search_aliases', COALESCE((
            SELECT jsonb_agg(a.alias ORDER BY a.position, a.created_at)
            FROM entity_aliases a
            WHERE (a.entity_type = 'movie_work' AND a.entity_id = w.id)
               OR (a.entity_type = 'movie_release' AND a.entity_id = r.id)
        ), '[]'::jsonb),
        'trailer_urls', COALESCE((
            SELECT jsonb_agg(jsonb_strip_nulls(jsonb_build_object(
                'url', l.url, 'site', l.site, 'name', l.name, 'kind', l.kind,
                'description', l.description, 'position', l.position
            )) ORDER BY l.position, l.created_at)
            FROM entity_links l
            WHERE l.link_type = 'trailer'
              AND ((l.entity_type = 'movie_work' AND l.entity_id = w.id)
                OR (l.entity_type = 'movie_release' AND l.entity_id = r.id))
        ), '[]'::jsonb)
    )),
    1,
    LEAST(w.created_at, r.created_at),
    GREATEST(w.updated_at, r.updated_at)
FROM movie_releases r
JOIN movie_works w ON w.id = r.work_id;

INSERT INTO movie_items (
    id, title, sort_key, barcode, catalog_number, details, revision,
    created_at, updated_at
)
SELECT
    w.id,
    w.title,
    w.sort_title,
    NULL,
    NULL,
    jsonb_strip_nulls(jsonb_build_object(
        'title', w.title,
        'sort_key', w.sort_title,
        'subtitle', w.subtitle,
        'original_title', w.original_title,
        'description', w.description,
        'language', w.original_language,
        'runtime_minutes', w.runtime_minutes,
        'age_rating', w.age_rating,
        'audience_rating', w.audience_rating,
        'cover_image_url', w.poster_image_url,
        'thumbnail_image_url', w.poster_image_url,
        'contributors', COALESCE((
            SELECT jsonb_agg(jsonb_strip_nulls(jsonb_build_object(
                'person_id', c.person_id,
                'name', p.name,
                'role', c.role,
                'role_id', c.role_id,
                'sequence', c.sequence
            )) ORDER BY c.sequence NULLS LAST, c.created_at)
            FROM movie_work_contributions c
            JOIN persons p ON p.id = c.person_id
            WHERE c.work_id = w.id
        ), '[]'::jsonb),
        'characters', COALESCE((
            SELECT jsonb_agg(jsonb_strip_nulls(jsonb_build_object(
                'character_id', ch.id,
                'name', ch.name,
                'role', ca.role,
                'description', ch.description,
                'image_url', ch.image_url
            )) ORDER BY ch.name, ca.id)
            FROM character_appearances ca
            JOIN characters ch ON ch.id = ca.character_id
            WHERE ca.entity_type = 'movie_work' AND ca.entity_id = w.id
        ), '[]'::jsonb),
        'external_links', COALESCE((
            SELECT jsonb_agg(jsonb_strip_nulls(jsonb_build_object(
                'url', l.url, 'site', l.site, 'name', l.name, 'kind', l.kind,
                'description', l.description, 'position', l.position
            )) ORDER BY l.position, l.created_at)
            FROM entity_links l
            WHERE l.entity_type = 'movie_work' AND l.entity_id = w.id
              AND l.link_type = 'external'
        ), '[]'::jsonb),
        'search_aliases', COALESCE((
            SELECT jsonb_agg(a.alias ORDER BY a.position, a.created_at)
            FROM entity_aliases a
            WHERE a.entity_type = 'movie_work' AND a.entity_id = w.id
        ), '[]'::jsonb),
        'trailer_urls', COALESCE((
            SELECT jsonb_agg(jsonb_strip_nulls(jsonb_build_object(
                'url', l.url, 'site', l.site, 'name', l.name, 'kind', l.kind,
                'description', l.description, 'position', l.position
            )) ORDER BY l.position, l.created_at)
            FROM entity_links l
            WHERE l.entity_type = 'movie_work' AND l.entity_id = w.id
              AND l.link_type = 'trailer'
        ), '[]'::jsonb)
    )),
    1,
    w.created_at,
    w.updated_at
FROM movie_works w
WHERE NOT EXISTS (SELECT 1 FROM movie_releases r WHERE r.work_id = w.id);

INSERT INTO movie_item_media (
    id, movie_item_id, media_number, media_type, title, aspect_ratio,
    screen_ratio, color, num_discs, nr_layers, layers, audio_tracks,
    subtitles, created_at, updated_at
)
SELECT
    m.id, m.release_id, m.media_number, m.media_type, m.title, m.aspect_ratio,
    m.screen_ratio, m.color, m.num_discs, m.nr_layers, m.layers,
    m.audio_tracks, m.subtitles, m.created_at, m.updated_at
FROM movie_release_media m
JOIN movie_releases r ON r.id = m.release_id;

INSERT INTO movie_item_legacy_identity_map (
    old_entity_type, old_entity_id, catalog_item_id, resolution
)
SELECT 'movie_release', r.id, r.id, 'preserved_concrete_id'
FROM movie_releases r;

INSERT INTO movie_item_legacy_identity_map (
    old_entity_type, old_entity_id, catalog_item_id, resolution
)
SELECT
    'movie_work', w.id, r.id,
    CASE WHEN counts.release_count = 1
         THEN 'single_release_unambiguous'
         ELSE 'ambiguous_parent_multiple_releases'
    END
FROM movie_works w
JOIN movie_releases r ON r.work_id = w.id
JOIN (
    SELECT work_id, count(*) AS release_count
    FROM movie_releases
    GROUP BY work_id
) counts ON counts.work_id = w.id;

INSERT INTO movie_item_legacy_identity_map (
    old_entity_type, old_entity_id, catalog_item_id, resolution
)
SELECT 'movie_work', w.id, w.id, 'preserved_work_without_release'
FROM movie_works w
WHERE NOT EXISTS (SELECT 1 FROM movie_releases r WHERE r.work_id = w.id);

INSERT INTO movie_item_legacy_identity_map (
    old_entity_type, old_entity_id, catalog_item_id, resolution
)
SELECT 'movie_release_media', m.id, m.release_id, 'preserved_child_id'
FROM movie_release_media m
JOIN movie_releases r ON r.id = m.release_id;

INSERT INTO movie_item_migration_review (
    catalog_item_id, source_table, source_id, field_key, legacy_payload
)
SELECT
    r.id,
    'movie_releases',
    r.id,
    'unmapped_release_metadata',
    jsonb_strip_nulls(jsonb_build_object(
        'original_release_date', w.original_release_date,
        'original_release_date_parts', w.original_release_date_parts,
        'language_audio', to_jsonb(r.language_audio),
        'language_subtitles', to_jsonb(r.language_subtitles),
        'cover_image_key', r.cover_image_key
    ))
FROM movie_releases r
JOIN movie_works w ON w.id = r.work_id
WHERE w.original_release_date IS NOT NULL
   OR w.original_release_date_parts IS NOT NULL
   OR r.language_audio IS NOT NULL
   OR r.language_subtitles IS NOT NULL
   OR r.cover_image_key IS NOT NULL
ON CONFLICT DO NOTHING;

INSERT INTO movie_item_migration_review (
    catalog_item_id, source_table, source_id, field_key, legacy_payload
)
SELECT
    w.id,
    'movie_works',
    w.id,
    'unmapped_original_release_date',
    jsonb_strip_nulls(jsonb_build_object(
        'original_release_date', w.original_release_date,
        'original_release_date_parts', w.original_release_date_parts
    ))
FROM movie_works w
WHERE NOT EXISTS (SELECT 1 FROM movie_releases r WHERE r.work_id = w.id)
  AND (w.original_release_date IS NOT NULL
    OR w.original_release_date_parts IS NOT NULL)
ON CONFLICT DO NOTHING;

INSERT INTO movie_item_migration_review (
    catalog_item_id, source_table, source_id, field_key, legacy_payload
)
SELECT
    identity.catalog_item_id,
    'movie_work_contributions',
    c.id,
    'unmapped_character_credit_name',
    jsonb_build_object('character_name', c.character_name)
FROM movie_work_contributions c
JOIN movie_item_legacy_identity_map identity
  ON identity.old_entity_type = 'movie_work'
 AND identity.old_entity_id = c.work_id
WHERE c.character_name IS NOT NULL
ON CONFLICT DO NOTHING;

INSERT INTO movie_item_migration_review (
    catalog_item_id, source_table, source_id, field_key, legacy_payload
)
SELECT
    r.id,
    'movie_works',
    w.id,
    'unmapped_work_financial_and_rating_fields',
    jsonb_strip_nulls(jsonb_build_object(
        'status', w.status,
        'budget_usd', w.budget_usd,
        'revenue_usd', w.revenue_usd,
        'rating_count', w.rating_count,
        'backdrop_image_url', w.backdrop_image_url,
        'backdrop_image_key', w.backdrop_image_key,
        'poster_image_key', w.poster_image_key
    ))
FROM movie_releases r
JOIN movie_works w ON w.id = r.work_id
WHERE w.status IS NOT NULL OR w.budget_usd IS NOT NULL
   OR w.revenue_usd IS NOT NULL OR w.rating_count IS NOT NULL
   OR w.backdrop_image_url IS NOT NULL OR w.backdrop_image_key IS NOT NULL
   OR w.poster_image_key IS NOT NULL
ON CONFLICT DO NOTHING;

INSERT INTO movie_item_migration_review (
    catalog_item_id, source_table, source_id, field_key, legacy_payload
)
SELECT
    COALESCE(r.id, w.id),
    'movie_work_identifiers',
    i.id,
    'unmapped_non_provider_identifier',
    jsonb_build_object(
        'identifier_type', i.identifier_type,
        'value', i.value,
        'normalized_value', i.normalized_value,
        'is_primary', i.is_primary
    )
FROM movie_work_identifiers i
JOIN movie_works w ON w.id = i.work_id
LEFT JOIN movie_releases r ON r.work_id = w.id
WHERE i.source_provider IS NULL
ON CONFLICT DO NOTHING;

INSERT INTO movie_item_migration_review (
    catalog_item_id, source_table, source_id, field_key, legacy_payload
)
SELECT
    identity.catalog_item_id,
    'entity_tags',
    et.id,
    'legacy_tag',
    jsonb_build_object('tag_id', t.id, 'name', t.name, 'kind', t.kind)
FROM entity_tags et
JOIN tags t ON t.id = et.tag_id
JOIN movie_item_legacy_identity_map identity
  ON identity.old_entity_type = et.entity_type
 AND identity.old_entity_id = et.entity_id
WHERE et.entity_type IN ('movie_work', 'movie_release')
ON CONFLICT DO NOTHING;

INSERT INTO movie_item_migration_review (
    catalog_item_id, source_table, source_id, field_key, legacy_payload
)
SELECT
    identity.catalog_item_id,
    'image_assets',
    image.id,
    'legacy_image_asset',
    jsonb_strip_nulls(jsonb_build_object(
        'image_type', image.image_type,
        'storage_key', image.storage_key,
        'thumbnail_storage_key', image.thumbnail_storage_key,
        'source_url', image.source_url,
        'attribution', image.attribution,
        'width', image.width,
        'height', image.height,
        'phash', image.phash,
        'is_primary', image.is_primary
    ))
FROM image_assets image
JOIN movie_item_legacy_identity_map identity
  ON identity.old_entity_type = image.entity_type
 AND identity.old_entity_id = image.entity_id
WHERE image.entity_type IN ('movie_work', 'movie_release')
ON CONFLICT DO NOTHING;

INSERT INTO movie_item_migration_review (
    catalog_item_id, source_table, source_id, field_key, legacy_payload
)
SELECT
    w.id,
    'movie_works',
    w.id,
    'unmapped_work_financial_and_rating_fields',
    jsonb_strip_nulls(jsonb_build_object(
        'status', w.status,
        'budget_usd', w.budget_usd,
        'revenue_usd', w.revenue_usd,
        'rating_count', w.rating_count,
        'backdrop_image_url', w.backdrop_image_url,
        'backdrop_image_key', w.backdrop_image_key,
        'poster_image_key', w.poster_image_key
    ))
FROM movie_works w
WHERE NOT EXISTS (SELECT 1 FROM movie_releases r WHERE r.work_id = w.id)
  AND (w.status IS NOT NULL OR w.budget_usd IS NOT NULL
    OR w.revenue_usd IS NOT NULL OR w.rating_count IS NOT NULL
    OR w.backdrop_image_url IS NOT NULL OR w.backdrop_image_key IS NOT NULL
    OR w.poster_image_key IS NOT NULL)
ON CONFLICT DO NOTHING;

DO $$
DECLARE
    expected_items bigint;
    actual_items bigint;
    expected_media bigint;
    actual_media bigint;
BEGIN
    SELECT (SELECT count(*) FROM movie_releases) +
           (SELECT count(*) FROM movie_works w
            WHERE NOT EXISTS (
                SELECT 1 FROM movie_releases r WHERE r.work_id = w.id
            ))
    INTO expected_items;
    SELECT count(*) INTO actual_items FROM movie_items;
    SELECT count(*) INTO expected_media
    FROM movie_release_media m
    JOIN movie_releases r ON r.id = m.release_id;
    SELECT count(*) INTO actual_media FROM movie_item_media;
    IF actual_items <> expected_items THEN
        RAISE EXCEPTION 'Movie item count mismatch: expected %, found %',
            expected_items, actual_items;
    END IF;
    IF actual_media <> expected_media THEN
        RAISE EXCEPTION 'Movie media count mismatch: expected %, found %',
            expected_media, actual_media;
    END IF;
END $$;

COMMIT;
