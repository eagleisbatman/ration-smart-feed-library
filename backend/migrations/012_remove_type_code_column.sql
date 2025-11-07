-- Migration: Remove type_code column from feed_types table
-- Date: 2025-08-06
-- Description: Remove the type_code column from feed_types table as it's no longer needed

-- Drop the unique constraint on type_code first
ALTER TABLE feed_types DROP CONSTRAINT IF EXISTS feed_types_type_code_key;

-- Remove type_code column from feed_types table
ALTER TABLE feed_types DROP COLUMN IF EXISTS type_code;

-- Add unique constraint on type_name to maintain data integrity
ALTER TABLE feed_types ADD CONSTRAINT feed_types_type_name_unique UNIQUE (type_name);

-- Log the migration
INSERT INTO migration_log (migration_name, applied_at, description) 
VALUES ('012_remove_type_code_column', NOW(), 'Removed type_code column from feed_types table'); 