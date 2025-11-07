-- =====================================================
-- Feed Formulation Database Schema Creation Script
-- =====================================================
-- This script creates the complete database schema
-- for the Feed Formulation application
-- 
-- Created: 2025-01-XX
-- Purpose: Direct database creation (alternative to migrations)
-- =====================================================

-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- =====================================================
-- 1. COUNTRY TABLE
-- =====================================================
CREATE TABLE IF NOT EXISTS country (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(100) NOT NULL UNIQUE,
    country_code VARCHAR(3) NOT NULL UNIQUE,
    currency VARCHAR(10),
    is_active BOOLEAN DEFAULT FALSE NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL
);

-- Indexes for country table
CREATE INDEX IF NOT EXISTS idx_country_name ON country(name);
CREATE INDEX IF NOT EXISTS idx_country_code ON country(country_code);
CREATE INDEX IF NOT EXISTS idx_country_active ON country(is_active);

-- Comments for country table
COMMENT ON TABLE country IS 'Countries with currency and active flags for user registration';
COMMENT ON COLUMN country.id IS 'Primary key UUID';
COMMENT ON COLUMN country.name IS 'Country name';
COMMENT ON COLUMN country.country_code IS 'ISO 3-letter country code';
COMMENT ON COLUMN country.currency IS 'Country currency code (e.g., USD, EUR, INR)';
COMMENT ON COLUMN country.is_active IS 'Flag indicating if country is active for registration';

