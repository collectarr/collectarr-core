-- One-way Manga Work -> Edition backfill into concrete Catalog Item roots.
-- Run only against a reviewed non-live copy of the pinned Core baseline.
-- Source tables stay intact until App and Sync have moved to these identities.

BEGIN;

CREATE TABLE IF NOT EXISTS manga_items (
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
CREATE INDEX IF NOT EXISTS ix_manga_items_title ON manga_items (title);
CREATE INDEX IF NOT EXISTS ix_manga_items_sort_key ON manga_items (sort_key);
CREATE INDEX IF NOT EXISTS ix_manga_items_barcode ON manga_items (barcode);
CREATE INDEX IF NOT EXISTS ix_manga_items_catalog_number ON manga_items (catalog_number);

CREATE TABLE IF NOT EXISTS manga_item_identifiers (
    id uuid PRIMARY KEY,
    manga_item_id uuid NOT NULL REFERENCES manga_items(id) ON DELETE CASCADE,
    identifier_type varchar(64) NOT NULL,
    value varchar(255) NOT NULL,
    normalized_value varchar(255) NOT NULL,
    is_primary boolean NOT NULL DEFAULT false,
    created_at timestamptz NOT NULL,
    updated_at timestamptz NOT NULL,
    CONSTRAINT uq_manga_item_identifier_normalized
        UNIQUE (manga_item_id, identifier_type, normalized_value)
);
CREATE INDEX IF NOT EXISTS ix_manga_item_identifiers_type_value
    ON manga_item_identifiers (identifier_type, normalized_value);

CREATE TABLE IF NOT EXISTS manga_item_legacy_identity_map (
    old_entity_type text NOT NULL,
    old_entity_id uuid NOT NULL,
    catalog_item_id uuid NOT NULL REFERENCES manga_items(id) ON DELETE CASCADE,
    resolution text NOT NULL,
    PRIMARY KEY (old_entity_type, old_entity_id, catalog_item_id)
);
CREATE INDEX IF NOT EXISTS ix_manga_item_legacy_identity_map_old
    ON manga_item_legacy_identity_map (old_entity_type, old_entity_id);

CREATE TABLE IF NOT EXISTS manga_item_migration_review (
    catalog_item_id uuid NOT NULL REFERENCES manga_items(id) ON DELETE CASCADE,
    source_table text NOT NULL,
    source_id uuid NOT NULL,
    field_key text NOT NULL,
    legacy_payload jsonb NOT NULL,
    PRIMARY KEY (catalog_item_id, source_table, source_id, field_key)
);

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM manga_items)
       OR EXISTS (SELECT 1 FROM manga_item_identifiers)
       OR EXISTS (SELECT 1 FROM manga_item_legacy_identity_map)
       OR EXISTS (SELECT 1 FROM manga_item_migration_review) THEN
        RAISE EXCEPTION 'Manga Catalog Item backfill destination is not empty';
    END IF;
    IF EXISTS (
        SELECT 1 FROM manga_editions e
        LEFT JOIN manga_works w ON w.id = e.work_id
        WHERE w.id IS NULL
    ) THEN
        RAISE EXCEPTION 'Manga Catalog Item backfill found an edition without a work';
    END IF;
    IF EXISTS (
        SELECT 1 FROM manga_works w
        WHERE NOT EXISTS (SELECT 1 FROM manga_editions e WHERE e.work_id = w.id)
          AND EXISTS (SELECT 1 FROM manga_editions e WHERE e.id = w.id)
    ) THEN
        RAISE EXCEPTION 'Manga Catalog Item backfill found a root ID collision';
    END IF;
    IF EXISTS (
        SELECT edition_id, identifier_type, normalized_value
        FROM manga_edition_identifiers
        GROUP BY edition_id, identifier_type, normalized_value
        HAVING count(*) > 1
    ) THEN
        RAISE EXCEPTION 'Manga Catalog Item backfill found duplicate edition identifiers';
    END IF;
