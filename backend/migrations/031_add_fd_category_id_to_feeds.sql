-- Migration: Add fd_category_id column to feeds table
-- Date: 2024-09-27
-- Description: Add foreign key reference to feed_categories table for better data integrity

-- Add fd_category_id column to feeds table
ALTER TABLE feeds 
ADD COLUMN fd_category_id UUID;

-- Add foreign key constraint to feed_categories table
ALTER TABLE feeds 
ADD CONSTRAINT fk_feeds_fd_category_id 
FOREIGN KEY (fd_category_id) REFERENCES feed_categories(id);

-- Add index for better query performance
CREATE INDEX idx_feeds_fd_category_id ON feeds(fd_category_id);

-- Add comment to document the column purpose
COMMENT ON COLUMN feeds.fd_category_id IS 'Foreign key reference to feed_categories.id for data integrity validation';
