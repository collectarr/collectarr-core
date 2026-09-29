-- One-way backfill from the pre-flattened Music Release Group -> Release graph.
-- Create the three destination tables from app.models.catalog_music_item first
-- (the normal application bootstrap does this for a fresh database), then run
-- this script once against a non-live database backup.
--
-- Release IDs become Music Item IDs. Group-only rows keep the group ID. Disc
-- and track IDs are preserved. This script intentionally does not delete the
-- source tables; they remain available for audit until all App consumers move.

BEGIN;

DO $$
BEGIN
    IF EXISTS (
        SELECT 1
        FROM music_releases AS r
        JOIN music_release_groups AS g ON g.id = r.release_group_id
        JOIN music_items AS i ON i.id = r.id
    ) OR EXISTS (
        SELECT 1
        FROM music_release_groups AS g
        WHERE NOT EXISTS (
            SELECT 1 FROM music_releases AS r WHERE r.release_group_id = g.id
        )
          AND EXISTS (SELECT 1 FROM music_items AS i WHERE i.id = g.id)
    ) THEN
        RAISE EXCEPTION 'Music Catalog Item backfill found destination ID collisions';
    END IF;
END $$;

INSERT INTO music_items (
    id, title, sort_title, subtitle, artist, artist_credits,
    original_release_date, original_release_date_parts,
    recording_date, recording_date_parts, release_date, release_date_parts,
    label, format, barcode, catalog_number, genres, packaging, studio, studios,
    country, is_live, sound_types, vinyl_color, vinyl_weight, rpm, extra, spars,
    box_set, composers, conductors, choruses, compositions, orchestras,
    songwriters, producers, engineers, musicians, external_links,
    cover_image_url, back_cover_image_url, thumbnail_image_url,
    revision, created_at, updated_at
)
SELECT
    r.id,
    g.title,
    g.sort_title,
    r.subtitle,
    g.artist,
    COALESCE((
        SELECT jsonb_agg(jsonb_build_object(
            'name', c.credited_name,
            'join_phrase', c.join_phrase,
            'sequence', c.sequence
        ) ORDER BY c.sequence NULLS LAST, c.created_at)
        FROM music_artist_credits AS c
        WHERE c.release_id = r.id
    ), (
        SELECT jsonb_agg(jsonb_build_object(
            'name', c.credited_name,
            'join_phrase', c.join_phrase,
            'sequence', c.sequence
        ) ORDER BY c.sequence NULLS LAST, c.created_at)
        FROM music_artist_credits AS c
        WHERE c.release_group_id = g.id AND c.release_id IS NULL
    ), '[]'::jsonb),
    g.original_release_date,
    CASE WHEN g.original_release_date_parts IS NULL THEN NULL
         ELSE to_jsonb(g.original_release_date_parts) END,
    g.recording_date,
    CASE WHEN g.recording_date_parts IS NULL THEN NULL
         ELSE to_jsonb(g.recording_date_parts) END,
    r.release_date,
    CASE WHEN r.release_date_parts IS NULL THEN NULL
         ELSE to_jsonb(r.release_date_parts) END,
    COALESCE((SELECT l.label_name FROM music_release_labels AS l
              WHERE l.release_id = r.id ORDER BY l.sequence NULLS LAST, l.created_at LIMIT 1),
             r.publisher),
    COALESCE(r.release_type, r.packaging),
    COALESCE(r.barcode, r.upc),
    COALESCE(r.catalog_number, (SELECT l.catalog_number FROM music_release_labels AS l
              WHERE l.release_id = r.id AND l.catalog_number IS NOT NULL
              ORDER BY l.sequence NULLS LAST, l.created_at LIMIT 1)),
    COALESCE((SELECT jsonb_agg(gg.value ORDER BY gg.position, gg.created_at)
              FROM music_release_group_genres AS gg WHERE gg.release_group_id = g.id),
             '[]'::jsonb),
    r.packaging,
    g.studio,
    CASE WHEN g.studio IS NULL OR btrim(g.studio) = '' THEN '[]'::jsonb
         ELSE jsonb_build_array(g.studio) END,
    r.country_code,
    g.is_live,
    COALESCE((SELECT jsonb_agg(sound_types.sound_type ORDER BY sound_types.first_medium)
              FROM (
                  SELECT m.sound_type, min(m.medium_number) AS first_medium
                  FROM music_mediums AS m
                  WHERE m.release_id = r.id AND m.sound_type IS NOT NULL
                  GROUP BY m.sound_type
              ) AS sound_types), '[]'::jsonb),
    (SELECT m.vinyl_color FROM music_mediums AS m
     WHERE m.release_id = r.id AND m.vinyl_color IS NOT NULL
     ORDER BY m.medium_number LIMIT 1),
    (SELECT m.vinyl_weight FROM music_mediums AS m
     WHERE m.release_id = r.id AND m.vinyl_weight IS NOT NULL
     ORDER BY m.medium_number LIMIT 1),
    (SELECT m.rpm FROM music_mediums AS m
     WHERE m.release_id = r.id AND m.rpm IS NOT NULL
     ORDER BY m.medium_number LIMIT 1),
    NULL,
    (SELECT m.spars FROM music_mediums AS m
     WHERE m.release_id = r.id AND m.spars IS NOT NULL
     ORDER BY m.medium_number LIMIT 1),
    NULL,
    COALESCE((SELECT jsonb_agg(jsonb_build_object(
        'name', p.name, 'role', c.role, 'role_id', c.role_id, 'sequence', c.sequence
    ) ORDER BY c.sequence NULLS LAST, c.created_at)
    FROM music_release_contributions AS c JOIN persons AS p ON p.id = c.person_id
    WHERE c.release_id = r.id AND lower(btrim(c.role)) = 'composer'), '[]'::jsonb),
    COALESCE((SELECT jsonb_agg(jsonb_build_object(
        'name', p.name, 'role', c.role, 'role_id', c.role_id, 'sequence', c.sequence
    ) ORDER BY c.sequence NULLS LAST, c.created_at)
    FROM music_release_contributions AS c JOIN persons AS p ON p.id = c.person_id
    WHERE c.release_id = r.id AND lower(btrim(c.role)) = 'conductor'), '[]'::jsonb),
    COALESCE((SELECT jsonb_agg(p.name ORDER BY c.sequence NULLS LAST, c.created_at)
    FROM music_release_contributions AS c JOIN persons AS p ON p.id = c.person_id
    WHERE c.release_id = r.id AND lower(btrim(c.role)) IN ('chorus', 'choir')), '[]'::jsonb),
    COALESCE((SELECT jsonb_agg(p.name ORDER BY c.sequence NULLS LAST, c.created_at)
    FROM music_release_contributions AS c JOIN persons AS p ON p.id = c.person_id
    WHERE c.release_id = r.id AND lower(btrim(c.role)) = 'composition'), '[]'::jsonb),
    COALESCE((SELECT jsonb_agg(p.name ORDER BY c.sequence NULLS LAST, c.created_at)
    FROM music_release_contributions AS c JOIN persons AS p ON p.id = c.person_id
    WHERE c.release_id = r.id AND lower(btrim(c.role)) = 'orchestra'), '[]'::jsonb),
    COALESCE((SELECT jsonb_agg(jsonb_build_object(
        'name', p.name, 'role', c.role, 'role_id', c.role_id, 'sequence', c.sequence
    ) ORDER BY c.sequence NULLS LAST, c.created_at)
    FROM music_release_contributions AS c JOIN persons AS p ON p.id = c.person_id
    WHERE c.release_id = r.id AND lower(btrim(c.role)) = 'songwriter'), '[]'::jsonb),
    COALESCE((SELECT jsonb_agg(jsonb_build_object(
        'name', p.name, 'role', c.role, 'role_id', c.role_id, 'sequence', c.sequence
    ) ORDER BY c.sequence NULLS LAST, c.created_at)
    FROM music_release_contributions AS c JOIN persons AS p ON p.id = c.person_id
    WHERE c.release_id = r.id AND lower(btrim(c.role)) = 'producer'), '[]'::jsonb),
    COALESCE((SELECT jsonb_agg(jsonb_build_object(
        'name', p.name, 'role', c.role, 'role_id', c.role_id, 'sequence', c.sequence
    ) ORDER BY c.sequence NULLS LAST, c.created_at)
    FROM music_release_contributions AS c JOIN persons AS p ON p.id = c.person_id
    WHERE c.release_id = r.id AND lower(btrim(c.role)) = 'engineer'), '[]'::jsonb),
    COALESCE((SELECT jsonb_agg(jsonb_build_object(
        'name', p.name, 'role', c.role, 'role_id', c.role_id, 'sequence', c.sequence
    ) ORDER BY c.sequence NULLS LAST, c.created_at)
    FROM music_release_contributions AS c JOIN persons AS p ON p.id = c.person_id
    WHERE c.release_id = r.id AND lower(btrim(c.role)) = 'musician'), '[]'::jsonb),
    COALESCE((SELECT jsonb_agg(jsonb_build_object(
        'url', e.url, 'site', e.site, 'name', e.name, 'kind', e.kind,
        'description', e.description, 'position', e.position
    ) ORDER BY e.position, e.created_at)
    FROM entity_links AS e
    WHERE e.entity_type = 'music_release' AND e.entity_id = r.id AND e.link_type = 'external'),
    '[]'::jsonb),
    COALESCE(r.cover_image_url, g.cover_image_url),
    NULL,
    NULL,
    1,
    r.created_at,
    GREATEST(r.updated_at, g.updated_at)
