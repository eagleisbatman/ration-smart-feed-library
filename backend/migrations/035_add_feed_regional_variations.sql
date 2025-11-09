-- Migration: Add Feed Regional Variations Support
-- Description: Add table to store regional variations of feeds (same feed, different regions/zones with different nutritional values)
-- Date: 2025-01-XX

-- Feed Regional Variations table
CREATE TABLE IF NOT EXISTS feed_regional_variations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    feed_id UUID NOT NULL REFERENCES feeds(id) ON DELETE CASCADE,
    
    -- Location information
    region VARCHAR(255),
    zone VARCHAR(255),
    town_woreda VARCHAR(255),
    agro_ecology VARCHAR(255),
    production_system VARCHAR(255),
    
    -- Regional nutritional values (may differ from base feed)
    fd_dm NUMERIC(5,2),
    fd_ash NUMERIC(5,2),
    fd_cp NUMERIC(5,2),
    fd_ee NUMERIC(5,2),
    fd_st NUMERIC(5,2),
    fd_ndf NUMERIC(5,2),
    fd_adf NUMERIC(5,2),
    fd_lg NUMERIC(5,2),
    fd_ca NUMERIC(5,2),
    fd_p NUMERIC(5,2),
    fd_cf NUMERIC(5,2),
    fd_nfe NUMERIC(5,2),
    fd_hemicellulose NUMERIC(5,2),
    fd_cellulose NUMERIC(5,2),
    fd_ndin NUMERIC(5,2),
    fd_adin NUMERIC(5,2),
    fd_npn_cp INTEGER,
    
    -- Additional metadata
    reference VARCHAR(255),
    processing_methods VARCHAR(255),
    forms_of_feed_presentation VARCHAR(255),
    
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    
    UNIQUE(feed_id, region, zone, town_woreda)
);

CREATE INDEX idx_feed_regional_variations_feed ON feed_regional_variations(feed_id);
CREATE INDEX idx_feed_regional_variations_region ON feed_regional_variations(region);
CREATE INDEX idx_feed_regional_variations_zone ON feed_regional_variations(zone);

COMMENT ON TABLE feed_regional_variations IS 'Stores regional variations of feeds - same feed name but different nutritional values by region/zone';