END $$;

WITH item_source AS (
    SELECT e.id AS item_id, e.work_id, e.id AS edition_id,
           w.title, w.sort_title, w.subtitle, w.description, w.volume_number,
           w.original_language, w.original_publication_date,
           w.original_publication_date_parts, w.first_publication_date,
           w.first_publication_date_parts, w.status,
           w.created_at AS work_created_at, w.updated_at AS work_updated_at,
           e.display_title, e.edition_statement, e.format, e.binding,
           e.publication_date, e.publication_date_parts, e.publisher,
           e.imprint, e.language, e.country, e.isbn10, e.isbn13, e.barcode,
           e.page_count, e.cover_image_url, e.description AS edition_description,
           e.created_at AS edition_created_at, e.updated_at AS edition_updated_at
    FROM manga_editions e
    JOIN manga_works w ON w.id = e.work_id
    UNION ALL
    SELECT w.id AS item_id, w.id AS work_id, NULL::uuid AS edition_id,
           w.title, w.sort_title, w.subtitle, w.description, w.volume_number,
           w.original_language, w.original_publication_date,
           w.original_publication_date_parts, w.first_publication_date,
           w.first_publication_date_parts, w.status,
           w.created_at AS work_created_at, w.updated_at AS work_updated_at,
           NULL::varchar AS display_title, NULL::varchar AS edition_statement,
           NULL::varchar AS format, NULL::varchar AS binding,
           NULL::date AS publication_date, NULL::varchar AS publication_date_parts,
           NULL::varchar AS publisher, NULL::varchar AS imprint,
           NULL::varchar AS language, NULL::varchar AS country,
           NULL::varchar AS isbn10, NULL::varchar AS isbn13,
           NULL::varchar AS barcode, NULL::integer AS page_count,
           NULL::varchar AS cover_image_url, NULL::text AS edition_description,
           NULL::timestamptz AS edition_created_at,
           NULL::timestamptz AS edition_updated_at
    FROM manga_works w
    WHERE NOT EXISTS (SELECT 1 FROM manga_editions e WHERE e.work_id = w.id)
)
INSERT INTO manga_items (
    id, title, sort_key, barcode, catalog_number, details, revision,
    created_at, updated_at
)
SELECT
    s.item_id,
    s.title,
    s.sort_title,
    s.barcode,
    s.isbn13,
    jsonb_strip_nulls(jsonb_build_object(
        'title', s.title,
        'sort_key', s.sort_title,
        'subtitle', s.subtitle,
        'description', COALESCE(s.edition_description, s.description),
        'edition_title', COALESCE(s.display_title, s.edition_statement),
        'localized_title', s.display_title,
        'variant_name', s.edition_statement,
        'physical_format', COALESCE(s.format, s.binding),
        'publisher', s.publisher,
        'imprint', s.imprint,
        'release_date', COALESCE(
            to_jsonb(s.publication_date_parts), to_jsonb(s.publication_date),
            to_jsonb(s.first_publication_date_parts), to_jsonb(s.first_publication_date),
            to_jsonb(s.original_publication_date_parts), to_jsonb(s.original_publication_date)
        ),
        'release_date_parts', COALESCE(
            s.publication_date_parts, s.first_publication_date_parts,
            s.original_publication_date_parts
        ),
        'release_status', s.status,
        'language', COALESCE(s.language, s.original_language),
        'country', s.country,
        'barcode', s.barcode,
        'isbn', COALESCE(s.isbn13, s.isbn10),
        'isbn10', s.isbn10,
        'isbn13', s.isbn13,
        'page_count', s.page_count,
        'volume_number', s.volume_number::text,
        'volume_name', s.volume_number::text,
        'item_number', s.volume_number::text,
        'original_title', series_values.original_title,
        'series_title', series_values.series_title,
        'series_group', series_values.series_group,
        'series_tags', COALESCE(series_values.series_tags, '[]'::jsonb),
        'chapters', COALESCE(chapter_values.chapters, '[]'::jsonb),
        'creators', COALESCE(credit_values.creators, '[]'::jsonb),
        'contributors', COALESCE(credit_values.contributors, '[]'::jsonb),
        'characters', COALESCE(character_values.characters, '[]'::jsonb),
        'character_details', COALESCE(character_values.details, '[]'::jsonb),
        'search_aliases', COALESCE(alias_values.aliases, '[]'::jsonb),
        'external_links', COALESCE(link_values.links, '[]'::jsonb),
        'cover_image_url', s.cover_image_url,
        'thumbnail_image_url', s.cover_image_url
    )),
    1,
    LEAST(s.work_created_at, COALESCE(s.edition_created_at, s.work_created_at)),
    GREATEST(s.work_updated_at, COALESCE(s.edition_updated_at, s.work_updated_at))