FROM music_releases AS r
JOIN music_release_groups AS g ON g.id = r.release_group_id;

INSERT INTO music_items (
    id, title, sort_title, artist, artist_credits,
    original_release_date, original_release_date_parts,
    recording_date, recording_date_parts, genres, studio, studios, is_live,
    composers, conductors, choruses, compositions, orchestras, songwriters,
    producers, engineers, musicians, external_links, cover_image_url,
    back_cover_image_url,
    revision, created_at, updated_at
)
SELECT
    g.id, g.title, g.sort_title, g.artist,
    COALESCE((SELECT jsonb_agg(jsonb_build_object(
        'name', c.credited_name, 'join_phrase', c.join_phrase, 'sequence', c.sequence
    ) ORDER BY c.sequence NULLS LAST, c.created_at)
    FROM music_artist_credits AS c
    WHERE c.release_group_id = g.id AND c.release_id IS NULL), '[]'::jsonb),
    g.original_release_date,
    CASE WHEN g.original_release_date_parts IS NULL THEN NULL
         ELSE to_jsonb(g.original_release_date_parts) END,
    g.recording_date,
    CASE WHEN g.recording_date_parts IS NULL THEN NULL
         ELSE to_jsonb(g.recording_date_parts) END,
    COALESCE((SELECT jsonb_agg(gg.value ORDER BY gg.position, gg.created_at)
              FROM music_release_group_genres AS gg WHERE gg.release_group_id = g.id),
             '[]'::jsonb),
    g.studio,
    CASE WHEN g.studio IS NULL OR btrim(g.studio) = '' THEN '[]'::jsonb
         ELSE jsonb_build_array(g.studio) END,
    g.is_live,
    '[]'::jsonb, '[]'::jsonb, '[]'::jsonb, '[]'::jsonb, '[]'::jsonb,
    '[]'::jsonb, '[]'::jsonb, '[]'::jsonb, '[]'::jsonb,
    COALESCE((SELECT jsonb_agg(jsonb_build_object(
        'url', e.url, 'site', e.site, 'name', e.name, 'kind', e.kind,
        'description', e.description, 'position', e.position
    ) ORDER BY e.position, e.created_at)
    FROM entity_links AS e
    WHERE e.entity_type = 'music_release_group' AND e.entity_id = g.id AND e.link_type = 'external'),
    '[]'::jsonb),
    g.cover_image_url,
    NULL,
    1,
    g.created_at,
    g.updated_at
