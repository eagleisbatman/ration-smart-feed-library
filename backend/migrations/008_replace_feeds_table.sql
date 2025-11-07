-- Migration 008: Replace feeds table with new simplified structure
-- Created: 2025-01-27
-- Description: Drop old feeds and feed_price tables, create new feeds table with fd_country_id FK
-- Status: COMPLETED SUCCESSFULLY - Table structure already matches new schema

-- ===========================
-- DROP OLD TABLES
-- ===========================

-- Drop feed_price table first (due to FK dependency)
DROP TABLE IF EXISTS feed_price CASCADE;

-- Drop old feeds table
DROP TABLE IF EXISTS feeds CASCADE;

-- ===========================
-- CREATE NEW FEEDS TABLE
-- ===========================

CREATE TABLE feeds (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    feed_code VARCHAR(20) UNIQUE NOT NULL,  -- Format: 'IND-1223' (country_code + '-' + unique number)
    fd_country_id UUID REFERENCES country(id) ON DELETE SET NULL,
    fd_country_name VARCHAR(100),  -- Maps to old Fd_Country
    fd_country_cd VARCHAR(10),
    fd_name VARCHAR(100) NOT NULL,
    fd_category VARCHAR(50),
    fd_type VARCHAR(50),
    fd_dm VARCHAR(20),
    fd_ash VARCHAR(20),
    fd_cp VARCHAR(20),
    fd_ee VARCHAR(20),
    fd_cf VARCHAR(20),
    fd_nfe VARCHAR(20),
    fd_starch VARCHAR(20),
    fd_ndf VARCHAR(20),
    fd_hemicellulose VARCHAR(20),
    fd_adf VARCHAR(20),
    fd_cellulose VARCHAR(20),
    fd_lignin VARCHAR(20),
    fd_ndin VARCHAR(20),
    fd_adin VARCHAR(20),
    fd_calcium VARCHAR(20),
    fd_phosphorus VARCHAR(20),
    id_orginin VARCHAR(50),
    id_ipb_local_lab VARCHAR(50),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ===========================
-- ADD INDEXES FOR PERFORMANCE
-- ===========================

CREATE INDEX idx_feeds_country_id ON feeds(fd_country_id);
CREATE INDEX idx_feeds_country_name ON feeds(fd_country_name);
CREATE INDEX idx_feeds_type ON feeds(fd_type);
CREATE INDEX idx_feeds_category ON feeds(fd_category);

-- ===========================
-- ADD COMMENTS
-- ===========================

COMMENT ON TABLE feeds IS 'Simplified feeds table with country foreign key relationship';
COMMENT ON COLUMN feeds.fd_country_id IS 'Foreign key reference to country table';
COMMENT ON COLUMN feeds.fd_country_name IS 'Country name (maps to old Fd_Country column)';
COMMENT ON COLUMN feeds.fd_country_cd IS 'Country code';
COMMENT ON COLUMN feeds.fd_name IS 'Feed name';
COMMENT ON COLUMN feeds.fd_category IS 'Feed category';
COMMENT ON COLUMN feeds.fd_type IS 'Feed type';

-- ===========================
-- VERIFICATION QUERIES
-- ===========================

-- Verify table creation (commented out for production)
-- SELECT 'New feeds table created successfully' as status;
-- SELECT COUNT(*) as table_count FROM information_schema.tables WHERE table_name = 'feeds';
-- SELECT column_name, data_type, is_nullable FROM information_schema.columns WHERE table_name = 'feeds' ORDER BY ordinal_position; 