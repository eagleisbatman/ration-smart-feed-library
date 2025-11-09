-- Database Sync Verification Script
-- Run this to verify your database is in sync with the latest code

-- Check 1: Verify feed_translations table exists (from migration 001)
SELECT EXISTS (
    SELECT FROM information_schema.tables 
    WHERE table_schema = 'public' 
    AND table_name = 'feed_translations'
) AS feed_translations_exists;

-- Check 2: Verify country_languages table exists (from migration 001)
SELECT EXISTS (
    SELECT FROM information_schema.tables 
    WHERE table_schema = 'public' 
    AND table_name = 'country_languages'
) AS country_languages_exists;

-- Check 3: Verify multi-tenant tables exist (from migration 033)
SELECT EXISTS (
    SELECT FROM information_schema.tables 
    WHERE table_schema = 'public' 
    AND table_name = 'organizations'
) AS organizations_exists;

SELECT EXISTS (
    SELECT FROM information_schema.tables 
    WHERE table_schema = 'public' 
    AND table_name = 'api_keys'
) AS api_keys_exists;

SELECT EXISTS (
    SELECT FROM information_schema.tables 
    WHERE table_schema = 'public' 
    AND table_name = 'api_usage'
) AS api_usage_exists;

-- Check 4: Verify OTP table exists (from migration 034)
SELECT EXISTS (
    SELECT FROM information_schema.tables 
    WHERE table_schema = 'public' 
    AND table_name = 'otp_codes'
) AS otp_codes_exists;

-- Check 5: Verify superadmin columns exist (from migration 034)
SELECT EXISTS (
    SELECT FROM information_schema.columns 
    WHERE table_name = 'users' AND column_name = 'is_superadmin'
) AS is_superadmin_column_exists;

SELECT EXISTS (
    SELECT FROM information_schema.columns 
    WHERE table_name = 'users' AND column_name = 'country_admin_country_id'
) AS country_admin_column_exists;

SELECT EXISTS (
    SELECT FROM information_schema.columns 
    WHERE table_name = 'users' AND column_name = 'organization_admin_org_id'
) AS org_admin_column_exists;

-- Check 6: Verify feed_regional_variations table exists (from migration 035)
SELECT EXISTS (
    SELECT FROM information_schema.tables 
    WHERE table_schema = 'public' 
    AND table_name = 'feed_regional_variations'
) AS feed_regional_variations_exists;

-- Check 7: Verify feed data exists
SELECT COUNT(*) as ethiopia_feeds_count FROM feeds WHERE fd_country_name = 'Ethiopia';
SELECT COUNT(*) as vietnam_feeds_count FROM feeds WHERE fd_country_name = 'Vietnam';

-- Summary query - Run this to get all checks at once
SELECT 
    (SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'feed_translations')) AS feed_translations,
    (SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'country_languages')) AS country_languages,
    (SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'organizations')) AS organizations,
    (SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'api_keys')) AS api_keys,
    (SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'api_usage')) AS api_usage,
    (SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'otp_codes')) AS otp_codes,
    (SELECT EXISTS (SELECT FROM information_schema.columns WHERE table_name = 'users' AND column_name = 'is_superadmin')) AS superadmin_column,
    (SELECT EXISTS (SELECT FROM information_schema.columns WHERE table_name = 'users' AND column_name = 'country_admin_country_id')) AS country_admin_column,
    (SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'feed_regional_variations')) AS feed_regional_variations,
    (SELECT COUNT(*) FROM feeds WHERE fd_country_name = 'Ethiopia') AS ethiopia_feeds,
    (SELECT COUNT(*) FROM feeds WHERE fd_country_name = 'Vietnam') AS vietnam_feeds;

