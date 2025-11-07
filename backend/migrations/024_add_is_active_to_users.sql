-- Migration: Add is_active field to user_information table
-- This allows admins to enable/disable users without deleting them

-- Add is_active column to user_information table
ALTER TABLE user_information 
ADD COLUMN is_active BOOLEAN NOT NULL DEFAULT TRUE;

-- Add index for better query performance on is_active
CREATE INDEX idx_user_information_is_active ON user_information(is_active);

-- Add comment to document the column
COMMENT ON COLUMN user_information.is_active IS 'Flag to indicate if user account is active (enabled/disabled by admin)';

-- Update existing users to be active by default
UPDATE user_information SET is_active = TRUE WHERE is_active IS NULL;
