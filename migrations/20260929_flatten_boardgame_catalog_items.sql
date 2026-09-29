-- One-way Board Game Work -> Edition backfill into concrete Catalog Item roots.
-- Run only against a reviewed non-live copy of the pinned Core baseline.
-- Source tables stay intact until App and Sync have moved to these identities.

BEGIN;

CREATE TABLE IF NOT EXISTS boardgame_items (
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
CREATE INDEX IF NOT EXISTS ix_boardgame_items_title ON boardgame_items (title);
CREATE INDEX IF NOT EXISTS ix_boardgame_items_sort_key ON boardgame_items (sort_key);
CREATE INDEX IF NOT EXISTS ix_boardgame_items_barcode ON boardgame_items (barcode);
CREATE INDEX IF NOT EXISTS ix_boardgame_items_catalog_number
    ON boardgame_items (catalog_number);

CREATE TABLE IF NOT EXISTS boardgame_item_identifiers (
    id uuid PRIMARY KEY,
    boardgame_item_id uuid NOT NULL REFERENCES boardgame_items(id) ON DELETE CASCADE,
    identifier_type varchar(64) NOT NULL,
    value varchar(255) NOT NULL,
    normalized_value varchar(255) NOT NULL,
    is_primary boolean NOT NULL DEFAULT false,
    created_at timestamptz NOT NULL,
    updated_at timestamptz NOT NULL,
    CONSTRAINT uq_boardgame_item_identifier_normalized
        UNIQUE (boardgame_item_id, identifier_type, normalized_value)
);
CREATE INDEX IF NOT EXISTS ix_boardgame_item_identifiers_type_value
    ON boardgame_item_identifiers (identifier_type, normalized_value);

CREATE TABLE IF NOT EXISTS boardgame_item_legacy_identity_map (
    old_entity_type text NOT NULL,
    old_entity_id uuid NOT NULL,
    catalog_item_id uuid NOT NULL REFERENCES boardgame_items(id) ON DELETE CASCADE,
    resolution text NOT NULL,
    PRIMARY KEY (old_entity_type, old_entity_id, catalog_item_id)
);
CREATE INDEX IF NOT EXISTS ix_boardgame_item_legacy_identity_map_old
    ON boardgame_item_legacy_identity_map (old_entity_type, old_entity_id);

CREATE TABLE IF NOT EXISTS boardgame_item_migration_review (
    catalog_item_id uuid NOT NULL REFERENCES boardgame_items(id) ON DELETE CASCADE,
    source_table text NOT NULL,
    source_id uuid NOT NULL,
    field_key text NOT NULL,
    legacy_payload jsonb NOT NULL,
    PRIMARY KEY (catalog_item_id, source_table, source_id, field_key)
);

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM boardgame_items)
       OR EXISTS (SELECT 1 FROM boardgame_item_identifiers)
       OR EXISTS (SELECT 1 FROM boardgame_item_legacy_identity_map)
       OR EXISTS (SELECT 1 FROM boardgame_item_migration_review) THEN
        RAISE EXCEPTION 'Board Game Catalog Item backfill destination is not empty';
    END IF;
    IF EXISTS (
        SELECT 1
        FROM boardgame_editions e
        LEFT JOIN boardgame_works w ON w.id = e.work_id
        WHERE w.id IS NULL
    ) THEN
        RAISE EXCEPTION 'Board Game Catalog Item backfill found an edition without a work';
    END IF;
    IF EXISTS (
        SELECT 1
        FROM boardgame_works w
        WHERE NOT EXISTS (
            SELECT 1 FROM boardgame_editions e WHERE e.work_id = w.id
        )
          AND EXISTS (
            SELECT 1 FROM boardgame_editions e WHERE e.id = w.id
        )
    ) THEN
        RAISE EXCEPTION 'Board Game Catalog Item backfill found a root ID collision';
    END IF;
END $$;

