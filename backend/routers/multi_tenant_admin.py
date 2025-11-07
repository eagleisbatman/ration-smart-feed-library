"""
Admin Router for Multi-Tenant Management
Handles organization and API key management
"""

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime, timedelta
import uuid
from pydantic import BaseModel, Field

from app.dependencies import get_db
from app.multi_tenant_models import Organization, APIKey, APIUsage
from app.models import UserInformationModel
from services.api_key_auth import (
    create_organization,
    create_api_key,
    revoke_api_key,
    get_organization_by_slug
)
from middleware.auth_middleware import require_auth, AuthContext
from middleware.logging_config import get_logger

logger = get_logger("admin.multi_tenant")

router = APIRouter(prefix="/admin", tags=["Admin - Multi-Tenant"])

# Pydantic models for requests/responses
class OrganizationCreate(BaseModel):
    name: str = Field(..., max_length=255, description="Organization name")
    slug: str = Field(..., max_length=100, description="URL-friendly identifier (lowercase, no spaces)")
    contact_email: Optional[str] = Field(None, max_length=255, description="Contact email")
    rate_limit_per_hour: int = Field(1000, ge=1, le=100000, description="Rate limit per hour")

class OrganizationResponse(BaseModel):
    id: str
    name: str
    slug: str
    contact_email: Optional[str]
    is_active: bool
    rate_limit_per_hour: int
    created_at: datetime
    
    class Config:
        orm_mode = True

class APIKeyCreate(BaseModel):
    name: Optional[str] = Field(None, max_length=255, description="Friendly name for the key")
    expires_in_days: Optional[int] = Field(None, ge=1, description="Days until expiration (None = no expiration)")
    environment: str = Field("live", description="Environment: 'live' or 'test'")

class APIKeyResponse(BaseModel):
    id: str
    key_prefix: str  # Only prefix, never full key
    name: Optional[str]
    is_active: bool
    last_used_at: Optional[datetime]
    expires_at: Optional[datetime]
    created_at: datetime
    
    class Config:
        orm_mode = True

class APIKeyCreateResponse(BaseModel):
    api_key: str  # Full key - only shown once!
    key_prefix: str
    organization_id: str
    expires_at: Optional[datetime]
    message: str = "Store this API key securely. It will not be shown again."

@router.post("/organizations", response_model=OrganizationResponse, tags=["Admin - Multi-Tenant"])
async def create_organization_endpoint(
    org_data: OrganizationCreate,
    admin_user_id: str = Query(..., description="Admin user UUID"),
    db: Session = Depends(get_db)
):
    """
    Create a new organization (Admin only)
    
    - **name**: Organization name
    - **slug**: URL-friendly identifier (must be unique, lowercase, no spaces)
    - **contact_email**: Contact email (optional)
    - **rate_limit_per_hour**: Rate limit per hour (default: 1000)
    """
    logger.info(f"Create organization request by admin: {admin_user_id}")
    
    # Verify admin
    admin_user = db.query(UserInformationModel).filter(
        UserInformationModel.id == uuid.UUID(admin_user_id),
        UserInformationModel.is_admin == True
    ).first()
    
    if not admin_user:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin privileges required"
        )
    
    # Check if slug already exists
    existing = get_organization_by_slug(db, org_data.slug)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Organization with slug '{org_data.slug}' already exists"
        )
    
    # Create organization
    organization = create_organization(
        db=db,
        name=org_data.name,
        slug=org_data.slug,
        contact_email=org_data.contact_email,
        rate_limit_per_hour=org_data.rate_limit_per_hour
    )
    
    logger.info(f"Organization created: {organization.name} ({organization.slug})")
    
    return OrganizationResponse(
        id=str(organization.id),
        name=organization.name,
        slug=organization.slug,
        contact_email=organization.contact_email,
        is_active=organization.is_active,
        rate_limit_per_hour=organization.rate_limit_per_hour,
        created_at=organization.created_at
    )

