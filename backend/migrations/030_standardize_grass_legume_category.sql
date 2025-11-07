-- Migration: Standardize Grass/Legume Forage category name
-- Description: Update category name from 'Grass/Legume forage' to 'Grass/Legume Forage'
-- Date: 2025-09-30
-- Author: System

-- Log the migration start
INSERT INTO migration_log (migration_name, applied_at, description) 
VALUES ('030_standardize_grass_legume_category', NOW(), 'Standardize Grass/Legume Forage category name');

-- Check current count before update
DO $$
DECLARE
    old_count INTEGER;
    new_count INTEGER;
BEGIN
    -- Count records with old category name
    SELECT COUNT(*) INTO old_count FROM feeds WHERE fd_category = 'Grass/Legume forage';
    
    -- Log the count
    RAISE NOTICE 'Records to be updated: %', old_count;
    
    -- Perform the update
    UPDATE feeds 
    SET fd_category = 'Grass/Legume Forage' 
    WHERE fd_category = 'Grass/Legume forage';
    
    -- Count records after update
    SELECT COUNT(*) INTO new_count FROM feeds WHERE fd_category = 'Grass/Legume Forage';
    
    -- Log the result
    RAISE NOTICE 'Records updated: %', new_count;
    
    -- Verify the update
    IF new_count >= old_count THEN
        RAISE NOTICE 'Migration completed successfully';
    ELSE
        RAISE EXCEPTION 'Migration failed - record count mismatch';
    END IF;
END $$;

-- Log the migration completion
UPDATE migration_log 
SET completed_at = NOW(), status = 'completed' 
WHERE migration_name = '030_standardize_grass_legume_category' 
AND completed_at IS NULL;
