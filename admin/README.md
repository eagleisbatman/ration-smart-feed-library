# Ration Smart Feed Library - Admin Dashboard

Admin dashboard for managing feed database, organizations, and API keys for the Ration Smart Feed Library.

## 🎯 Purpose

This is the admin interface for the **Ration Smart Feed Library** - a comprehensive feed database administration system with multi-language support and API key management for organizations.

## 📋 Features

### Feed Management
- ✅ Multi-country feed management
- ✅ Multi-language feed names (Traduora integration)
- ✅ Feed nutritional values management
- ✅ Bulk import/export
- ✅ Search and filter feeds

### Organization & API Management
- ✅ Organization management
- ✅ API key generation and management
- ✅ Rate limit configuration
- ✅ Usage tracking

### UI Features
- ✅ Dark/Light mode
- ✅ Multi-language support (English, Spanish, French)
- ✅ Responsive design
- ✅ shadcn UI components

## 🚀 Quick Start

### Prerequisites
- Node.js 18+ 
- npm or yarn

### Installation

```bash
# Install dependencies
npm install

# Set up environment variables
cp .env.example .env.local
# Edit .env.local with your configuration
```

### Environment Variables

Create `.env.local`:

```env
# Backend API
NEXT_PUBLIC_API_URL=http://localhost:8000

# Traduora (Optional - falls back to next-intl if not configured)
NEXT_PUBLIC_TRADUORA_URL=http://localhost:3000
TRADUORA_TOKEN=your_traduora_token_here
NEXT_PUBLIC_TRADUORA_ADMIN_PROJECT_ID=admin-ui-project-id
NEXT_PUBLIC_TRADUORA_API_MGMT_PROJECT_ID=api-mgmt-project-id
```

### Development

```bash
# Start development server
npm run dev
```

Visit `http://localhost:3000`

### Build

```bash
# Build for production
npm run build

# Start production server
npm start
```

## 📁 Project Structure

```
ration-smart-feed-library/
├── admin/              # This admin UI (Next.js)
├── backend/           # Backend API (FastAPI)
├── migrations/         # Database migrations
└── scripts/            # Utility scripts
```

## 🔗 Related Repositories

- **[ration-smart-mcp-server](https://github.com/eagleisbatman/ration-smart-mcp-server)** - MCP server for AI agent integration
- **Backend API** - Part of this repository (`backend/` folder)

## 📚 Documentation

- [UI Design](./UI_DESIGN.md)
- [Traduora Setup](./TRADUORA_SETUP.md)
- [Admin UI Complete](./ADMIN_UI_COMPLETE.md)

## 🎨 Tech Stack

- **Framework**: Next.js 16
- **UI**: shadcn/ui + Tailwind CSS
- **State**: React Query
- **i18n**: next-intl + Traduora
- **Theme**: next-themes (dark/light mode)

## 📝 License

MIT
