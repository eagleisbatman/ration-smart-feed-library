"""
Authentication Router for Feed Formulation Backend
Handles user registration, login, and country management endpoints
"""

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from typing import List
from datetime import datetime
import uuid

from app.dependencies import get_db
from app.models import (
    UserRegistration, 
    UserLogin, 
    AuthenticationResponse, 
    UserResponse, 
    Country,
    UserInformationModel,
    CountryModel,
    ForgotPinRequest,
    ForgotPinResponse,
    ChangePinRequest,
    ChangePinResponse,
    UserDeleteAccountResponse,
    CountryLanguage
)
from app.models import UserUpdateRequest
from services.auth_utils import (
    create_user, 
    authenticate_user, 
    get_user_by_email, 
    get_country_by_id, 
    get_all_countries,
    forgot_pin_direct,
    change_user_pin,
    deactivate_user_account,
    verify_pin
)
from services.email_service import email_service
from middleware.logging_config import get_logger, log_error

# Initialize logger
logger = get_logger("auth.router")

# Create router instance
auth_router = APIRouter(prefix="/auth", tags=["Authentication"])

@auth_router.post("/register", response_model=AuthenticationResponse)
async def register_user(
    user_data: UserRegistration,
    db: Session = Depends(get_db)
):
    """
    Register a new user with email and PIN
    
    - **name**: User's full name (1-100 characters)
    - **email_id**: Valid email address (unique)
    - **pin**: Exactly 4 digits (0000-9999)
    - **country_id**: Valid country UUID from /auth/countries
    """
    logger.info(f"User registration attempt: {user_data.email_id} | Country: {user_data.country_id}")
    
    try:
        # Check if email already exists
        existing_user = get_user_by_email(db, user_data.email_id)
        if existing_user:
            logger.warning(f"Registration failed - Email already exists: {user_data.email_id}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email address already registered"
            )
        
        # Verify country exists
        country = get_country_by_id(db, user_data.country_id)
        if not country:
            logger.warning(f"Registration failed - Invalid country: {user_data.country_id}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid country selected"
            )
        
        # Create new user
        new_user = create_user(
            db=db,
            name=user_data.name,
            email_id=user_data.email_id,
            pin=user_data.pin,
            country_id=user_data.country_id
        )
        
        # Explicit commit to ensure data is saved
        db.commit()
        
        logger.info(f"User registered successfully: {user_data.email_id} | User ID: {new_user.id}")
        
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
            created_at=new_user.created_at,
            updated_at=new_user.updated_at
        )
        
        return AuthenticationResponse(
            success=True,
            message="User registered successfully",
            user=user_response
        )
        
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email address already registered"
        )
    except HTTPException as http_exc:
        # Re-raise HTTP exceptions (like duplicate email)
        db.rollback()
        raise http_exc
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Registration failed: {str(e)}"
        )

@auth_router.post("/login", response_model=AuthenticationResponse)
async def login_user(
    login_data: UserLogin,
    db: Session = Depends(get_db)
):
    """
    Authenticate user with email and PIN
    
    - **email_id**: Registered email address
    - **pin**: 4-digit PIN
    """
    logger.info(f"Login attempt: {login_data.email_id}")
    
    try:
        # Authenticate user with specific error messages
        user, error_message = authenticate_user(db, login_data.email_id, login_data.pin)
        
        if not user:
            logger.warning(f"Login failed - {error_message}: {login_data.email_id}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=error_message
            )
        
        logger.info(f"Login successful: {login_data.email_id} | User ID: {user.id}")
        
        # Get country information if available
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
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Login failed: {str(e)}"
        )

