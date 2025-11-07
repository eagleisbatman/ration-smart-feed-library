-- Migration: Make overall_rating nullable in user_feedback table
-- Date: 2025-09-27
-- Description: Allow overall_rating to be NULL to support feedback submissions with only feedback_type

-- Make overall_rating column nullable
ALTER TABLE user_feedback ALTER COLUMN overall_rating DROP NOT NULL;

-- Update any existing records with NULL overall_rating to have a default value if needed
-- (This is optional - you might want to keep NULL values as they are)
-- UPDATE user_feedback SET overall_rating = 3 WHERE overall_rating IS NULL;
