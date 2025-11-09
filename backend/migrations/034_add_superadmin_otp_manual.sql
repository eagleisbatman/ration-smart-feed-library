-- Manual Migration Required: Add columns to user_information table
-- This requires database owner permissions
-- Run these commands as the database owner (postgres user) or through Railway's database interface

-- Add superadmin and country admin columns
ALTER TABLE user_information ADD COLUMN IF NOT EXISTS is_superadmin BOOLEAN DEFAULT FALSE;
ALTER TABLE user_information ADD COLUMN IF NOT EXISTS country_admin_country_id UUID REFERENCES country(id);
ALTER TABLE user_information ADD COLUMN IF NOT EXISTS organization_admin_org_id UUID REFERENCES organizations(id);

-- Create indexes
CREATE INDEX IF NOT EXISTS idx_users_superadmin ON user_information(is_superadmin) WHERE is_superadmin = TRUE;
CREATE INDEX IF NOT EXISTS idx_users_country_admin ON user_information(country_admin_country_id) WHERE country_admin_country_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_users_org_admin ON user_information(organization_admin_org_id) WHERE organization_admin_org_id IS NOT NULL;

-- Add comments
COMMENT ON COLUMN user_information.is_superadmin IS 'Superadmin can create country admins and manage all countries';
COMMENT ON COLUMN user_information.country_admin_country_id IS 'Country-level admin assigned to specific country';
COMMENT ON COLUMN user_information.organization_admin_org_id IS 'Organization-level admin for API key management';