-- Every Edition keeps its identity and receives shared Work fields.
INSERT INTO boardgame_items (
    id, title, sort_key, barcode, catalog_number, details, revision,
    created_at, updated_at
)
SELECT
    e.id,
    w.title,
    w.sort_title,
    e.barcode,
    e.catalog_number,
    jsonb_strip_nulls(jsonb_build_object(
        'title', w.title,
        'sort_key', w.sort_title,
        'subtitle', w.subtitle,
        'description', COALESCE(e.description, w.description),
        'edition_title', e.edition_title,
        'release_date', COALESCE(to_jsonb(e.release_date_parts), to_jsonb(e.release_date)),
        'release_date_parts', e.release_date_parts,
        'release_status', e.release_status,
        'publisher', e.publisher,
        'country', e.country,
        'language', COALESCE(e.language, w.original_language),
        'age_rating', COALESCE(e.age_rating, w.age_rating),
        'audience_rating', COALESCE(e.audience_rating, w.audience_rating),
        'barcode', e.barcode,
        'catalog_number', e.catalog_number,
        'physical_format', e.format,
        'min_players', e.min_players,
        'max_players', e.max_players,
        'playing_time_minutes', e.playing_time_minutes,
        'min_age', e.min_age,
        'year_published', COALESCE(
            EXTRACT(YEAR FROM e.release_date)::integer,
            NULLIF(substring(e.release_date_parts FROM '"?year"?\s*[:=]\s*"?(\d{1,4})'), '')::integer,
            NULLIF(substring(e.release_date_parts FROM '^(\d{4})'), '')::integer
        ),
        'cover_image_url', COALESCE(e.cover_image_url, w.cover_image_url),
        'thumbnail_image_url', COALESCE(e.cover_image_url, w.cover_image_url),
        'genres', COALESCE(work_values.genres, '[]'::jsonb),
        'platforms', COALESCE(work_values.platforms, '[]'::jsonb),
        'contributors', COALESCE(work_values.contributors, '[]'::jsonb),
        'mechanics', COALESCE(work_values.mechanics, '[]'::jsonb),
        'categories', COALESCE(work_values.categories, '[]'::jsonb),
        'families', COALESCE(work_values.families, '[]'::jsonb),
        'expansions', COALESCE(work_values.expansions, '[]'::jsonb),
        'rankings', COALESCE(work_values.rankings, '[]'::jsonb),
        'search_aliases', COALESCE(alias_values.aliases, '[]'::jsonb),
        'external_links', COALESCE(link_values.links, '[]'::jsonb)
    )),
    1,
    LEAST(w.created_at, e.created_at),
    GREATEST(w.updated_at, e.updated_at)
FROM boardgame_editions e
JOIN boardgame_works w ON w.id = e.work_id
LEFT JOIN LATERAL (
    SELECT
        (SELECT jsonb_agg(g.value ORDER BY g.sequence, g.value)
         FROM boardgame_genres g WHERE g.work_id = w.id) AS genres,
        (SELECT jsonb_agg(p.value ORDER BY p.sequence, p.value)
         FROM boardgame_platforms p WHERE p.work_id = w.id) AS platforms,
        (SELECT jsonb_agg(jsonb_strip_nulls(jsonb_build_object(
             'person_id', c.person_id, 'name', p.name, 'role', c.role,
             'sequence', c.sequence
         )) ORDER BY c.sequence NULLS LAST, c.created_at)
         FROM boardgame_contributions c
         JOIN persons p ON p.id = c.person_id
         WHERE c.work_id = w.id) AS contributors,
        (SELECT jsonb_agg(m.value ORDER BY m.sequence NULLS LAST, m.value)
         FROM boardgame_mechanics m WHERE m.work_id = w.id) AS mechanics,
        (SELECT jsonb_agg(c.value ORDER BY c.sequence NULLS LAST, c.value)
         FROM boardgame_categories c WHERE c.work_id = w.id) AS categories,
        (SELECT jsonb_agg(f.value ORDER BY f.sequence NULLS LAST, f.value)
         FROM boardgame_families f WHERE f.work_id = w.id) AS families,
        (SELECT jsonb_agg(x.value ORDER BY x.sequence NULLS LAST, x.value)
         FROM boardgame_expansions x WHERE x.work_id = w.id) AS expansions,
        (SELECT jsonb_agg(r.ranking_name ORDER BY r.snapshot_date NULLS LAST,
                          r.ranking_name)
         FROM boardgame_rankings_snapshot r WHERE r.work_id = w.id) AS rankings
) work_values ON true
LEFT JOIN LATERAL (
    SELECT jsonb_agg(a.alias ORDER BY a.position, a.created_at) AS aliases
    FROM entity_aliases a
    WHERE (a.entity_type = 'boardgame_work' AND a.entity_id = w.id)
       OR (a.entity_type = 'boardgame_edition' AND a.entity_id = e.id)
) alias_values ON true
LEFT JOIN LATERAL (
    SELECT jsonb_agg(jsonb_strip_nulls(jsonb_build_object(
        'url', l.url, 'site', l.site, 'name', l.name, 'kind', l.kind,
        'description', l.description, 'position', l.position, 'link_type', l.link_type
    )) ORDER BY l.position, l.created_at) AS links
    FROM entity_links l
    WHERE (l.entity_type = 'boardgame_work' AND l.entity_id = w.id)
       OR (l.entity_type = 'boardgame_edition' AND l.entity_id = e.id)
) link_values ON true;

