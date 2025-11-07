-- Migration: Create New Database Schema with Multi-Language Support
-- Description: Complete schema for new database with multi-language feed support
-- Date: 2025-01-XX

-- 1. Countries table (with language support)
CREATE TABLE IF NOT EXISTS countries (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(100) NOT NULL UNIQUE,
    country_code VARCHAR(3) NOT NULL UNIQUE,
    currency VARCHAR(10),
    is_active BOOLEAN DEFAULT FALSE,
    supported_languages JSONB DEFAULT '["en"]'::jsonb, -- Array of language codes
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_countries_code ON countries(country_code);
CREATE INDEX idx_countries_active ON countries(is_active) WHERE is_active = TRUE;

-- 2. Country Languages mapping
CREATE TABLE IF NOT EXISTS country_languages (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    country_id UUID NOT NULL REFERENCES countries(id) ON DELETE CASCADE,
    language_code VARCHAR(10) NOT NULL, -- ISO 639-1 or 639-2
    language_name VARCHAR(100) NOT NULL, -- 'English', 'Afan Oromo', 'Amharic'
    is_default BOOLEAN DEFAULT FALSE,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(country_id, language_code)
);

CREATE INDEX idx_country_languages_country ON country_languages(country_id);
CREATE INDEX idx_country_languages_code ON country_languages(language_code);

-- 3. Feed Types
CREATE TABLE IF NOT EXISTS feed_types (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    type_name VARCHAR(50) NOT NULL UNIQUE, -- 'Forage', 'Concentrate'
    description TEXT,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- 4. Feed Categories
CREATE TABLE IF NOT EXISTS feed_categories (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    category_name VARCHAR(100) NOT NULL,
    feed_type_id UUID REFERENCES feed_types(id),
    description TEXT,
    sort_order INTEGER DEFAULT 0,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(category_name, feed_type_id)
);

CREATE INDEX idx_feed_categories_type ON feed_categories(feed_type_id);

-- 5. Feeds table (base, language-agnostic)
CREATE TABLE IF NOT EXISTS feeds (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    fd_code VARCHAR(50) NOT NULL,
    fd_type VARCHAR(50) NOT NULL, -- 'Forage' or 'Concentrate'
    fd_category VARCHAR(50),
    fd_country_id UUID NOT NULL REFERENCES countries(id),
    
    -- Nutritional values (language-agnostic)
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
    
    -- Metadata
    fd_season VARCHAR(50),
    fd_orginin VARCHAR(255),
    fd_ipb_local_lab VARCHAR(255),
    
    -- Default name (English, for reference/search)
    fd_name_default VARCHAR(255) NOT NULL,
    
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(fd_code, fd_country_id)
);

CREATE INDEX idx_feeds_country ON feeds(fd_country_id);
CREATE INDEX idx_feeds_type ON feeds(fd_type);
CREATE INDEX idx_feeds_category ON feeds(fd_category);
CREATE INDEX idx_feeds_active ON feeds(is_active) WHERE is_active = TRUE;
CREATE INDEX idx_feeds_name_search ON feeds USING gin(to_tsvector('english', fd_name_default));

-- 6. Feed Translations table (multi-language names/descriptions)
CREATE TABLE IF NOT EXISTS feed_translations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    feed_id UUID NOT NULL REFERENCES feeds(id) ON DELETE CASCADE,
    language_code VARCHAR(10) NOT NULL, -- ISO 639-1 or 639-2
    country_id UUID REFERENCES countries(id), -- NULL = global translation
    fd_name VARCHAR(255) NOT NULL,
    fd_description TEXT,
    is_primary BOOLEAN DEFAULT FALSE, -- Primary translation for this language
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(feed_id, language_code, country_id)
);

CREATE INDEX idx_feed_translations_feed ON feed_translations(feed_id);
CREATE INDEX idx_feed_translations_lang ON feed_translations(language_code);
CREATE INDEX idx_feed_translations_country ON feed_translations(country_id);
CREATE INDEX idx_feed_translations_primary ON feed_translations(feed_id, language_code, is_primary) WHERE is_primary = TRUE;

-- 7. Users table
CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(100) NOT NULL,
    email_id VARCHAR(255) NOT NULL UNIQUE,
    pin_hash VARCHAR(255) NOT NULL,
    country_id UUID REFERENCES countries(id),
    organization_id UUID, -- Will reference organizations table
    is_admin BOOLEAN DEFAULT FALSE,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_users_email ON users(email_id);
CREATE INDEX idx_users_country ON users(country_id);
CREATE INDEX idx_users_org ON users(organization_id);
CREATE INDEX idx_users_admin ON users(is_admin) WHERE is_admin = TRUE;

-- 8. Organizations table (multi-tenant)
CREATE TABLE IF NOT EXISTS organizations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL,
    slug VARCHAR(100) UNIQUE NOT NULL,
    contact_email VARCHAR(255),
    is_active BOOLEAN DEFAULT TRUE,
    rate_limit_per_hour INTEGER DEFAULT 1000,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_organizations_slug ON organizations(slug);
CREATE INDEX idx_organizations_active ON organizations(is_active) WHERE is_active = TRUE;

-- 9. API Keys table
CREATE TABLE IF NOT EXISTS api_keys (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    key_hash VARCHAR(255) NOT NULL UNIQUE,
    key_prefix VARCHAR(20) NOT NULL,
    name VARCHAR(255),
    is_active BOOLEAN DEFAULT TRUE,
    last_used_at TIMESTAMP,
    expires_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW(),
    created_by UUID REFERENCES users(id)
);

CREATE INDEX idx_api_keys_org ON api_keys(organization_id);
CREATE INDEX idx_api_keys_hash ON api_keys(key_hash);
CREATE INDEX idx_api_keys_active ON api_keys(is_active) WHERE is_active = TRUE;

-- 10. API Usage tracking
CREATE TABLE IF NOT EXISTS api_usage (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    api_key_id UUID REFERENCES api_keys(id),
    endpoint VARCHAR(255) NOT NULL,
    method VARCHAR(10) NOT NULL,
    response_status INTEGER,
    response_time_ms INTEGER,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_api_usage_org ON api_usage(organization_id, created_at);
CREATE INDEX idx_api_usage_key ON api_usage(api_key_id, created_at);
CREATE INDEX idx_api_usage_endpoint ON api_usage(endpoint, created_at);

-- 11. Insert default feed types
INSERT INTO feed_types (type_name, description) VALUES
    ('Forage', 'Forage feeds including grasses, hay, and silage'),
    ('Concentrate', 'Concentrate feeds including grains and supplements')
ON CONFLICT (type_name) DO NOTHING;

-- Notes:
-- - Feeds table stores language-agnostic data
-- - Feed translations table stores multi-language names/descriptions
-- - Country languages table maps countries to their supported languages
-- - Traduora will be used for managing translations
-- - API will return feeds with names in requested language

