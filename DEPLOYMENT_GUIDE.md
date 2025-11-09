# Deployment Guide - Railway & Supabase

## 📊 Quick Overview

| Service | Repository | Root Directory | Database | Builder |
|---------|------------|----------------|----------|---------|
| **Backend API** | `ration-smart-feed-library` | `backend/` | Railway PostgreSQL | Dockerfile |
| **Frontend Admin** | `ration-smart-feed-library` | `admin/` | None | Nixpacks (Next.js) |
| **MCP Server** | `ration-smart-mcp-server` | `.` (root) | None | Nixpacks (Node.js) |
| **OTP Service** | N/A | N/A | Supabase (email only) | Supabase Cloud |

---

## 🚂 Railway Deployment

### Backend API Deployment

| Step | Action | Details | Notes |
|------|--------|---------|-------|
| 1 | Create Railway Project | Go to Railway dashboard → New Project | Name: `ration-smart-backend` |
| 2 | Connect Repository | Connect `ration-smart-feed-library` repo | Select `backend` folder as root |
| 3 | Set Root Directory | Set root to `backend/` | In Railway project settings |
| 4 | Add PostgreSQL Service | Add PostgreSQL database service | Railway will auto-create DB |
| 5 | Set Environment Variables | See "Backend Environment Variables" table below | Copy from `.env.example` |
| 6 | Railway Auto-Detects | Railway detects `railway.json` | Uses Dockerfile build |
| 7 | Build Command | Auto-detected from Dockerfile | `pip install -r requirements.txt` |
| 8 | Start Command | From `railway.json` | `uvicorn app.main:app --host 0.0.0.0 --port $PORT` |
| 9 | Deploy | Railway will auto-deploy on push | Monitor deployment logs |
| 10 | Get Backend URL | Copy Railway-generated URL | Example: `https://backend-production.up.railway.app` |
| 11 | Run Migrations | Use Railway CLI: `railway connect postgres` then `python scripts/run_migrations.py` | Or use Railway dashboard SQL editor |

### Frontend Admin Dashboard Deployment

| Step | Action | Details | Notes |
|------|--------|---------|-------|
| 1 | Create Railway Project | Go to Railway dashboard → New Project | Name: `ration-smart-admin` |
| 2 | Connect Repository | Connect `ration-smart-feed-library` repo | Select `admin` folder as root |
| 3 | Set Root Directory | Set root to `admin/` | In Railway project settings |
| 4 | Set Environment Variables | See "Frontend Environment Variables" table below | Copy from `.env.example` |
| 5 | Railway Auto-Detects | Railway detects Next.js | Uses Nixpacks builder |
| 6 | Build Command | Auto-detected | `npm install && npm run build` |
| 7 | Start Command | From `package.json` | `npm start` (runs `next start`) |
| 8 | Set Node Version | Node.js 18+ | In Railway settings (auto-detected) |
| 9 | Deploy | Railway will auto-deploy on push | Monitor deployment logs |
| 10 | Get Frontend URL | Copy Railway-generated URL | Example: `https://admin-production.up.railway.app` |

### MCP Server Deployment

| Step | Action | Details | Notes |
|------|--------|---------|-------|
| 1 | Create Railway Project | Go to Railway dashboard → New Project | Name: `ration-smart-mcp-server` |
| 2 | Connect Repository | Connect `ration-smart-mcp-server` repo | Root directory is repo root |
| 3 | Set Environment Variables | See "MCP Server Environment Variables" table below | Copy from `.env.example` |
| 4 | Railway Auto-Detects | Railway detects Node.js | Uses Nixpacks builder |
| 5 | Build Command | Auto-detected | `npm install && npm run build` |
| 6 | Start Command | From `railway.json` | `npm start` (runs `node dist/index.js`) |
| 7 | Set Node Version | Node.js 18+ | In Railway settings (auto-detected) |
| 8 | Deploy | Railway will auto-deploy on push | Monitor deployment logs |
| 9 | Get MCP Server URL | Copy Railway-generated URL | Example: `https://mcp-server-production.up.railway.app` |

---

## 🗄️ Database Setup

