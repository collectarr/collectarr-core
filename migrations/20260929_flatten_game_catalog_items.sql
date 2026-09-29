-- One-way Game Work -> Release backfill into concrete Catalog Item roots.
-- Run only against a reviewed non-live copy of the pinned Core baseline.
-- Source tables stay intact until App and Sync have moved to these identities.

BEGIN;

CREATE TABLE IF NOT EXISTS game_items (
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
CREATE INDEX IF NOT EXISTS ix_game_items_title ON game_items (title);
CREATE INDEX IF NOT EXISTS ix_game_items_sort_key ON game_items (sort_key);
CREATE INDEX IF NOT EXISTS ix_game_items_barcode ON game_items (barcode);
CREATE INDEX IF NOT EXISTS ix_game_items_catalog_number ON game_items (catalog_number);

CREATE TABLE IF NOT EXISTS game_item_identifiers (
    id uuid PRIMARY KEY,
    game_item_id uuid NOT NULL REFERENCES game_items(id) ON DELETE CASCADE,
    identifier_type varchar(64) NOT NULL,
    value varchar(255) NOT NULL,
    normalized_value varchar(255) NOT NULL,
    is_primary boolean NOT NULL DEFAULT false,
    created_at timestamptz NOT NULL,
    updated_at timestamptz NOT NULL,
    CONSTRAINT uq_game_item_identifier_normalized
        UNIQUE (game_item_id, identifier_type, normalized_value)
);
CREATE INDEX IF NOT EXISTS ix_game_item_identifiers_type_value
    ON game_item_identifiers (identifier_type, normalized_value);

CREATE TABLE IF NOT EXISTS game_item_legacy_identity_map (
    old_entity_type text NOT NULL,
    old_entity_id uuid NOT NULL,
    catalog_item_id uuid NOT NULL REFERENCES game_items(id) ON DELETE CASCADE,
    resolution text NOT NULL,
    PRIMARY KEY (old_entity_type, old_entity_id, catalog_item_id)
);
CREATE INDEX IF NOT EXISTS ix_game_item_legacy_identity_map_old
    ON game_item_legacy_identity_map (old_entity_type, old_entity_id);

CREATE TABLE IF NOT EXISTS game_item_migration_review (
    catalog_item_id uuid NOT NULL REFERENCES game_items(id) ON DELETE CASCADE,
    source_table text NOT NULL,
    source_id uuid NOT NULL,
    field_key text NOT NULL,
    legacy_payload jsonb NOT NULL,
    PRIMARY KEY (catalog_item_id, source_table, source_id, field_key)
);

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM game_items)
       OR EXISTS (SELECT 1 FROM game_item_identifiers)
       OR EXISTS (SELECT 1 FROM game_item_legacy_identity_map)
       OR EXISTS (SELECT 1 FROM game_item_migration_review) THEN
        RAISE EXCEPTION 'Game Catalog Item backfill destination is not empty';
    END IF;
    IF EXISTS (
        SELECT 1 FROM game_releases r
        LEFT JOIN game_works w ON w.id = r.work_id
        WHERE w.id IS NULL
    ) THEN
        RAISE EXCEPTION 'Game Catalog Item backfill found a release without a work';
    END IF;
    IF EXISTS (
        SELECT 1 FROM game_works w
        WHERE NOT EXISTS (SELECT 1 FROM game_releases r WHERE r.work_id = w.id)
          AND EXISTS (SELECT 1 FROM game_releases r WHERE r.id = w.id)
    ) THEN
        RAISE EXCEPTION 'Game Catalog Item backfill found a root ID collision';
    END IF;
END $$;

