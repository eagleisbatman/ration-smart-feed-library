-- Migration: Improve Schema for MCP Server Fork
-- Description: Add indexes, soft delete support, and data integrity constraints
-- Date: 2025-01-XX

-- 1. Add indexes for frequently queried fields
CREATE INDEX IF NOT EXISTS idx_feeds_country_id ON feeds(fd_country_id);
CREATE INDEX IF NOT EXISTS idx_feeds_type ON feeds(fd_type);
CREATE INDEX IF NOT EXISTS idx_feeds_category ON feeds(fd_category);
CREATE INDEX IF NOT EXISTS idx_feeds_name_search ON feeds USING gin(to_tsvector('english', fd_name));

-- 2. Add is_active flag for soft deletes
ALTER TABLE feeds ADD COLUMN IF NOT EXISTS is_active BOOLEAN DEFAULT TRUE;
CREATE INDEX IF NOT EXISTS idx_feeds_is_active ON feeds(is_active);

-- 3. Update existing feeds to be active
UPDATE feeds SET is_active = TRUE WHERE is_active IS NULL;

-- 4. Add data integrity constraints
ALTER TABLE feeds 
  ADD CONSTRAINT chk_feed_dm_range CHECK (fd_dm IS NULL OR (fd_dm >= 0 AND fd_dm <= 100));
ALTER TABLE feeds 
  ADD CONSTRAINT chk_feed_cp_range CHECK (fd_cp IS NULL OR (fd_cp >= 0 AND fd_cp <= 100));

-- 5. Add index on user_information for faster auth lookups
CREATE INDEX IF NOT EXISTS idx_user_email ON user_information(email_id);
CREATE INDEX IF NOT EXISTS idx_user_country_id ON user_information(country_id);

-- 6. Add index on country for faster lookups
CREATE INDEX IF NOT EXISTS idx_country_name ON country(name);
CREATE INDEX IF NOT EXISTS idx_country_code ON country(country_code);

-- 7. Add composite index for feed search queries
CREATE INDEX IF NOT EXISTS idx_feeds_search ON feeds(fd_country_id, fd_type, fd_category) WHERE is_active = TRUE;

-- Notes:
-- - Indexes improve query performance for feed search
-- - Soft delete allows recovery of accidentally deleted feeds
-- - Constraints ensure data quality
-- - Composite index optimizes common search patterns

