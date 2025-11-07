-- Migration: Create diet_reports table
-- Description: Table to store PDF diet recommendation reports

CREATE TABLE IF NOT EXISTS diet_reports (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES user_information(id) ON DELETE CASCADE,
    case_id VARCHAR(20) NOT NULL,
    report_name VARCHAR(255) NOT NULL,
    file_name VARCHAR(255) NOT NULL,
    pdf_data BYTEA NOT NULL,
    file_size INTEGER NOT NULL,
    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Create index on case_id for faster lookups
CREATE INDEX IF NOT EXISTS idx_diet_reports_case_id ON diet_reports(case_id);

-- Create index on user_id for faster user-specific queries
CREATE INDEX IF NOT EXISTS idx_diet_reports_user_id ON diet_reports(user_id);

-- Create index on created_at for chronological queries
CREATE INDEX IF NOT EXISTS idx_diet_reports_created_at ON diet_reports(created_at);

-- Add comment to table
COMMENT ON TABLE diet_reports IS 'Stores PDF diet recommendation reports generated for users';
COMMENT ON COLUMN diet_reports.id IS 'Primary key - UUID';
COMMENT ON COLUMN diet_reports.user_id IS 'Foreign key to user_information table';
COMMENT ON COLUMN diet_reports.case_id IS 'Case identifier (e.g., abc-1234)';
COMMENT ON COLUMN diet_reports.report_name IS 'Human-readable report name';
COMMENT ON COLUMN diet_reports.file_name IS 'Original filename of the PDF';
COMMENT ON COLUMN diet_reports.pdf_data IS 'The actual PDF file as binary data';
COMMENT ON COLUMN diet_reports.file_size IS 'Size of the PDF file in bytes';
COMMENT ON COLUMN diet_reports.created_at IS 'Timestamp when report was created';
COMMENT ON COLUMN diet_reports.updated_at IS 'Timestamp when report was last updated';
