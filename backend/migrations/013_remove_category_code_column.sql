-- Migration: Remove category_code column from feed_categories table
-- Date: 2025-08-06
-- Description: Remove the category_code column from feed_categories table as it's no longer needed

-- Drop the unique constraint on category_code first
ALTER TABLE feed_categories DROP CONSTRAINT IF EXISTS feed_categories_category_code_key;

-- Remove category_code column from feed_categories table
ALTER TABLE feed_categories DROP COLUMN IF EXISTS category_code;

-- Add unique constraint on category_name to maintain data integrity
ALTER TABLE feed_categories ADD CONSTRAINT feed_categories_category_name_unique UNIQUE (category_name);

-- Log the migration
INSERT INTO migration_log (migration_name, applied_at, description) 
VALUES ('013_remove_category_code_column', NOW(), 'Removed category_code column from feed_categories table'); 