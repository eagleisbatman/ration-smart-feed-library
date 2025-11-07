-- Migration: Fix common columns in custom_feeds to match feeds table
-- Date: 2025-08-09
-- Description: Align common columns in custom_feeds with feeds table (source of truth)

-- Fix fd_code to match feeds table (double precision)
ALTER TABLE custom_feeds ALTER COLUMN fd_code TYPE DOUBLE PRECISION USING CAST(fd_code AS DOUBLE PRECISION);

-- Fix text columns to match feeds table (TEXT instead of VARCHAR)
ALTER TABLE custom_feeds ALTER COLUMN fd_country_name TYPE TEXT;
ALTER TABLE custom_feeds ALTER COLUMN fd_country_cd TYPE TEXT;
ALTER TABLE custom_feeds ALTER COLUMN fd_name TYPE TEXT;
ALTER TABLE custom_feeds ALTER COLUMN fd_category TYPE TEXT;
ALTER TABLE custom_feeds ALTER COLUMN fd_type TYPE TEXT;
ALTER TABLE custom_feeds ALTER COLUMN fd_origin TYPE TEXT;
ALTER TABLE custom_feeds ALTER COLUMN fd_ipb_local_lab TYPE TEXT;



