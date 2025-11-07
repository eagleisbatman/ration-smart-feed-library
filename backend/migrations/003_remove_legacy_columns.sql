-- Migration 003: Remove legacy columns from user_information table
-- These columns are no longer needed in the new authentication system

-- Remove legacy geographic hierarchy columns
ALTER TABLE user_information DROP COLUMN IF EXISTS phone_number;
ALTER TABLE user_information DROP COLUMN IF EXISTS country;
ALTER TABLE user_information DROP COLUMN IF EXISTS region;
ALTER TABLE user_information DROP COLUMN IF EXISTS zone;
ALTER TABLE user_information DROP COLUMN IF EXISTS woreda;
ALTER TABLE user_information DROP COLUMN IF EXISTS kebele;
ALTER TABLE user_information DROP COLUMN IF EXISTS language;

-- Verify the table structure after cleanup
-- The table should now only have: id, name, email_id, pin_hash, country_id, created_at, updated_at 