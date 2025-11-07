# Repository Structure - Ration Smart Feed Library

## 📦 Repository Organization

This repository contains both the **Backend API** and **Admin Dashboard** for the Ration Smart Feed Library.

## 📁 Structure

```
ration-smart-feed-library/
├── backend/              # Backend API (FastAPI)
│   ├── app/             # Main application
│   ├── routers/         # API routes
│   ├── middleware/      # Auth and logging
│   ├── services/        # Business logic
│   ├── migrations/      # Database migrations
│   └── scripts/         # Utility scripts
│
├── admin/               # Admin Dashboard (Next.js)
│   ├── app/            # Next.js app directory
│   ├── components/     # React components
│   ├── lib/            # Utilities and API client
│   └── hooks/          # React hooks
│
└── README.md           # This file
```

## 🎯 Components

### Backend API (`backend/`)
- FastAPI application
- Feed database with multi-language support
- Diet formulation and evaluation
- Multi-tenant organization management
- API key authentication

### Admin Dashboard (`admin/`)
- Next.js admin interface
- Feed management UI
- Organization and API key management
- Multi-language support (Traduora integration)
- Dark/Light mode

## 🔗 Related Repository

- **[ration-smart-mcp-server](https://github.com/eagleisbatman/ration-smart-mcp-server)** - MCP server for AI agent integration

## 🚀 Getting Started

### Backend

```bash
cd backend
pip install -r requirements.txt
cp .env.example .env
# Edit .env with database credentials
python scripts/run_migrations.py
uvicorn app.main:app --reload
```

### Admin Dashboard

```bash
cd admin
npm install
cp .env.example .env.local
# Edit .env.local with API URL
npm run dev
```

## 📚 Documentation

- [Backend README](./backend/README.md)
- [Admin README](./admin/README.md)
- [Multi-Tenant Auth Guide](./backend/MULTI_TENANT_AUTH_GUIDE.md)

## 📝 License

MIT

