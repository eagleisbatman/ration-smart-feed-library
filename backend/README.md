# Ration Smart Feed Library - Backend API

Backend API for the Ration Smart Feed Library - A comprehensive dairy cattle nutrition optimization system with multi-language feed support and multi-tenant API key management.

## 🎯 Purpose

This is the backend API for the **Ration Smart Feed Library** - optimized for MCP server integration and admin dashboard management. It provides:

- Feed database with multi-language support
- Diet formulation and evaluation
- Multi-tenant organization management
- API key authentication
- Feed management endpoints

## 📋 What's Included

### ✅ Core Features
- **Authentication**: Email + PIN and API Key authentication
- **Feed Management**: Multi-language feed database
- **Diet Operations**: Recommendation and evaluation endpoints
- **Organization Management**: Multi-tenant support with API keys
- **Core Logic**: All optimization and calculation logic
- **Database Models**: Complete schema with multi-language support

### ❌ Removed (Mobile App Features)
- PDF generation and report saving
- User feedback system
- Feed analytics tracking
- Custom feeds management
- User report management
- Email service
- AWS S3 integration

## 🚀 Quick Start

### Local Development

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Set up environment variables
cp .env.example .env
# Edit .env with your database credentials

# 3. Run migrations
python scripts/run_migrations.py

# 4. Start server
uvicorn app.main:app --reload
```

### Railway Deployment

1. **Create Railway Project:**
   - Add PostgreSQL service
   - Add Python service
   - Link PostgreSQL to Python service

2. **Set Environment Variables:**
   - Railway auto-generates `DATABASE_URL`
   - Or set individual variables:
     - `POSTGRES_HOST`
     - `POSTGRES_PORT`
     - `POSTGRES_USER`
     - `POSTGRES_PASSWORD`
     - `POSTGRES_DB`

3. **Deploy:**
   ```bash
   railway up
   ```

## 📁 Project Structure

```
ration-smart-feed-library/
├── backend/              # This backend API (FastAPI)
│   ├── app/              # Main application
│   ├── routers/          # API routes
│   ├── middleware/       # Auth and logging middleware
│   ├── services/         # Business logic
│   └── models.py         # Database models
├── admin/                # Admin dashboard (Next.js)
├── migrations/           # Database migrations
└── scripts/              # Utility scripts
```

## 🔐 Authentication

### API Key (Recommended)

```bash
curl -H "Authorization: Bearer ff_live_xxxxxxxxxxxx" \
  https://api.example.com/diet-recommendation-working/
```

### Email + PIN (Backward Compatible)

```bash
curl -X POST https://api.example.com/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email_id": "user@example.com", "pin": "1234"}'
```

## 📚 API Endpoints

### Authentication
- `POST /auth/login` - Email + PIN login

### Feeds
- `GET /feeds/search` - Search feeds
- `GET /feeds/{feed_id}` - Get feed details

### Diet Operations
- `POST /diet-recommendation-working/` - Get diet recommendation
- `POST /diet-evaluation-working/` - Evaluate existing diet

### Admin (Multi-Tenant)
- `POST /admin/organizations` - Create organization
- `POST /admin/organizations/{org_id}/api-keys` - Generate API key
- `GET /admin/organizations/{org_id}/api-keys` - List API keys

## 🗄️ Database

### Schema Features
- Multi-language feed support (`feed_translations` table)
- Country language mapping (`country_languages` table)
- Multi-tenant organizations (`organizations`, `api_keys` tables)
- Usage tracking (`api_usage` table)

### Migrations

```bash
# Run all migrations
python scripts/run_migrations.py

# Run specific migration
python scripts/run_single_migration.py migrations/001_create_new_database_schema.sql
```

## 🔗 Related Repositories

- **[ration-smart-mcp-server](https://github.com/eagleisbatman/ration-smart-mcp-server)** - MCP server for AI agent integration
- **Admin Dashboard** - Part of this repository (`admin/` folder)

## 📝 Environment Variables

```env
# Database
DATABASE_URL=postgresql://user:pass@host:port/db
# Or individual variables:
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_USER=postgres
POSTGRES_PASSWORD=password
POSTGRES_DB=ration_smart

# Server
PORT=8000
ENVIRONMENT=development
```

## 🧪 Testing

```bash
# Run tests
pytest

# Test specific endpoint
curl http://localhost:8000/docs
```

## 📝 License

MIT

## 🔗 Links

- **MCP Server**: [ration-smart-mcp-server](https://github.com/eagleisbatman/ration-smart-mcp-server)
- **Admin Dashboard**: Part of this repository (`admin/` folder)
