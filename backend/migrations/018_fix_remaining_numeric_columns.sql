-- Migration 018: Fix remaining numeric columns in custom_feeds table
-- This migration converts the remaining double precision columns to TEXT

-- Convert remaining numeric columns in custom_feeds table to TEXT
ALTER TABLE custom_feeds ALTER COLUMN fd_st TYPE TEXT USING CAST(fd_st AS TEXT);
ALTER TABLE custom_feeds ALTER COLUMN fd_lg TYPE TEXT USING CAST(fd_lg AS TEXT);
ALTER TABLE custom_feeds ALTER COLUMN fd_ca TYPE TEXT USING CAST(fd_ca AS TEXT);
ALTER TABLE custom_feeds ALTER COLUMN fd_p TYPE TEXT USING CAST(fd_p AS TEXT);

-- Add comments for the converted columns
COMMENT ON COLUMN custom_feeds.fd_st IS 'Starch percentage stored as TEXT';
COMMENT ON COLUMN custom_feeds.fd_lg IS 'Lignin percentage stored as TEXT';
COMMENT ON COLUMN custom_feeds.fd_ca IS 'Calcium percentage stored as TEXT';
COMMENT ON COLUMN custom_feeds.fd_p IS 'Phosphorus percentage stored as TEXT';