-- A Work with no Edition remains one standalone root.
INSERT INTO boardgame_items (
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
        'description', w.description,
        'release_date', COALESCE(to_jsonb(w.release_date_parts), to_jsonb(w.release_date)),
        'release_date_parts', w.release_date_parts,
        'year_published', COALESCE(
            EXTRACT(YEAR FROM w.release_date)::integer,
            NULLIF(substring(w.release_date_parts FROM '"?year"?\s*[:=]\s*"?(\d{1,4})'), '')::integer,
            NULLIF(substring(w.release_date_parts FROM '^(\d{4})'), '')::integer
        ),
        'language', w.original_language,
        'age_rating', w.age_rating,
        'audience_rating', w.audience_rating,
        'cover_image_url', w.cover_image_url,
        'thumbnail_image_url', w.cover_image_url,
        'genres', COALESCE(work_values.genres, '[]'::jsonb),
        'platforms', COALESCE(work_values.platforms, '[]'::jsonb),
        'contributors', COALESCE(work_values.contributors, '[]'::jsonb),
        'mechanics', COALESCE(work_values.mechanics, '[]'::jsonb),
        'categories', COALESCE(work_values.categories, '[]'::jsonb),
        'families', COALESCE(work_values.families, '[]'::jsonb),
        'expansions', COALESCE(work_values.expansions, '[]'::jsonb),
        'rankings', COALESCE(work_values.rankings, '[]'::jsonb),
        'search_aliases', COALESCE(alias_values.aliases, '[]'::jsonb),
        'external_links', COALESCE(link_values.links, '[]'::jsonb)
    )),
    1,
    w.created_at,
    w.updated_at