FROM item_source s
LEFT JOIN LATERAL (
    SELECT
        (SELECT se.title FROM manga_series_memberships sm
         JOIN manga_series se ON se.id = sm.series_id
         WHERE sm.work_id = s.work_id
         ORDER BY sm.sequence NULLS LAST, se.title LIMIT 1) AS series_title,
        (SELECT COALESCE(se.slug, se.title) FROM manga_series_memberships sm
         JOIN manga_series se ON se.id = sm.series_id
         WHERE sm.work_id = s.work_id
         ORDER BY sm.sequence NULLS LAST, se.title LIMIT 1) AS series_group,
        (SELECT se.original_title FROM manga_series_memberships sm
         JOIN manga_series se ON se.id = sm.series_id
         WHERE sm.work_id = s.work_id
         ORDER BY sm.sequence NULLS LAST, se.title LIMIT 1) AS original_title,
        (SELECT jsonb_agg(se.title ORDER BY sm.sequence NULLS LAST, se.title)
         FROM manga_series_memberships sm
         JOIN manga_series se ON se.id = sm.series_id
         WHERE sm.work_id = s.work_id) AS series_tags
) series_values ON true
LEFT JOIN LATERAL (
    SELECT jsonb_agg(jsonb_strip_nulls(jsonb_build_object(
        'chapter_number', CASE
            WHEN chapter.chapter_number = trunc(chapter.chapter_number)
                THEN chapter.chapter_number::integer
            ELSE NULL
        END,
        'title', chapter.chapter_title,
        'release_date', COALESCE(
            to_jsonb(chapter.publication_date_parts),
            to_jsonb(chapter.publication_date)
        ),
        'page_count', chapter.page_count,
        'position', chapter.position
    )) ORDER BY chapter.chapter_number NULLS LAST, chapter.created_at, chapter.id) AS chapters
    FROM (
        SELECT c.*,
               row_number() OVER (
                   ORDER BY c.chapter_number NULLS LAST, c.created_at, c.id
               )::integer - 1 AS position
        FROM manga_chapters c
        WHERE c.work_id = s.work_id
    ) chapter
) chapter_values ON true
LEFT JOIN LATERAL (
    SELECT
        jsonb_agg(credit ORDER BY sequence NULLS LAST, name)
            FILTER (WHERE lower(role) IN ('author', 'writer', 'artist', 'illustrator', 'creator')) AS creators,
        jsonb_agg(credit ORDER BY sequence NULLS LAST, name)
            FILTER (WHERE lower(role) NOT IN ('author', 'writer', 'artist', 'illustrator', 'creator')) AS contributors
    FROM (
        SELECT jsonb_strip_nulls(jsonb_build_object(
            'person_id', p.id, 'name', p.name, 'role', c.role,
            'role_id', c.role_id, 'sequence', c.sequence
        )) AS credit, c.role, c.sequence, p.name
        FROM manga_contributions c
        JOIN persons p ON p.id = c.person_id
        WHERE c.work_id = s.work_id
        UNION ALL
        SELECT jsonb_strip_nulls(jsonb_build_object(
            'person_id', p.id, 'name', p.name, 'role', c.role,
            'role_id', c.role_id, 'sequence', c.sequence
        )), c.role, c.sequence, p.name
        FROM manga_edition_contributions c
        JOIN persons p ON p.id = c.person_id
        WHERE c.edition_id = s.edition_id
    ) contribution_rows
) credit_values ON true
LEFT JOIN LATERAL (
    SELECT
        jsonb_agg(c.name ORDER BY a.role, c.name) AS characters,
        jsonb_agg(jsonb_strip_nulls(jsonb_build_object(
            'character_id', c.id,
            'name', c.name,
            'aliases', COALESCE(character_aliases.aliases, '[]'::jsonb),
            'role', a.role,
            'description', c.description,
            'image_url', c.image_url
        )) ORDER BY a.role, c.name) AS details
    FROM manga_character_appearances a
    JOIN characters c ON c.id = a.character_id
    LEFT JOIN LATERAL (
        SELECT jsonb_agg(alias.alias ORDER BY alias.position, alias.created_at) AS aliases
        FROM entity_aliases alias
        WHERE alias.entity_type = 'character' AND alias.entity_id = c.id
    ) character_aliases ON true
    WHERE a.work_id = s.work_id
) character_values ON true
LEFT JOIN LATERAL (
    SELECT jsonb_agg(a.alias ORDER BY a.position, a.created_at) AS aliases
    FROM entity_aliases a
    WHERE (a.entity_type = 'manga_work' AND a.entity_id = s.work_id)
       OR (a.entity_type = 'manga_edition' AND a.entity_id = s.edition_id)
) alias_values ON true
LEFT JOIN LATERAL (
    SELECT jsonb_agg(jsonb_strip_nulls(jsonb_build_object(
        'url', l.url, 'site', l.site, 'name', l.name, 'kind', l.kind,
        'description', l.description, 'position', l.position, 'link_type', l.link_type
    )) ORDER BY l.position, l.created_at) AS links
    FROM entity_links l
    WHERE (l.entity_type = 'manga_work' AND l.entity_id = s.work_id)
       OR (l.entity_type = 'manga_edition' AND l.entity_id = s.edition_id)
) link_values ON true;

