-- Migration 010: Create Feed Classification Tables
-- This migration creates the feed_types and feed_categories tables

-- Feed Types Table
CREATE TABLE feed_types (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    type_code VARCHAR(20) UNIQUE NOT NULL,           -- e.g., 'FORAGE', 'CONCENTRATE'
    type_name VARCHAR(100) NOT NULL,                 -- e.g., 'Forage', 'Concentrate'
    description TEXT,                                 -- Optional description
    sort_order INTEGER DEFAULT 0,                    -- For display ordering
    is_active BOOLEAN DEFAULT TRUE,                  -- Soft delete
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Feed Categories Table
CREATE TABLE feed_categories (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    category_code VARCHAR(50) UNIQUE NOT NULL,       -- e.g., 'GRAIN_CROP_FORAGE'
    category_name VARCHAR(100) NOT NULL,             -- e.g., 'Grain Crop Forage'
    feed_type_id UUID NOT NULL REFERENCES feed_types(id),
    description TEXT,                                 -- Optional description
    sort_order INTEGER DEFAULT 0,                    -- For display ordering
    is_active BOOLEAN DEFAULT TRUE,                  -- Soft delete
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for performance
CREATE INDEX idx_feed_categories_type_id ON feed_categories(feed_type_id);
CREATE INDEX idx_feed_types_active ON feed_types(is_active);
CREATE INDEX idx_feed_categories_active ON feed_categories(is_active);

-- Comments for documentation
COMMENT ON TABLE feed_types IS 'Master table for feed types (Forage, Concentrate)';
COMMENT ON TABLE feed_categories IS 'Master table for feed categories, linked to feed types';
COMMENT ON COLUMN feed_types.type_code IS 'Unique code for the feed type';
COMMENT ON COLUMN feed_categories.category_code IS 'Unique code for the feed category';
COMMENT ON COLUMN feed_categories.feed_type_id IS 'Foreign key to feed_types table';

-- Insert initial data
INSERT INTO feed_types (type_code, type_name, description, sort_order) VALUES
('FORAGE', 'Forage', 'Roughage feeds including hay, silage, and pasture', 1),
('CONCENTRATE', 'Concentrate', 'High-energy and protein feeds', 2);

-- Insert categories for Forage
INSERT INTO feed_categories (category_code, category_name, feed_type_id, description, sort_order) VALUES
('GRAIN_CROP_FORAGE', 'Grain Crop Forage', (SELECT id FROM feed_types WHERE type_code = 'FORAGE'), 'Forage from grain crops like corn silage', 1),
('GRASS_LEGUME_FORAGE', 'Grass/Legume Forage', (SELECT id FROM feed_types WHERE type_code = 'FORAGE'), 'Mixed grass and legume forages', 2),
('PASTURE', 'Pasture', (SELECT id FROM feed_types WHERE type_code = 'FORAGE'), 'Fresh pasture and grazing materials', 3);

-- Insert categories for Concentrate
INSERT INTO feed_categories (category_code, category_name, feed_type_id, description, sort_order) VALUES
('ADDITIVE', 'Additive', (SELECT id FROM feed_types WHERE type_code = 'CONCENTRATE'), 'Feed additives and supplements', 1),
('BY_PRODUCT_OTHER', 'By-Product/Other', (SELECT id FROM feed_types WHERE type_code = 'CONCENTRATE'), 'By-products and miscellaneous feeds', 2),
('ENERGY_SOURCE', 'Energy Source', (SELECT id FROM feed_types WHERE type_code = 'CONCENTRATE'), 'High-energy feeds like grains', 3),
('GRAIN_CROP_BY_PRODUCT', 'Grain Crop/By-product', (SELECT id FROM feed_types WHERE type_code = 'CONCENTRATE'), 'Grain by-products and processed grains', 4),
('PLANT_PROTEIN', 'Plant Protein', (SELECT id FROM feed_types WHERE type_code = 'CONCENTRATE'), 'Plant-based protein sources', 5),
('SUGAR_SUGAR_ALCOHOL', 'Sugar/Sugar Alcohol', (SELECT id FROM feed_types WHERE type_code = 'CONCENTRATE'), 'Sugar-based feeds and sweeteners', 6),
('MINERAL', 'Mineral', (SELECT id FROM feed_types WHERE type_code = 'CONCENTRATE'), 'Mineral supplements and premixes', 7); 