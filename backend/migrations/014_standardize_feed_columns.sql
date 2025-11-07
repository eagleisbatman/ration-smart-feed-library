-- Migration: Standardize feed columns to use fd_ prefix
-- Date: 2025-08-09
-- Description: Rename feed columns to use consistent fd_ prefix for all feed-related columns

-- Rename columns in feeds table
ALTER TABLE feeds RENAME COLUMN feed_code TO fd_code;
ALTER TABLE feeds RENAME COLUMN feed_id TO fd_id;
ALTER TABLE feeds RENAME COLUMN nfe_pct TO fd_nfe;
ALTER TABLE feeds RENAME COLUMN season TO fd_season;
ALTER TABLE feeds RENAME COLUMN id_orginin TO fd_origin;
ALTER TABLE feeds RENAME COLUMN id_ipb_local_lab TO fd_ipb_local_lab;

-- Rename columns in custom_feeds table (if they exist)
ALTER TABLE custom_feeds RENAME COLUMN feed_code TO fd_code;
ALTER TABLE custom_feeds RENAME COLUMN id_orginin TO fd_origin;
ALTER TABLE custom_feeds RENAME COLUMN id_ipb_local_lab TO fd_ipb_local_lab;

-- Update any foreign key constraints if needed
-- Note: The primary key 'id' remains unchanged as it's the UUID primary key