INSERT INTO manga_item_identifiers (
    id, manga_item_id, identifier_type, value, normalized_value, is_primary,
    created_at, updated_at
)
SELECT i.id, i.edition_id, i.identifier_type, i.value, i.normalized_value,
       i.is_primary, i.created_at, i.updated_at
FROM manga_edition_identifiers i
WHERE i.source_provider IS NULL;

INSERT INTO manga_item_identifiers (
    id, manga_item_id, identifier_type, value, normalized_value, is_primary,
    created_at, updated_at
)
SELECT i.id, i.work_id, i.identifier_type, i.value, i.normalized_value,
       i.is_primary, i.created_at, i.updated_at
FROM manga_identifiers i
WHERE i.source_provider IS NULL
  AND NOT EXISTS (SELECT 1 FROM manga_editions e WHERE e.work_id = i.work_id);

INSERT INTO manga_item_legacy_identity_map (
    old_entity_type, old_entity_id, catalog_item_id, resolution
)
SELECT 'manga_edition', e.id, e.id, 'preserved_as_catalog_item'
FROM manga_editions e;

INSERT INTO manga_item_legacy_identity_map (
    old_entity_type, old_entity_id, catalog_item_id, resolution
)
SELECT
    'manga_work', w.id, e.id,
    CASE WHEN counts.edition_count = 1 THEN 'mapped_to_single_item'
         ELSE 'ambiguous_multiple_editions' END
FROM manga_works w
JOIN manga_editions e ON e.work_id = w.id
JOIN LATERAL (
    SELECT count(*)::integer AS edition_count
    FROM manga_editions child WHERE child.work_id = w.id
) counts ON true;

