"""
API Key Authentication Utilities
Handles API key generation, validation, and organization context
"""

import secrets
import hashlib
import hmac
from datetime import datetime, timedelta
from typing import Optional, Tuple
from sqlalchemy.orm import Session
from app.multi_tenant_models import Organization, APIKey
from middleware.logging_config import get_logger

logger = get_logger("api_key_auth")

def generate_api_key(environment: str = "live") -> Tuple[str, str]:
    """
    Generate a new API key
    
    Args:
        environment: 'live' or 'test'
        
    Returns:
        Tuple of (full_key, key_prefix)
        Format: ff_{env}_{20_random_chars}
    """
    # Generate 20-character random string
    random_part = secrets.token_urlsafe(20)[:20]
    full_key = f"ff_{environment}_{random_part}"
    key_prefix = f"ff_{environment}_{random_part[:4]}"
    
    return full_key, key_prefix

def hash_api_key(api_key: str) -> str:
    """
    Hash an API key for storage (similar to password hashing)
    
    Args:
        api_key: The API key to hash
        
    Returns:
        Hashed key
    """
    return hashlib.sha256(api_key.encode()).hexdigest()

def verify_api_key(api_key: str, key_hash: str) -> bool:
    """
    Verify an API key against its hash
    
    Args:
        api_key: The API key to verify
        key_hash: The stored hash
        
    Returns:
        True if valid, False otherwise
    """
    computed_hash = hash_api_key(api_key)
    return hmac.compare_digest(computed_hash, key_hash)

def create_api_key(
    db: Session,
    organization_id: str,
    name: Optional[str] = None,
    expires_in_days: Optional[int] = None,
    created_by: Optional[str] = None,
    environment: str = "live"
) -> Tuple[str, APIKey]:
    """
    Create a new API key for an organization
    
    Args:
        db: Database session
        organization_id: Organization UUID
        name: Friendly name for the key
        expires_in_days: Days until expiration (None = no expiration)
        created_by: User ID who created the key
        environment: 'live' or 'test'
        
    Returns:
        Tuple of (full_key, APIKey object)
        Note: Full key is only returned once!
    """
    # Generate API key
    full_key, key_prefix = generate_api_key(environment)
    key_hash = hash_api_key(full_key)
    
    # Calculate expiration
    expires_at = None
    if expires_in_days:
        expires_at = datetime.utcnow() + timedelta(days=expires_in_days)
    
    # Create database record
    api_key = APIKey(
        organization_id=organization_id,
        key_hash=key_hash,
        key_prefix=key_prefix,
        name=name or f"API Key {datetime.utcnow().strftime('%Y-%m-%d')}",
        expires_at=expires_at,
        created_by=created_by
    )
    
    db.add(api_key)
    db.commit()
    db.refresh(api_key)
    
    logger.info(f"Created API key for organization {organization_id}: {key_prefix}...")
    
    return full_key, api_key

def authenticate_api_key(db: Session, api_key: str) -> Optional[Tuple[Organization, APIKey]]:
    """
    Authenticate an API key and return organization context
    
    Args:
        db: Database session
        api_key: The API key to authenticate
        
    Returns:
        Tuple of (Organization, APIKey) if valid, None otherwise
    """
    try:
        # Hash the provided key
        key_hash = hash_api_key(api_key)
        
        # Find matching API key
        api_key_obj = db.query(APIKey).filter(
            APIKey.key_hash == key_hash,
            APIKey.is_active == True
        ).first()
        
        if not api_key_obj:
            logger.warning("API key not found or inactive")
            return None
        
        # Check expiration
        if api_key_obj.expires_at and api_key_obj.expires_at < datetime.utcnow():
            logger.warning(f"API key expired: {api_key_obj.key_prefix}")
            return None
        
        # Get organization
        organization = db.query(Organization).filter(
            Organization.id == api_key_obj.organization_id,
            Organization.is_active == True
        ).first()
        
        if not organization:
            logger.warning(f"Organization not found or inactive: {api_key_obj.organization_id}")
            return None
        
        # Update last used timestamp
        api_key_obj.last_used_at = datetime.utcnow()
        db.commit()
        
        logger.info(f"API key authenticated: {api_key_obj.key_prefix} for org: {organization.name}")
        
        return organization, api_key_obj
        
    except Exception as e:
        logger.error(f"Error authenticating API key: {str(e)}")
        return None

def revoke_api_key(db: Session, api_key_id: str) -> bool:
    """
    Revoke an API key
    
    Args:
        db: Database session
        api_key_id: API key UUID
        
    Returns:
        True if revoked, False otherwise
    """
    try:
        api_key = db.query(APIKey).filter(APIKey.id == api_key_id).first()
        if not api_key:
            return False
        
        api_key.is_active = False
        db.commit()
        
        logger.info(f"API key revoked: {api_key.key_prefix}")
        return True
        
    except Exception as e:
        logger.error(f"Error revoking API key: {str(e)}")
        db.rollback()
        return False

def get_organization_by_slug(db: Session, slug: str) -> Optional[Organization]:
    """Get organization by slug"""
    return db.query(Organization).filter(
        Organization.slug == slug,
        Organization.is_active == True
    ).first()

def create_organization(
    db: Session,
    name: str,
    slug: str,
    contact_email: Optional[str] = None,
    rate_limit_per_hour: int = 1000
) -> Organization:
    """
    Create a new organization
    
    Args:
        db: Database session
        name: Organization name
        slug: URL-friendly identifier (must be unique)
        contact_email: Contact email
        rate_limit_per_hour: Rate limit per hour
        
    Returns:
        Organization object
    """
    organization = Organization(
        name=name,
        slug=slug,
        contact_email=contact_email,
        rate_limit_per_hour=rate_limit_per_hour
    )
    
    db.add(organization)
    db.commit()
    db.refresh(organization)
    
    logger.info(f"Created organization: {name} ({slug})")
    
    return organization

