# Database Sync Verification Guide

## ✅ What Should Already Be in Your Database

Based on your previous setup, these should already exist:

### Core Tables (Migration 001)
- ✅ `feeds` - Feed data table
- ✅ `feed_translations` - Multi-language feed names/descriptions
- ✅ `country_languages` - Supported languages per country
- ✅ `countries` - Country data
- ✅ `users` (or `user_information`) - User accounts
- ✅ Feed data for Ethiopia and Vietnam

### Multi-Tenant Tables (Migration 033)
- ✅ `organizations` - Organization/tenant table
- ✅ `api_keys` - API key management
- ✅ `api_usage` - API usage tracking

---

## ⚠️ New Migrations That May Need to Be Run

### Migration 034: Superadmin & OTP Support
**Status:** May need to run  
**What it adds:**
- `otp_codes` table (for OTP authentication)
- `is_superadmin` column to `users` table
- `country_admin_country_id` column to `users` table
- `organization_admin_org_id` column to `users` table

**To check if needed:**
```sql
SELECT EXISTS (
    SELECT FROM information_schema.tables 
    WHERE table_name = 'otp_codes'
) AS needs_migration_034;
```

**To run:**
```bash
railway connect postgres
# Then run: backend/migrations/034_add_superadmin_otp.sql
```

### Migration 035: Feed Regional Variations
**Status:** Optional (only if you need regional variations)  
**What it adds:**
- `feed_regional_variations` table (for storing location-specific feed data)

**To check if needed:**
```sql
SELECT EXISTS (
    SELECT FROM information_schema.tables 
    WHERE table_name = 'feed_regional_variations'
) AS needs_migration_035;
```

**To run:**
```bash
railway connect postgres
# Then run: backend/migrations/035_add_feed_regional_variations.sql
```

---

## 🔍 Quick Verification Steps

### Option 1: Use Railway Dashboard
1. Go to Railway → Your Backend Project → PostgreSQL Service
2. Click "Query" tab
3. Run the verification script: `scripts/verify_database_sync.sql`

### Option 2: Use Railway CLI
```bash
# Install Railway CLI if not already installed
npm i -g @railway/cli

# Login
railway login

# Link to your backend project
cd ration-smart-feed-library/backend
railway link

# Connect to PostgreSQL
railway connect postgres

# Run verification queries
psql < scripts/verify_database_sync.sql
```

### Option 3: Run Python Script
```bash
cd ration-smart-feed-library/backend
python scripts/verify_database.py  # (if we create this)
```

---

## 📋 Expected Results

If your database is fully synced, you should see:

| Table/Column | Should Exist | Purpose |
|--------------|--------------|---------|
| `feed_translations` | ✅ Yes | Multi-language feed names |
| `country_languages` | ✅ Yes | Supported languages per country |
| `organizations` | ✅ Yes | Multi-tenant organizations |
| `api_keys` | ✅ Yes | API key management |
| `api_usage` | ✅ Yes | Rate limiting tracking |
| `otp_codes` | ⚠️ Check | OTP authentication |
| `is_superadmin` column | ⚠️ Check | Superadmin role |
| `country_admin_country_id` column | ⚠️ Check | Country admin assignment |
| `feed_regional_variations` | ⚠️ Optional | Regional feed variations |
| Ethiopia feeds | ✅ Yes | Your imported data |
| Vietnam feeds | ✅ Yes | Your imported data |

---

## 🚀 Running Missing Migrations

If verification shows missing tables/columns:

### Step 1: Connect to Database
```bash
railway connect postgres
```

### Step 2: Run Missing Migrations
```sql
-- Copy and paste the SQL from:
-- backend/migrations/034_add_superadmin_otp.sql
-- backend/migrations/035_add_feed_regional_variations.sql
```

### Step 3: Verify Again
Run the verification script again to confirm.

---

## 📝 Notes

- **Migration 034 is REQUIRED** for OTP authentication and superadmin features
- **Migration 035 is OPTIONAL** - only needed if you want regional feed variations
- Your existing feed data (Ethiopia & Vietnam) will NOT be affected
- All migrations use `IF NOT EXISTS` - safe to run multiple times
- Migrations are backward compatible

---

## ✅ Quick Check Command

Run this single query to see what's missing:

```sql
SELECT 
    'feed_translations' AS table_name,
    EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'feed_translations') AS exists
UNION ALL
SELECT 'country_languages', EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'country_languages')
UNION ALL
SELECT 'organizations', EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'organizations')
UNION ALL
SELECT 'api_keys', EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'api_keys')
UNION ALL
SELECT 'api_usage', EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'api_usage')
UNION ALL
SELECT 'otp_codes', EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'otp_codes')
UNION ALL
SELECT 'feed_regional_variations', EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'feed_regional_variations');
```

All should return `exists = true` if database is fully synced.

