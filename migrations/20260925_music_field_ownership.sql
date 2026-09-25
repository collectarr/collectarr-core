-- Archive legacy Music values before moving them out of the canonical schema.
-- Run this migration against the Core PostgreSQL database before deploying
-- code that expects the updated SQLAlchemy models.

BEGIN;

CREATE TABLE IF NOT EXISTS music_release_group_synopsis_archive (
    release_group_id uuid PRIMARY KEY,
    synopsis text NOT NULL,
    archived_at timestamptz NOT NULL DEFAULT now()
);

INSERT INTO music_release_group_synopsis_archive (
    release_group_id,
    synopsis,
    archived_at
)
SELECT id, synopsis, now()
FROM music_release_groups
WHERE synopsis IS NOT NULL
ON CONFLICT (release_group_id) DO UPDATE
SET synopsis = EXCLUDED.synopsis,
    archived_at = EXCLUDED.archived_at;

CREATE TABLE IF NOT EXISTS music_medium_condition_archive (
    medium_id uuid PRIMARY KEY,
    release_id uuid NOT NULL,
    medium_number integer NOT NULL,
    media_condition varchar(100) NOT NULL,
    archived_at timestamptz NOT NULL DEFAULT now()
);

INSERT INTO music_medium_condition_archive (
    medium_id,
    release_id,
    medium_number,
    media_condition,
    archived_at
)
SELECT id, release_id, medium_number, media_condition, now()
FROM music_mediums
WHERE media_condition IS NOT NULL
ON CONFLICT (medium_id) DO UPDATE
SET release_id = EXCLUDED.release_id,
    medium_number = EXCLUDED.medium_number,
    media_condition = EXCLUDED.media_condition,
    archived_at = EXCLUDED.archived_at;

ALTER TABLE music_release_groups DROP COLUMN IF EXISTS synopsis;
ALTER TABLE music_mediums DROP COLUMN IF EXISTS media_condition;
ALTER TABLE music_tracks ADD COLUMN IF NOT EXISTS recording_id varchar(128);

COMMIT;
