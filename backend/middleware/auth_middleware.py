"""
Multi-Tenant Authentication Middleware
Handles both API key and email+PIN authentication
"""

from fastapi import Request, HTTPException, status, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from typing import Optional, Tuple
from app.dependencies import get_db
from app.multi_tenant_models import Organization, APIKey
from services.api_key_auth import authenticate_api_key
from services.auth_utils import authenticate_user, get_user_by_email
from middleware.logging_config import get_logger

logger = get_logger("auth_middleware")

security = HTTPBearer(auto_error=False)

class AuthContext:
    """Authentication context for requests"""
    def __init__(
        self,
        organization: Optional[Organization] = None,
        api_key: Optional[APIKey] = None,
        user_id: Optional[str] = None,
        auth_method: str = "none"
    ):
        self.organization = organization
        self.api_key = api_key
        self.user_id = user_id
        self.auth_method = auth_method  # 'api_key', 'email_pin', 'none'
    
    @property
    def is_authenticated(self) -> bool:
        return self.auth_method != "none"
    
    @property
    def org_id(self) -> Optional[str]:
        return str(self.organization.id) if self.organization else None

async def get_auth_context(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    db: Session = Depends(get_db)
) -> AuthContext:
    """
    Get authentication context from request
    Supports both API key (Bearer token) and email+PIN (body)
    
    Priority:
    1. API key in Authorization header (Bearer token)
    2. Email+PIN in request body (for backward compatibility)
    3. No authentication (public endpoints)
    """
    # Try API key authentication first
    if credentials and credentials.credentials:
        api_key = credentials.credentials
        
        # Remove 'Bearer ' prefix if present
        if api_key.startswith('Bearer '):
            api_key = api_key[7:]
        
        result = authenticate_api_key(db, api_key)
        if result:
            organization, api_key_obj = result
            logger.info(f"API key authenticated: {api_key_obj.key_prefix} for org: {organization.name}")
            return AuthContext(
                organization=organization,
                api_key=api_key_obj,
                auth_method="api_key"
            )
    
    # Try email+PIN authentication (for backward compatibility)
    # This is handled in individual endpoints that need it
    
    # No authentication
    return AuthContext(auth_method="none")

def require_auth(auth_context: AuthContext = Depends(get_auth_context)) -> AuthContext:
    """
    Dependency to require authentication
    Raises 401 if not authenticated
    """
    if not auth_context.is_authenticated:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required. Provide API key in Authorization header or email+PIN in request body."
        )
    return auth_context

def require_api_key(auth_context: AuthContext = Depends(get_auth_context)) -> AuthContext:
    """
    Dependency to require API key authentication
    Raises 401 if not authenticated via API key
    """
    if auth_context.auth_method != "api_key":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API key authentication required. Provide API key in Authorization: Bearer <key> header."
        )
    return auth_context

def require_email_pin(
    email_id: Optional[str] = None,
    pin: Optional[str] = None,
    db: Session = Depends(get_db)
) -> Tuple[str, AuthContext]:
    """
    Dependency to require email+PIN authentication
    For backward compatibility with existing endpoints
    """
    if not email_id or not pin:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email and PIN required for authentication"
        )
    
    user, error_message = authenticate_user(db, email_id, pin)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=error_message or "Invalid email or PIN"
        )
    
    # Create auth context with user info
    auth_context = AuthContext(
        user_id=str(user.id),
        auth_method="email_pin"
    )
    
    return str(user.id), auth_context

