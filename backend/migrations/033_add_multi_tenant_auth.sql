-- Migration: Add Multi-Tenant Authentication Support
-- Description: Add organizations, API keys, and usage tracking tables
-- Date: 2025-01-XX

-- 1. Organizations table
CREATE TABLE IF NOT EXISTS organizations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL,
    slug VARCHAR(100) UNIQUE NOT NULL,
    contact_email VARCHAR(255),
    is_active BOOLEAN DEFAULT TRUE,
    rate_limit_per_hour INTEGER DEFAULT 1000,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- 2. API Keys table
CREATE TABLE IF NOT EXISTS api_keys (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL,
    key_hash VARCHAR(255) NOT NULL UNIQUE,
    key_prefix VARCHAR(20) NOT NULL,
    name VARCHAR(255),
    is_active BOOLEAN DEFAULT TRUE,
    last_used_at TIMESTAMP,
    expires_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW(),
    created_by UUID REFERENCES user_information(id),
    CONSTRAINT fk_api_keys_org FOREIGN KEY (organization_id) REFERENCES organizations(id) ON DELETE CASCADE
);

-- 3. API Usage tracking table
CREATE TABLE IF NOT EXISTS api_usage (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL,
    api_key_id UUID REFERENCES api_keys(id),
    endpoint VARCHAR(255) NOT NULL,
    method VARCHAR(10) NOT NULL,
    response_status INTEGER,
    response_time_ms INTEGER,
    created_at TIMESTAMP DEFAULT NOW(),
    CONSTRAINT fk_api_usage_org FOREIGN KEY (organization_id) REFERENCES organizations(id) ON DELETE CASCADE
);

-- 4. Indexes for performance
CREATE INDEX IF NOT EXISTS idx_api_keys_org ON api_keys(organization_id);
CREATE INDEX IF NOT EXISTS idx_api_keys_hash ON api_keys(key_hash);
CREATE INDEX IF NOT EXISTS idx_api_keys_active ON api_keys(is_active) WHERE is_active = TRUE;
CREATE INDEX IF NOT EXISTS idx_api_usage_org ON api_usage(organization_id, created_at);
CREATE INDEX IF NOT EXISTS idx_api_usage_key ON api_usage(api_key_id, created_at);
CREATE INDEX IF NOT EXISTS idx_api_usage_endpoint ON api_usage(endpoint, created_at);
CREATE INDEX IF NOT EXISTS idx_organizations_slug ON organizations(slug);
CREATE INDEX IF NOT EXISTS idx_organizations_active ON organizations(is_active) WHERE is_active = TRUE;

-- 5. Add organization_id to user_information (optional, for admin users)
-- Check if column exists first (PostgreSQL 9.6+)
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'user_information' AND column_name = 'organization_id'
    ) THEN
        ALTER TABLE user_information ADD COLUMN organization_id UUID;
        ALTER TABLE user_information 
          ADD CONSTRAINT fk_user_org FOREIGN KEY (organization_id) REFERENCES organizations(id);
    END IF;
END $$;

CREATE INDEX IF NOT EXISTS idx_user_org ON user_information(organization_id);

-- 6. Create default organization for existing users (optional migration)
-- This creates a default organization and associates existing users
DO $$
DECLARE
    default_org_id UUID;
BEGIN
    -- Create default organization if it doesn't exist
    INSERT INTO organizations (id, name, slug, contact_email, is_active)
    VALUES (
        gen_random_uuid(),
        'Default Organization',
        'default',
        'admin@feedformulation.com',
        TRUE
    )
    ON CONFLICT (slug) DO NOTHING
    RETURNING id INTO default_org_id;
    
    -- If we created a new org, associate existing users (optional - uncomment if needed)
    -- UPDATE user_information SET organization_id = default_org_id WHERE organization_id IS NULL;
END $$;

-- Notes:
-- - Organizations represent tenants/organizations using the API
-- - API keys are hashed for security (like passwords)
-- - Usage tracking enables monitoring and billing
-- - Rate limiting can be implemented per organization
-- - Backward compatible: email+PIN still works