INSERT INTO manga_item_legacy_identity_map (
    old_entity_type, old_entity_id, catalog_item_id, resolution
)
SELECT 'manga_work', w.id, w.id, 'preserved_without_edition'
FROM manga_works w
WHERE NOT EXISTS (SELECT 1 FROM manga_editions e WHERE e.work_id = w.id);

INSERT INTO manga_item_legacy_identity_map (
    old_entity_type, old_entity_id, catalog_item_id, resolution
)
SELECT
    'manga_chapter', c.id, i.id,
    CASE WHEN item_counts.item_count > 1 THEN 'copied_from_shared_work'
         ELSE 'retained_as_contained_chapter' END
FROM manga_chapters c
JOIN manga_item_legacy_identity_map work_map
  ON work_map.old_entity_type = 'manga_work' AND work_map.old_entity_id = c.work_id
JOIN manga_items i ON i.id = work_map.catalog_item_id
JOIN LATERAL (
    SELECT count(*)::integer AS item_count
    FROM manga_item_legacy_identity_map all_work_items
    WHERE all_work_items.old_entity_type = 'manga_work'
      AND all_work_items.old_entity_id = c.work_id
) item_counts ON true;

INSERT INTO manga_item_migration_review (
    catalog_item_id, source_table, source_id, field_key, legacy_payload
)
SELECT i.id, 'manga_works', w.id, 'source_row', to_jsonb(w)
FROM manga_items i
JOIN manga_item_legacy_identity_map m
  ON m.catalog_item_id = i.id AND m.old_entity_type = 'manga_work'
JOIN manga_works w ON w.id = m.old_entity_id
ON CONFLICT DO NOTHING;

INSERT INTO manga_item_migration_review (
    catalog_item_id, source_table, source_id, field_key, legacy_payload
)
SELECT e.id, 'manga_editions', e.id, 'source_row', to_jsonb(e)
FROM manga_editions e;

INSERT INTO manga_item_migration_review (
    catalog_item_id, source_table, source_id, field_key, legacy_payload
)
SELECT i.id, 'manga_work_children', w.id, 'source_rows', jsonb_build_object(
    'chapters', COALESCE((SELECT jsonb_agg(to_jsonb(c)) FROM manga_chapters c WHERE c.work_id = w.id), '[]'::jsonb),
    'work_contributions', COALESCE((SELECT jsonb_agg(to_jsonb(c)) FROM manga_contributions c WHERE c.work_id = w.id), '[]'::jsonb),
    'chapter_contributions', COALESCE((SELECT jsonb_agg(to_jsonb(c)) FROM manga_contributions c JOIN manga_chapters ch ON ch.id = c.chapter_id WHERE ch.work_id = w.id), '[]'::jsonb),
    'identifiers', COALESCE((SELECT jsonb_agg(to_jsonb(x)) FROM manga_identifiers x WHERE x.work_id = w.id), '[]'::jsonb),
    'character_appearances', COALESCE((
        SELECT jsonb_agg(jsonb_build_object(
            'appearance', to_jsonb(a),
            'character', to_jsonb(ch),
            'aliases', COALESCE((SELECT jsonb_agg(to_jsonb(alias)) FROM entity_aliases alias WHERE alias.entity_type = 'character' AND alias.entity_id = ch.id), '[]'::jsonb),
            'provider_ids', COALESCE((SELECT jsonb_agg(to_jsonb(provider_id)) FROM external_provider_ids provider_id WHERE provider_id.entity_type = 'character' AND provider_id.entity_id = ch.id), '[]'::jsonb)
        ))
        FROM manga_character_appearances a
        JOIN characters ch ON ch.id = a.character_id
        WHERE a.work_id = w.id
    ), '[]'::jsonb),
    'series_memberships', COALESCE((SELECT jsonb_agg(jsonb_build_object('membership', to_jsonb(m), 'series', to_jsonb(s)) ORDER BY m.sequence NULLS LAST) FROM manga_series_memberships m JOIN manga_series s ON s.id = m.series_id WHERE m.work_id = w.id), '[]'::jsonb),
    'series_provider_ids', COALESCE((SELECT jsonb_agg(to_jsonb(p)) FROM external_provider_ids p JOIN manga_series_memberships m ON m.series_id = p.entity_id WHERE m.work_id = w.id AND p.entity_type = 'manga_series'), '[]'::jsonb),
    'provider_ids', COALESCE((SELECT jsonb_agg(to_jsonb(x)) FROM external_provider_ids x WHERE x.entity_type = 'manga_work' AND x.entity_id = w.id), '[]'::jsonb),
    'people', COALESCE((SELECT jsonb_agg(to_jsonb(x)) FROM entity_persons x WHERE x.entity_type = 'manga_work' AND x.entity_id = w.id), '[]'::jsonb),
    'organizations', COALESCE((SELECT jsonb_agg(to_jsonb(x)) FROM entity_organizations x WHERE x.entity_type = 'manga_work' AND x.entity_id = w.id), '[]'::jsonb),
    'aliases', COALESCE((SELECT jsonb_agg(to_jsonb(x)) FROM entity_aliases x WHERE x.entity_type = 'manga_work' AND x.entity_id = w.id), '[]'::jsonb),
    'links', COALESCE((SELECT jsonb_agg(to_jsonb(x)) FROM entity_links x WHERE x.entity_type = 'manga_work' AND x.entity_id = w.id), '[]'::jsonb),
    'images', COALESCE((SELECT jsonb_agg(to_jsonb(x)) FROM image_assets x WHERE x.entity_type = 'manga_work' AND x.entity_id = w.id), '[]'::jsonb)
)
FROM manga_items i
JOIN manga_item_legacy_identity_map m
  ON m.catalog_item_id = i.id AND m.old_entity_type = 'manga_work'
