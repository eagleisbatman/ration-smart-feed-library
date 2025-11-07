-- Migration 026: Add save_report column to reports table
-- Date: 2025-08-28

-- Add save_report column with default value False
ALTER TABLE reports 
ADD COLUMN save_report BOOLEAN DEFAULT FALSE NOT NULL;

-- Add comment to document the column purpose
COMMENT ON COLUMN reports.save_report IS 'Flag to indicate if user has explicitly saved the report (set by /save-report/ API)';