-- Every Release keeps its UUID and receives shared Work fields. Work-only
-- values that cannot be assigned to a specific edition remain review data.
WITH item_source AS (
    SELECT r.id AS item_id, r.work_id, r.id AS release_id,
           w.title, w.sort_title, w.subtitle, w.description,
           w.age_rating, w.audience_rating, w.original_language,
           w.release_date AS work_release_date,
           w.release_date_parts AS work_release_date_parts,
           w.created_at AS work_created_at, w.updated_at AS work_updated_at,
           r.release_title, r.platform, r.release_date, r.release_date_parts,
           r.region_code, r.format, r.publisher, r.catalog_number,
           r.barcode, r.release_status, r.language,
           r.cover_image_url, r.cover_image_key,
           r.created_at AS release_created_at, r.updated_at AS release_updated_at
    FROM game_releases r
    JOIN game_works w ON w.id = r.work_id
    UNION ALL
    SELECT w.id AS item_id, w.id AS work_id, NULL::uuid AS release_id,
           w.title, w.sort_title, w.subtitle, w.description,
           w.age_rating, w.audience_rating, w.original_language,
           w.release_date AS work_release_date,
           w.release_date_parts AS work_release_date_parts,
           w.created_at AS work_created_at, w.updated_at AS work_updated_at,
           NULL::varchar AS release_title, NULL::varchar AS platform,
           NULL::date AS release_date, NULL::varchar AS release_date_parts,
           NULL::varchar AS region_code, NULL::varchar AS format,
           NULL::varchar AS publisher, NULL::varchar AS catalog_number,
           NULL::varchar AS barcode, NULL::varchar AS release_status,
           NULL::varchar AS language, NULL::varchar AS cover_image_url,
           NULL::varchar AS cover_image_key,
           NULL::timestamptz AS release_created_at,
           NULL::timestamptz AS release_updated_at
    FROM game_works w
    WHERE NOT EXISTS (SELECT 1 FROM game_releases r WHERE r.work_id = w.id)
)
INSERT INTO game_items (
    id, title, sort_key, barcode, catalog_number, details, revision,
    created_at, updated_at
)
SELECT
    s.item_id,
    s.title,
    s.sort_title,
    s.barcode,
    s.catalog_number,
    jsonb_strip_nulls(jsonb_build_object(
        'title', s.title,
        'sort_key', s.sort_title,
        'subtitle', s.subtitle,
        'description', s.description,
        'age_rating', s.age_rating,
        'audience_rating', s.audience_rating,
        'edition_title', s.release_title,
        'physical_format', s.format,
        'publisher', s.publisher,
        'release_date', COALESCE(
            to_jsonb(s.release_date_parts), to_jsonb(s.release_date),
            to_jsonb(s.work_release_date_parts), to_jsonb(s.work_release_date)
        ),
        'release_date_parts', COALESCE(s.release_date_parts, s.work_release_date_parts),
        'release_region', s.region_code,
        'release_status', s.release_status,
        'language', COALESCE(s.language, s.original_language),
        'barcode', s.barcode,
        'catalog_number', s.catalog_number,
        'cover_image_url', COALESCE(s.cover_image_url, (SELECT w.cover_image_url FROM game_works w WHERE w.id = s.work_id)),
        'thumbnail_image_url', COALESCE(s.cover_image_url, (SELECT w.cover_image_url FROM game_works w WHERE w.id = s.work_id)),
        'genres', COALESCE(work_values.genres, '[]'::jsonb),
        'company_roles', COALESCE(work_values.company_roles, '[]'::jsonb),
        'developers', COALESCE(work_values.developers, '[]'::jsonb),
        'platforms', COALESCE(release_values.platforms, work_values.platforms, '[]'::jsonb),
        'identifiers', COALESCE(identifier_values.identifiers, '[]'::jsonb),
        'series_title', work_values.series_title,
        'series_tags', COALESCE(work_values.series_tags, '[]'::jsonb),
        'search_aliases', COALESCE(alias_values.aliases, '[]'::jsonb),
        'external_links', COALESCE(link_values.external_links, '[]'::jsonb),
        'trailer_urls', COALESCE(link_values.trailer_urls, '[]'::jsonb)
    )),
    1,
    LEAST(s.work_created_at, COALESCE(s.release_created_at, s.work_created_at)),
    GREATEST(s.work_updated_at, COALESCE(s.release_updated_at, s.work_updated_at))