FROM boardgame_works w
LEFT JOIN LATERAL (
    SELECT
        (SELECT jsonb_agg(g.value ORDER BY g.sequence, g.value)
         FROM boardgame_genres g WHERE g.work_id = w.id) AS genres,
        (SELECT jsonb_agg(p.value ORDER BY p.sequence, p.value)
         FROM boardgame_platforms p WHERE p.work_id = w.id) AS platforms,
        (SELECT jsonb_agg(jsonb_strip_nulls(jsonb_build_object(
             'person_id', c.person_id, 'name', p.name, 'role', c.role,
             'sequence', c.sequence
         )) ORDER BY c.sequence NULLS LAST, c.created_at)
         FROM boardgame_contributions c
         JOIN persons p ON p.id = c.person_id
         WHERE c.work_id = w.id) AS contributors,
        (SELECT jsonb_agg(m.value ORDER BY m.sequence NULLS LAST, m.value)
         FROM boardgame_mechanics m WHERE m.work_id = w.id) AS mechanics,
        (SELECT jsonb_agg(c.value ORDER BY c.sequence NULLS LAST, c.value)
         FROM boardgame_categories c WHERE c.work_id = w.id) AS categories,
        (SELECT jsonb_agg(f.value ORDER BY f.sequence NULLS LAST, f.value)
         FROM boardgame_families f WHERE f.work_id = w.id) AS families,
        (SELECT jsonb_agg(x.value ORDER BY x.sequence NULLS LAST, x.value)
         FROM boardgame_expansions x WHERE x.work_id = w.id) AS expansions,
        (SELECT jsonb_agg(r.ranking_name ORDER BY r.snapshot_date NULLS LAST,
                          r.ranking_name)
         FROM boardgame_rankings_snapshot r WHERE r.work_id = w.id) AS rankings
) work_values ON true
LEFT JOIN LATERAL (
    SELECT jsonb_agg(a.alias ORDER BY a.position, a.created_at) AS aliases
    FROM entity_aliases a
    WHERE a.entity_type = 'boardgame_work' AND a.entity_id = w.id
) alias_values ON true
LEFT JOIN LATERAL (
    SELECT jsonb_agg(jsonb_strip_nulls(jsonb_build_object(
        'url', l.url, 'site', l.site, 'name', l.name, 'kind', l.kind,
        'description', l.description, 'position', l.position, 'link_type', l.link_type
    )) ORDER BY l.position, l.created_at) AS links
    FROM entity_links l
    WHERE l.entity_type = 'boardgame_work' AND l.entity_id = w.id
) link_values ON true
WHERE NOT EXISTS (
    SELECT 1 FROM boardgame_editions e WHERE e.work_id = w.id
);

-- Keep canonical edition identifiers in the new child table. Work-level
-- provider identifiers and unmodeled ratings/votes remain in review snapshots.
INSERT INTO boardgame_item_identifiers (
    id, boardgame_item_id, identifier_type, value, normalized_value, is_primary,
    created_at, updated_at
)
SELECT
    i.id, i.edition_id, i.identifier_type, i.value, i.normalized_value,
    i.is_primary, i.created_at, i.updated_at
FROM boardgame_edition_identifiers i;

-- Record every old root/edition identity and make parent fan-out explicit.
INSERT INTO boardgame_item_legacy_identity_map (
    old_entity_type, old_entity_id, catalog_item_id, resolution
)
SELECT
    'boardgame_edition', e.id, e.id, 'preserved_as_catalog_item'
FROM boardgame_editions e;

INSERT INTO boardgame_item_legacy_identity_map (
    old_entity_type, old_entity_id, catalog_item_id, resolution
)
SELECT
    'boardgame_work', w.id, e.id,
    CASE WHEN child_counts.count = 1 THEN 'mapped_to_single_item'
         ELSE 'ambiguous_multiple_editions' END
FROM boardgame_works w
JOIN boardgame_editions e ON e.work_id = w.id
JOIN LATERAL (
    SELECT count(*)::integer AS count
    FROM boardgame_editions child
    WHERE child.work_id = w.id
) child_counts ON true;

INSERT INTO boardgame_item_legacy_identity_map (
    old_entity_type, old_entity_id, catalog_item_id, resolution
)
SELECT 'boardgame_work', w.id, w.id, 'preserved_without_edition'
FROM boardgame_works w
WHERE NOT EXISTS (
    SELECT 1 FROM boardgame_editions e WHERE e.work_id = w.id
);

-- Retain complete source rows and child data needed for explicit review. The
-- legacy tables are not dropped by this migration.
INSERT INTO boardgame_item_migration_review (
    catalog_item_id, source_table, source_id, field_key, legacy_payload
)
SELECT i.id, 'boardgame_works', w.id, 'source_row', to_jsonb(w)
FROM boardgame_items i
JOIN boardgame_item_legacy_identity_map map
  ON map.catalog_item_id = i.id AND map.old_entity_type = 'boardgame_work'
JOIN boardgame_works w ON w.id = map.old_entity_id
ON CONFLICT DO NOTHING;

INSERT INTO boardgame_item_migration_review (
    catalog_item_id, source_table, source_id, field_key, legacy_payload
)
SELECT e.id, 'boardgame_editions', e.id, 'source_row', to_jsonb(e)
FROM boardgame_editions e;

