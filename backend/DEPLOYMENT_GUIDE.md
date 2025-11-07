# Deployment Guide - Ration Smart Feed Library

## 🚀 Railway Deployment

### Prerequisites
- Railway account
- GitHub repository connected
- Railway CLI installed (optional)

### Step 1: Create Railway Project

1. Go to [Railway Dashboard](https://railway.app)
2. Click "New Project"
3. Select "Deploy from GitHub repo"
4. Choose `ration-smart-feed-library` repository

### Step 2: Add PostgreSQL Database

1. In Railway project, click "New"
2. Select "Database" → "PostgreSQL"
3. Railway will auto-generate `DATABASE_URL`

### Step 3: Deploy Backend

1. Click "New" → "GitHub Repo"
2. Select `ration-smart-feed-library`
3. Set root directory: `backend`
4. Set start command: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`

### Step 4: Configure Environment Variables

**Backend Service:**
```env
DATABASE_URL=${{Postgres.DATABASE_URL}}
ENVIRONMENT=production
LOG_LEVEL=INFO
PORT=${{PORT}}
```

**Or manually:**
- `DATABASE_URL`: From PostgreSQL service
- `ENVIRONMENT`: `production`
- `LOG_LEVEL`: `INFO`
- `PORT`: Auto-set by Railway

### Step 5: Run Migrations

**Option 1: Railway CLI**
```bash
railway run python scripts/run_migrations.py
```

**Option 2: Railway Dashboard**
1. Go to backend service
2. Click "Deployments" → "View Logs"
3. Use Railway shell to run migrations

### Step 6: Deploy Admin Dashboard (Optional)

1. Click "New" → "GitHub Repo"
2. Select `ration-smart-feed-library`
3. Set root directory: `admin`
4. Set start command: `npm start`
5. Set build command: `npm run build`

**Environment Variables:**
```env
NEXT_PUBLIC_API_URL=${{Backend.RAILWAY_PUBLIC_DOMAIN}}
```

## 🔧 Local Development Setup

### Backend

```bash
cd backend
pip install -r requirements.txt

# Create .env file
cat > .env << EOF
DATABASE_URL=postgresql://user:pass@localhost:5432/ration_smart
ENVIRONMENT=development
LOG_LEVEL=DEBUG
EOF

# Run migrations
python scripts/run_migrations.py

# Start server
uvicorn app.main:app --reload
```

### Admin Dashboard

```bash
cd admin
npm install

# Create .env.local file
cat > .env.local << EOF
NEXT_PUBLIC_API_URL=http://localhost:8000
EOF

# Start dev server
npm run dev
```

## 📊 Database Setup

### Initial Migration

```bash
cd backend
python scripts/run_migrations.py
```

### Copy Countries

```bash
# Set DATABASE_URL for Railway DB
export DATABASE_URL="postgresql://postgres:pass@host:port/railway"

# Run copy script
node scripts/copy-countries-to-new-db.js
```

## 🔐 API Key Setup

1. **Create Organization** (via Admin Dashboard or API)
   ```bash
   curl -X POST https://api.example.com/admin/organizations \
     -H "Content-Type: application/json" \
     -d '{
       "name": "My Organization",
       "slug": "my-org",
       "contact_email": "admin@example.com",
       "rate_limit_per_hour": 1000
     }'
   ```

2. **Generate API Key**
   ```bash
   curl -X POST https://api.example.com/admin/organizations/{org_id}/api-keys \
     -H "Content-Type: application/json" \
     -d '{"name": "Production Key"}'
   ```

3. **Use API Key**
   ```bash
   curl -H "Authorization: Bearer ff_live_xxxxxxxxxxxx" \
     https://api.example.com/diet-recommendation-working/
   ```

## 🌐 Domain Setup

### Custom Domain (Railway)

1. Go to service settings
2. Click "Generate Domain" or "Custom Domain"
3. Add your domain
4. Update DNS records

### Environment Variables Update

After domain setup, update:
```env
NEXT_PUBLIC_API_URL=https://your-domain.com
```

## 📝 Health Checks

### Backend Health
```bash
curl https://your-backend.railway.app/health
```

### Admin Dashboard
```bash
curl https://your-admin.railway.app
```

## 🔍 Troubleshooting

### Database Connection Issues
- Check `DATABASE_URL` is set correctly
- Verify PostgreSQL service is running
- Check network connectivity

### Migration Errors
- Ensure database exists
- Check user permissions
- Review migration logs

### API Key Issues
- Verify API key is active
- Check organization is active
- Review rate limits

## 📚 Additional Resources

- [Railway Documentation](https://docs.railway.app)
- [Backend README](./backend/README.md)
- [Admin README](./admin/README.md)

