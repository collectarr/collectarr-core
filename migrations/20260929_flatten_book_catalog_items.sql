-- One-way backfill from Book Work -> Edition -> Printing to Catalog Items.
-- Run only against a reviewed non-live copy of the pinned Core baseline.
-- Source tables remain intact until App and Sync have moved to the new IDs.

BEGIN;

CREATE TABLE IF NOT EXISTS book_items (
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
CREATE INDEX IF NOT EXISTS ix_book_items_title ON book_items (title);
CREATE INDEX IF NOT EXISTS ix_book_items_sort_key ON book_items (sort_key);
CREATE INDEX IF NOT EXISTS ix_book_items_barcode ON book_items (barcode);
CREATE INDEX IF NOT EXISTS ix_book_items_catalog_number ON book_items (catalog_number);

CREATE TABLE IF NOT EXISTS book_item_printings (
    id uuid PRIMARY KEY,
    book_item_id uuid NOT NULL REFERENCES book_items(id) ON DELETE CASCADE,
    printing_number integer,
    title varchar(255),
    release_date jsonb,
    publisher varchar(255),
    language varchar(16),
    isbn varchar(32),
    created_at timestamptz NOT NULL,
    updated_at timestamptz NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_book_item_printings_item
    ON book_item_printings (book_item_id);

CREATE TABLE IF NOT EXISTS book_item_credits (
    id uuid PRIMARY KEY,
    book_item_id uuid NOT NULL REFERENCES book_items(id) ON DELETE CASCADE,
    credit_type varchar(32) NOT NULL,
    person_id uuid REFERENCES persons(id) ON DELETE SET NULL,
    name varchar(255) NOT NULL,
    role varchar(64),
    role_id varchar(64),
    sequence integer,
    created_at timestamptz NOT NULL,
    updated_at timestamptz NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_book_item_credits_item_role
    ON book_item_credits (book_item_id, credit_type, sequence);

CREATE TABLE IF NOT EXISTS book_item_identifiers (
    id uuid PRIMARY KEY,
    book_item_id uuid NOT NULL REFERENCES book_items(id) ON DELETE CASCADE,
    identifier_type varchar(64) NOT NULL,
    value varchar(255) NOT NULL,
    normalized_value varchar(255),
    is_primary boolean NOT NULL DEFAULT false,
    created_at timestamptz NOT NULL,
    updated_at timestamptz NOT NULL,
    CONSTRAINT uq_book_item_identifier_normalized
        UNIQUE (book_item_id, identifier_type, normalized_value)
);
CREATE INDEX IF NOT EXISTS ix_book_item_identifiers_type_value
    ON book_item_identifiers (identifier_type, normalized_value);

CREATE TABLE IF NOT EXISTS book_item_legacy_identity_map (
    old_entity_type text NOT NULL,
    old_entity_id uuid NOT NULL,
    catalog_item_id uuid NOT NULL REFERENCES book_items(id) ON DELETE CASCADE,
    resolution text NOT NULL,
    PRIMARY KEY (old_entity_type, old_entity_id, catalog_item_id)
);
CREATE INDEX IF NOT EXISTS ix_book_item_legacy_identity_map_old
    ON book_item_legacy_identity_map (old_entity_type, old_entity_id);

CREATE TABLE IF NOT EXISTS book_item_migration_review (
    catalog_item_id uuid NOT NULL REFERENCES book_items(id) ON DELETE CASCADE,
    source_table text NOT NULL,
    source_id uuid NOT NULL,
    field_key text NOT NULL,
    legacy_payload jsonb NOT NULL,
    PRIMARY KEY (catalog_item_id, source_table, source_id, field_key)
);

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM book_items)
       OR EXISTS (SELECT 1 FROM book_item_printings)
       OR EXISTS (SELECT 1 FROM book_item_credits)
       OR EXISTS (SELECT 1 FROM book_item_identifiers)
       OR EXISTS (SELECT 1 FROM book_item_legacy_identity_map)
       OR EXISTS (SELECT 1 FROM book_item_migration_review) THEN
        RAISE EXCEPTION 'Book Catalog Item backfill destination is not empty';
    END IF;
    IF EXISTS (
        SELECT 1
        FROM book_editions e
        JOIN book_works collision ON collision.id = e.id
    ) THEN
        RAISE EXCEPTION 'Book Catalog Item backfill found an edition/work ID collision';
    END IF;
    IF EXISTS (
        SELECT 1 FROM book_editions e
        LEFT JOIN book_works w ON w.id = e.work_id
        WHERE w.id IS NULL
    ) THEN
        RAISE EXCEPTION 'Book Catalog Item backfill found an edition without a work';
    END IF;
END $$;

-- Every Edition keeps its identity and receives shared Work metadata.
INSERT INTO book_items (
    id, title, sort_key, barcode, catalog_number, details, revision,
    created_at, updated_at
)
SELECT
    e.id,
    w.title,
    w.sort_title,
    barcode.value,
    catalog_number.value,
    jsonb_strip_nulls(jsonb_build_object(
        'title', w.title,
        'sort_key', w.sort_title,
        'subtitle', w.subtitle,
        'description', COALESCE(e.description, w.description),
        'edition_title', e.edition_statement,
        'localized_title', e.display_title,
        'release_date', COALESCE(to_jsonb(e.publication_date_parts), to_jsonb(e.publication_date)),
        'release_date_parts', e.publication_date_parts,
        'release_status', e.release_status,
        'publisher', COALESCE(e.publisher, e.imprint, w.original_publisher),
        'imprint', e.imprint,
        'country', e.region,
        'language', COALESCE(e.language, w.original_language),
        'barcode', barcode.value,
        'catalog_number', catalog_number.value,
        'physical_format', COALESCE(e.format, e.binding),
        'page_count', e.page_count,
        'age_rating', e.age_rating,
        'cover_image_url', e.cover_image_url,
        'thumbnail_image_url', e.cover_image_url,
        'genres', COALESCE(genre_values.json_value, '[]'::jsonb),
        'search_aliases', COALESCE(alias_values.json_value, '[]'::jsonb),
        'series_title', series_values.first_title,
        'series_group', series_values.first_slug,
        'series_tags', COALESCE(series_values.titles, '[]'::jsonb),
        'volume_number', series_values.first_display_number,
        'external_links', COALESCE(link_values.json_value, '[]'::jsonb),
        'isbn', isbn.value,
        'isbn10', isbn10.value,
        'isbn13', isbn13.value
    )),
    1,
    LEAST(w.created_at, e.created_at),
    GREATEST(w.updated_at, e.updated_at)
FROM book_editions e
JOIN book_works w ON w.id = e.work_id
LEFT JOIN LATERAL (
    SELECT i.value
    FROM book_identifiers i
    WHERE i.edition_id = e.id
      AND i.identifier_type IN ('barcode', 'ean', 'upc')
    ORDER BY i.is_primary DESC, i.id
    LIMIT 1
) barcode ON true
LEFT JOIN LATERAL (
    SELECT i.value
    FROM book_identifiers i
    WHERE i.edition_id = e.id AND i.identifier_type = 'catalog_number'
    ORDER BY i.is_primary DESC, i.id
    LIMIT 1
) catalog_number ON true
LEFT JOIN LATERAL (
    SELECT i.value
    FROM book_identifiers i
    WHERE i.edition_id = e.id AND i.identifier_type IN ('isbn', 'isbn13', 'isbn10')
    ORDER BY i.is_primary DESC, i.id
    LIMIT 1
) isbn ON true
LEFT JOIN LATERAL (
    SELECT i.value
    FROM book_identifiers i
    WHERE i.edition_id = e.id AND i.identifier_type = 'isbn10'
    ORDER BY i.is_primary DESC, i.id
    LIMIT 1
) isbn10 ON true
LEFT JOIN LATERAL (
    SELECT i.value
    FROM book_identifiers i
    WHERE i.edition_id = e.id AND i.identifier_type = 'isbn13'
    ORDER BY i.is_primary DESC, i.id
    LIMIT 1
) isbn13 ON true
LEFT JOIN LATERAL (
    SELECT jsonb_agg(t.name ORDER BY t.name) AS json_value
    FROM entity_tags et
    JOIN tags t ON t.id = et.tag_id
    WHERE t.kind = 'genre'
      AND ((et.entity_type = 'book_work' AND et.entity_id = w.id)
        OR (et.entity_type = 'book_edition' AND et.entity_id = e.id))
) genre_values ON true
LEFT JOIN LATERAL (
    SELECT jsonb_agg(a.alias ORDER BY a.position, a.created_at) AS json_value
    FROM entity_aliases a
    WHERE (a.entity_type = 'book_work' AND a.entity_id = w.id)
       OR (a.entity_type = 'book_edition' AND a.entity_id = e.id)
) alias_values ON true
LEFT JOIN LATERAL (
    SELECT
        (array_agg(s.title ORDER BY m.sequence NULLS LAST, s.title))[1] AS first_title,
        (array_agg(s.slug ORDER BY m.sequence NULLS LAST, s.title))[1] AS first_slug,
        (array_agg(m.display_number ORDER BY m.sequence NULLS LAST, s.title))[1]
            AS first_display_number,
        jsonb_agg(s.title ORDER BY m.sequence NULLS LAST, s.title) AS titles
    FROM book_series_memberships m
    JOIN book_series s ON s.id = m.series_id
    WHERE m.work_id = w.id
) series_values ON true
LEFT JOIN LATERAL (
    SELECT jsonb_agg(jsonb_strip_nulls(jsonb_build_object(
        'url', l.url, 'site', l.site, 'name', l.name, 'kind', l.kind,
        'description', l.description, 'position', l.position, 'link_type', l.link_type
    )) ORDER BY l.position, l.created_at) AS json_value
    FROM entity_links l
    WHERE (l.entity_type = 'book_work' AND l.entity_id = w.id)
       OR (l.entity_type = 'book_edition' AND l.entity_id = e.id)
) link_values ON true;

-- A Work with no Edition still becomes one root. Edition-only facts stay null.
INSERT INTO book_items (
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
        'language', w.original_language,
        'publisher', w.original_publisher,
        'genres', COALESCE(genre_values.json_value, '[]'::jsonb),
        'search_aliases', COALESCE(alias_values.json_value, '[]'::jsonb),
        'series_title', series_values.first_title,
        'series_group', series_values.first_slug,
        'series_tags', COALESCE(series_values.titles, '[]'::jsonb),
        'volume_number', series_values.first_display_number,
        'external_links', COALESCE(link_values.json_value, '[]'::jsonb)
    )),
    1,
    w.created_at,
    w.updated_at
FROM book_works w
LEFT JOIN LATERAL (
    SELECT jsonb_agg(t.name ORDER BY t.name) AS json_value
    FROM entity_tags et
    JOIN tags t ON t.id = et.tag_id
    WHERE t.kind = 'genre' AND et.entity_type = 'book_work' AND et.entity_id = w.id
) genre_values ON true
LEFT JOIN LATERAL (
    SELECT jsonb_agg(a.alias ORDER BY a.position, a.created_at) AS json_value
    FROM entity_aliases a
    WHERE a.entity_type = 'book_work' AND a.entity_id = w.id
) alias_values ON true
LEFT JOIN LATERAL (
    SELECT
        (array_agg(s.title ORDER BY m.sequence NULLS LAST, s.title))[1] AS first_title,
        (array_agg(s.slug ORDER BY m.sequence NULLS LAST, s.title))[1] AS first_slug,
        (array_agg(m.display_number ORDER BY m.sequence NULLS LAST, s.title))[1]
            AS first_display_number,
        jsonb_agg(s.title ORDER BY m.sequence NULLS LAST, s.title) AS titles
    FROM book_series_memberships m
    JOIN book_series s ON s.id = m.series_id
    WHERE m.work_id = w.id
) series_values ON true
LEFT JOIN LATERAL (
    SELECT jsonb_agg(jsonb_strip_nulls(jsonb_build_object(
        'url', l.url, 'site', l.site, 'name', l.name, 'kind', l.kind,
        'description', l.description, 'position', l.position, 'link_type', l.link_type
    )) ORDER BY l.position, l.created_at) AS json_value
    FROM entity_links l
    WHERE l.entity_type = 'book_work' AND l.entity_id = w.id
) link_values ON true
WHERE NOT EXISTS (SELECT 1 FROM book_editions e WHERE e.work_id = w.id);

INSERT INTO book_item_legacy_identity_map (
    old_entity_type, old_entity_id, catalog_item_id, resolution
)
SELECT 'book_edition', e.id, e.id, 'preserved_concrete_id'
FROM book_editions e;

INSERT INTO book_item_legacy_identity_map (
    old_entity_type, old_entity_id, catalog_item_id, resolution
)
SELECT
    'book_work', w.id, e.id,
    CASE WHEN counts.edition_count = 1
         THEN 'single_edition_unambiguous'
         ELSE 'ambiguous_parent_multiple_editions'
    END
FROM book_works w
JOIN book_editions e ON e.work_id = w.id
JOIN (
    SELECT work_id, count(*) AS edition_count
    FROM book_editions
    GROUP BY work_id
) counts ON counts.work_id = w.id;

INSERT INTO book_item_legacy_identity_map (
    old_entity_type, old_entity_id, catalog_item_id, resolution
)
SELECT 'book_work', w.id, w.id, 'preserved_work_without_edition'
FROM book_works w
WHERE NOT EXISTS (SELECT 1 FROM book_editions e WHERE e.work_id = w.id);

INSERT INTO book_item_printings (
    id, book_item_id, printing_number, title, release_date, publisher, language, isbn,
    created_at, updated_at
)
SELECT
    p.id, p.edition_id, p.printing_number, p.printing_statement, NULL, NULL, NULL, NULL,
    p.created_at, p.updated_at
FROM book_printings p
JOIN book_editions e ON e.id = p.edition_id;

-- Preserve edition identifiers without provider provenance. Work-level control
-- numbers become kind-neutral identifier records copied onto each resulting item.
INSERT INTO book_item_identifiers (
    id, book_item_id, identifier_type, value, normalized_value, is_primary,
    created_at, updated_at
)
SELECT
    i.id, i.edition_id, i.identifier_type, i.value, i.normalized_value, i.is_primary,
    i.created_at, i.updated_at
FROM book_identifiers i
JOIN book_editions e ON e.id = i.edition_id;

INSERT INTO book_item_identifiers (
    id, book_item_id, identifier_type, value, normalized_value, is_primary,
    created_at, updated_at
)
SELECT
    md5(concat_ws(':', w.id::text, identity.catalog_item_id::text, legacy.identifier_type))::uuid,
    identity.catalog_item_id,
    legacy.identifier_type,
    legacy.value,
    lower(regexp_replace(legacy.value, '[^a-zA-Z0-9]', '', 'g')),
    false,
    w.created_at,
    w.updated_at
FROM book_works w
JOIN book_item_legacy_identity_map identity
  ON identity.old_entity_type = 'book_work' AND identity.old_entity_id = w.id
CROSS JOIN LATERAL (
    VALUES
        ('dewey', w.dewey),
        ('lccn', w.lccn),
        ('loc_control_number', w.loc_control_number)
) AS legacy(identifier_type, value)
WHERE legacy.value IS NOT NULL;

-- Edition-level credits retain their UUID. Work credits are copied with stable,
-- root-scoped IDs so each Edition can stand alone after the Work graph is removed.
INSERT INTO book_item_credits (
    id, book_item_id, credit_type, person_id, name, role, role_id, sequence,
    created_at, updated_at
)
SELECT
    CASE WHEN c.edition_id IS NOT NULL THEN c.id
         ELSE md5(concat_ws(':', c.id::text, identity.catalog_item_id::text, 'book-credit'))::uuid
    END,
    identity.catalog_item_id,
    'contributor',
    c.person_id,
    p.name,
    c.role,
    c.role_id,
    c.sequence,
    c.created_at,
    c.updated_at
FROM book_contributions c
JOIN persons p ON p.id = c.person_id
JOIN book_item_legacy_identity_map identity
  ON (c.edition_id IS NOT NULL
      AND identity.old_entity_type = 'book_edition'
      AND identity.old_entity_id = c.edition_id)
  OR (c.work_id IS NOT NULL
      AND identity.old_entity_type = 'book_work'
      AND identity.old_entity_id = c.work_id);

INSERT INTO book_item_legacy_identity_map (
    old_entity_type, old_entity_id, catalog_item_id, resolution
)
SELECT 'book_printing', p.id, p.edition_id, 'preserved_child_id'
FROM book_printings p
JOIN book_editions e ON e.id = p.edition_id;

INSERT INTO book_item_legacy_identity_map (
    old_entity_type, old_entity_id, catalog_item_id, resolution
)
SELECT
    'book_contribution', c.id, identity.catalog_item_id,
    CASE WHEN c.edition_id IS NOT NULL THEN 'edition_contribution'
         ELSE 'copied_work_contribution'
    END
FROM book_contributions c
JOIN book_item_legacy_identity_map identity
  ON (c.edition_id IS NOT NULL
      AND identity.old_entity_type = 'book_edition'
      AND identity.old_entity_id = c.edition_id)
  OR (c.work_id IS NOT NULL
      AND identity.old_entity_type = 'book_work'
      AND identity.old_entity_id = c.work_id);

INSERT INTO book_item_legacy_identity_map (
    old_entity_type, old_entity_id, catalog_item_id, resolution
)
SELECT 'book_identifier', i.id, i.edition_id, 'preserved_identifier_id'
FROM book_identifiers i
JOIN book_editions e ON e.id = i.edition_id;

INSERT INTO book_item_migration_review (
    catalog_item_id, source_table, source_id, field_key, legacy_payload
)
SELECT
    p.edition_id,
    'book_printings',
    p.id,
    'unmapped_print_run',
    jsonb_strip_nulls(jsonb_build_object('print_run', p.print_run))
FROM book_printings p
WHERE p.print_run IS NOT NULL
ON CONFLICT DO NOTHING;

INSERT INTO book_item_migration_review (
    catalog_item_id, source_table, source_id, field_key, legacy_payload
)
SELECT
    identity.catalog_item_id,
    'book_editions',
    e.id,
    'unmapped_edition_specific_fields',
    jsonb_strip_nulls(jsonb_build_object(
        'audio_length_minutes', e.audio_length_minutes,
        'dimensions', e.dimensions,
        'dust_jacket', e.dust_jacket,
        'printing', e.printing,
        'first_edition', e.first_edition,
        'number_line', e.number_line,
        'cover_image_key', e.cover_image_key
    ))
FROM book_editions e
JOIN book_item_legacy_identity_map identity
  ON identity.old_entity_type = 'book_edition' AND identity.old_entity_id = e.id
WHERE e.audio_length_minutes IS NOT NULL OR e.dimensions IS NOT NULL
   OR e.dust_jacket IS NOT NULL OR e.printing IS NOT NULL
   OR e.first_edition IS NOT NULL OR e.number_line IS NOT NULL
   OR e.cover_image_key IS NOT NULL
ON CONFLICT DO NOTHING;

INSERT INTO book_item_migration_review (
    catalog_item_id, source_table, source_id, field_key, legacy_payload
)
SELECT
    identity.catalog_item_id,
    'book_works',
    w.id,
    'unmapped_work_publication_metadata',
    jsonb_strip_nulls(jsonb_build_object(
        'original_publication_date', w.original_publication_date,
        'original_publication_date_parts', w.original_publication_date_parts,
        'first_publication_date', w.first_publication_date,
        'first_publication_date_parts', w.first_publication_date_parts,
        'original_publisher', w.original_publisher
    ))
FROM book_works w
JOIN book_item_legacy_identity_map identity
  ON identity.old_entity_type = 'book_work' AND identity.old_entity_id = w.id
WHERE w.original_publication_date IS NOT NULL
   OR w.original_publication_date_parts IS NOT NULL
   OR w.first_publication_date IS NOT NULL
   OR w.first_publication_date_parts IS NOT NULL
   OR w.original_publisher IS NOT NULL
ON CONFLICT DO NOTHING;

INSERT INTO book_item_migration_review (
    catalog_item_id, source_table, source_id, field_key, legacy_payload
)
SELECT
    identity.catalog_item_id,
    'book_series_memberships',
    membership.id,
    'legacy_series_membership',
    jsonb_strip_nulls(jsonb_build_object(
        'series_id', membership.series_id,
        'sequence', membership.sequence,
        'display_number', membership.display_number
    ))
FROM book_series_memberships membership
JOIN book_item_legacy_identity_map identity
  ON identity.old_entity_type = 'book_work'
 AND identity.old_entity_id = membership.work_id
ON CONFLICT DO NOTHING;

INSERT INTO book_item_migration_review (
    catalog_item_id, source_table, source_id, field_key, legacy_payload
)
SELECT
    identity.catalog_item_id,
    'book_series',
    series.id,
    'unmapped_series_metadata',
    jsonb_strip_nulls(jsonb_build_object(
        'slug', series.slug,
        'description', series.description,
        'original_title', series.original_title,
        'start_date', series.start_date,
        'start_date_parts', series.start_date_parts,
        'end_date', series.end_date,
        'end_date_parts', series.end_date_parts,
        'status', series.status,
        'language', series.language,
        'country', series.country
    ))
FROM book_series_memberships membership
JOIN book_series series ON series.id = membership.series_id
JOIN book_item_legacy_identity_map identity
  ON identity.old_entity_type = 'book_work'
 AND identity.old_entity_id = membership.work_id
WHERE series.description IS NOT NULL
   OR series.original_title IS NOT NULL
   OR series.start_date IS NOT NULL
   OR series.start_date_parts IS NOT NULL
   OR series.end_date IS NOT NULL
   OR series.end_date_parts IS NOT NULL
   OR series.status IS NOT NULL
   OR series.language IS NOT NULL
   OR series.country IS NOT NULL
ON CONFLICT DO NOTHING;

INSERT INTO book_item_migration_review (
    catalog_item_id, source_table, source_id, field_key, legacy_payload
)
SELECT
    identity.catalog_item_id,
    'entity_tags',
    et.id,
    'unmapped_non_genre_tag',
    jsonb_build_object('tag_id', t.id, 'name', t.name, 'kind', t.kind)
FROM entity_tags et
JOIN tags t ON t.id = et.tag_id
JOIN book_item_legacy_identity_map identity
  ON identity.old_entity_type = et.entity_type
 AND identity.old_entity_id = et.entity_id
WHERE et.entity_type IN ('book_work', 'book_edition')
  AND t.kind <> 'genre'
ON CONFLICT DO NOTHING;

INSERT INTO book_item_migration_review (
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
JOIN book_item_legacy_identity_map identity
  ON identity.old_entity_type = image.entity_type
 AND identity.old_entity_id = image.entity_id
WHERE image.entity_type IN ('book_work', 'book_edition')
ON CONFLICT DO NOTHING;

DO $$
DECLARE
    expected_items bigint;
    actual_items bigint;
    expected_printings bigint;
    actual_printings bigint;
BEGIN
    SELECT (SELECT count(*) FROM book_editions) +
           (SELECT count(*) FROM book_works w
            WHERE NOT EXISTS (
                SELECT 1 FROM book_editions e WHERE e.work_id = w.id
            ))
    INTO expected_items;
    SELECT count(*) INTO actual_items FROM book_items;
    SELECT count(*) INTO expected_printings
    FROM book_printings p JOIN book_editions e ON e.id = p.edition_id;
    SELECT count(*) INTO actual_printings FROM book_item_printings;
    IF actual_items <> expected_items THEN
        RAISE EXCEPTION 'Book item count mismatch: expected %, found %',
            expected_items, actual_items;
    END IF;
    IF actual_printings <> expected_printings THEN
        RAISE EXCEPTION 'Book printing count mismatch: expected %, found %',
            expected_printings, actual_printings;
    END IF;
END $$;

COMMIT;