FROM music_release_groups AS g
WHERE NOT EXISTS (
    SELECT 1 FROM music_releases AS r WHERE r.release_group_id = g.id
);

INSERT INTO music_item_discs (
    id, music_item_id, disc_number, title, created_at, updated_at
)
SELECT
    m.id,
    m.release_id,
    m.medium_number,
    m.title,
    m.created_at,
    m.updated_at
FROM music_mediums AS m
JOIN music_releases AS r ON r.id = m.release_id;

WITH ordered_tracks AS (
    SELECT
        t.id,
        t.medium_id,
        t.position,
        t.title,
        t.artist,
        t.duration_ms,
        t.created_at,
        t.updated_at,
        row_number() OVER (
            PARTITION BY t.medium_id ORDER BY t.position, t.created_at, t.id
        ) - 1 AS position_order
    FROM music_tracks AS t
    WHERE NOT t.is_header
)
INSERT INTO music_item_tracks (
    id, disc_id, position, position_order, title, artist, duration_ms, created_at, updated_at
)
SELECT
    t.id,
    t.medium_id,
    t.position,
    t.position_order,
    t.title,
    t.artist,
    t.duration_ms,
    t.created_at,
    t.updated_at
FROM ordered_tracks AS t;

CREATE TABLE IF NOT EXISTS music_item_migration_conflicts (
    old_release_id uuid PRIMARY KEY,
    music_item_id uuid NOT NULL,
    conflict_type text NOT NULL,
    old_release_title text NOT NULL,
    selected_item_title text NOT NULL
);

