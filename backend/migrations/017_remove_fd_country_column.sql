-- Migration 017: Remove deprecated fd_country column from feeds table
-- Description: Removes the legacy fd_country column as fd_country_name is now the standard
-- Date: 2025-08-09

-- Remove the deprecated fd_country column from feeds table
ALTER TABLE feeds DROP COLUMN IF EXISTS fd_country;

-- Add comment to document the change
COMMENT ON TABLE feeds IS 'Updated: Removed deprecated fd_country column - use fd_country_name instead';