JOIN manga_works w ON w.id = m.old_entity_id
ON CONFLICT DO NOTHING;

INSERT INTO manga_item_migration_review (
    catalog_item_id, source_table, source_id, field_key, legacy_payload
)
SELECT e.id, 'manga_edition_children', e.id, 'source_rows', jsonb_build_object(
    'contributions', COALESCE((SELECT jsonb_agg(to_jsonb(c)) FROM manga_edition_contributions c WHERE c.edition_id = e.id), '[]'::jsonb),
    'identifiers', COALESCE((SELECT jsonb_agg(to_jsonb(x)) FROM manga_edition_identifiers x WHERE x.edition_id = e.id), '[]'::jsonb),
    'provider_ids', COALESCE((SELECT jsonb_agg(to_jsonb(x)) FROM external_provider_ids x WHERE x.entity_type = 'manga_edition' AND x.entity_id = e.id), '[]'::jsonb),
    'people', COALESCE((SELECT jsonb_agg(to_jsonb(x)) FROM entity_persons x WHERE x.entity_type = 'manga_edition' AND x.entity_id = e.id), '[]'::jsonb),
    'organizations', COALESCE((SELECT jsonb_agg(to_jsonb(x)) FROM entity_organizations x WHERE x.entity_type = 'manga_edition' AND x.entity_id = e.id), '[]'::jsonb),
    'aliases', COALESCE((SELECT jsonb_agg(to_jsonb(x)) FROM entity_aliases x WHERE x.entity_type = 'manga_edition' AND x.entity_id = e.id), '[]'::jsonb),
    'links', COALESCE((SELECT jsonb_agg(to_jsonb(x)) FROM entity_links x WHERE x.entity_type = 'manga_edition' AND x.entity_id = e.id), '[]'::jsonb),
    'images', COALESCE((SELECT jsonb_agg(to_jsonb(x)) FROM image_assets x WHERE x.entity_type = 'manga_edition' AND x.entity_id = e.id), '[]'::jsonb)
)
FROM manga_editions e;