FROM item_source s
LEFT JOIN LATERAL (
    SELECT
        (SELECT jsonb_agg(g.value ORDER BY g.sequence, g.value)
         FROM game_genres g WHERE g.work_id = s.work_id) AS genres,
        (SELECT jsonb_agg(DISTINCT p.role ORDER BY p.role)
         FROM game_company_roles p WHERE p.work_id = s.work_id) AS company_roles,
        (SELECT jsonb_agg(DISTINCT o.name ORDER BY o.name)
         FROM game_company_roles cr
         JOIN organizations o ON o.id = cr.organization_id
         WHERE cr.work_id = s.work_id AND lower(cr.role) = 'developer') AS developers,
        (SELECT jsonb_agg(p.platform_name ORDER BY p.sequence NULLS LAST, p.platform_name)
         FROM game_platforms p WHERE p.work_id = s.work_id) AS platforms,
        (SELECT m.series_name FROM game_series_memberships m
         WHERE m.work_id = s.work_id
         ORDER BY m.sequence NULLS LAST, m.series_name LIMIT 1) AS series_title,
        (SELECT jsonb_agg(m.series_name ORDER BY m.sequence NULLS LAST, m.series_name)
         FROM game_series_memberships m WHERE m.work_id = s.work_id) AS series_tags
) work_values ON true
LEFT JOIN LATERAL (
    SELECT jsonb_agg(platform_name ORDER BY sequence NULLS LAST, platform_name) AS platforms
    FROM (
        SELECT p.platform_name, rp.sequence
        FROM game_release_platforms rp
        JOIN game_platforms p ON p.id = rp.platform_id
        WHERE rp.release_id = s.release_id
        UNION ALL
        SELECT s.platform, 0
        WHERE s.platform IS NOT NULL
          AND NOT EXISTS (
              SELECT 1 FROM game_release_platforms rp
              WHERE rp.release_id = s.release_id
          )
    ) release_platform_values
) release_values ON true
LEFT JOIN LATERAL (
    SELECT jsonb_agg(jsonb_strip_nulls(jsonb_build_object(
        'identifier_type', i.identifier_type,
        'value', i.value,
        'normalized_value', i.normalized_value,
        'is_primary', i.is_primary
    )) ORDER BY i.identifier_type, i.value) AS identifiers
    FROM game_release_identifiers i
    WHERE i.release_id = s.release_id AND i.source_provider IS NULL
) identifier_values ON true
LEFT JOIN LATERAL (
    SELECT jsonb_agg(a.alias ORDER BY a.position, a.created_at) AS aliases
    FROM entity_aliases a
    WHERE (a.entity_type = 'game_work' AND a.entity_id = s.work_id)
       OR (a.entity_type = 'game_release' AND a.entity_id = s.release_id)
) alias_values ON true
LEFT JOIN LATERAL (
    SELECT
        jsonb_agg(jsonb_strip_nulls(jsonb_build_object(
            'url', l.url, 'site', l.site, 'name', l.name, 'kind', l.kind,
            'description', l.description, 'position', l.position, 'link_type', l.link_type
        )) ORDER BY l.position, l.created_at) FILTER (WHERE l.link_type = 'external') AS external_links,
        jsonb_agg(jsonb_strip_nulls(jsonb_build_object(
            'url', l.url, 'site', l.site, 'name', l.name, 'kind', l.kind,
            'description', l.description, 'position', l.position, 'link_type', l.link_type
        )) ORDER BY l.position, l.created_at) FILTER (WHERE l.link_type = 'trailer') AS trailer_urls
    FROM entity_links l
    WHERE (l.entity_type = 'game_work' AND l.entity_id = s.work_id)
       OR (l.entity_type = 'game_release' AND l.entity_id = s.release_id)
) link_values ON true;

INSERT INTO game_item_identifiers (
    id, game_item_id, identifier_type, value, normalized_value, is_primary,
    created_at, updated_at
)
SELECT
    i.id, i.release_id, i.identifier_type, i.value, i.normalized_value,
    i.is_primary, i.created_at, i.updated_at
FROM game_release_identifiers i
WHERE i.source_provider IS NULL;

INSERT INTO game_item_identifiers (
    id, game_item_id, identifier_type, value, normalized_value, is_primary,
    created_at, updated_at
)
SELECT
    i.id, w.id, i.identifier_type, i.value, i.normalized_value,
    i.is_primary, i.created_at, i.updated_at
FROM game_identifiers i
JOIN game_works w ON w.id = i.work_id
WHERE i.source_provider IS NULL
  AND NOT EXISTS (SELECT 1 FROM game_releases r WHERE r.work_id = w.id);

INSERT INTO game_item_identifiers (
    id, game_item_id, identifier_type, value, normalized_value, is_primary,
    created_at, updated_at
)
SELECT
    i.id, w.id, i.identifier_type, i.value, i.normalized_value,
    i.is_primary, i.created_at, i.updated_at
FROM game_identifiers i
JOIN game_works w ON w.id = i.work_id
WHERE i.source_provider IS NULL
  AND NOT EXISTS (SELECT 1 FROM game_releases r WHERE r.work_id = w.id);

INSERT INTO game_item_legacy_identity_map (
    old_entity_type, old_entity_id, catalog_item_id, resolution
)
SELECT 'game_release', r.id, r.id, 'preserved_as_catalog_item'
FROM game_releases r;

