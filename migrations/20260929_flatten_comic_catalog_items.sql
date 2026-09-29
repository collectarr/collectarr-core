-- One-way Comic Work/Issue/Variant backfill into concrete Catalog Item roots.
-- Run only against a reviewed, non-live copy of the pinned Core baseline.
-- Do not remove or mutate the source tables until App and Sync have migrated.

BEGIN;

CREATE TABLE IF NOT EXISTS comic_items (
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
CREATE INDEX IF NOT EXISTS ix_comic_items_title ON comic_items (title);
CREATE INDEX IF NOT EXISTS ix_comic_items_sort_key ON comic_items (sort_key);
CREATE INDEX IF NOT EXISTS ix_comic_items_barcode ON comic_items (barcode);
CREATE INDEX IF NOT EXISTS ix_comic_items_catalog_number ON comic_items (catalog_number);

CREATE TABLE IF NOT EXISTS comic_item_identifiers (
    id uuid PRIMARY KEY,
    comic_item_id uuid NOT NULL REFERENCES comic_items(id) ON DELETE CASCADE,
    identifier_type varchar(64) NOT NULL,
    value varchar(255) NOT NULL,
    normalized_value varchar(255) NOT NULL,
    is_primary boolean NOT NULL DEFAULT false,
    created_at timestamptz NOT NULL,
    updated_at timestamptz NOT NULL,
    CONSTRAINT uq_comic_item_identifier_normalized
        UNIQUE (comic_item_id, identifier_type, normalized_value)
);
CREATE INDEX IF NOT EXISTS ix_comic_item_identifiers_type_value
    ON comic_item_identifiers (identifier_type, normalized_value);

CREATE TABLE IF NOT EXISTS comic_item_legacy_identity_map (
    old_entity_type text NOT NULL,
    old_entity_id uuid NOT NULL,
    catalog_item_id uuid NOT NULL REFERENCES comic_items(id) ON DELETE CASCADE,
    resolution text NOT NULL,
    PRIMARY KEY (old_entity_type, old_entity_id, catalog_item_id)
);
CREATE INDEX IF NOT EXISTS ix_comic_item_legacy_identity_map_old
    ON comic_item_legacy_identity_map (old_entity_type, old_entity_id);

CREATE TABLE IF NOT EXISTS comic_item_migration_review (
    snapshot_id bigserial PRIMARY KEY,
    catalog_item_id uuid REFERENCES comic_items(id) ON DELETE SET NULL,
    source_table text NOT NULL,
    source_id uuid NOT NULL,
    legacy_payload jsonb NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_comic_item_migration_review_source
    ON comic_item_migration_review (source_table, source_id);

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM comic_items)
       OR EXISTS (SELECT 1 FROM comic_item_identifiers)
       OR EXISTS (SELECT 1 FROM comic_item_legacy_identity_map)
       OR EXISTS (SELECT 1 FROM comic_item_migration_review) THEN
        RAISE EXCEPTION 'Comic Catalog Item backfill destination is not empty';
    END IF;
    IF EXISTS (
        SELECT 1 FROM comic_issues i
        LEFT JOIN comic_works w ON w.id = i.work_id
        WHERE w.id IS NULL
    ) THEN
        RAISE EXCEPTION 'Comic Catalog Item backfill found an issue without a work';
    END IF;
    IF EXISTS (
        SELECT 1 FROM comic_variants v
        LEFT JOIN comic_issues i ON i.id = v.issue_id
        WHERE i.id IS NULL
    ) THEN
        RAISE EXCEPTION 'Comic Catalog Item backfill found a variant without an issue';
    END IF;
    IF EXISTS (
        SELECT 1 FROM comic_issues i
        WHERE NOT EXISTS (SELECT 1 FROM comic_variants v WHERE v.issue_id = i.id)
          AND EXISTS (SELECT 1 FROM comic_variants v WHERE v.id = i.id)
    ) OR EXISTS (
        SELECT 1 FROM comic_works w
        WHERE NOT EXISTS (SELECT 1 FROM comic_issues i WHERE i.work_id = w.id)
          AND EXISTS (SELECT 1 FROM comic_issues i WHERE i.id = w.id)
    ) THEN
        RAISE EXCEPTION 'Comic Catalog Item backfill found a root ID collision';
    END IF;
END $$;

CREATE TEMP TABLE _comic_item_roots ON COMMIT DROP AS
SELECT
    v.id AS item_id,
    i.id AS issue_id,
    w.id AS work_id,
    v.id AS variant_id,
    v.created_at AS item_created_at,
    v.updated_at AS item_updated_at
FROM comic_variants v
JOIN comic_issues i ON i.id = v.issue_id
JOIN comic_works w ON w.id = i.work_id
UNION ALL
SELECT
    i.id, i.id, w.id, NULL::uuid, i.created_at, i.updated_at
FROM comic_issues i
JOIN comic_works w ON w.id = i.work_id
WHERE NOT EXISTS (SELECT 1 FROM comic_variants v WHERE v.issue_id = i.id)
UNION ALL
SELECT
    w.id, NULL::uuid, w.id, NULL::uuid, w.created_at, w.updated_at
FROM comic_works w
WHERE NOT EXISTS (SELECT 1 FROM comic_issues i WHERE i.work_id = w.id);

INSERT INTO comic_items (
    id, title, sort_key, barcode, catalog_number, details, revision, created_at, updated_at
)
SELECT
    r.item_id,
    COALESCE(NULLIF(i.display_title, ''), w.title),
    w.sort_title,
    COALESCE(v.barcode, i.barcode),
    COALESCE(v.catalog_number, i.catalog_number),
    jsonb_strip_nulls(jsonb_build_object(
        'title', COALESCE(NULLIF(i.display_title, ''), w.title),
        'sort_key', w.sort_title,
        'original_title', w.title,
        'subtitle', w.subtitle,
        'description', COALESCE(v.description, i.description, w.description),
        'issue_number', i.issue_number,
        'item_number', i.issue_number,
        'edition_title', COALESCE(v.variant_name, i.display_title),
        'variant_name', v.variant_name,
        'physical_format', v.physical_format,
        'publisher', COALESCE(v.publisher, i.publisher),
        'imprint', COALESCE(v.imprint, i.imprint),
        'release_date', COALESCE(
            to_jsonb(v.release_date_parts), to_jsonb(v.release_date),
            to_jsonb(i.release_date_parts), to_jsonb(i.release_date),
            to_jsonb(i.publication_date_parts), to_jsonb(i.publication_date),
            to_jsonb(w.first_publication_date_parts), to_jsonb(w.first_publication_date)
        ),
        'release_date_parts', COALESCE(
            v.release_date_parts, i.release_date_parts,
            i.publication_date_parts, w.first_publication_date_parts
        ),
        'country', i.region,
        'language', COALESCE(v.language, i.language, w.original_language),
        'page_count', i.page_count,
        'cover_price_cents', i.cover_price_cents,
        'currency', i.currency,
        'release_status', i.release_status,
        'age_rating', i.age_rating,
        'key_comic', i.key_comic,
        'key_reason', i.key_reason,
        'series_title', series.title,
        'series_group', series.slug,
        'cover_image_url', COALESCE(v.cover_image_url, i.cover_image_url),
        'thumbnail_image_url', COALESCE(v.cover_image_url, i.cover_image_url),
        'creators', COALESCE(credit_data.creators, '[]'::jsonb),
        'contributors', COALESCE(credit_data.contributors, '[]'::jsonb),
        'characters', COALESCE(character_data.names, '[]'::jsonb),
        'character_details', COALESCE(character_data.details, '[]'::jsonb),
        'story_arcs', COALESCE(story_arc_data.arcs, '[]'::jsonb)
    )),
    1,
    r.item_created_at,
    r.item_updated_at
FROM _comic_item_roots r
JOIN comic_works w ON w.id = r.work_id
LEFT JOIN comic_issues i ON i.id = r.issue_id
LEFT JOIN comic_variants v ON v.id = r.variant_id
LEFT JOIN LATERAL (
    SELECT s.title, s.slug
    FROM comic_series_memberships sm
    JOIN comic_series s ON s.id = sm.series_id
    WHERE sm.work_id = r.work_id
    ORDER BY sm.sequence NULLS LAST, s.title
    LIMIT 1
) series ON true
LEFT JOIN LATERAL (
    SELECT
        jsonb_agg(credit ORDER BY sequence NULLS LAST, name)
            FILTER (WHERE lower(role) IN ('writer', 'artist', 'penciller', 'inker', 'colorist', 'letterer', 'creator')) AS creators,
        jsonb_agg(credit ORDER BY sequence NULLS LAST, name)
            FILTER (WHERE lower(role) NOT IN ('writer', 'artist', 'penciller', 'inker', 'colorist', 'letterer', 'creator')) AS contributors
    FROM (
        SELECT jsonb_strip_nulls(jsonb_build_object(
            'person_id', p.id, 'name', p.name, 'role', c.role,
            'role_id', c.role_id, 'sequence', c.sequence
        )) AS credit, c.role, c.sequence, p.name
        FROM comic_contributions c
        JOIN persons p ON p.id = c.person_id
        WHERE c.work_id = r.work_id OR c.issue_id = r.issue_id
        UNION ALL
        SELECT jsonb_strip_nulls(jsonb_build_object(
            'person_id', p.id, 'name', p.name, 'role', c.role,
            'role_id', c.role_id, 'sequence', c.sequence
        )), c.role, c.sequence, p.name
        FROM comic_variant_contributions c
        JOIN persons p ON p.id = c.person_id
        WHERE c.variant_id = r.variant_id
    ) credits
) credit_data ON true
LEFT JOIN LATERAL (
    SELECT
        jsonb_agg(c.name ORDER BY a.role, c.name) AS names,
        jsonb_agg(jsonb_strip_nulls(jsonb_build_object(
            'character_id', c.id, 'name', c.name, 'role', a.role,
            'description', c.description, 'image_url', c.image_url
        )) ORDER BY a.role, c.name) AS details
    FROM comic_character_appearances a
    JOIN comic_characters c ON c.id = a.character_id
    WHERE a.issue_id = r.issue_id
) character_data ON true
LEFT JOIN LATERAL (
    SELECT jsonb_agg(jsonb_strip_nulls(jsonb_build_object(
        'story_arc_id', a.id, 'name', a.name, 'description', a.description,
        'publisher', a.publisher, 'start_date', a.start_date, 'end_date', a.end_date
    )) ORDER BY m.ordinal NULLS LAST, a.name) AS arcs
    FROM comic_story_arc_memberships m
    JOIN story_arcs a ON a.id = m.story_arc_id
    WHERE m.issue_id = r.issue_id
) story_arc_data ON true;

INSERT INTO comic_item_identifiers (
    id, comic_item_id, identifier_type, value, normalized_value, is_primary, created_at, updated_at
)
SELECT md5(
           'comic-item-identifier:' || r.item_id::text || ':' ||
           ids.identifier_type || ':' || ids.normalized_value
       )::uuid,
       r.item_id, ids.identifier_type, ids.value,
       ids.normalized_value, ids.is_primary, r.item_created_at, r.item_updated_at
FROM _comic_item_roots r
JOIN LATERAL (
    SELECT ci.identifier_type, ci.value, ci.normalized_value, ci.is_primary
    FROM comic_identifiers ci
    WHERE ci.issue_id = r.issue_id AND ci.source_provider IS NULL
    UNION ALL
    SELECT ci.identifier_type, ci.value, ci.normalized_value, ci.is_primary
    FROM comic_variant_identifiers ci
    WHERE ci.variant_id = r.variant_id AND ci.source_provider IS NULL
    UNION ALL
    SELECT 'barcode', COALESCE(v.barcode, i.barcode),
           regexp_replace(lower(COALESCE(v.barcode, i.barcode)), '[^a-z0-9]', '', 'g'), true
    FROM comic_issues i
    LEFT JOIN comic_variants v ON v.id = r.variant_id
    WHERE i.id = r.issue_id AND COALESCE(v.barcode, i.barcode) IS NOT NULL
) ids ON true
ON CONFLICT (comic_item_id, identifier_type, normalized_value) DO NOTHING;

INSERT INTO comic_item_legacy_identity_map (
    old_entity_type, old_entity_id, catalog_item_id, resolution
)
SELECT 'comic_variant', r.variant_id, r.item_id, 'exact'
FROM _comic_item_roots r WHERE r.variant_id IS NOT NULL
UNION ALL
SELECT 'comic_issue', r.issue_id, r.item_id,
       CASE WHEN counts.item_count = 1 THEN 'exact' ELSE 'ambiguous_issue_variants' END
FROM _comic_item_roots r
JOIN LATERAL (
    SELECT count(*) AS item_count FROM _comic_item_roots rr WHERE rr.issue_id = r.issue_id
) counts ON true
WHERE r.issue_id IS NOT NULL
UNION ALL
SELECT 'comic_work', r.work_id, r.item_id,
       CASE WHEN counts.item_count = 1 THEN 'exact' ELSE 'ambiguous_work_items' END
FROM _comic_item_roots r
JOIN LATERAL (
    SELECT count(*) AS item_count FROM _comic_item_roots rr WHERE rr.work_id = r.work_id
) counts ON true;

-- Keep complete source rows for review, including records whose fields are not
-- part of the current Catalog Item contract. Child IDs remain recoverable here.
INSERT INTO comic_item_migration_review (catalog_item_id, source_table, source_id, legacy_payload)
SELECT r.item_id, 'comic_works', w.id, to_jsonb(w)
FROM _comic_item_roots r JOIN comic_works w ON w.id = r.work_id
UNION ALL
SELECT r.item_id, 'comic_issues', i.id, to_jsonb(i)
FROM _comic_item_roots r JOIN comic_issues i ON i.id = r.issue_id
UNION ALL
SELECT r.item_id, 'comic_variants', v.id, to_jsonb(v)
FROM _comic_item_roots r JOIN comic_variants v ON v.id = r.variant_id
UNION ALL
SELECT r.item_id, 'comic_contributions', c.id, to_jsonb(c)
FROM _comic_item_roots r JOIN comic_contributions c
  ON c.work_id = r.work_id OR c.issue_id = r.issue_id
UNION ALL
SELECT r.item_id, 'comic_variant_contributions', c.id, to_jsonb(c)
FROM _comic_item_roots r JOIN comic_variant_contributions c ON c.variant_id = r.variant_id
UNION ALL
SELECT r.item_id, 'comic_identifiers', c.id, to_jsonb(c)
FROM _comic_item_roots r JOIN comic_identifiers c ON c.issue_id = r.issue_id
UNION ALL
SELECT r.item_id, 'comic_variant_identifiers', c.id, to_jsonb(c)
FROM _comic_item_roots r JOIN comic_variant_identifiers c ON c.variant_id = r.variant_id
UNION ALL
SELECT r.item_id, 'comic_story_arc_memberships', c.id, to_jsonb(c)
FROM _comic_item_roots r JOIN comic_story_arc_memberships c ON c.issue_id = r.issue_id
UNION ALL
SELECT r.item_id, 'comic_character_appearances', c.id, to_jsonb(c)
FROM _comic_item_roots r JOIN comic_character_appearances c ON c.issue_id = r.issue_id
UNION ALL
SELECT r.item_id, 'comic_series_memberships', c.id, to_jsonb(c)
FROM _comic_item_roots r JOIN comic_series_memberships c ON c.work_id = r.work_id
UNION ALL
SELECT r.item_id, 'comic_work_missing_issue_numbers', c.id, to_jsonb(c)
FROM _comic_item_roots r JOIN comic_work_missing_issue_numbers c ON c.work_id = r.work_id
UNION ALL
SELECT r.item_id, 'comic_volumes', v.id, to_jsonb(v)
FROM _comic_item_roots r JOIN comic_works w ON w.id = r.work_id
JOIN comic_volumes v ON v.id = w.volume_id
UNION ALL
SELECT r.item_id, 'comic_series', s.id, to_jsonb(s)
FROM _comic_item_roots r JOIN comic_series_memberships m ON m.work_id = r.work_id
JOIN comic_series s ON s.id = m.series_id
UNION ALL
SELECT r.item_id, 'story_arcs', a.id, to_jsonb(a)
FROM _comic_item_roots r JOIN comic_story_arc_memberships m ON m.issue_id = r.issue_id
JOIN story_arcs a ON a.id = m.story_arc_id
UNION ALL
SELECT NULL, 'comic_characters', c.id, to_jsonb(c)
FROM comic_characters c
UNION ALL
SELECT NULL, 'comic_character_external_identifiers', c.id, to_jsonb(c)
FROM comic_character_external_identifiers c
UNION ALL
SELECT NULL, 'external_provider_ids', p.id, to_jsonb(p)
FROM external_provider_ids p
WHERE p.entity_type IN (
    'comic_work', 'comic_issue', 'comic_variant', 'comic_volume',
    'comic_series', 'comic_character'
);

DO $$
DECLARE
    expected_items bigint;
    actual_items bigint;
    expected_roots bigint;
    actual_mapped_roots bigint;
BEGIN
    SELECT count(*) INTO expected_items FROM _comic_item_roots;
    SELECT count(*) INTO actual_items FROM comic_items;
    SELECT count(*) INTO expected_roots FROM (
        SELECT id FROM comic_works
        UNION ALL SELECT id FROM comic_issues
        UNION ALL SELECT id FROM comic_variants
    ) roots;
    SELECT count(DISTINCT old_entity_type || ':' || old_entity_id::text)
        INTO actual_mapped_roots FROM comic_item_legacy_identity_map;
    IF expected_items <> actual_items THEN
        RAISE EXCEPTION 'Comic Catalog Item count mismatch: expected %, found %', expected_items, actual_items;
    END IF;
    IF expected_roots <> actual_mapped_roots THEN
        RAISE EXCEPTION 'Comic old-root identity mapping mismatch: expected %, found %', expected_roots, actual_mapped_roots;
    END IF;
END $$;

COMMIT;
