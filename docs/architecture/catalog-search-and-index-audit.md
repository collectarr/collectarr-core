# Catalog Search and Identifier Index Audit

Updated: 2026-10-05

## Search contract

The shared and kind-specific Catalog Item search endpoints return a stable
page with `items`, `next_offset`, and `has_more`. Cross-kind results are
combined before pagination and ordered by normalized sort title, normalized
title, kind, and item ID. Kind-specific searches use the same page shape and
sort by their kind's sort value, title, and item ID. Each query fetches one
look-ahead row to determine `has_more`. Music keeps its detailed disc and track
payload in that page because Add needs album contents while searching.

## Identifier paths and indexes

| Kind | Exact barcode | Exact catalog number | Additional identifiers | Index path |
| --- | --- | --- | --- | --- |
| Anime | `barcode` | `catalog_number` | Normalized identifier objects | B-tree columns; `details @>` with GIN |
| Board Game | `barcode` | `catalog_number` | Normalized identifier objects | B-tree columns; `details @>` with GIN |
| Book | `barcode` | `catalog_number` | ISBN values and normalized identifier objects | B-tree columns; `details @>` with GIN |
| Comic | `barcode` | `catalog_number` | Normalized identifier objects | B-tree columns; `details @>` with GIN |
| Game | `barcode` | `catalog_number` | Normalized identifier objects | B-tree columns; `details @>` with GIN |
| Manga | `barcode` | `catalog_number` | ISBN values and normalized identifier objects | B-tree columns; `details @>` with GIN |
| Movie | `barcode` | `catalog_number` | Normalized identifier objects | B-tree columns; `details @>` with GIN |
| Music | `barcode` | `catalog_number` | No separate identifier list | B-tree columns |
| TV | `barcode` | `catalog_number` | Normalized identifier objects | B-tree columns; `details @>` with GIN |

The eight non-Music item tables index their JSONB `details` column with
`jsonb_path_ops`. Identifier lookups use JSONB containment against
`identifiers[].normalized_value`, which is supported by that GIN operator
class. Book and Manga write paths copy ISBN fields into the same normalized
identifier list. Manga's scalar ISBN lookups also use JSONB containment, so
the same GIN index supports them. Movie proposal writes normalize contained
identifier values before saving them. Music stores its supported barcode and
catalog number in indexed scalar columns.

Every item table has B-tree indexes for `barcode` and `catalog_number`. The
Music catalog-number filters use exact equality so they can use the existing
B-tree index; title, artist, label, and subtitle text searches retain their
trigram indexes. Other kinds use exact identifier filters or indexed JSONB
containment rather than casting the complete JSON document to text.

Title search uses trigram indexes on the title and sort-title columns. Music
also indexes artist, label, and subtitle with trigram indexes. The cross-kind
search does not scan `CAST(details AS text)`.

## Query planner verification

The ORM definitions and query operators are index-compatible by inspection.
An actual PostgreSQL `EXPLAIN` run was not available in the implementation
environment: it has no local PostgreSQL service or command-line tools, and the
configured test database is not available. No configured or live database was
queried. Planner confirmation remains an environment-dependent verification
item; run the Core PostgreSQL test suite against its isolated `*_test` database
before deployment.
