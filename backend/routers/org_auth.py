"""
Organization Registration and Login Router
Public endpoints for organizations to register, login, and manage API keys
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import Optional
from pydantic import BaseModel, Field, validator
import re
import uuid

from app.dependencies import get_db
from app.multi_tenant_models import Organization, APIKey
from services.api_key_auth import create_organization, create_api_key
from services.otp_service import create_otp, verify_otp
from services.email_service_otp import email_service
from middleware.logging_config import get_logger

logger = get_logger("org.auth")

org_auth_router = APIRouter(prefix="/org", tags=["Organization Authentication"])

# Pydantic models
class OrganizationRegistration(BaseModel):
    name: str = Field(..., max_length=255, description="Organization name")
    slug: str = Field(..., max_length=100, description="URL-friendly identifier")
    contact_email: str = Field(..., max_length=255, description="Contact email")
    otp_code: str = Field(..., min_length=6, max_length=6, description="6-digit OTP code")

    @validator('contact_email')
    def validate_email(cls, v):
        email_regex = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        if not re.match(email_regex, v):
            raise ValueError('Invalid email format')
        return v.lower().strip()

    @validator('slug')
    def validate_slug(cls, v):
        if not re.match(r'^[a-z0-9-]+$', v):
            raise ValueError('Slug must contain only lowercase letters, numbers, and hyphens')
        return v.lower().strip()

class OrganizationLogin(BaseModel):
    contact_email: str = Field(..., max_length=255, description="Organization contact email")
    otp_code: str = Field(..., min_length=6, max_length=6, description="6-digit OTP code")

    @validator('contact_email')
    def validate_email(cls, v):
        email_regex = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        if not re.match(email_regex, v):
            raise ValueError('Invalid email format')
        return v.lower().strip()

class OrganizationResponse(BaseModel):
    id: str
    name: str
    slug: str
    contact_email: str
    is_active: bool
    rate_limit_per_hour: int

    class Config:
        orm_mode = True

class OrganizationAuthResponse(BaseModel):
    success: bool
    message: str
    organization: Optional[OrganizationResponse] = None
    api_keys: Optional[list] = None

@org_auth_router.post("/request-otp")
async def request_org_otp(
    email: str,
    purpose: str = 'registration',  # 'registration' or 'login'
    db: Session = Depends(get_db)
):
    """
    Request OTP for organization registration or login
    
    - **email**: Organization contact email
    - **purpose**: 'registration' or 'login'
    """
    logger.info(f"Organization OTP request: {email} | Purpose: {purpose}")
    
    try:
        # For registration, check if organization already exists
        if purpose == 'registration':
            existing_org = db.query(Organization).filter(
                Organization.contact_email == email.lower().strip()
            ).first()
            if existing_org:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Organization with this email already exists"
                )
        
        # For login, check if organization exists
        elif purpose == 'login':
            org = db.query(Organization).filter(
                Organization.contact_email == email.lower().strip()
            ).first()
            if not org:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Organization not found"
                )
            if not org.is_active:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Organization account is inactive"
                )
        
        # Generate and send OTP
        try:
            otp_code = create_otp(db, email, purpose)
        except ValueError as e:
            # Rate limit exceeded
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=str(e)
            )
        email_sent = email_service.send_otp(email, otp_code, purpose)
        
        dev_mode = not email_service.enabled
        return {
            "success": True,
            "message": f"OTP sent to {email}" if not dev_mode else f"OTP generated (dev mode): {otp_code}",
            "otp_code": otp_code if dev_mode else None
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"OTP request failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to request OTP: {str(e)}"
        )

@org_auth_router.post("/register", response_model=OrganizationAuthResponse)
async def register_organization(
    org_data: OrganizationRegistration,
    db: Session = Depends(get_db)
):
    """
    Register a new organization
    
    - **name**: Organization name
    - **slug**: URL-friendly identifier
    - **contact_email**: Contact email (will receive OTPs)
    - **otp_code**: 6-digit OTP code sent to email
    """
    logger.info(f"Organization registration: {org_data.name} | Email: {org_data.contact_email}")
    
    try:
        # Verify OTP
        if not verify_otp(db, org_data.contact_email, org_data.otp_code, 'registration'):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid or expired OTP code"
            )
        
        # Check if slug already exists
        existing_org = db.query(Organization).filter(
            Organization.slug == org_data.slug
        ).first()
        if existing_org:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Organization slug already exists"
            )
        
        # Create organization
        new_org = Organization(
            name=org_data.name,
            slug=org_data.slug,
            contact_email=org_data.contact_email.lower().strip(),
            is_active=True,
            rate_limit_per_hour=1000  # Default rate limit
        )
        
        db.add(new_org)
        db.commit()
        db.refresh(new_org)
        
        logger.info(f"Organization registered: {org_data.slug} | ID: {new_org.id}")
        
        return OrganizationAuthResponse(
            success=True,
            message="Organization registered successfully",
            organization=OrganizationResponse(
                id=str(new_org.id),
                name=new_org.name,
                slug=new_org.slug,
                contact_email=new_org.contact_email,
                is_active=new_org.is_active,
                rate_limit_per_hour=new_org.rate_limit_per_hour
            ),
            api_keys=[]
        )
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Organization registration failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Registration failed: {str(e)}"
        )

@org_auth_router.post("/login", response_model=OrganizationAuthResponse)
async def login_organization(
    login_data: OrganizationLogin,
    db: Session = Depends(get_db)
):
    """
    Login organization with email and OTP
    
    - **contact_email**: Organization contact email
    - **otp_code**: 6-digit OTP code sent to email
    """
    logger.info(f"Organization login: {login_data.contact_email}")
    
    try:
        # Get organization
        org = db.query(Organization).filter(
            Organization.contact_email == login_data.contact_email.lower().strip()
        ).first()
        
        if not org:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Organization not found"
            )
        
        if not org.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Organization account is inactive"
            )
        
        # Verify OTP
        if not verify_otp(db, login_data.contact_email, login_data.otp_code, 'login'):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired OTP code"
            )
        
        # Get API keys for this organization
        api_keys = db.query(APIKey).filter(
            APIKey.organization_id == org.id,
            APIKey.is_active == True
        ).all()
        
        api_keys_list = [{
            "id": str(key.id),
            "name": key.name,
            "key_prefix": key.key_prefix,
            "is_active": key.is_active,
            "last_used_at": key.last_used_at.isoformat() if key.last_used_at else None,
            "expires_at": key.expires_at.isoformat() if key.expires_at else None
        } for key in api_keys]
        
        logger.info(f"Organization login successful: {org.slug}")
        
        return OrganizationAuthResponse(
            success=True,
            message="Login successful",
            organization=OrganizationResponse(
                id=str(org.id),
                name=org.name,
                slug=org.slug,
                contact_email=org.contact_email,
                is_active=org.is_active,
                rate_limit_per_hour=org.rate_limit_per_hour
            ),
            api_keys=api_keys_list
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Organization login failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Login failed: {str(e)}"
        )

@org_auth_router.post("/{org_id}/api-keys/create")
async def create_org_api_key(
    org_id: str,
    contact_email: str,
    otp_code: str,
    key_name: Optional[str] = None,
    expires_in_days: Optional[int] = None,
    db: Session = Depends(get_db)
):
    """
    Create API key for organization (requires OTP verification)
    
    - **org_id**: Organization UUID
    - **contact_email**: Organization contact email
    - **otp_code**: 6-digit OTP code
    - **key_name**: Optional name for the API key
    - **expires_in_days**: Optional expiration in days
    """
    logger.info(f"Creating API key for organization: {org_id}")
    
    try:
        # Get organization
        org = db.query(Organization).filter(
            Organization.id == uuid.UUID(org_id),
            Organization.contact_email == contact_email.lower().strip()
        ).first()
        
        if not org:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Organization not found or email mismatch"
            )
        
        # Verify OTP
        if not verify_otp(db, contact_email, otp_code, 'login'):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired OTP code"
            )
        
        # Create API key
        from datetime import datetime, timedelta
        expires_at = None
        if expires_in_days:
            expires_at = datetime.utcnow() + timedelta(days=expires_in_days)
        
        full_key, api_key_obj = create_api_key(
            db=db,
            organization_id=org_id,
            name=key_name or "API Key",
            expires_in_days=expires_in_days,
            created_by=None,
            environment="live"
        )
        
        db.commit()
        
        logger.info(f"API key created for organization: {org.slug}")
        
        return {
            "success": True,
            "message": "API key created successfully",
            "api_key": full_key,  # Full key (only shown once)
            "key_prefix": api_key_obj.key_prefix,
            "expires_at": api_key_obj.expires_at.isoformat() if api_key_obj.expires_at else None
        }
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"API key creation failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create API key: {str(e)}"
        )

