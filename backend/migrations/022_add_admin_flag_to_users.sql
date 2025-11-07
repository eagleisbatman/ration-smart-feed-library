-- Migration 022: Add admin flag to user_information table
-- This migration adds an is_admin boolean flag to the user_information table
-- to support admin functionality for the feedback system

-- Add is_admin column to user_information table
ALTER TABLE user_information ADD COLUMN is_admin BOOLEAN DEFAULT FALSE;

-- Add comment to document the purpose of this column
COMMENT ON COLUMN user_information.is_admin IS 'Flag to indicate if user has admin privileges for feedback management';

-- Create index for better performance on admin queries
CREATE INDEX idx_user_information_is_admin ON user_information(is_admin);
