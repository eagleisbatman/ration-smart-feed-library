-- Migration: Make fd_code nullable in feeds table
-- Date: 2025-09-08
-- Description: Allow fd_code to be null to support bulk uploads without feed codes

-- Make fd_code column nullable
ALTER TABLE feeds ALTER COLUMN fd_code DROP NOT NULL;

-- Add comment to document the change
COMMENT ON COLUMN feeds.fd_code IS 'Feed code (format: country_code-number). Can be null for bulk uploaded feeds without specific codes.';
