"""
Rate Limiting Middleware
Enforces rate limits per organization based on API key
"""
from fastapi import Request, HTTPException, status
from starlette.middleware.base import BaseHTTPMiddleware
from sqlalchemy.orm import Session
from sqlalchemy import func, and_
from datetime import datetime, timedelta
from typing import Optional
from app.dependencies import get_db
from app.multi_tenant_models import Organization, APIUsage
from middleware.auth_middleware import get_auth_context
from middleware.logging_config import get_logger

logger = get_logger("rate_limiter")

class RateLimitMiddleware(BaseHTTPMiddleware):
    """Middleware to enforce rate limits per organization"""
    
    async def dispatch(self, request: Request, call_next):
        # Skip rate limiting for health checks and public endpoints
        if request.url.path in ['/health', '/', '/docs', '/redoc', '/openapi.json']:
            return await call_next(request)
        
        # Get auth context to identify organization
        # Note: This is a simplified check - in production, you'd want to cache this
        try:
            from app.dependencies import get_db
            db_gen = get_db()
            db = next(db_gen)
            
            try:
                auth_context = await get_auth_context(request, None, db)
                
                if auth_context.organization:
                    # Check rate limit for this organization
                    org = auth_context.organization
                    
                    # Count requests in the last hour
                    one_hour_ago = datetime.utcnow() - timedelta(hours=1)
                    recent_requests = db.query(func.count(APIUsage.id)).filter(
                        and_(
                            APIUsage.organization_id == org.id,
                            APIUsage.created_at >= one_hour_ago
                        )
                    ).scalar() or 0
                    
                    # Check if limit exceeded
                    if recent_requests >= org.rate_limit_per_hour:
                        logger.warning(
                            f"Rate limit exceeded for organization {org.name} "
                            f"({org.id}): {recent_requests}/{org.rate_limit_per_hour}"
                        )
                        raise HTTPException(
                            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                            detail={
                                "error": "Rate limit exceeded",
                                "message": f"Maximum {org.rate_limit_per_hour} requests per hour",
                                "retry_after": 3600  # seconds
                            },
                            headers={"Retry-After": "3600"}
                        )
                    
                    # Track API usage (async after response)
                    # Note: In production, use background task or queue
                    try:
                        usage = APIUsage(
                            organization_id=org.id,
                            api_key_id=auth_context.api_key.id if auth_context.api_key else None,
                            endpoint=request.url.path,
                            method=request.method,
                            response_status=None,  # Will be updated after response
                            response_time_ms=None
                        )
                        db.add(usage)
                        db.commit()
                    except Exception as e:
                        logger.error(f"Failed to track API usage: {str(e)}")
                        db.rollback()
                
            finally:
                db.close()
        except HTTPException:
            raise
        except Exception as e:
            # Don't block requests if rate limiting fails
            logger.error(f"Rate limiting error: {str(e)}")
        
        # Process request
        response = await call_next(request)
        return response

