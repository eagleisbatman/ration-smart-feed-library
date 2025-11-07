-- Migration: Create custom_feeds table
-- Description: Creates custom_feeds table as a replica of feeds table with additional user_id foreign key

CREATE TABLE IF NOT EXISTS custom_feeds (
    -- Primary Key
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- User Foreign Key
    user_id UUID NOT NULL REFERENCES user_information(id) ON DELETE CASCADE,
    
    -- Feed Code (format: 'IND-1223' - country_code + '-' + unique number)
    feed_code VARCHAR(20) UNIQUE NOT NULL,
    
    -- Country Information
    fd_country_id UUID REFERENCES country(id),
    fd_country_name VARCHAR(100),
    fd_country_cd VARCHAR(10),
    
    -- Feed Information
    fd_name VARCHAR(100) NOT NULL,
    fd_category VARCHAR(50),
    fd_type VARCHAR(50),
    
    -- Nutritional Data
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
    
    -- Additional Fields
    id_orginin VARCHAR(50),
    id_ipb_local_lab VARCHAR(50),
    
    -- Metadata
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL
);

-- Create indexes for better performance
CREATE INDEX IF NOT EXISTS idx_custom_feeds_user_id ON custom_feeds(user_id);
CREATE INDEX IF NOT EXISTS idx_custom_feeds_feed_code ON custom_feeds(feed_code);
CREATE INDEX IF NOT EXISTS idx_custom_feeds_country_id ON custom_feeds(fd_country_id);

-- Add comment to table
COMMENT ON TABLE custom_feeds IS 'Custom feeds created by users, replica of feeds table with user_id foreign key';

-- Add comments to key columns
COMMENT ON COLUMN custom_feeds.id IS 'Primary key, auto-generated UUID';
COMMENT ON COLUMN custom_feeds.user_id IS 'Foreign key to user_information table';
COMMENT ON COLUMN custom_feeds.feed_code IS 'Unique feed code (e.g., IND-1234)';
COMMENT ON COLUMN custom_feeds.fd_name IS 'Feed name (required)'; 