-- =====================================================
-- 2. USER INFORMATION TABLE
-- =====================================================
CREATE TABLE IF NOT EXISTS user_information (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(100) NOT NULL,
    email_id VARCHAR(255) NOT NULL UNIQUE,
    pin_hash VARCHAR(255) NOT NULL,
    country_id UUID NOT NULL REFERENCES country(id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
    is_admin BOOLEAN DEFAULT FALSE NOT NULL,
    is_active BOOLEAN DEFAULT TRUE NOT NULL
);

-- Indexes for user_information table
CREATE INDEX IF NOT EXISTS idx_user_email ON user_information(email_id);
CREATE INDEX IF NOT EXISTS idx_user_country ON user_information(country_id);
CREATE INDEX IF NOT EXISTS idx_user_admin ON user_information(is_admin);
CREATE INDEX IF NOT EXISTS idx_user_active ON user_information(is_active);

-- Comments for user_information table
COMMENT ON TABLE user_information IS 'User authentication and profile data';
COMMENT ON COLUMN user_information.id IS 'Primary key UUID';
COMMENT ON COLUMN user_information.name IS 'User full name';
COMMENT ON COLUMN user_information.email_id IS 'User email address (unique)';
COMMENT ON COLUMN user_information.pin_hash IS 'Hashed 4-digit PIN';
COMMENT ON COLUMN user_information.country_id IS 'Foreign key to country table';
COMMENT ON COLUMN user_information.is_admin IS 'Admin flag for feedback management';
COMMENT ON COLUMN user_information.is_active IS 'User status flag for admin management';

-- =====================================================
-- 3. FEED TYPES TABLE
-- =====================================================
CREATE TABLE IF NOT EXISTS feed_type (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    type_code VARCHAR(20) UNIQUE NOT NULL,
    type_name VARCHAR(100) NOT NULL,
    description TEXT,
    sort_order INTEGER DEFAULT 0,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for feed_type table
CREATE INDEX IF NOT EXISTS idx_feed_type_code ON feed_type(type_code);
CREATE INDEX IF NOT EXISTS idx_feed_type_active ON feed_type(is_active);
CREATE INDEX IF NOT EXISTS idx_feed_type_sort ON feed_type(sort_order);

-- Comments for feed_type table
COMMENT ON TABLE feed_type IS 'Master table for feed types (Forage, Concentrate)';
COMMENT ON COLUMN feed_type.type_code IS 'Unique code for the feed type';
COMMENT ON COLUMN feed_type.type_name IS 'Human-readable feed type name';

-- =====================================================
-- 4. FEED CATEGORIES TABLE
-- =====================================================
CREATE TABLE IF NOT EXISTS feed_category (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    category_code VARCHAR(50) UNIQUE NOT NULL,
    category_name VARCHAR(100) NOT NULL,
    feed_type_id UUID NOT NULL REFERENCES feed_type(id),
    description TEXT,
    sort_order INTEGER DEFAULT 0,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for feed_category table
CREATE INDEX IF NOT EXISTS idx_feed_category_code ON feed_category(category_code);
CREATE INDEX IF NOT EXISTS idx_feed_category_type ON feed_category(feed_type_id);
CREATE INDEX IF NOT EXISTS idx_feed_category_active ON feed_category(is_active);
CREATE INDEX IF NOT EXISTS idx_feed_category_sort ON feed_category(sort_order);

-- Comments for feed_category table
COMMENT ON TABLE feed_category IS 'Master table for feed categories, linked to feed types';
COMMENT ON COLUMN feed_category.category_code IS 'Unique code for the feed category';
COMMENT ON COLUMN feed_category.feed_type_id IS 'Foreign key to feed_type table';

-- =====================================================
-- 5. FEEDS TABLE
-- =====================================================
CREATE TABLE IF NOT EXISTS feeds (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    feed_code VARCHAR(20) UNIQUE NOT NULL,
    fd_country_id UUID REFERENCES country(id) ON DELETE SET NULL,
    fd_country_name VARCHAR(100),
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

-- Indexes for feeds table
CREATE INDEX IF NOT EXISTS idx_feeds_code ON feeds(feed_code);
CREATE INDEX IF NOT EXISTS idx_feeds_country_id ON feeds(fd_country_id);
CREATE INDEX IF NOT EXISTS idx_feeds_country_name ON feeds(fd_country_name);
CREATE INDEX IF NOT EXISTS idx_feeds_type ON feeds(fd_type);
CREATE INDEX IF NOT EXISTS idx_feeds_category ON feeds(fd_category);

-- Comments for feeds table
COMMENT ON TABLE feeds IS 'Standard feed ingredients with nutritional data';
COMMENT ON COLUMN feeds.feed_code IS 'Unique feed code (e.g., IND-1223)';
COMMENT ON COLUMN feeds.fd_country_id IS 'Foreign key reference to country table';
COMMENT ON COLUMN feeds.fd_name IS 'Feed name';
COMMENT ON COLUMN feeds.fd_category IS 'Feed category';
COMMENT ON COLUMN feeds.fd_type IS 'Feed type';

-- =====================================================
-- 6. CUSTOM FEEDS TABLE
-- =====================================================
CREATE TABLE IF NOT EXISTS custom_feeds (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES user_information(id) ON DELETE CASCADE,
    feed_name VARCHAR(100) NOT NULL,
    feed_category VARCHAR(50),
    feed_type VARCHAR(50),
    dm VARCHAR(20),
    ash VARCHAR(20),
    cp VARCHAR(20),
    ee VARCHAR(20),
    cf VARCHAR(20),
    nfe VARCHAR(20),
    starch VARCHAR(20),
    ndf VARCHAR(20),
    hemicellulose VARCHAR(20),
    adf VARCHAR(20),
    cellulose VARCHAR(20),
    lignin VARCHAR(20),
    ndin VARCHAR(20),
    adin VARCHAR(20),
    calcium VARCHAR(20),
    phosphorus VARCHAR(20),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for custom_feeds table
CREATE INDEX IF NOT EXISTS idx_custom_feeds_user ON custom_feeds(user_id);
CREATE INDEX IF NOT EXISTS idx_custom_feeds_name ON custom_feeds(feed_name);
CREATE INDEX IF NOT EXISTS idx_custom_feeds_type ON custom_feeds(feed_type);
CREATE INDEX IF NOT EXISTS idx_custom_feeds_category ON custom_feeds(feed_category);

-- Comments for custom_feeds table
COMMENT ON TABLE custom_feeds IS 'User-created custom feed ingredients';
COMMENT ON COLUMN custom_feeds.user_id IS 'Foreign key to user_information table';
COMMENT ON COLUMN custom_feeds.feed_name IS 'Custom feed name';

-- =====================================================
-- 7. FEED ANALYTICS TABLE
-- =====================================================
CREATE TABLE IF NOT EXISTS feed_analytics (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    feed_id UUID NOT NULL,
    feed_type VARCHAR(20) NOT NULL CHECK (feed_type IN ('standard', 'custom')),
    user_id UUID REFERENCES user_information(id),
    usage_count INTEGER DEFAULT 1,
    last_used_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for feed_analytics table
CREATE INDEX IF NOT EXISTS idx_feed_analytics_feed ON feed_analytics(feed_id);
CREATE INDEX IF NOT EXISTS idx_feed_analytics_type ON feed_analytics(feed_type);
CREATE INDEX IF NOT EXISTS idx_feed_analytics_user ON feed_analytics(user_id);
CREATE INDEX IF NOT EXISTS idx_feed_analytics_usage ON feed_analytics(usage_count);
CREATE INDEX IF NOT EXISTS idx_feed_analytics_last_used ON feed_analytics(last_used_at);

-- Comments for feed_analytics table
COMMENT ON TABLE feed_analytics IS 'Feed usage analytics and statistics';
COMMENT ON COLUMN feed_analytics.feed_id IS 'ID of the feed (standard or custom)';
COMMENT ON COLUMN feed_analytics.feed_type IS 'Type: standard or custom';
COMMENT ON COLUMN feed_analytics.usage_count IS 'Number of times this feed was used';

-- =====================================================
-- 8. DIET REPORTS TABLE
-- =====================================================
CREATE TABLE IF NOT EXISTS diet_reports (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES user_information(id) ON DELETE CASCADE,
    simulation_id VARCHAR(20) NOT NULL,
    report_name VARCHAR(255) NOT NULL,
    file_name VARCHAR(255) NOT NULL,
    pdf_data BYTEA NOT NULL,
    file_size INTEGER NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for diet_reports table
CREATE INDEX IF NOT EXISTS idx_diet_reports_user ON diet_reports(user_id);
CREATE INDEX IF NOT EXISTS idx_diet_reports_simulation ON diet_reports(simulation_id);
CREATE INDEX IF NOT EXISTS idx_diet_reports_created ON diet_reports(created_at);

-- Comments for diet_reports table
COMMENT ON TABLE diet_reports IS 'Stores PDF diet recommendation reports generated for users';
COMMENT ON COLUMN diet_reports.id IS 'Primary key - UUID';
COMMENT ON COLUMN diet_reports.user_id IS 'Foreign key to user_information table';
COMMENT ON COLUMN diet_reports.simulation_id IS 'Simulation identifier (e.g., sim-1234)';
COMMENT ON COLUMN diet_reports.report_name IS 'Human-readable report name';
COMMENT ON COLUMN diet_reports.file_name IS 'Original filename of the PDF';
COMMENT ON COLUMN diet_reports.pdf_data IS 'The actual PDF file as binary data';
COMMENT ON COLUMN diet_reports.file_size IS 'Size of the PDF file in bytes';

-- =====================================================
-- 9. REPORTS TABLE
-- =====================================================
CREATE TABLE IF NOT EXISTS reports (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    report_id VARCHAR(50) NOT NULL UNIQUE,
    report_type VARCHAR(10) NOT NULL CHECK (report_type IN ('rec', 'eval')),
    user_id UUID NOT NULL REFERENCES user_information(id),
    bucket_url TEXT,
    json_result JSONB,
    saved_to_bucket BOOLEAN DEFAULT FALSE,
    save_report BOOLEAN DEFAULT FALSE,
    report BYTEA,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for reports table
CREATE INDEX IF NOT EXISTS idx_reports_report_id ON reports(report_id);
CREATE INDEX IF NOT EXISTS idx_reports_user_id ON reports(user_id);
CREATE INDEX IF NOT EXISTS idx_reports_report_type ON reports(report_type);
CREATE INDEX IF NOT EXISTS idx_reports_created_at ON reports(created_at);

-- Comments for reports table
COMMENT ON TABLE reports IS 'Stores PDF reports and JSON results for diet recommendations and evaluations';
COMMENT ON COLUMN reports.id IS 'Primary key UUID';
COMMENT ON COLUMN reports.report_id IS 'Unique report identifier in format rec-xxxxxx or eval-xxxxxx';
COMMENT ON COLUMN reports.report_type IS 'Type of report: rec (recommendation) or eval (evaluation)';
COMMENT ON COLUMN reports.user_id IS 'Foreign key to user_information table';
COMMENT ON COLUMN reports.bucket_url IS 'URL of PDF report stored in AWS S3 bucket';
COMMENT ON COLUMN reports.json_result IS 'Complete API response JSON data';
COMMENT ON COLUMN reports.saved_to_bucket IS 'Boolean flag indicating if PDF was successfully saved to AWS bucket';
COMMENT ON COLUMN reports.save_report IS 'Boolean flag for user explicitly saving report';
COMMENT ON COLUMN reports.report IS 'Binary PDF file data';

-- =====================================================
-- 10. USER FEEDBACK TABLE
-- =====================================================
CREATE TABLE IF NOT EXISTS user_feedback (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES user_information(id) ON DELETE CASCADE,
    overall_rating INTEGER NOT NULL CHECK (overall_rating >= 1 AND overall_rating <= 5),
    text_feedback TEXT,
    feedback_type VARCHAR(50) DEFAULT 'General',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for user_feedback table
CREATE INDEX IF NOT EXISTS idx_user_feedback_user ON user_feedback(user_id);
CREATE INDEX IF NOT EXISTS idx_user_feedback_rating ON user_feedback(overall_rating);
CREATE INDEX IF NOT EXISTS idx_user_feedback_type ON user_feedback(feedback_type);
CREATE INDEX IF NOT EXISTS idx_user_feedback_created ON user_feedback(created_at);

-- Comments for user_feedback table
COMMENT ON TABLE user_feedback IS 'User feedback and ratings for the application';
COMMENT ON COLUMN user_feedback.user_id IS 'Foreign key to user_information table';
COMMENT ON COLUMN user_feedback.overall_rating IS 'Star rating from 1 to 5';
COMMENT ON COLUMN user_feedback.text_feedback IS 'Optional text feedback';
COMMENT ON COLUMN user_feedback.feedback_type IS 'Type of feedback (General, Bug, Feature, etc.)';

-- =====================================================
-- INITIAL DATA POPULATION
-- =====================================================

-- Insert initial countries
INSERT INTO country (name, country_code, currency, is_active) VALUES
('India', 'IND', 'INR', true),
('United States', 'USA', 'USD', true),
('United Kingdom', 'GBR', 'GBP', true),
('Canada', 'CAN', 'CAD', true),
('Australia', 'AUS', 'AUD', true),
('Germany', 'DEU', 'EUR', true),
('France', 'FRA', 'EUR', true),
('Brazil', 'BRA', 'BRL', true),
('China', 'CHN', 'CNY', true),
('Japan', 'JPN', 'JPY', true)
ON CONFLICT (country_code) DO NOTHING;

-- Insert initial feed types
INSERT INTO feed_type (type_code, type_name, description, sort_order) VALUES
('FORAGE', 'Forage', 'Roughage feeds including hay, silage, and pasture', 1),
('CONCENTRATE', 'Concentrate', 'High-energy and protein feeds', 2)
ON CONFLICT (type_code) DO NOTHING;

-- Insert initial feed categories
INSERT INTO feed_category (category_code, category_name, feed_type_id, description, sort_order) VALUES
('GRAIN_CROP_FORAGE', 'Grain Crop Forage', (SELECT id FROM feed_type WHERE type_code = 'FORAGE'), 'Forage from grain crops like corn silage', 1),
('GRASS_LEGUME_FORAGE', 'Grass/Legume Forage', (SELECT id FROM feed_type WHERE type_code = 'FORAGE'), 'Mixed grass and legume forages', 2),
('PASTURE', 'Pasture', (SELECT id FROM feed_type WHERE type_code = 'FORAGE'), 'Fresh pasture and grazing materials', 3),
('ENERGY_CONCENTRATE', 'Energy Concentrate', (SELECT id FROM feed_type WHERE type_code = 'CONCENTRATE'), 'High-energy feeds like grains', 4),
('PROTEIN_CONCENTRATE', 'Protein Concentrate', (SELECT id FROM feed_type WHERE type_code = 'CONCENTRATE'), 'High-protein feeds like soybean meal', 5),
('MINERAL_SUPPLEMENT', 'Mineral Supplement', (SELECT id FROM feed_type WHERE type_code = 'CONCENTRATE'), 'Mineral supplements and premixes', 6)
ON CONFLICT (category_code) DO NOTHING;

-- =====================================================
-- VERIFICATION QUERIES
-- =====================================================

-- Verify all tables were created
SELECT 
    'Database Schema Creation Complete' as status,
    COUNT(*) as total_tables
FROM information_schema.tables 
WHERE table_schema = 'public' 
AND table_name IN (
    'country', 'user_information', 'feed_type', 'feed_category', 
    'feeds', 'custom_feeds', 'feed_analytics', 'diet_reports', 
    'reports', 'user_feedback'
);

-- Verify initial data was inserted
SELECT 'Countries' as table_name, COUNT(*) as record_count FROM country
UNION ALL
SELECT 'Feed Types', COUNT(*) FROM feed_type
UNION ALL
SELECT 'Feed Categories', COUNT(*) FROM feed_category;

-- =====================================================
-- END OF SCRIPT
-- =====================================================
