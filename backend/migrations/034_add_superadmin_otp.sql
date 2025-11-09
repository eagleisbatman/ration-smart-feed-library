-- Migration: Add Superadmin, Country Admin, and OTP Support
-- Description: Add superadmin system, country admin assignment, and OTP authentication
-- Date: 2025-01-XX

-- 1. Add superadmin and country admin columns to user_information table
ALTER TABLE user_information ADD COLUMN IF NOT EXISTS is_superadmin BOOLEAN DEFAULT FALSE;
ALTER TABLE user_information ADD COLUMN IF NOT EXISTS country_admin_country_id UUID REFERENCES countries(id);

CREATE INDEX IF NOT EXISTS idx_users_superadmin ON user_information(is_superadmin) WHERE is_superadmin = TRUE;
CREATE INDEX IF NOT EXISTS idx_users_country_admin ON user_information(country_admin_country_id) WHERE country_admin_country_id IS NOT NULL;

-- 2. Create OTP codes table for authentication
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

CREATE INDEX idx_otp_codes_email ON otp_codes(email_id);
CREATE INDEX idx_otp_codes_expires ON otp_codes(expires_at);
CREATE INDEX idx_otp_codes_unused ON otp_codes(email_id, purpose, is_used, expires_at) WHERE is_used = FALSE;

-- 3. Remove pin_hash column (replaced by OTP)
-- Note: Keep pin_hash for backward compatibility during migration, but mark as deprecated
-- ALTER TABLE user_information DROP COLUMN pin_hash; -- Uncomment after migration period

-- 4. Add organization admin flag (for organization-level admins)
ALTER TABLE user_information ADD COLUMN IF NOT EXISTS organization_admin_org_id UUID REFERENCES organizations(id);

CREATE INDEX IF NOT EXISTS idx_users_org_admin ON user_information(organization_admin_org_id) WHERE organization_admin_org_id IS NOT NULL;

-- 5. Comments for documentation
COMMENT ON COLUMN user_information.is_superadmin IS 'Superadmin can create country admins and manage all countries';
COMMENT ON COLUMN user_information.country_admin_country_id IS 'Country-level admin assigned to specific country';
COMMENT ON COLUMN user_information.organization_admin_org_id IS 'Organization-level admin for API key management';
COMMENT ON TABLE otp_codes IS 'One-time passwords for email-based authentication';

