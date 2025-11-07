-- Migration 004: Fix Authentication Column Constraints
-- Make authentication columns NOT NULL as required by the system

-- Step 1: Update any existing NULL values (shouldn't be any, but safety first)
UPDATE user_information 
SET email_id = 'unknown@example.com' 
WHERE email_id IS NULL;

UPDATE user_information 
SET pin_hash = 'placeholder_hash' 
WHERE pin_hash IS NULL;

-- For country_id, set to a default country (we'll use the first available country)
UPDATE user_information 
SET country_id = (SELECT id FROM country LIMIT 1)
WHERE country_id IS NULL;

-- Step 2: Add NOT NULL constraints
ALTER TABLE user_information 
ALTER COLUMN email_id SET NOT NULL;

ALTER TABLE user_information 
ALTER COLUMN pin_hash SET NOT NULL;

ALTER TABLE user_information 
ALTER COLUMN country_id SET NOT NULL;

-- Step 3: Ensure the foreign key constraint exists
ALTER TABLE user_information 
DROP CONSTRAINT IF EXISTS fk_user_country;

ALTER TABLE user_information 
ADD CONSTRAINT fk_user_country 
FOREIGN KEY (country_id) REFERENCES country(id) ON DELETE RESTRICT;

-- Step 4: Ensure unique constraint on email_id exists
ALTER TABLE user_information 
DROP CONSTRAINT IF EXISTS uq_user_email;

ALTER TABLE user_information 
ADD CONSTRAINT uq_user_email 
UNIQUE (email_id);

-- Step 5: Add indexes for performance
CREATE INDEX IF NOT EXISTS idx_user_email 
ON user_information(email_id);

CREATE INDEX IF NOT EXISTS idx_user_country 
ON user_information(country_id);

-- Verification query
SELECT 
    column_name, 
    is_nullable, 
    data_type 
FROM information_schema.columns 
WHERE table_name = 'user_information' 
    AND column_name IN ('email_id', 'pin_hash', 'country_id')
ORDER BY column_name; 