### PostgreSQL Database (Railway)

| Step | Action | Details | Notes |
|------|--------|---------|-------|
| 1 | Create PostgreSQL Service | Add PostgreSQL in Railway project | Railway auto-creates DB |
| 2 | Get Connection String | Copy PostgreSQL connection URL | Format: `postgresql://user:pass@host:port/db` |
| 3 | Run Migrations | Use Railway CLI or script | See "Migration Steps" below |
| 4 | Verify Tables | Check tables created | Use Railway PostgreSQL dashboard |

### Migration Steps

| Step | Command | Details |
|------|---------|---------|
| 1 | Install Railway CLI | `npm i -g @railway/cli` |
| 2 | Login to Railway | `railway login` |
| 3 | Link to project | `railway link` (in backend directory) |
| 4 | Connect to PostgreSQL | `railway connect postgres` |
| 5 | Run Migrations | `python scripts/run_migrations.py` | Or use Railway dashboard SQL editor |
| 6 | Verify Tables | Check tables: `feeds`, `users`, `organizations`, `api_keys`, `otp_codes` |

---

## 🔐 Environment Variables

### Backend Environment Variables (Railway)

| Variable | Value | Required | Notes |
|----------|-------|----------|-------|
| `POSTGRES_USER` | Auto-set by Railway | ✅ | From PostgreSQL service |
| `POSTGRES_PASSWORD` | Auto-set by Railway | ✅ | From PostgreSQL service |
| `POSTGRES_DB` | Auto-set by Railway | ✅ | From PostgreSQL service |
| `POSTGRES_HOST` | Auto-set by Railway | ✅ | From PostgreSQL service |
| `POSTGRES_PORT` | Auto-set by Railway | ✅ | From PostgreSQL service |
| `DATABASE_URL` | Auto-set by Railway | ✅ | Full connection string |
| `CORS_ORIGINS` | `https://admin-production.up.railway.app` | ✅ | Comma-separated frontend URLs |
| `ENVIRONMENT` | `production` | ✅ | Set to `production` |
| `SUPABASE_URL` | From Supabase dashboard | ✅ | See Supabase setup |
| `SUPABASE_ANON_KEY` | From Supabase dashboard | ✅ | See Supabase setup |
| `SUPABASE_SERVICE_KEY` | From Supabase dashboard | ⚠️ | Optional, for admin operations |
| `SMTP_HOST` | Your SMTP server | ⚠️ | Optional, for email OTP |
| `SMTP_PORT` | `587` or `465` | ⚠️ | If using SMTP |
| `SMTP_USER` | SMTP username | ⚠️ | If using SMTP |
| `SMTP_PASSWORD` | SMTP password | ⚠️ | If using SMTP |
| `SMTP_FROM_EMAIL` | Sender email | ⚠️ | If using SMTP |

### Frontend Environment Variables (Railway)

| Variable | Value | Required | Notes |
|----------|-------|----------|-------|
| `NEXT_PUBLIC_API_URL` | Backend Railway URL | ✅ | `https://backend-production.up.railway.app` |
| `NEXT_PUBLIC_MCP_SERVER_URL` | MCP Server Railway URL | ⚠️ | Optional, if frontend needs MCP |
| `NODE_ENV` | `production` | ✅ | Set automatically by Railway |

### MCP Server Environment Variables (Railway)

| Variable | Value | Required | Notes |
|----------|-------|----------|-------|
| `FEED_API_BASE_URL` | Backend Railway URL | ✅ | `https://backend-production.up.railway.app` |
| `FEED_API_KEY` | Organization API key | ⚠️ | Optional, for default auth |
| `PORT` | Auto-set by Railway | ✅ | Railway sets this automatically |
| `ALLOWED_ORIGINS` | `*` or specific origins | ⚠️ | CORS configuration |

---

## 🔵 Supabase Setup

### Project Creation

| Step | Action | Details | Notes |
|------|--------|---------|-------|
| 1 | Create Supabase Project | Go to supabase.com → New Project | Name: `ration-smart-feed` |
| 2 | Choose Region | Select closest region | For better latency |
| 3 | Set Database Password | Strong password | Save securely |
| 4 | Wait for Setup | ~2 minutes | Supabase creates project |