CREATE TABLE IF NOT EXISTS music_item_legacy_identity_map (
    map_id bigserial PRIMARY KEY,
    old_entity_type text NOT NULL,
    old_entity_id uuid NOT NULL,
    new_entity_type text,
    new_entity_id uuid,
    catalog_item_id uuid,
    resolution text NOT NULL
);

CREATE INDEX IF NOT EXISTS ix_music_item_legacy_identity_map_old
    ON music_item_legacy_identity_map (old_entity_type, old_entity_id);

INSERT INTO music_item_legacy_identity_map (
    old_entity_type, old_entity_id, new_entity_type, new_entity_id,
    catalog_item_id, resolution
)
SELECT 'music_release', r.id, 'catalog_item', r.id, r.id, 'preserved_concrete_id'
FROM music_releases AS r
ON CONFLICT DO NOTHING;

INSERT INTO music_item_legacy_identity_map (
    old_entity_type, old_entity_id, new_entity_type, new_entity_id,
    catalog_item_id, resolution
)
SELECT 'music_release_group', g.id, 'catalog_item', g.id, g.id, 'preserved_group_only_id'
FROM music_release_groups AS g
WHERE NOT EXISTS (
    SELECT 1 FROM music_releases AS r WHERE r.release_group_id = g.id
)
ON CONFLICT DO NOTHING;

INSERT INTO music_item_legacy_identity_map (
    old_entity_type, old_entity_id, new_entity_type, new_entity_id,
    catalog_item_id, resolution
)
SELECT
    'music_release_group', g.id, 'catalog_item', r.id, r.id,
    CASE WHEN child_counts.release_count = 1
         THEN 'single_release_unambiguous'
         ELSE 'ambiguous_parent_multiple_releases'
    END
FROM music_release_groups AS g
JOIN music_releases AS r ON r.release_group_id = g.id
JOIN (
    SELECT release_group_id, count(*) AS release_count
    FROM music_releases
    GROUP BY release_group_id
) AS child_counts ON child_counts.release_group_id = g.id
ON CONFLICT DO NOTHING;

