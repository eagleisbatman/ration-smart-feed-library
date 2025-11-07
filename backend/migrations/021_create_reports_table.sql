-- Migration: Create reports table for storing PDF reports and JSON results
-- Date: 2024-01-XX

-- Create reports table
CREATE TABLE IF NOT EXISTS reports (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    report_id VARCHAR(50) NOT NULL UNIQUE,
    report_type VARCHAR(10) NOT NULL CHECK (report_type IN ('rec', 'eval')),
    user_id UUID NOT NULL REFERENCES user_information(id),
    bucket_url TEXT,
    json_result JSONB,
    saved_to_bucket BOOLEAN DEFAULT FALSE,
    report BYTEA,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create indexes for better performance
CREATE INDEX IF NOT EXISTS idx_reports_report_id ON reports(report_id);
CREATE INDEX IF NOT EXISTS idx_reports_user_id ON reports(user_id);
CREATE INDEX IF NOT EXISTS idx_reports_report_type ON reports(report_type);
CREATE INDEX IF NOT EXISTS idx_reports_created_at ON reports(created_at);

-- Add comments for documentation
COMMENT ON TABLE reports IS 'Stores PDF reports and JSON results for diet recommendations and evaluations';
COMMENT ON COLUMN reports.id IS 'Primary key UUID';
COMMENT ON COLUMN reports.report_id IS 'Unique report identifier in format rec-xxxxxx or eval-xxxxxx';
COMMENT ON COLUMN reports.report_type IS 'Type of report: rec (recommendation) or eval (evaluation)';
COMMENT ON COLUMN reports.user_id IS 'Foreign key to user_information table';
COMMENT ON COLUMN reports.bucket_url IS 'URL of PDF report stored in AWS S3 bucket';
COMMENT ON COLUMN reports.json_result IS 'Complete API response JSON data';
COMMENT ON COLUMN reports.saved_to_bucket IS 'Boolean flag indicating if PDF was successfully saved to AWS bucket';
COMMENT ON COLUMN reports.report IS 'Binary PDF file data';
COMMENT ON COLUMN reports.created_at IS 'Timestamp when report was created';
COMMENT ON COLUMN reports.updated_at IS 'Timestamp when report was last updated';
