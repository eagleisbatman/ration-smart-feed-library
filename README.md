# Ration Smart Feed Library

A comprehensive feed database administration system with multi-language support, multi-tenant API key management, and MCP server integration for dairy cattle nutrition optimization.

## 🎯 Overview

Ration Smart Feed Library provides:
- **Feed Database**: Multi-country, multi-language feed database
- **Diet Optimization**: Dairy cattle nutrition optimization algorithms
- **API Management**: Multi-tenant organization and API key management
- **Admin Dashboard**: Modern web interface for feed and API management
- **MCP Integration**: Ready for AI agent integration via Model Context Protocol

## 📦 Repository Structure

```
ration-smart-feed-library/
├── backend/              # Backend API (FastAPI)
│   ├── app/            # Main application
│   ├── routers/        # API routes
│   ├── middleware/     # Auth and logging
│   ├── services/       # Business logic
│   ├── migrations/     # Database migrations
│   └── scripts/        # Utility scripts
│
├── admin/               # Admin Dashboard (Next.js)
│   ├── app/            # Next.js app directory
│   ├── components/     # React components
│   ├── lib/            # Utilities and API client
│   └── hooks/          # React hooks
│
└── README.md           # This file
```

## 🚀 Quick Start

### Prerequisites
- Python 3.9+
- Node.js 18+
- PostgreSQL 12+
- Railway account (for deployment)

### Backend Setup

```bash
cd backend
pip install -r requirements.txt
cp .env.example .env
# Edit .env with database credentials
python scripts/run_migrations.py
uvicorn app.main:app --reload
```

### Admin Dashboard Setup

```bash
cd admin
npm install
cp .env.example .env.local
# Edit .env.local with API URL
npm run dev
```

## 🗄️ Database

### Railway PostgreSQL

The database is hosted on Railway. Connection details are provided via `DATABASE_URL` environment variable.

### Schema Features
- Multi-language feed support (`feed_translations` table)
- Country language mapping (`country_languages` table)
- Multi-tenant organizations (`organizations`, `api_keys` tables)
- Usage tracking (`api_usage` table)

### Migrations

```bash
# Run all migrations
cd backend
python scripts/run_migrations.py

# Run specific migration
python scripts/run_single_migration.py migrations/001_create_new_database_schema.sql
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

## 🌐 Multi-Language Support

### Supported Languages
- **Ethiopia**: English, Afan Oromo, Amharic
- **Vietnam**: English, Vietnamese
- **All Countries**: English (default)

### Translation Management
- **Traduora Integration**: Optional translation management system
- **Fallback**: Uses next-intl if Traduora not configured
- **Feed Translations**: Stored in `feed_translations` table

## 🔗 Related Repositories

- **[ration-smart-mcp-server](https://github.com/eagleisbatman/ration-smart-mcp-server)** - MCP server for AI agent integration

## 📖 Documentation

- [Backend README](./backend/README.md)
- [Admin Dashboard README](./admin/README.md)
- [Multi-Tenant Auth Guide](./backend/MULTI_TENANT_AUTH_GUIDE.md)
- [Repository Structure](./backend/REPOSITORY_STRUCTURE.md)

## 🚢 Deployment

### Railway Deployment

1. **Create Railway Project**
   - Add PostgreSQL service
   - Add Python service (backend)
   - Add Node.js service (admin - optional)

2. **Configure Environment Variables**
   - Railway auto-generates `DATABASE_URL`
   - Set `ENVIRONMENT=production`
   - Set `LOG_LEVEL=INFO`

3. **Deploy**
   ```bash
   railway up
   ```

### Environment Variables

**Backend (.env)**
```env
DATABASE_URL=postgresql://user:pass@host:port/db
ENVIRONMENT=production
LOG_LEVEL=INFO
```

**Admin (.env.local)**
```env
NEXT_PUBLIC_API_URL=https://your-backend.railway.app
```

## 🧪 Development

### Backend
```bash
cd backend
uvicorn app.main:app --reload
```

### Admin Dashboard
```bash
cd admin
npm run dev
```

## 📝 License

MIT

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Submit a pull request

## 📧 Support

For issues and questions, please open an issue on GitHub.

---

**Built with ❤️ for dairy farmers worldwide**