INSERT INTO music_item_legacy_identity_map (
    old_entity_type, old_entity_id, new_entity_type, new_entity_id,
    catalog_item_id, resolution
)
SELECT 'music_medium', m.id, 'music_disc', m.id, m.release_id, 'preserved_child_id'
FROM music_mediums AS m
JOIN music_releases AS r ON r.id = m.release_id
ON CONFLICT DO NOTHING;

INSERT INTO music_item_legacy_identity_map (
    old_entity_type, old_entity_id, new_entity_type, new_entity_id,
    catalog_item_id, resolution
)
SELECT
    'music_track', t.id,
    CASE WHEN t.is_header THEN NULL ELSE 'music_track' END,
    CASE WHEN t.is_header THEN NULL ELSE t.id END,
    m.release_id,
    CASE WHEN t.is_header THEN 'legacy_header_excluded' ELSE 'preserved_child_id' END
FROM music_tracks AS t
JOIN music_mediums AS m ON m.id = t.medium_id
JOIN music_releases AS r ON r.id = m.release_id
ON CONFLICT DO NOTHING;

INSERT INTO music_item_migration_conflicts (
    old_release_id, music_item_id, conflict_type, old_release_title, selected_item_title
)
SELECT r.id, r.id, 'release_title_differs_from_group_title', r.title, g.title
FROM music_releases AS r
JOIN music_release_groups AS g ON g.id = r.release_group_id
WHERE r.title <> g.title
ON CONFLICT (old_release_id) DO NOTHING;

CREATE TABLE IF NOT EXISTS music_item_migration_review (
    music_item_id uuid NOT NULL,
    source_table text NOT NULL,
    source_id uuid NOT NULL,
    field_key text NOT NULL,
    legacy_payload jsonb NOT NULL,
    PRIMARY KEY (music_item_id, source_table, source_id, field_key)
);

-- Keep catalog values with no equivalent in the saved CLZ Music form available
-- for a human migration review instead of silently dropping them.
INSERT INTO music_item_migration_review (
    music_item_id, source_table, source_id, field_key, legacy_payload
)
SELECT
    r.id,
    'music_release_contributions',
    c.id,
    'unmapped_credit_role',
    jsonb_build_object(
        'role', c.role,
        'role_id', c.role_id,
        'sequence', c.sequence,
        'person_id', c.person_id,
        'person_name', p.name
    )
FROM music_release_contributions AS c
JOIN music_releases AS r ON r.id = c.release_id
JOIN persons AS p ON p.id = c.person_id
WHERE lower(btrim(c.role)) NOT IN (
    'composer', 'conductor', 'chorus', 'choir', 'composition', 'orchestra',
    'songwriter', 'producer', 'engineer', 'musician'
)
ON CONFLICT DO NOTHING;

INSERT INTO music_item_migration_review (
    music_item_id, source_table, source_id, field_key, legacy_payload
)
SELECT
    m.release_id,
    'music_medium_missing_track_positions',
    missing.id,
    'legacy_missing_track_position',
    jsonb_build_object('position', missing.position, 'position_order', missing.position_order)
FROM music_medium_missing_track_positions AS missing
JOIN music_mediums AS m ON m.id = missing.medium_id
JOIN music_releases AS r ON r.id = m.release_id
ON CONFLICT DO NOTHING;

INSERT INTO music_item_migration_review (
    music_item_id, source_table, source_id, field_key, legacy_payload
)
SELECT
    m.release_id,
    'music_tracks',
    t.id,
    'legacy_header_track',
    jsonb_build_object(
        'position', t.position,
        'title', t.title,
        'artist', t.artist,
        'indent_level', t.indent_level,
        'parent_header_id', t.parent_header_id
    )
FROM music_tracks AS t
JOIN music_mediums AS m ON m.id = t.medium_id
JOIN music_releases AS r ON r.id = m.release_id
WHERE t.is_header
ON CONFLICT DO NOTHING;

INSERT INTO music_item_migration_review (
    music_item_id, source_table, source_id, field_key, legacy_payload
)
SELECT
    r.id,
    'music_release_labels',
    l.id,
    'additional_label',
    jsonb_build_object(
        'label_name', l.label_name,
        'catalog_number', l.catalog_number,
        'sequence', l.sequence
    )
