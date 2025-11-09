from fastapi import FastAPI
from routers.animal import router as animal_router  # Keep diet endpoints
from routers.auth import auth_router  # Keep authentication (legacy PIN + new OTP)
from routers.otp_auth import otp_auth_router  # New OTP authentication
from routers.org_auth import org_auth_router  # Organization registration/login
from routers.admin import admin_router  # Keep minimal admin (feed management)
from routers.country_admin import country_admin_router  # Country admin endpoints
from routers.multi_tenant_admin import router as multi_tenant_router  # Multi-tenant management
from routers.superadmin import superadmin_router  # Superadmin management
from routers.feeds import router as feeds_router  # Public feeds endpoints
from middleware.middleware import LoggingMiddleware
from middleware.cors_config import setup_cors
from middleware.error_handler import ErrorHandlerMiddleware
from middleware.logging_config import get_logger

# Initialize logging
logger = get_logger("main")

app = FastAPI(
    title="Feed Formulation Backend - MCP Server Fork",
    description="""
# Feed Formulation Backend API - MCP Server Edition

A simplified dairy cattle nutrition optimization system optimized for MCP server integration.

## API Categories

### 🔐 Authentication
- **Email + PIN**: Traditional authentication (backward compatible)
- **API Key**: Multi-tenant API key authentication (recommended for organizations)

### 🌾 Feeds
Feed search and retrieval by ID.

### 🥗 Diet Operations
Diet formulation and evaluation for dairy cattle nutrition optimization.

### 🔧 Admin Management
- **Feed Management**: Minimal admin functions for feed management (data import)
- **Multi-Tenant**: Organization and API key management

## Authentication

**Two Methods Supported:**

1. **API Key** (Recommended for Organizations):
   - Header: `Authorization: Bearer ff_live_xxxxxxxxxxxx`
   - Per-organization tracking and rate limiting
   - Best for server-to-server (MCP server)

2. **Email + PIN** (Backward Compatible):
   - Body: `{"email_id": "...", "pin": "1234"}`
   - Works for admin access and testing

**Note:** This is a simplified fork optimized for MCP server integration. 
Mobile app features (PDF generation, report saving) have been removed.
    """,
    version="3.0.0-mcp",
    docs_url="/docs",
    redoc_url="/redoc"
)

# Configure CORS (must be before other middleware)
setup_cors(app)

# Add error handler middleware (catches all exceptions)
app.add_middleware(ErrorHandlerMiddleware)

# Add logging middleware
app.add_middleware(LoggingMiddleware)

# Add rate limiting middleware (after CORS, before logging)
from middleware.rate_limiter import RateLimitMiddleware
app.add_middleware(RateLimitMiddleware)

# Include only essential routers
app.include_router(feeds_router)  # Public feeds endpoints (MCP server + frontend)
app.include_router(animal_router)  # Diet endpoints
app.include_router(auth_router)  # Authentication (legacy PIN)
app.include_router(otp_auth_router)  # OTP authentication
app.include_router(org_auth_router)  # Organization registration/login
app.include_router(admin_router)  # Minimal admin (feed management only)
app.include_router(country_admin_router)  # Country admin endpoints
app.include_router(multi_tenant_router)  # Multi-tenant management
app.include_router(superadmin_router)  # Superadmin management

@app.get("/")
async def root():
    logger.info("Root endpoint accessed")
    return {
        "message": "Feed Formulation Backend v3.0 - MCP Server Fork", 
        "status": "running",
        "authentication": "API Key (recommended) or Email + PIN (backward compatible)",
        "docs": "/docs",
        "version": "3.0.0-mcp",
        "note": "Simplified fork optimized for MCP server integration with multi-tenant support"
    }

@app.on_event("startup")
async def startup_event():
    logger.info("Feed Formulation Backend (MCP Fork) starting up...")

@app.on_event("shutdown")
async def shutdown_event():
    logger.info("Feed Formulation Backend (MCP Fork) shutting down...")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
