# Quick Deployment Reference

## 🚀 Railway Deployment Summary

### 1. Backend API (`ration-smart-feed-library/backend`)

**Railway Configuration:**
- Root Directory: `backend/`
- Build: Dockerfile (auto-detected)
- Start: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
- Database: Add PostgreSQL service

**Required Environment Variables:**
```
DATABASE_URL=<railway-postgres-url>
CORS_ORIGINS=https://admin-production.up.railway.app
ENVIRONMENT=production
SUPABASE_URL=https://xxxxx.supabase.co
SUPABASE_ANON_KEY=<supabase-anon-key>
```

**Post-Deploy:**
```bash
railway connect postgres
python scripts/run_migrations.py
```

---

### 2. Frontend Admin (`ration-smart-feed-library/admin`)

**Railway Configuration:**
- Root Directory: `admin/`
- Build: Nixpacks (auto-detected)
- Start: `npm start`
- Node Version: 18+

**Required Environment Variables:**
```
NEXT_PUBLIC_API_URL=https://backend-production.up.railway.app
NODE_ENV=production
```

---

### 3. MCP Server (`ration-smart-mcp-server`)

**Railway Configuration:**
- Root Directory: `.` (repo root)
- Build: Nixpacks (auto-detected)
- Start: `npm start`
- Node Version: 18+

**Required Environment Variables:**
```
FEED_API_BASE_URL=https://backend-production.up.railway.app
PORT=<auto-set-by-railway>
```

---

## 🔵 Supabase Setup Summary

### Required Steps:

1. **Create Project**
   - Go to supabase.com
   - New Project → Name: `ration-smart-feed`
   - Choose region
   - Set database password

2. **Configure Authentication**
   - Dashboard → Authentication → Providers
   - Enable Email provider
   - Configure email templates (optional)

3. **Get API Keys**
   - Settings → API
   - Copy: Project URL → `SUPABASE_URL`
   - Copy: anon/public key → `SUPABASE_ANON_KEY`

4. **Set Redirect URLs**
   - Authentication → URL Configuration
   - Add: `https://admin-production.up.railway.app`

**Note:** Supabase is ONLY used for OTP email delivery. All data is stored in Railway PostgreSQL.

---

## ✅ Deployment Checklist

### Backend
- [ ] Railway project created
- [ ] PostgreSQL service added
- [ ] Environment variables set
- [ ] Deployed successfully
- [ ] Migrations run
- [ ] `/docs` endpoint accessible

### Frontend
- [ ] Railway project created
- [ ] Environment variables set
- [ ] Deployed successfully
- [ ] Login page accessible

### MCP Server
- [ ] Railway project created
- [ ] Environment variables set
- [ ] Deployed successfully
- [ ] `/health` endpoint accessible

### Supabase
- [ ] Project created
- [ ] Email auth enabled
- [ ] API keys copied
- [ ] Redirect URLs configured
- [ ] Test OTP sent

---

**See `DEPLOYMENT_GUIDE.md` for detailed step-by-step instructions.**