FROM music_release_labels AS l
JOIN music_releases AS r ON r.id = l.release_id
WHERE l.id <> (
    SELECT first_label.id
    FROM music_release_labels AS first_label
    WHERE first_label.release_id = r.id
    ORDER BY first_label.sequence NULLS LAST, first_label.created_at
    LIMIT 1
)
ON CONFLICT DO NOTHING;

INSERT INTO music_item_migration_review (
    music_item_id, source_table, source_id, field_key, legacy_payload
)
SELECT
    r.id,
    'music_release_identifiers',
    i.id,
    'additional_identifier',
    jsonb_build_object(
        'identifier_type', i.identifier_type,
        'value', i.value,
        'normalized_value', i.normalized_value,
        'is_primary', i.is_primary
    )
FROM music_release_identifiers AS i
JOIN music_releases AS r ON r.id = i.release_id
WHERE NOT (
    lower(i.identifier_type) IN ('barcode', 'upc', 'ean', 'ean13')
    AND i.value = COALESCE(r.barcode, r.upc)
)
AND NOT (
    lower(i.identifier_type) IN ('catalog_number', 'cat_no')
    AND i.value = r.catalog_number
)
ON CONFLICT DO NOTHING;

INSERT INTO music_item_migration_review (
    music_item_id, source_table, source_id, field_key, legacy_payload
)
SELECT
    r.id,
    'music_release_groups',
    g.id,
    'legacy_original_title',
    jsonb_build_object('original_title', g.original_title)
FROM music_release_groups AS g
JOIN music_releases AS r ON r.release_group_id = g.id
WHERE g.original_title IS NOT NULL AND btrim(g.original_title) <> ''
ON CONFLICT DO NOTHING;

INSERT INTO music_item_migration_review (
    music_item_id, source_table, source_id, field_key, legacy_payload
)
SELECT
    g.id,
    'music_release_groups',
    g.id,
    'legacy_original_title',
    jsonb_build_object('original_title', g.original_title)
FROM music_release_groups AS g
WHERE g.original_title IS NOT NULL
  AND btrim(g.original_title) <> ''
  AND NOT EXISTS (
      SELECT 1 FROM music_releases AS r WHERE r.release_group_id = g.id
  )
ON CONFLICT DO NOTHING;

DO $$
DECLARE
    expected_items bigint;
    actual_items bigint;
    expected_discs bigint;
    actual_discs bigint;
    expected_tracks bigint;
    actual_tracks bigint;
BEGIN
    SELECT
        (SELECT count(*) FROM music_releases) +
        (SELECT count(*) FROM music_release_groups AS g
         WHERE NOT EXISTS (
             SELECT 1 FROM music_releases AS r WHERE r.release_group_id = g.id
         ))
    INTO expected_items;
    SELECT count(*) INTO actual_items FROM music_items;
    SELECT count(*) INTO expected_discs FROM music_mediums AS m
    JOIN music_releases AS r ON r.id = m.release_id;
    SELECT count(*) INTO actual_discs FROM music_item_discs;
    SELECT count(*) INTO expected_tracks FROM music_tracks AS t
    JOIN music_mediums AS m ON m.id = t.medium_id
    JOIN music_releases AS r ON r.id = m.release_id
    WHERE NOT t.is_header;
    SELECT count(*) INTO actual_tracks FROM music_item_tracks;

    IF actual_items <> expected_items THEN
        RAISE EXCEPTION 'Music item count mismatch: expected %, found %', expected_items, actual_items;
    END IF;
    IF actual_discs <> expected_discs THEN
        RAISE EXCEPTION 'Music disc count mismatch: expected %, found %', expected_discs, actual_discs;
    END IF;
    IF actual_tracks <> expected_tracks THEN
        RAISE EXCEPTION 'Music track count mismatch: expected %, found %', expected_tracks, actual_tracks;
    END IF;
END $$;

COMMIT;
