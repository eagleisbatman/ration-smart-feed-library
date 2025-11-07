-- Migration 023: Create user feedback table
-- This migration creates the user_feedback table to store user feedback
-- for the mobile application with star ratings and text feedback

-- Create user_feedback table
CREATE TABLE user_feedback (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES user_information(id) ON DELETE CASCADE,
    overall_rating INTEGER NOT NULL CHECK (overall_rating >= 1 AND overall_rating <= 5),
    text_feedback TEXT,
    feedback_type VARCHAR(50) DEFAULT 'General',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create indexes for better performance
CREATE INDEX idx_user_feedback_user_id ON user_feedback(user_id);
CREATE INDEX idx_user_feedback_created_at ON user_feedback(created_at);
CREATE INDEX idx_user_feedback_feedback_type ON user_feedback(feedback_type);
CREATE INDEX idx_user_feedback_rating ON user_feedback(overall_rating);

-- Add comments to document the table and columns
COMMENT ON TABLE user_feedback IS 'Stores user feedback for the mobile application';
COMMENT ON COLUMN user_feedback.id IS 'Unique identifier for the feedback entry';
COMMENT ON COLUMN user_feedback.user_id IS 'Reference to the user who submitted the feedback';
COMMENT ON COLUMN user_feedback.overall_rating IS 'Star rating from 1 to 5 representing overall app experience';
COMMENT ON COLUMN user_feedback.text_feedback IS 'Optional text feedback with maximum 1000 characters';
COMMENT ON COLUMN user_feedback.feedback_type IS 'Type of feedback: General, Bug, or Feature Request';
COMMENT ON COLUMN user_feedback.created_at IS 'Timestamp when feedback was submitted';
COMMENT ON COLUMN user_feedback.updated_at IS 'Timestamp when feedback was last updated';

-- Create a trigger to automatically update the updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_user_feedback_updated_at 
    BEFORE UPDATE ON user_feedback 
    FOR EACH ROW 
    EXECUTE FUNCTION update_updated_at_column();