### OTP Configuration

| Step | Action | Details | Notes |
|------|--------|---------|-------|
| 1 | Go to Authentication | Dashboard → Authentication | Left sidebar |
| 2 | Enable Email Auth | Settings → Auth Providers → Email | Enable email provider |
| 3 | Configure Email Templates | Authentication → Email Templates | Customize OTP email |
| 4 | Set Redirect URLs | Authentication → URL Configuration | Add your frontend URL |
| 5 | Get API Keys | Settings → API | Copy URL and keys |

### Supabase Environment Variables

| Variable | Where to Find | Required | Notes |
|----------|---------------|----------|-------|
| `SUPABASE_URL` | Settings → API → Project URL | ✅ | Format: `https://xxxxx.supabase.co` |
| `SUPABASE_ANON_KEY` | Settings → API → anon/public key | ✅ | Public key (safe for frontend) |
| `SUPABASE_SERVICE_KEY` | Settings → API → service_role key | ⚠️ | Secret key (backend only) |

### Email Configuration (Optional)

| Step | Action | Details | Notes |
|------|--------|---------|-------|
| 1 | Go to Settings | Settings → Auth | Left sidebar |
| 2 | Configure SMTP | Auth → SMTP Settings | Use custom SMTP or Supabase default |
| 3 | Test Email | Send test email | Verify OTP delivery |
| 4 | Set Rate Limits | Auth → Rate Limits | Configure OTP rate limits |

### Database Tables (Not Required)

| Note | Details |
|------|--------|
| ⚠️ | Supabase database is NOT used for feed data |
| ✅ | PostgreSQL on Railway is used for all data |
| ✅ | Supabase is ONLY used for OTP email delivery |
| ✅ | No migrations needed in Supabase |

---

## 📋 Deployment Checklist

### Pre-Deployment

| Task | Status | Notes |
|------|--------|-------|
| [ ] Railway account created | ⬜ | Sign up at railway.app |
| [ ] Supabase account created | ⬜ | Sign up at supabase.com |
| [ ] GitHub repos connected | ⬜ | Connect repositories to Railway |
| [ ] Environment variables prepared | ⬜ | Copy from tables above |
| [ ] Database migrations ready | ⬜ | Verify migration scripts |

### Backend Deployment

| Task | Status | Notes |
|------|--------|-------|
| [ ] Railway project created | ⬜ | Name: `ration-smart-backend` |
| [ ] PostgreSQL service added | ⬜ | Railway auto-creates DB |
| [ ] Environment variables set | ⬜ | See Backend Environment Variables |
| [ ] Root directory set to `backend/` | ⬜ | In Railway settings |
| [ ] Build command configured | ⬜ | `pip install -r requirements.txt` |
| [ ] Start command configured | ⬜ | `uvicorn app.main:app --host 0.0.0.0 --port $PORT` |
| [ ] Deployed successfully | ⬜ | Check deployment logs |
| [ ] Health check passes | ⬜ | Visit `/` endpoint |
| [ ] Database migrations run | ⬜ | Use Railway CLI or script |
| [ ] API docs accessible | ⬜ | Visit `/docs` endpoint |

### Frontend Deployment

| Task | Status | Notes |
|------|--------|-------|
| [ ] Railway project created | ⬜ | Name: `ration-smart-admin` |
| [ ] Root directory set to `admin/` | ⬜ | In Railway settings |
| [ ] Environment variables set | ⬜ | See Frontend Environment Variables |
| [ ] Node version set (18+) | ⬜ | In Railway settings |
| [ ] Build command configured | ⬜ | `npm install && npm run build` |
| [ ] Start command configured | ⬜ | `npm start` |
| [ ] Deployed successfully | ⬜ | Check deployment logs |
| [ ] Frontend accessible | ⬜ | Visit Railway URL |
| [ ] API connection works | ⬜ | Test login functionality |

### MCP Server Deployment

