"""
Superadmin Router
Handles superadmin operations: creating country admins, managing users
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional
import os
import uuid

from app.dependencies import get_db
from app.models import (
    UserInformationModel,
    CountryModel,
    UserResponse,
    Country
)
from services.auth_utils import get_user_by_email, get_country_by_id
from services.email_service_otp import email_service
from services.otp_service import create_otp
from middleware.logging_config import get_logger

logger = get_logger("superadmin")

superadmin_router = APIRouter(prefix="/admin/superadmin", tags=["Admin - Superadmin"])

# Get superadmin emails from environment
SUPERADMIN_EMAILS = os.getenv('SUPERADMIN_EMAILS', '').split(',')
SUPERADMIN_EMAILS = [email.strip().lower() for email in SUPERADMIN_EMAILS if email.strip()]

def is_superadmin(email_id: str) -> bool:
    """Check if email is in superadmin list"""
    return email_id.lower().strip() in SUPERADMIN_EMAILS

def get_superadmin_user(db: Session, email_id: str) -> Optional[UserInformationModel]:
    """Get superadmin user, create if doesn't exist"""
    if not is_superadmin(email_id):
        return None
    
    user = get_user_by_email(db, email_id)
    if not user:
        # Create superadmin user if doesn't exist
        user = UserInformationModel(
            name="Superadmin",
            email_id=email_id.lower().strip(),
            pin_hash=None,  # OTP-only
            country_id=uuid.UUID('00000000-0000-0000-0000-000000000000'),  # Dummy country
            is_superadmin=True,
            is_admin=True,
            is_active=True
        )
        db.add(user)
        db.commit()
        db.refresh(user)
    else:
        # Ensure user is marked as superadmin
        if not user.is_superadmin:
            user.is_superadmin = True
            user.is_admin = True
            db.commit()
            db.refresh(user)
    
    return user

@superadmin_router.get("/check")
async def check_superadmin(
    email_id: str,
    db: Session = Depends(get_db)
):
    """Check if email is a superadmin"""
    return {
        "is_superadmin": is_superadmin(email_id),
        "email": email_id
    }

@superadmin_router.post("/create-country-admin")
async def create_country_admin(
    admin_email: str,
    admin_name: str,
    country_id: str,
    superadmin_email: str,  # Superadmin email for verification
    db: Session = Depends(get_db)
):
    """
    Create a country-level admin
    
    - **admin_email**: Email of the new country admin
    - **admin_name**: Name of the new country admin
    - **country_id**: Country UUID to assign admin to
    - **superadmin_email**: Superadmin email for verification
    """
    logger.info(f"Creating country admin: {admin_email} for country {country_id} by {superadmin_email}")
    
    # Verify superadmin
    superadmin = get_superadmin_user(db, superadmin_email)
    if not superadmin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Unauthorized: Not a superadmin"
        )
    
    # Verify country exists
    country = get_country_by_id(db, country_id)
    if not country:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid country ID"
        )
    
    # Check if user already exists
    existing_user = get_user_by_email(db, admin_email)
    if existing_user:
        # Update existing user to be country admin
        existing_user.country_admin_country_id = uuid.UUID(country_id)
        existing_user.is_admin = True
        existing_user.name = admin_name
        db.commit()
        db.refresh(existing_user)
        
        # Send OTP for first login
        try:
            otp_code = create_otp(db, admin_email, 'login')
        except ValueError as e:
            # Rate limit exceeded
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=str(e)
            )
        email_service.send_otp(admin_email, otp_code, 'login')
        
        return {
            "success": True,
            "message": f"User updated to country admin for {country.name}",
            "user": {
                "id": str(existing_user.id),
                "email": existing_user.email_id,
                "name": existing_user.name,
                "country_id": country_id,
                "country_name": country.name
            }
        }
    
    # Create new country admin user
    new_admin = UserInformationModel(
        name=admin_name,
        email_id=admin_email.lower().strip(),
        pin_hash=None,  # OTP-only
        country_id=uuid.UUID(country_id),
        country_admin_country_id=uuid.UUID(country_id),
        is_admin=True,
        is_superadmin=False,
        is_active=True
    )
    
    db.add(new_admin)
    db.commit()
    db.refresh(new_admin)
    
    # Send OTP for first login
    otp_code = create_otp(db, admin_email, 'login')
    email_service.send_otp(admin_email, otp_code, 'login')
    
    logger.info(f"Country admin created: {admin_email} for {country.name}")
    
    return {
        "success": True,
        "message": f"Country admin created for {country.name}",
        "user": {
            "id": str(new_admin.id),
            "email": new_admin.email_id,
            "name": new_admin.name,
            "country_id": country_id,
            "country_name": country.name
        },
        "otp_sent": True
    }

@superadmin_router.get("/country-admins")
async def list_country_admins(
    superadmin_email: str,
    db: Session = Depends(get_db)
):
    """List all country admins"""
    # Verify superadmin
    superadmin = get_superadmin_user(db, superadmin_email)
    if not superadmin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Unauthorized: Not a superadmin"
        )
    
    # Get all country admins
    country_admins = db.query(UserInformationModel).filter(
        UserInformationModel.country_admin_country_id.isnot(None),
        UserInformationModel.is_active == True
    ).all()
    
    result = []
    for admin in country_admins:
        country = get_country_by_id(db, str(admin.country_admin_country_id)) if admin.country_admin_country_id else None
        result.append({
            "id": str(admin.id),
            "name": admin.name,
            "email": admin.email_id,
            "country_id": str(admin.country_admin_country_id),
            "country_name": country.name if country else None,
            "is_active": admin.is_active,
            "created_at": admin.created_at.isoformat() if admin.created_at else None
        })
    
    return {
        "success": True,
        "count": len(result),
        "admins": result
    }

@superadmin_router.delete("/country-admin/{admin_id}")
async def remove_country_admin(
    admin_id: str,
    superadmin_email: str,
    db: Session = Depends(get_db)
):
    """Remove country admin (deactivate)"""
    # Verify superadmin
    superadmin = get_superadmin_user(db, superadmin_email)
    if not superadmin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Unauthorized: Not a superadmin"
        )
    
    # Get admin
    admin = db.query(UserInformationModel).filter(
        UserInformationModel.id == uuid.UUID(admin_id)
    ).first()
    
    if not admin:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Admin not found"
        )
    
    # Deactivate
    admin.is_active = False
    admin.country_admin_country_id = None
    admin.is_admin = False
    db.commit()
    
    return {
        "success": True,
        "message": f"Country admin {admin.email_id} deactivated"
    }

