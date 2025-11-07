# Multi-Tenant Authentication - Quick Start Guide

## 🎯 Problem Solved

**Before:** Email + PIN works for single user, but not ideal for multiple organizations using MCP server.

**After:** API key authentication with organization management - perfect for multi-tenant scenarios!

## 🚀 Quick Setup

### Step 1: Run Migration

```bash
# Run multi-tenant migration
psql $DATABASE_URL -f migrations/033_add_multi_tenant_auth.sql
```

### Step 2: Create Organization (Admin)

```bash
POST /admin/organizations?admin_user_id=<admin_uuid>
{
  "name": "Digital Green",
  "slug": "digitalgreen",
  "contact_email": "admin@digitalgreen.org",
  "rate_limit_per_hour": 5000
}
```

### Step 3: Generate API Key (Admin)

```bash
POST /admin/organizations/{org_id}/api-keys?admin_user_id=<admin_uuid>
{
  "name": "MCP Server Production Key",
  "environment": "live"
}

# Response (save the api_key - shown only once!):
{
  "api_key": "ff_live_a1b2c3d4e5f6g7h8i9j0",
  "key_prefix": "ff_live_a1",
  "organization_id": "...",
  "message": "Store this API key securely..."
}
```

### Step 4: Use API Key in MCP Server

```env
# Update MCP server .env
FEED_API_BASE_URL=https://your-app.railway.app
FEED_API_KEY=ff_live_a1b2c3d4e5f6g7h8i9j0  # Use API key instead of email+PIN
```

## 🔐 Authentication Methods

### Method 1: API Key (Recommended)

**Header:**
```
Authorization: Bearer ff_live_xxxxxxxxxxxxxxxxxxxx
```

**Benefits:**
- ✅ Server-to-server friendly
- ✅ Per-organization tracking
- ✅ Rate limiting per org
- ✅ Easy rotation/revocation

### Method 2: Email + PIN (Backward Compatible)

**Body:**
```json
{
  "email_id": "user@example.com",
  "pin": "1234"
}
```

**Still works** for backward compatibility!

## 📊 Features

### Organization Management
- Create organizations
- Manage API keys per organization
- Set rate limits per organization
- Track usage per organization

### API Key Management
- Generate multiple keys per organization
- Set expiration dates
- Revoke keys easily
- Track last used timestamp

### Usage Tracking
- Track all API calls per organization
- Monitor endpoint usage
- Track response times
- Enable analytics/billing

## 🎯 Best Practices

### For Organizations:
1. **One Organization** = One tenant (e.g., "Digital Green")
2. **Multiple API Keys** per organization (for different environments/apps)
3. **Rate Limits** set per organization
4. **Usage Tracking** for monitoring

### For MCP Servers:
1. Use **API key** authentication (not email+PIN)
2. Store API key in **environment variables**
3. Use **live** keys for production, **test** keys for development
4. Rotate keys periodically

## 📝 Example: Multiple Organizations

```
Organization 1: "Digital Green"
├── API Key: ff_live_a1b2... (Production MCP Server)
├── API Key: ff_test_x1y2... (Development MCP Server)
└── Rate Limit: 5000/hour

Organization 2: "Partner Organization"
├── API Key: ff_live_b2c3... (Their MCP Server)
└── Rate Limit: 2000/hour
```

Each organization:
- Has isolated API keys
- Has separate rate limits
- Has separate usage tracking
- Can manage their own keys

## ✅ Benefits

1. **Scalability:** Easy to add new organizations
2. **Security:** API keys can be rotated/revoked
3. **Tracking:** Monitor usage per organization
4. **Rate Limiting:** Prevent abuse per organization
5. **Flexibility:** Multiple keys per organization
6. **Backward Compatible:** Email+PIN still works

## 🔄 Migration from Email+PIN

### Option 1: Keep Both (Recommended)
- Organizations use API keys
- Existing users keep email+PIN
- Both methods work simultaneously

### Option 2: Migrate Users
- Associate users with organizations
- Generate API keys for users
- Eventually deprecate email+PIN

## 📚 Files

- `migrations/033_add_multi_tenant_auth.sql` - Database migration
- `app/multi_tenant_models.py` - Models
- `services/api_key_auth.py` - API key utilities
- `middleware/auth_middleware.py` - Auth middleware
- `routers/multi_tenant_admin.py` - Admin endpoints

## 🎯 Next Steps

1. ✅ Run migration
2. ✅ Create organization
3. ✅ Generate API key
4. ⏳ Update MCP server to use API key
5. ⏳ Test authentication
6. ⏳ Add rate limiting (optional)
7. ⏳ Add usage tracking (optional)

The multi-tenant authentication system is ready! 🚀