@router.post("/organizations/{org_id}/api-keys", response_model=APIKeyCreateResponse, tags=["Admin - Multi-Tenant"])
async def create_api_key_endpoint(
    org_id: str,
    key_data: APIKeyCreate,
    admin_user_id: str = Query(..., description="Admin user UUID"),
    db: Session = Depends(get_db)
):
    """
    Create a new API key for an organization (Admin only)
    
    **IMPORTANT:** The full API key is only shown once in the response.
    Store it securely - it cannot be retrieved again.
    
    - **name**: Friendly name for the key (optional)
    - **expires_in_days**: Days until expiration (optional, None = no expiration)
    - **environment**: 'live' or 'test' (default: 'live')
    """
    logger.info(f"Create API key request by admin: {admin_user_id} for org: {org_id}")
    
    # Verify admin
    admin_user = db.query(UserInformationModel).filter(
        UserInformationModel.id == uuid.UUID(admin_user_id),
        UserInformationModel.is_admin == True
    ).first()
    
    if not admin_user:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin privileges required"
        )
    
    # Verify organization exists
    organization = db.query(Organization).filter(Organization.id == uuid.UUID(org_id)).first()
    if not organization:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Organization not found"
        )
    
    # Create API key
    full_key, api_key_obj = create_api_key(
        db=db,
        organization_id=org_id,
        name=key_data.name,
        expires_in_days=key_data.expires_in_days,
        created_by=admin_user_id,
        environment=key_data.environment
    )
    
    logger.info(f"API key created for organization {organization.name}: {api_key_obj.key_prefix}...")
    
    return APIKeyCreateResponse(
        api_key=full_key,  # Only shown once!
        key_prefix=api_key_obj.key_prefix,
        organization_id=str(organization.id),
        expires_at=api_key_obj.expires_at,
        message="Store this API key securely. It will not be shown again."
    )

@router.get("/organizations", response_model=List[OrganizationResponse], tags=["Admin - Multi-Tenant"])
async def list_organizations(
    admin_user_id: str = Query(..., description="Admin user UUID"),
    db: Session = Depends(get_db)
):
    """List all organizations (Admin only)"""
    # Verify admin
    admin_user = db.query(UserInformationModel).filter(
        UserInformationModel.id == uuid.UUID(admin_user_id),
        UserInformationModel.is_admin == True
    ).first()
    
    if not admin_user:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin privileges required"
        )
    
    organizations = db.query(Organization).all()
    
    return [
        OrganizationResponse(
            id=str(org.id),
            name=org.name,
            slug=org.slug,
            contact_email=org.contact_email,
            is_active=org.is_active,
            rate_limit_per_hour=org.rate_limit_per_hour,
            created_at=org.created_at
        )
        for org in organizations
    ]

@router.get("/organizations/{org_id}/api-keys", response_model=List[APIKeyResponse], tags=["Admin - Multi-Tenant"])
async def list_api_keys(
    org_id: str,
    admin_user_id: str = Query(..., description="Admin user UUID"),
    db: Session = Depends(get_db)
):
    """List API keys for an organization (Admin only)"""
    # Verify admin
    admin_user = db.query(UserInformationModel).filter(
        UserInformationModel.id == uuid.UUID(admin_user_id),
        UserInformationModel.is_admin == True
    ).first()
    
    if not admin_user:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin privileges required"
        )
    
    # Verify organization exists
    organization = db.query(Organization).filter(Organization.id == uuid.UUID(org_id)).first()
    if not organization:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Organization not found"
        )
    
    api_keys = db.query(APIKey).filter(APIKey.organization_id == uuid.UUID(org_id)).all()
    
    return [
        APIKeyResponse(
            id=str(key.id),
            key_prefix=key.key_prefix,
            name=key.name,
            is_active=key.is_active,
            last_used_at=key.last_used_at,
            expires_at=key.expires_at,
            created_at=key.created_at
        )
        for key in api_keys
    ]

@router.delete("/api-keys/{key_id}", tags=["Admin - Multi-Tenant"])
async def revoke_api_key_endpoint(
    key_id: str,
    admin_user_id: str = Query(..., description="Admin user UUID"),
    db: Session = Depends(get_db)
):
    """Revoke an API key (Admin only)"""
    # Verify admin
    admin_user = db.query(UserInformationModel).filter(
        UserInformationModel.id == uuid.UUID(admin_user_id),
        UserInformationModel.is_admin == True
    ).first()
    
    if not admin_user:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin privileges required"
        )
    
    success = revoke_api_key(db, key_id)
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="API key not found"
        )
    
    return {"success": True, "message": "API key revoked successfully"}