INSERT INTO game_item_legacy_identity_map (
    old_entity_type, old_entity_id, catalog_item_id, resolution
)
SELECT
    'game_work', w.id, r.id,
    CASE WHEN counts.release_count = 1 THEN 'mapped_to_single_item'
         ELSE 'ambiguous_multiple_releases' END
FROM game_works w
JOIN game_releases r ON r.work_id = w.id
JOIN LATERAL (
    SELECT count(*)::integer AS release_count
    FROM game_releases child WHERE child.work_id = w.id
) counts ON true;

INSERT INTO game_item_legacy_identity_map (
    old_entity_type, old_entity_id, catalog_item_id, resolution
)
SELECT 'game_work', w.id, w.id, 'preserved_without_release'
FROM game_works w
WHERE NOT EXISTS (SELECT 1 FROM game_releases r WHERE r.work_id = w.id);

INSERT INTO game_item_migration_review (
    catalog_item_id, source_table, source_id, field_key, legacy_payload
)
SELECT i.id, 'game_works', w.id, 'source_row', to_jsonb(w)
FROM game_items i
JOIN game_item_legacy_identity_map m
  ON m.catalog_item_id = i.id AND m.old_entity_type = 'game_work'
JOIN game_works w ON w.id = m.old_entity_id
ON CONFLICT DO NOTHING;

INSERT INTO game_item_migration_review (
    catalog_item_id, source_table, source_id, field_key, legacy_payload
)
SELECT r.id, 'game_releases', r.id, 'source_row', to_jsonb(r)
FROM game_releases r;

INSERT INTO game_item_migration_review (
    catalog_item_id, source_table, source_id, field_key, legacy_payload
)
SELECT i.id, 'game_work_children', w.id, 'source_rows', jsonb_build_object(
    'genres', COALESCE((SELECT jsonb_agg(to_jsonb(x)) FROM game_genres x WHERE x.work_id = w.id), '[]'::jsonb),
    'platforms', COALESCE((SELECT jsonb_agg(to_jsonb(x)) FROM game_platforms x WHERE x.work_id = w.id), '[]'::jsonb),
    'identifiers', COALESCE((SELECT jsonb_agg(to_jsonb(x)) FROM game_identifiers x WHERE x.work_id = w.id), '[]'::jsonb),
    'company_roles', COALESCE((SELECT jsonb_agg(to_jsonb(x)) FROM game_company_roles x WHERE x.work_id = w.id), '[]'::jsonb),
    'age_ratings', COALESCE((SELECT jsonb_agg(to_jsonb(x)) FROM game_age_ratings x WHERE x.work_id = w.id), '[]'::jsonb),
    'series_memberships', COALESCE((SELECT jsonb_agg(to_jsonb(x)) FROM game_series_memberships x WHERE x.work_id = w.id), '[]'::jsonb),
    'provider_ids', COALESCE((SELECT jsonb_agg(to_jsonb(x)) FROM external_provider_ids x WHERE x.entity_type = 'game_work' AND x.entity_id = w.id), '[]'::jsonb),
    'people', COALESCE((SELECT jsonb_agg(to_jsonb(x)) FROM entity_persons x WHERE x.entity_type = 'game_work' AND x.entity_id = w.id), '[]'::jsonb),
    'organizations', COALESCE((SELECT jsonb_agg(to_jsonb(x)) FROM entity_organizations x WHERE x.entity_type = 'game_work' AND x.entity_id = w.id), '[]'::jsonb),
    'aliases', COALESCE((SELECT jsonb_agg(to_jsonb(x)) FROM entity_aliases x WHERE x.entity_type = 'game_work' AND x.entity_id = w.id), '[]'::jsonb),
    'links', COALESCE((SELECT jsonb_agg(to_jsonb(x)) FROM entity_links x WHERE x.entity_type = 'game_work' AND x.entity_id = w.id), '[]'::jsonb),
    'images', COALESCE((SELECT jsonb_agg(to_jsonb(x)) FROM image_assets x WHERE x.entity_type = 'game_work' AND x.entity_id = w.id), '[]'::jsonb)
)
FROM game_items i
JOIN game_item_legacy_identity_map m
  ON m.catalog_item_id = i.id AND m.old_entity_type = 'game_work'
JOIN game_works w ON w.id = m.old_entity_id
ON CONFLICT DO NOTHING;

