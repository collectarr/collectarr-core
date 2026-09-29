-- Up migration: persist source-neutral user proposals for moderator review.
-- Apply this only through the normal migration process; do not run it against
-- a live database as part of the flattened-catalog cutover work.

CREATE TABLE IF NOT EXISTS catalog_item_proposals (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    kind item_kind NOT NULL,
    catalog_item JSONB NOT NULL,
    title VARCHAR(255) NOT NULL,
    submitted_by_user_id UUID NULL REFERENCES users(id) ON DELETE SET NULL,
    status VARCHAR(32) NOT NULL DEFAULT 'pending',
    review_note VARCHAR(2000) NULL
);

CREATE INDEX IF NOT EXISTS ix_catalog_item_proposals_kind
    ON catalog_item_proposals (kind);
CREATE INDEX IF NOT EXISTS ix_catalog_item_proposals_title
    ON catalog_item_proposals (title);
CREATE INDEX IF NOT EXISTS ix_catalog_item_proposals_status
    ON catalog_item_proposals (status);

-- Down migration, for rollback before accepting submissions:
-- DROP TABLE IF EXISTS catalog_item_proposals;
