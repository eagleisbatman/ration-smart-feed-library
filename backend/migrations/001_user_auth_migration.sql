-- Migration 001: User Authentication System Schema Changes
-- Date: 2025-01-27
-- Description: Convert from phone number-based to email+PIN authentication system

-- =====================================================
-- STEP 1: CREATE COUNTRY TABLE
-- =====================================================

-- Create the country table
CREATE TABLE IF NOT EXISTS country (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(100) NOT NULL UNIQUE,
    country_code VARCHAR(3) NOT NULL UNIQUE,
    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Create index for faster lookups
CREATE INDEX IF NOT EXISTS idx_country_code ON country(country_code);
CREATE INDEX IF NOT EXISTS idx_country_name ON country(name);

-- =====================================================
-- STEP 2: ADD NEW COLUMNS TO user_information TABLE
-- =====================================================

-- Add new authentication columns
ALTER TABLE user_information 
ADD COLUMN IF NOT EXISTS email_id VARCHAR(255),
ADD COLUMN IF NOT EXISTS pin_hash VARCHAR(255),
ADD COLUMN IF NOT EXISTS country_id UUID,
ADD COLUMN IF NOT EXISTS created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP,
ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP;

-- =====================================================
-- STEP 3: CREATE CONSTRAINTS AND INDEXES
-- =====================================================

-- Add foreign key constraint to country table
ALTER TABLE user_information 
ADD CONSTRAINT fk_user_country 
FOREIGN KEY (country_id) REFERENCES country(id) ON DELETE SET NULL;

-- Create unique constraint on email_id (will be added after data migration)
-- Note: This will be uncommented after data migration is complete
-- ALTER TABLE user_information ADD CONSTRAINT uq_user_email UNIQUE (email_id);

-- Create indexes for better performance
CREATE INDEX IF NOT EXISTS idx_user_email ON user_information(email_id);
CREATE INDEX IF NOT EXISTS idx_user_country ON user_information(country_id);
CREATE INDEX IF NOT EXISTS idx_user_created_at ON user_information(created_at);

-- =====================================================
-- STEP 4: CREATE TRIGGER FOR UPDATED_AT TIMESTAMP
-- =====================================================

-- Create function to update the updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Create triggers for both tables
DROP TRIGGER IF EXISTS update_user_information_updated_at ON user_information;
CREATE TRIGGER update_user_information_updated_at
    BEFORE UPDATE ON user_information
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

DROP TRIGGER IF EXISTS update_country_updated_at ON country;
CREATE TRIGGER update_country_updated_at
    BEFORE UPDATE ON country
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- =====================================================
-- STEP 5: DATA MIGRATION NOTES
-- =====================================================

-- IMPORTANT: After this migration, you will need to:
-- 1. Run 002_populate_countries.sql to populate the COUNTRY table
-- 2. Update existing user records with proper country_id values
-- 3. Once data migration is complete, uncomment the unique constraint on email_id
-- 4. Remove old columns (phone_number, region, zone, woreda, kebele, language, country)

-- Example data migration queries (to be run manually after country population):
-- UPDATE user_information 
-- SET country_id = (SELECT id FROM country WHERE name = user_information.country)
-- WHERE country_id IS NULL AND country IS NOT NULL;

-- =====================================================
-- VERIFICATION QUERIES
-- =====================================================

-- Verify table structure
-- SELECT column_name, data_type, is_nullable, column_default 
-- FROM information_schema.columns 
-- WHERE table_name = 'user_information' 
-- ORDER BY ordinal_position;

-- SELECT column_name, data_type, is_nullable, column_default 
-- FROM information_schema.columns 
-- WHERE table_name = 'country' 
-- ORDER BY ordinal_position;

-- Check constraints
-- SELECT conname, contype, pg_get_constraintdef(oid) 
-- FROM pg_constraint 
-- WHERE conrelid = 'user_information'::regclass;

COMMIT; 