@auth_router.get("/countries")
async def get_countries(db: Session = Depends(get_db)):
    """
    Get all active countries for registration dropdown
    
    Returns list of active countries with:
    - **id**: Country UUID 
    - **name**: Country name
    - **country_code**: ISO 3-letter country code
    - **currency**: Country currency code (e.g., USD, EUR, INR)
    - **is_active**: Boolean flag indicating if country is active for registration
    """
    try:
        countries = get_all_countries(db)
        
        # Get country languages for each country
        result = []
        for country in countries:
            # Fetch country languages
            country_languages = db.query(CountryLanguage).filter(
                CountryLanguage.country_id == country.id,
                CountryLanguage.is_active == True
            ).all()
            
            # Build country response with languages
            country_dict = {
                "id": str(country.id),
                "name": country.name,
                "country_code": country.country_code,
                "currency": country.currency,
                "is_active": country.is_active,
                "created_at": country.created_at,
                "updated_at": country.updated_at,
                "supported_languages": country.supported_languages if hasattr(country, 'supported_languages') else ["en"],
                "country_languages": [
                    {
                        "id": str(lang.id),
                        "language_code": lang.language_code,
                        "language_name": lang.language_name,
                        "is_default": lang.is_default,
                        "is_active": lang.is_active
                    }
                    for lang in country_languages
                ]
            }
            result.append(country_dict)
        
        return result
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch countries: {str(e)}"
        )

@auth_router.get("/user/{email_id}", response_model=UserResponse)
async def get_user_info(
    email_id: str,
    db: Session = Depends(get_db)
):
    """
    Get user information by email (for testing purposes)
    
    - **email_id**: User's email address
    """
    try:
        user = get_user_by_email(db, email_id)
        
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        # Get country information if available
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
        
        return UserResponse(
            id=str(user.id),
            name=user.name,
            email_id=user.email_id,
            country_id=str(user.country_id) if user.country_id else None,
            country=country,
            is_admin=user.is_admin,
            created_at=user.created_at,
            updated_at=user.updated_at
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch user: {str(e)}"
        )

@auth_router.put("/user/{email_id}", response_model=UserResponse)
async def update_user_profile(
    email_id: str,
    user_update: UserUpdateRequest,
    db: Session = Depends(get_db)
):
    """
    Update user profile information (name and/or country)
    
    - **email_id**: User's email address (path parameter)
    - **name**: Optional updated name (if null, name won't be updated)
    - **country_id**: Optional updated country UUID (if null, country won't be updated)
    
    Features:
    - Partial updates: Only provided fields are updated
    - Email validation: Ensures user exists
    - Country validation: Ensures country exists if provided
    - Returns complete updated user information
    """
    try:
        logger.info(f"User profile update request: {email_id}")
        
        # Find the user by email
        user = get_user_by_email(db, email_id)
        if not user:
            logger.warning(f"User profile update failed - User not found: {email_id}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        # Track what fields are being updated
        updated_fields = []
        
        # Update name if provided
        if user_update.name is not None:
            user.name = user_update.name.strip()
            updated_fields.append("name")
            logger.info(f"Updating name for user {email_id}")
        
        # Update country if provided
        if user_update.country_id is not None:
            # Validate country exists
            country = get_country_by_id(db, user_update.country_id)
            if not country:
                logger.warning(f"User profile update failed - Invalid country: {user_update.country_id}")
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid country selected"
                )
            user.country_id = user_update.country_id
            updated_fields.append("country")
            logger.info(f"Updating country for user {email_id} to {country.name}")
        
        # Update the timestamp
        user.updated_at = datetime.utcnow()
        
        # Commit changes
        db.commit()
        
        logger.info(f"User profile updated successfully: {email_id} | Updated fields: {updated_fields}")
        
        # Get updated country information
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
        
        # Return complete user information
        return UserResponse(
            id=str(user.id),
            name=user.name,
            email_id=user.email_id,
            country_id=str(user.country_id) if user.country_id else None,
            country=country,
            created_at=user.created_at,
            updated_at=user.updated_at
        )
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"User profile update failed: {email_id} | Error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update user profile: {str(e)}"
        )

