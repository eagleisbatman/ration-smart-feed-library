-- Migration: Remove type_code and category_code columns
-- Date: 2025-01-27
-- Description: Remove unused type_code and category_code columns from feed classification tables

-- Remove type_code column from feed_types table
ALTER TABLE feed_types DROP COLUMN IF EXISTS type_code;

-- Remove category_code column from feed_categories table  
ALTER TABLE feed_categories DROP COLUMN IF EXISTS category_code;

-- Add unique constraints on type_name and category_name to maintain data integrity
ALTER TABLE feed_types ADD CONSTRAINT feed_types_type_name_unique UNIQUE (type_name);
ALTER TABLE feed_categories ADD CONSTRAINT feed_categories_category_name_unique UNIQUE (category_name);

-- Log the migration
INSERT INTO migration_log (migration_name, applied_at, description) 
VALUES ('011_remove_type_code_category_code', NOW(), 'Removed unused type_code and category_code columns from feed classification tables'); 