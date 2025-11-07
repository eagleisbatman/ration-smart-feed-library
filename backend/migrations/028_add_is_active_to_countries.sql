-- Migration: Add is_active column to country table
-- Date: 2024-01-XX
-- Description: Add boolean column to control which countries are active for user registration

-- Add is_active column to country table
ALTER TABLE country 
ADD COLUMN is_active BOOLEAN DEFAULT FALSE NOT NULL;

-- Add comment for documentation
COMMENT ON COLUMN country.is_active IS 'Boolean flag to control if country is active for user registration';

-- Create index for better performance when filtering by is_active
CREATE INDEX IF NOT EXISTS idx_country_is_active ON country(is_active);

-- Optional: Set some countries as active (uncomment and modify as needed)
-- UPDATE country SET is_active = TRUE WHERE country_code IN ('USA', 'CAN', 'GBR', 'AUS', 'IND');