| Task | Status | Notes |
|------|--------|-------|
| [ ] Railway project created | ⬜ | Name: `ration-smart-mcp-server` |
| [ ] Environment variables set | ⬜ | See MCP Server Environment Variables |
| [ ] Node version set (18+) | ⬜ | In Railway settings |
| [ ] Build command configured | ⬜ | `npm install && npm run build` |
| [ ] Start command configured | ⬜ | `npm start` |
| [ ] Deployed successfully | ⬜ | Check deployment logs |
| [ ] Health check passes | ⬜ | Visit `/health` endpoint |
| [ ] MCP endpoint accessible | ⬜ | Test `/mcp` endpoint |

### Supabase Configuration

| Task | Status | Notes |
|------|--------|-------|
| [ ] Project created | ⬜ | Name: `ration-smart-feed` |
| [ ] Email auth enabled | ⬜ | Authentication → Email Provider |
| [ ] API keys copied | ⬜ | Settings → API |
| [ ] Environment variables set | ⬜ | In Railway backend project |
| [ ] Email templates configured | ⬜ | Optional customization |
| [ ] Redirect URLs set | ⬜ | Add frontend URL |
| [ ] Test OTP sent | ⬜ | Verify email delivery |

### Post-Deployment

| Task | Status | Notes |
|------|--------|-------|
| [ ] All services running | ⬜ | Check Railway dashboard |
| [ ] Database migrations complete | ⬜ | Verify tables exist |
| [ ] Frontend connects to backend | ⬜ | Test login flow |
| [ ] OTP emails working | ⬜ | Test registration/login |
| [ ] API keys can be created | ⬜ | Test organization flow |
| [ ] MCP server accessible | ⬜ | Test MCP endpoint |
| [ ] CORS configured correctly | ⬜ | No CORS errors in browser |
| [ ] Rate limiting working | ⬜ | Test API rate limits |
| [ ] Error handling working | ⬜ | Test error scenarios |

---

## 🔧 Railway CLI Commands (Optional)

| Command | Purpose | Notes |
|---------|---------|-------|
| `railway login` | Login to Railway | First time setup |
| `railway init` | Initialize Railway project | In project directory |
| `railway link` | Link to existing project | Connect local to Railway |
| `railway up` | Deploy to Railway | Manual deployment |
| `railway logs` | View deployment logs | Debugging |
| `railway connect postgres` | Connect to PostgreSQL | Run migrations |
| `railway variables` | Manage environment variables | CLI alternative to dashboard |

---

## 📝 Quick Reference URLs

| Service | URL Pattern | Example |
|---------|-------------|---------|
| Backend API | `https://[project-name].up.railway.app` | `https://backend-production.up.railway.app` |
| Frontend Admin | `https://[project-name].up.railway.app` | `https://admin-production.up.railway.app` |
| MCP Server | `https://[project-name].up.railway.app` | `https://mcp-server-production.up.railway.app` |
| Supabase Dashboard | `https://app.supabase.com/project/[project-id]` | Dashboard URL |
| Backend API Docs | `https://[backend-url]/docs` | Swagger UI |
| Backend ReDoc | `https://[backend-url]/redoc` | Alternative docs |

---

## 🚨 Common Issues & Solutions

| Issue | Solution | Notes |
|-------|----------|-------|
| Build fails | Check Node/Python version | Set in Railway settings |
| Database connection fails | Verify DATABASE_URL | Check PostgreSQL service |
| CORS errors | Update CORS_ORIGINS | Add frontend URL |
| OTP not sending | Check Supabase config | Verify API keys |
| Environment variables not loading | Check variable names | Case-sensitive |
| Migration fails | Run migrations manually | Use Railway CLI |
| Frontend can't connect | Check NEXT_PUBLIC_API_URL | Must be full URL |

---

## 📚 Additional Resources

- **Railway Docs:** https://docs.railway.app
- **Supabase Docs:** https://supabase.com/docs
- **Next.js Deployment:** https://nextjs.org/docs/deployment
- **FastAPI Deployment:** https://fastapi.tiangolo.com/deployment/

---

**Last Updated:** 2025-01-XX  
**Status:** ✅ Production Ready