@auth_router.post("/forgot-pin", response_model=ForgotPinResponse)
async def forgot_pin(
    request: ForgotPinRequest,
    db: Session = Depends(get_db)
):
    """
    Reset user's PIN by sending new PIN to registered email
    
    - **email_id**: Registered email address
    
    Simple Process:
    1. Validates email exists in system & correct format
    2. Generates new random 4-digit PIN
    3. Immediately updates user's PIN in database
    4. Sends new PIN to user's email
    5. User can login with new PIN right away
    """
    try:
        # Process forgot PIN request - this updates the PIN immediately
        success, message, new_pin = forgot_pin_direct(db, request.email_id)
        
        if not success:
            # Handle different error cases
            if "not found" in message.lower():
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=message
                )
            else:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=message
                )
        
        # Get user information for email
        user = get_user_by_email(db, request.email_id)
        
        # Send email with new PIN
        email_sent = await email_service.send_pin_reset_email(
            to_email=user.email_id,
            user_name=user.name,
            new_pin=new_pin
        )
        
        if email_sent:
            # Commit the PIN change to database
            db.commit()
            
            return ForgotPinResponse(
                success=True,
                message=f"New PIN sent to {user.email_id}. Please check your email.",
                new_pin=new_pin  # Include in response for development/testing
            )
        else:
            # Email failed - rollback the PIN change
            db.rollback()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to send email. Please try again later."
            )
            
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"PIN reset failed: {str(e)}"
        )

@auth_router.post("/change-pin", response_model=ChangePinResponse)
async def change_pin(
    request: ChangePinRequest,
    db: Session = Depends(get_db)
):
    """
    Change user's PIN (requires current PIN verification)
    
    - **email_id**: User's email address
    - **current_pin**: Current 4-digit PIN for verification
    - **new_pin**: New 4-digit PIN to set
    
    Security:
    - Requires current PIN for verification
    - New PIN must be different from current PIN
    - PIN is hashed before storage
    """
    try:
        # Validate that new PIN is different from current PIN
        if request.current_pin == request.new_pin:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="New PIN must be different from current PIN"
            )
        
        # Change PIN
        success, message = change_user_pin(
            db, 
            request.email_id, 
            request.current_pin, 
            request.new_pin
        )
        
        if success:
            db.commit()
            return ChangePinResponse(
                success=True,
                message=message
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=message
            )
            
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"PIN change failed: {str(e)}"
        )

@auth_router.get("/email-config")
async def get_email_config():
    """
    Get email service configuration status (for admin/testing)
    """
    return email_service.test_email_configuration()

@auth_router.post("/user-delete-account", response_model=UserDeleteAccountResponse)
async def user_delete_account(
    user_id: str = Query(..., description="User UUID to deactivate"),
    pin: str = Query(..., min_length=4, max_length=4, description="4-digit PIN for authentication"),
    db: Session = Depends(get_db)
):
    """
    Deactivate user account (soft delete by setting is_active to false)
    
    - **user_id**: User UUID to deactivate
    - **pin**: 4-digit PIN for authentication
    
    Security:
    - User can only deactivate their own account
    - PIN verification required
    - Sets is_active to false (soft delete)
    
    Note: Only admins can reactivate accounts using separate admin endpoints
    """
    logger.info(f"User account deactivation attempt: {user_id}")
    
    try:
        # Verify user exists and get user information
        user = db.query(UserInformationModel).filter(
            UserInformationModel.id == uuid.UUID(user_id)
        ).first()
        
        if not user:
            logger.warning(f"Account deactivation failed - User not found: {user_id}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        # SECURITY CHECK: Verify PIN matches for the specific user
        # Logic: 1. Get user by user_id, 2. Verify PIN matches for that user, 3. Proceed with deletion
        
        if not verify_pin(pin, user.pin_hash):
            logger.warning(f"Account deactivation failed - PIN does not match for user {user_id}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid PIN"
            )
        
        # Check if account is already inactive
        if not user.is_active:
            logger.info(f"Account already inactive: {user_id}")
            return UserDeleteAccountResponse(
                success=True,
                message="Account is already inactive",
                user_id=str(user.id),
                user_name=user.name,
                user_email=user.email_id,
                deactivated_at=user.updated_at
            )
        
        # Deactivate the account
        success, message = deactivate_user_account(db, user_id)
        
        if success:
            db.commit()
            logger.info(f"User account deactivated successfully: {user_id} | User: {user.name}")
            
            return UserDeleteAccountResponse(
                success=True,
                message=message,
                user_id=str(user.id),
                user_name=user.name,
                user_email=user.email_id,
                deactivated_at=datetime.utcnow()
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=message
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Account deactivation failed: {str(e)}")
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Account deactivation failed: {str(e)}"
        ) 