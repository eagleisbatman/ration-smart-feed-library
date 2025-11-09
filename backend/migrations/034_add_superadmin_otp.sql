-- Migration: Add Superadmin, Country Admin, and OTP Support
-- Description: Add superadmin system, country admin assignment, and OTP authentication
-- Date: 2025-01-XX
-- Note: This migration requires ALTER TABLE permissions on user_information.
-- If you get permission errors, run as database owner or through Railway's database interface.

-- 1. Add superadmin and country admin columns to user_information table
-- Note: These commands require table owner permissions
DO $$
BEGIN
    -- Add is_superadmin column
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'user_information' AND column_name = 'is_superadmin'
    ) THEN
        ALTER TABLE user_information ADD COLUMN is_superadmin BOOLEAN DEFAULT FALSE;
    END IF;
    
    -- Add country_admin_country_id column
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'user_information' AND column_name = 'country_admin_country_id'
    ) THEN
        ALTER TABLE user_information ADD COLUMN country_admin_country_id UUID REFERENCES country(id);
    END IF;
    
    -- Add organization_admin_org_id column (only if organizations table exists)
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'organizations') THEN
        IF NOT EXISTS (
            SELECT 1 FROM information_schema.columns 
            WHERE table_name = 'user_information' AND column_name = 'organization_admin_org_id'
        ) THEN
            ALTER TABLE user_information ADD COLUMN organization_admin_org_id UUID REFERENCES organizations(id);
        END IF;
    END IF;
END $$;

-- Create indexes (these should work even without table owner)
CREATE INDEX IF NOT EXISTS idx_users_superadmin ON user_information(is_superadmin) WHERE is_superadmin = TRUE;
CREATE INDEX IF NOT EXISTS idx_users_country_admin ON user_information(country_admin_country_id) WHERE country_admin_country_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_users_org_admin ON user_information(organization_admin_org_id) WHERE organization_admin_org_id IS NOT NULL;

-- 2. Create OTP codes table for authentication (already created, but ensure it exists)
CREATE TABLE IF NOT EXISTS otp_codes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email_id VARCHAR(255) NOT NULL,
    otp_code VARCHAR(6) NOT NULL,
    purpose VARCHAR(50) NOT NULL, -- 'login', 'registration', 'password_reset'
    expires_at TIMESTAMP NOT NULL,
    is_used BOOLEAN DEFAULT FALSE,
    attempts INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(email_id, otp_code, purpose, expires_at)
);

CREATE INDEX IF NOT EXISTS idx_otp_codes_email ON otp_codes(email_id);
CREATE INDEX IF NOT EXISTS idx_otp_codes_expires ON otp_codes(expires_at);
CREATE INDEX IF NOT EXISTS idx_otp_codes_unused ON otp_codes(email_id, purpose, is_used, expires_at) WHERE is_used = FALSE;

-- 3. Comments for documentation
COMMENT ON COLUMN user_information.is_superadmin IS 'Superadmin can create country admins and manage all countries';
COMMENT ON COLUMN user_information.country_admin_country_id IS 'Country-level admin assigned to specific country';
COMMENT ON COLUMN user_information.organization_admin_org_id IS 'Organization-level admin for API key management';
COMMENT ON TABLE otp_codes IS 'One-time passwords for email-based authentication';