INSERT INTO boardgame_item_migration_review (
    catalog_item_id, source_table, source_id, field_key, legacy_payload
)
SELECT
    item_id, 'boardgame_work_children', work_id, 'source_rows', payload
FROM (
    SELECT
        i.id AS item_id,
        w.id AS work_id,
        jsonb_build_object(
            'identifiers', COALESCE((SELECT jsonb_agg(to_jsonb(x)) FROM boardgame_identifiers x WHERE x.work_id = w.id), '[]'::jsonb),
            'genres', COALESCE((SELECT jsonb_agg(to_jsonb(x)) FROM boardgame_genres x WHERE x.work_id = w.id), '[]'::jsonb),
            'platforms', COALESCE((SELECT jsonb_agg(to_jsonb(x)) FROM boardgame_platforms x WHERE x.work_id = w.id), '[]'::jsonb),
            'contributions', COALESCE((SELECT jsonb_agg(to_jsonb(x)) FROM boardgame_contributions x WHERE x.work_id = w.id), '[]'::jsonb),
            'mechanics', COALESCE((SELECT jsonb_agg(to_jsonb(x)) FROM boardgame_mechanics x WHERE x.work_id = w.id), '[]'::jsonb),
            'categories', COALESCE((SELECT jsonb_agg(to_jsonb(x)) FROM boardgame_categories x WHERE x.work_id = w.id), '[]'::jsonb),
            'families', COALESCE((SELECT jsonb_agg(to_jsonb(x)) FROM boardgame_families x WHERE x.work_id = w.id), '[]'::jsonb),
            'expansions', COALESCE((SELECT jsonb_agg(to_jsonb(x)) FROM boardgame_expansions x WHERE x.work_id = w.id), '[]'::jsonb),
            'rankings', COALESCE((SELECT jsonb_agg(to_jsonb(x)) FROM boardgame_rankings_snapshot x WHERE x.work_id = w.id), '[]'::jsonb),
            'player_count_votes', COALESCE((SELECT jsonb_agg(to_jsonb(x)) FROM boardgame_player_count_votes x JOIN boardgame_editions e ON e.id = x.edition_id WHERE e.work_id = w.id), '[]'::jsonb),
            'aliases', COALESCE((SELECT jsonb_agg(to_jsonb(x)) FROM entity_aliases x WHERE x.entity_type = 'boardgame_work' AND x.entity_id = w.id), '[]'::jsonb),
            'links', COALESCE((SELECT jsonb_agg(to_jsonb(x)) FROM entity_links x WHERE x.entity_type = 'boardgame_work' AND x.entity_id = w.id), '[]'::jsonb),
            'provider_ids', COALESCE((SELECT jsonb_agg(to_jsonb(x)) FROM external_provider_ids x WHERE x.entity_type = 'boardgame_work' AND x.entity_id = w.id), '[]'::jsonb),
            'people', COALESCE((SELECT jsonb_agg(to_jsonb(x)) FROM entity_persons x WHERE x.entity_type = 'boardgame_work' AND x.entity_id = w.id), '[]'::jsonb),
            'organizations', COALESCE((SELECT jsonb_agg(to_jsonb(x)) FROM entity_organizations x WHERE x.entity_type = 'boardgame_work' AND x.entity_id = w.id), '[]'::jsonb)
        ) AS payload
    FROM boardgame_items i
    JOIN boardgame_item_legacy_identity_map map
      ON map.catalog_item_id = i.id AND map.old_entity_type = 'boardgame_work'
    JOIN boardgame_works w ON w.id = map.old_entity_id
) snapshots
ON CONFLICT DO NOTHING;