INSERT INTO game_item_migration_review (
    catalog_item_id, source_table, source_id, field_key, legacy_payload
)
SELECT r.id, 'game_release_children', r.id, 'source_rows', jsonb_build_object(
    'identifiers', COALESCE((SELECT jsonb_agg(to_jsonb(x)) FROM game_release_identifiers x WHERE x.release_id = r.id), '[]'::jsonb),
    'platforms', COALESCE((SELECT jsonb_agg(to_jsonb(x)) FROM game_release_platforms x WHERE x.release_id = r.id), '[]'::jsonb),
    'provider_ids', COALESCE((SELECT jsonb_agg(to_jsonb(x)) FROM external_provider_ids x WHERE x.entity_type = 'game_release' AND x.entity_id = r.id), '[]'::jsonb),
    'people', COALESCE((SELECT jsonb_agg(to_jsonb(x)) FROM entity_persons x WHERE x.entity_type = 'game_release' AND x.entity_id = r.id), '[]'::jsonb),
    'organizations', COALESCE((SELECT jsonb_agg(to_jsonb(x)) FROM entity_organizations x WHERE x.entity_type = 'game_release' AND x.entity_id = r.id), '[]'::jsonb),
    'aliases', COALESCE((SELECT jsonb_agg(to_jsonb(x)) FROM entity_aliases x WHERE x.entity_type = 'game_release' AND x.entity_id = r.id), '[]'::jsonb),
    'links', COALESCE((SELECT jsonb_agg(to_jsonb(x)) FROM entity_links x WHERE x.entity_type = 'game_release' AND x.entity_id = r.id), '[]'::jsonb),
    'images', COALESCE((SELECT jsonb_agg(to_jsonb(x)) FROM image_assets x WHERE x.entity_type = 'game_release' AND x.entity_id = r.id), '[]'::jsonb)
)
FROM game_releases r;

DO $$
DECLARE
    expected_item_count bigint;
BEGIN
    SELECT (SELECT count(*) FROM game_releases)
         + (SELECT count(*) FROM game_works w
            WHERE NOT EXISTS (SELECT 1 FROM game_releases r WHERE r.work_id = w.id))
    INTO expected_item_count;
    IF (SELECT count(*) FROM game_items) <> expected_item_count THEN
        RAISE EXCEPTION 'Game item count does not match releases and standalone works';
    END IF;
    IF (SELECT count(*) FROM game_releases)
       <> (SELECT count(*) FROM game_item_legacy_identity_map WHERE old_entity_type = 'game_release') THEN
        RAISE EXCEPTION 'Game release identity map count does not match source';
    END IF;
    IF EXISTS (
        SELECT 1 FROM game_releases r
        LEFT JOIN game_item_legacy_identity_map m
          ON m.old_entity_type = 'game_release' AND m.old_entity_id = r.id
         AND m.catalog_item_id = r.id
        WHERE m.old_entity_id IS NULL
    ) THEN
        RAISE EXCEPTION 'Game Catalog Item backfill changed a release identity';
    END IF;
    IF (SELECT count(*) FROM game_item_legacy_identity_map WHERE old_entity_type = 'game_work')
       <> expected_item_count THEN
        RAISE EXCEPTION 'Game work identity map count does not match resulting roots';
    END IF;
    IF EXISTS (
        SELECT 1 FROM game_works w
        WHERE NOT EXISTS (
            SELECT 1 FROM game_item_legacy_identity_map m
            WHERE m.old_entity_type = 'game_work' AND m.old_entity_id = w.id
        )
    ) THEN
        RAISE EXCEPTION 'Game Catalog Item backfill left a work without an identity mapping';
    END IF;
    IF (SELECT count(*) FROM game_item_identifiers) < (
        SELECT count(*) FROM game_release_identifiers WHERE source_provider IS NULL
    ) + (
        SELECT count(*) FROM game_identifiers i
        WHERE i.source_provider IS NULL
          AND NOT EXISTS (SELECT 1 FROM game_releases r WHERE r.work_id = i.work_id)
    ) THEN
        RAISE EXCEPTION 'Game identifier count is lower than the eligible source rows';
    END IF;
    IF EXISTS (
        SELECT 1 FROM game_item_legacy_identity_map m
        LEFT JOIN game_items i ON i.id = m.catalog_item_id
        WHERE i.id IS NULL
    ) THEN
        RAISE EXCEPTION 'Game Catalog Item identity map contains an orphan';
    END IF;
END $$;

COMMIT;
