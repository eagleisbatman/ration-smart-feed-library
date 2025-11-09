-- Migration: Populate Feed Types and Categories from Feed Data
-- Description: Populate feed_types and feed_categories master tables from existing feed data
-- Date: 2025-01-XX

-- Step 1: Populate feed_types from distinct fd_type values in feeds table
INSERT INTO feed_types (type_name, description, is_active, created_at, updated_at)
SELECT DISTINCT 
    fd_type as type_name,
    CASE 
        WHEN fd_type = 'Forage' THEN 'Roughage feeds including hay, silage, and pasture'
        WHEN fd_type = 'Concentrate' THEN 'High-energy and protein feeds'
        ELSE 'Feed type: ' || fd_type
    END as description,
    TRUE as is_active,
    NOW() as created_at,
    NOW() as updated_at
FROM feeds
WHERE fd_type IS NOT NULL
ON CONFLICT (type_name) DO NOTHING;

-- Step 2: Populate feed_categories from distinct fd_category values in feeds table
-- Link categories to feed_types based on the feed's fd_type
INSERT INTO feed_categories (category_name, feed_type_id, description, is_active, created_at, updated_at)
SELECT DISTINCT
    f.fd_category as category_name,
    ft.id as feed_type_id,
    'Category: ' || f.fd_category as description,
    TRUE as is_active,
    NOW() as created_at,
    NOW() as updated_at
FROM feeds f
INNER JOIN feed_types ft ON ft.type_name = f.fd_type
WHERE f.fd_category IS NOT NULL
ON CONFLICT (category_name) DO NOTHING;

-- Step 3: Update feeds table to link fd_category_id
UPDATE feeds f
SET fd_category_id = fc.id
FROM feed_categories fc
WHERE f.fd_category = fc.category_name
AND f.fd_category_id IS NULL;

-- Verification queries (commented out - run manually to verify)
-- SELECT COUNT(*) as feed_types_count FROM feed_types;
-- SELECT COUNT(*) as feed_categories_count FROM feed_categories;
-- SELECT COUNT(*) as feeds_with_category_id FROM feeds WHERE fd_category_id IS NOT NULL;
-- SELECT ft.type_name, COUNT(fc.id) as category_count 
-- FROM feed_types ft 
-- LEFT JOIN feed_categories fc ON fc.feed_type_id = ft.id 
-- GROUP BY ft.type_name;