INSERT INTO manga_item_migration_review (
    catalog_item_id, source_table, source_id, field_key, legacy_payload
)
SELECT c.id, 'manga_chapter_children', c.id, 'source_rows', jsonb_build_object(
    'contributions', COALESCE((SELECT jsonb_agg(to_jsonb(x)) FROM manga_contributions x WHERE x.chapter_id = c.id), '[]'::jsonb),
    'images', COALESCE((SELECT jsonb_agg(to_jsonb(x)) FROM image_assets x WHERE x.entity_type = 'manga_chapter' AND x.entity_id = c.id), '[]'::jsonb)
)
FROM manga_chapters c
JOIN manga_item_legacy_identity_map m
  ON m.old_entity_type = 'manga_chapter' AND m.old_entity_id = c.id
ON CONFLICT DO NOTHING;

DO $$
DECLARE
    expected_item_count bigint;
BEGIN
    SELECT (SELECT count(*) FROM manga_editions)
         + (SELECT count(*) FROM manga_works w
            WHERE NOT EXISTS (SELECT 1 FROM manga_editions e WHERE e.work_id = w.id))
    INTO expected_item_count;
    IF (SELECT count(*) FROM manga_items) <> expected_item_count THEN
        RAISE EXCEPTION 'Manga item count does not match editions and standalone works';
    END IF;
    IF (SELECT count(*) FROM manga_editions)
       <> (SELECT count(*) FROM manga_item_legacy_identity_map WHERE old_entity_type = 'manga_edition') THEN
        RAISE EXCEPTION 'Manga edition identity map count does not match source';
    END IF;
    IF EXISTS (
        SELECT 1 FROM manga_editions e
        LEFT JOIN manga_item_legacy_identity_map m
          ON m.old_entity_type = 'manga_edition' AND m.old_entity_id = e.id
         AND m.catalog_item_id = e.id
        WHERE m.old_entity_id IS NULL
    ) THEN
        RAISE EXCEPTION 'Manga Catalog Item backfill changed an edition identity';
    END IF;
    IF (SELECT count(*) FROM manga_item_legacy_identity_map WHERE old_entity_type = 'manga_work')
       <> expected_item_count THEN
        RAISE EXCEPTION 'Manga work identity map count does not match resulting roots';
    END IF;
    IF EXISTS (
        SELECT 1 FROM manga_works w
        WHERE NOT EXISTS (
            SELECT 1 FROM manga_item_legacy_identity_map m
            WHERE m.old_entity_type = 'manga_work' AND m.old_entity_id = w.id
        )
    ) THEN
        RAISE EXCEPTION 'Manga Catalog Item backfill left a work without an identity mapping';
    END IF;
    IF EXISTS (
        SELECT 1 FROM manga_chapters c
        WHERE NOT EXISTS (
            SELECT 1 FROM manga_item_legacy_identity_map m
            WHERE m.old_entity_type = 'manga_chapter' AND m.old_entity_id = c.id
        )
    ) THEN
        RAISE EXCEPTION 'Manga Catalog Item backfill left a chapter without an item mapping';
    END IF;
    IF (SELECT count(*) FROM manga_item_legacy_identity_map
        WHERE old_entity_type = 'manga_chapter') <> (
        SELECT COALESCE(sum(work_item_counts.item_count), 0)
        FROM manga_chapters c
        JOIN LATERAL (
            SELECT count(*)::bigint AS item_count
            FROM manga_item_legacy_identity_map work_map
            WHERE work_map.old_entity_type = 'manga_work'
              AND work_map.old_entity_id = c.work_id
        ) work_item_counts ON true
    ) THEN
        RAISE EXCEPTION 'Manga chapter identity map does not cover every derived item';
    END IF;
    IF EXISTS (
        SELECT 1 FROM manga_item_legacy_identity_map m
        LEFT JOIN manga_items i ON i.id = m.catalog_item_id
        WHERE i.id IS NULL
    ) THEN
        RAISE EXCEPTION 'Manga Catalog Item identity map contains an orphan';
    END IF;
END $$;

COMMIT;
