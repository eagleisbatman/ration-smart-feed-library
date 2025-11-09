"""
CORS Configuration
Secure CORS settings for the API
"""
from fastapi.middleware.cors import CORSMiddleware
from fastapi import FastAPI
import os
from typing import List

def setup_cors(app: FastAPI):
    """
    Configure CORS middleware with secure settings
    
    Args:
        app: FastAPI application instance
    """
    # Get allowed origins from environment
    allowed_origins_env = os.getenv("CORS_ORIGINS", "")
    
    # Parse comma-separated origins
    if allowed_origins_env:
        allowed_origins = [origin.strip() for origin in allowed_origins_env.split(",")]
    else:
        # Default: only allow same origin (most restrictive)
        allowed_origins = []
    
    # In development, allow localhost
    if os.getenv("ENVIRONMENT", "production") == "development":
        allowed_origins.extend([
            "http://localhost:3000",
            "http://localhost:3001",
            "http://127.0.0.1:3000",
            "http://127.0.0.1:3001",
        ])
    
    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins,  # Specific origins only
        allow_credentials=True,  # Allow cookies/auth headers
        allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"],
        allow_headers=["Content-Type", "Authorization", "X-Requested-With"],
        expose_headers=["Mcp-Session-Id"],  # Expose MCP session ID
        max_age=3600,  # Cache preflight requests for 1 hour
    )

