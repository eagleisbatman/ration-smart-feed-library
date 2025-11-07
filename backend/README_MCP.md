# Feed Formulation Backend - MCP Server Fork

## ✅ Setup Complete!

Created a simplified fork optimized for MCP server integration.

## 📁 Location

**Fork:** `feed-formulation-backend-mcp/`

## 🔄 What Changed

### Removed:
- PDF generation (replaced with stubs)
- AWS S3 integration (replaced with stubs)  
- Email service
- User feedback router
- Feed classification router

### Kept:
- ✅ Authentication (email + PIN)
- ✅ Feed endpoints (`/feeds/`, `/feeds/{feed_id}`)
- ✅ Diet endpoints (`/diet-recommendation-working/`, `/diet-evaluation-working/`)
- ✅ Core optimization logic
- ✅ Database models and migrations

### Created:
- ✅ Minimal service stubs (`services/pdf_service.py`, `services/aws_service.py`)
- ✅ Railway configuration (`railway.json`)
- ✅ Schema improvements migration
- ✅ Documentation

## 🎯 MCP Server Endpoints

1. `POST /auth/login` - Email + PIN
2. `GET /auth/countries` - Get countries
3. `GET /feeds/` - Search feeds
4. `GET /feeds/{feed_id}` - Get feed details
5. `POST /diet-recommendation-working/` - Diet recommendation
6. `POST /diet-evaluation-working/` - Diet evaluation

## 🚀 Railway Deployment

### Quick Start:

1. **Create Railway Project:**
   - New Project → Deploy from GitHub
   - Select repository

2. **Add PostgreSQL:**
   - Add Database → PostgreSQL
   - Railway auto-generates `DATABASE_URL`

3. **Deploy:**
   - Railway auto-detects Dockerfile
   - Auto-deploys

4. **Run Migrations:**
   ```bash
   railway run python scripts/run_migrations.py
   railway run psql $DATABASE_URL -f migrations/032_improve_schema_for_mcp.sql
   ```

5. **Import Data:**
   - Countries, feed types, categories
   - Feeds (Vietnam, Ethiopia)

## 🔧 Authentication

**Email + PIN** (works perfectly for MCP server)

- Credentials stored in MCP server env vars
- Single service account
- No changes needed

## 📊 Database Schema

**Improvements:**
- Indexes for performance
- Soft delete support
- Data integrity constraints

**Migration:** `migrations/032_improve_schema_for_mcp.sql`

## ✅ Ready!

The fork is ready to deploy to Railway and connect to the MCP server.

**Next:** Deploy to Railway and test! 🚀
