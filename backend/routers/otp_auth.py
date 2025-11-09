"""
OTP-based Authentication Router
Handles OTP request, verification, and user registration/login
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import Optional
import os

from app.dependencies import get_db
from app.models import (
    OTPRequest,
    OTPResponse,
    UserRegistration,
    UserLogin,
    AuthenticationResponse,
    UserResponse,
    Country,
    UserInformationModel,
    CountryModel
)
from services.otp_service import create_otp, verify_otp, get_latest_otp, OTPCode
from services.email_service_otp import email_service
from services.auth_utils import (
    get_user_by_email,
    get_country_by_id
)
from middleware.logging_config import get_logger

logger = get_logger("auth.otp")

# Create router for OTP authentication
otp_auth_router = APIRouter(prefix="/auth/otp", tags=["Authentication - OTP"])

def create_user_without_pin(db: Session, name: str, email_id: str, country_id: str) -> UserInformationModel:
    """Create a new user without PIN (OTP-only authentication)"""
    db_user = UserInformationModel(
        name=name.strip(),
        email_id=email_id.lower().strip(),
        pin_hash=None,  # No PIN for OTP-only users
        country_id=country_id
    )
    
    db.add(db_user)
    db.flush()
    return db_user

@otp_auth_router.post("/request", response_model=OTPResponse)
async def request_otp(
    request: OTPRequest,
    db: Session = Depends(get_db)
):
    """
    Request an OTP code to be sent to email
    
    - **email_id**: Email address to send OTP
    - **purpose**: 'login', 'registration', or 'password_reset'
    
    Returns OTP code in development mode (when SMTP not configured)
    """
    logger.info(f"OTP request: {request.email_id} | Purpose: {request.purpose}")
    
    try:
        # For registration, check if email already exists
        if request.purpose == 'registration':
            existing_user = get_user_by_email(db, request.email_id)
            if existing_user:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Email address already registered"
                )
        
        # For login, check if user exists
        elif request.purpose == 'login':
            user = get_user_by_email(db, request.email_id)
            if not user:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Email address not found"
                )
            if not user.is_active:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Account is disabled. Please contact administrator."
                )
        
        # Generate and send OTP (with rate limiting)
        try:
            otp_code = create_otp(db, request.email_id, request.purpose)
        except ValueError as e:
            # Rate limit exceeded
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=str(e)
            )
        
        # Send email
        email_sent = email_service.send_otp(request.email_id, otp_code, request.purpose)
        
        if email_sent:
            # In development mode (email not configured), return OTP in response
            dev_mode = not email_service.enabled
            return OTPResponse(
                success=True,
                message=f"OTP sent to {request.email_id}" if not dev_mode else f"OTP generated (dev mode): {otp_code}",
                otp_code=otp_code if dev_mode else None
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to send OTP email. Please try again."
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"OTP request failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to request OTP: {str(e)}"
        )

@otp_auth_router.post("/register", response_model=AuthenticationResponse)
async def register_with_otp(
    user_data: UserRegistration,
    db: Session = Depends(get_db)
):
    """
    Register a new user with email and OTP verification
    
    - **name**: User's full name
    - **email_id**: Valid email address (unique)
    - **country_id**: Valid country UUID
    - **otp_code**: 6-digit OTP code sent to email
    """
    logger.info(f"User registration with OTP: {user_data.email_id} | Country: {user_data.country_id}")
    
    try:
        # Verify OTP
        if not verify_otp(db, user_data.email_id, user_data.otp_code, 'registration'):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid or expired OTP code"
            )
        
        # Check if email already exists
        existing_user = get_user_by_email(db, user_data.email_id)
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email address already registered"
            )
        
        # Verify country exists
        country = get_country_by_id(db, user_data.country_id)
        if not country:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid country selected"
            )
        
        # Create new user (without PIN)
        new_user = create_user_without_pin(
            db=db,
            name=user_data.name,
            email_id=user_data.email_id,
            country_id=user_data.country_id
        )
        
        db.commit()
        
        logger.info(f"User registered successfully: {user_data.email_id} | User ID: {new_user.id}")
        
        # Send welcome email
        email_service.send_welcome_email(user_data.email_id, user_data.name)
        
        # Prepare response
        user_response = UserResponse(
            id=str(new_user.id),
            name=new_user.name,
            email_id=new_user.email_id,
            country_id=str(new_user.country_id) if new_user.country_id else None,
            country=Country(
                id=str(country.id),
                name=country.name,
                country_code=country.country_code,
                currency=country.currency,
                is_active=country.is_active,
                created_at=country.created_at,
                updated_at=country.updated_at
            ) if country else None,
            is_admin=new_user.is_admin,
            is_superadmin=getattr(new_user, 'is_superadmin', False),
            country_admin_country_id=str(new_user.country_admin_country_id) if hasattr(new_user, 'country_admin_country_id') and new_user.country_admin_country_id else None,
            created_at=new_user.created_at,
            updated_at=new_user.updated_at
        )
        
        return AuthenticationResponse(
            success=True,
            message="User registered successfully",
            user=user_response
        )
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Registration failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Registration failed: {str(e)}"
        )

@otp_auth_router.post("/login", response_model=AuthenticationResponse)
async def login_with_otp(
    login_data: UserLogin,
    db: Session = Depends(get_db)
):
    """
    Authenticate user with email and OTP
    
    - **email_id**: Registered email address
    - **otp_code**: 6-digit OTP code sent to email
    """
    logger.info(f"Login attempt with OTP: {login_data.email_id}")
    
    try:
        # Get user
        user = get_user_by_email(db, login_data.email_id)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Email address not found"
            )
        
        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Account is disabled. Please contact administrator."
            )
        
        # Verify OTP
        if not verify_otp(db, login_data.email_id, login_data.otp_code, 'login'):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired OTP code"
            )
        
        logger.info(f"Login successful: {login_data.email_id} | User ID: {user.id}")
        
        # Get country information
        country = None
        if user.country_id:
            country_obj = get_country_by_id(db, str(user.country_id))
            if country_obj:
                country = Country(
                    id=str(country_obj.id),
                    name=country_obj.name,
                    country_code=country_obj.country_code,
                    currency=country_obj.currency,
                    is_active=country_obj.is_active,
                    created_at=country_obj.created_at,
                    updated_at=country_obj.updated_at
                )
        
        # Prepare response
        user_response = UserResponse(
            id=str(user.id),
            name=user.name,
            email_id=user.email_id,
            country_id=str(user.country_id) if user.country_id else None,
            country=country,
            is_admin=user.is_admin,
            is_superadmin=getattr(user, 'is_superadmin', False),
            country_admin_country_id=str(user.country_admin_country_id) if hasattr(user, 'country_admin_country_id') and user.country_admin_country_id else None,
            created_at=user.created_at,
            updated_at=user.updated_at
        )
        
        return AuthenticationResponse(
            success=True,
            message="Login successful",
            user=user_response
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Login failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Login failed: {str(e)}"
        )