INSERT INTO boardgame_item_migration_review (
    catalog_item_id, source_table, source_id, field_key, legacy_payload
)
SELECT
    e.id,
    'boardgame_edition_children',
    e.id,
    'source_rows',
    jsonb_build_object(
        'identifiers', COALESCE((
            SELECT jsonb_agg(to_jsonb(i))
            FROM boardgame_edition_identifiers i
            WHERE i.edition_id = e.id
        ), '[]'::jsonb),
        'player_count_votes', COALESCE((
            SELECT jsonb_agg(to_jsonb(v))
            FROM boardgame_player_count_votes v
            WHERE v.edition_id = e.id
        ), '[]'::jsonb),
        'aliases', COALESCE((SELECT jsonb_agg(to_jsonb(a)) FROM entity_aliases a WHERE a.entity_type = 'boardgame_edition' AND a.entity_id = e.id), '[]'::jsonb),
        'links', COALESCE((SELECT jsonb_agg(to_jsonb(l)) FROM entity_links l WHERE l.entity_type = 'boardgame_edition' AND l.entity_id = e.id), '[]'::jsonb),
        'provider_ids', COALESCE((SELECT jsonb_agg(to_jsonb(p)) FROM external_provider_ids p WHERE p.entity_type = 'boardgame_edition' AND p.entity_id = e.id), '[]'::jsonb),
        'people', COALESCE((SELECT jsonb_agg(to_jsonb(p)) FROM entity_persons p WHERE p.entity_type = 'boardgame_edition' AND p.entity_id = e.id), '[]'::jsonb),
        'organizations', COALESCE((SELECT jsonb_agg(to_jsonb(o)) FROM entity_organizations o WHERE o.entity_type = 'boardgame_edition' AND o.entity_id = e.id), '[]'::jsonb)
    )
FROM boardgame_editions e
ON CONFLICT DO NOTHING;

DO $$
DECLARE
    expected_item_count bigint;
BEGIN
    SELECT
        (SELECT count(*) FROM boardgame_editions)
        + (SELECT count(*)
           FROM boardgame_works w
           WHERE NOT EXISTS (
               SELECT 1 FROM boardgame_editions e WHERE e.work_id = w.id
           ))
    INTO expected_item_count;
    IF (SELECT count(*) FROM boardgame_items) <> expected_item_count THEN
        RAISE EXCEPTION 'Board Game item count does not match editions and standalone works';
    END IF;
    IF (SELECT count(*) FROM boardgame_editions)
       <> (SELECT count(*) FROM boardgame_item_legacy_identity_map
           WHERE old_entity_type = 'boardgame_edition') THEN
        RAISE EXCEPTION 'Board Game edition identity map count does not match source';
    END IF;
    IF EXISTS (
        SELECT 1
        FROM boardgame_editions e
        LEFT JOIN boardgame_item_legacy_identity_map m
          ON m.old_entity_type = 'boardgame_edition'
         AND m.old_entity_id = e.id
         AND m.catalog_item_id = e.id
        WHERE m.old_entity_id IS NULL
    ) THEN
        RAISE EXCEPTION 'Board Game Catalog Item backfill changed an edition identity';
    END IF;
    IF (SELECT count(*) FROM boardgame_item_legacy_identity_map
        WHERE old_entity_type = 'boardgame_work') <> expected_item_count THEN
        RAISE EXCEPTION 'Board Game work identity map count does not match resulting roots';
    END IF;
    IF EXISTS (
        SELECT 1 FROM boardgame_works w
        WHERE NOT EXISTS (
            SELECT 1 FROM boardgame_item_legacy_identity_map m
            WHERE m.old_entity_type = 'boardgame_work' AND m.old_entity_id = w.id
        )
    ) THEN
        RAISE EXCEPTION 'Board Game Catalog Item backfill left a work without an identity mapping';
    END IF;
    IF (SELECT count(*) FROM boardgame_edition_identifiers)
       <> (SELECT count(*) FROM boardgame_item_identifiers) THEN
        RAISE EXCEPTION 'Board Game edition identifier count does not match source';
    END IF;
    IF EXISTS (
        SELECT 1 FROM boardgame_item_legacy_identity_map m
        LEFT JOIN boardgame_items i ON i.id = m.catalog_item_id
        WHERE i.id IS NULL
    ) THEN
        RAISE EXCEPTION 'Board Game Catalog Item identity map contains an orphan';
    END IF;
END $$;

COMMIT;
