-- Exact row counts
SELECT 'items' AS tbl, count(*) AS rows FROM items
UNION ALL SELECT 'editions', count(*) FROM editions
UNION ALL SELECT 'variants', count(*) FROM variants
UNION ALL SELECT 'releases', count(*) FROM releases
UNION ALL SELECT 'series', count(*) FROM series
UNION ALL SELECT 'volumes', count(*) FROM volumes
UNION ALL SELECT 'characters', count(*) FROM characters
UNION ALL SELECT 'character_appearances', count(*) FROM character_appearances
UNION ALL SELECT 'persons', count(*) FROM persons
UNION ALL SELECT 'entity_persons', count(*) FROM entity_persons
UNION ALL SELECT 'organizations', count(*) FROM organizations
UNION ALL SELECT 'entity_organizations', count(*) FROM entity_organizations
UNION ALL SELECT 'story_arcs', count(*) FROM story_arcs
UNION ALL SELECT 'story_arc_items', count(*) FROM story_arc_items
UNION ALL SELECT 'tags', count(*) FROM tags
UNION ALL SELECT 'entity_tags', count(*) FROM entity_tags
UNION ALL SELECT 'external_provider_ids', count(*) FROM external_provider_ids
UNION ALL SELECT 'image_assets', count(*) FROM image_assets
UNION ALL SELECT 'image_cache_entries', count(*) FROM image_cache_entries
UNION ALL SELECT 'franchises', count(*) FROM franchises
UNION ALL SELECT 'metadata_proposals', count(*) FROM metadata_proposals
UNION ALL SELECT 'admin_audit_logs', count(*) FROM admin_audit_logs
UNION ALL SELECT 'provider_ingest_jobs', count(*) FROM provider_ingest_jobs
UNION ALL SELECT 'users', count(*) FROM users
ORDER BY rows DESC;

-- Items by kind
SELECT kind, count(*) FROM items GROUP BY kind ORDER BY count DESC;

-- Average row size per core table
SELECT 'items' AS tbl, pg_size_pretty(COALESCE(avg(pg_column_size(items.*))::bigint, 0)) AS avg_row FROM items
UNION ALL SELECT 'editions', pg_size_pretty(COALESCE(avg(pg_column_size(editions.*))::bigint, 0)) FROM editions
UNION ALL SELECT 'variants', pg_size_pretty(COALESCE(avg(pg_column_size(variants.*))::bigint, 0)) FROM variants
UNION ALL SELECT 'series', pg_size_pretty(COALESCE(avg(pg_column_size(series.*))::bigint, 0)) FROM series
UNION ALL SELECT 'characters', pg_size_pretty(COALESCE(avg(pg_column_size(characters.*))::bigint, 0)) FROM characters
UNION ALL SELECT 'persons', pg_size_pretty(COALESCE(avg(pg_column_size(persons.*))::bigint, 0)) FROM persons
UNION ALL SELECT 'external_provider_ids', pg_size_pretty(COALESCE(avg(pg_column_size(external_provider_ids.*))::bigint, 0)) FROM external_provider_ids
UNION ALL SELECT 'organizations', pg_size_pretty(COALESCE(avg(pg_column_size(organizations.*))::bigint, 0)) FROM organizations;

-- DB total
SELECT pg_size_pretty(pg_database_size('collectarr')) AS db_total;
