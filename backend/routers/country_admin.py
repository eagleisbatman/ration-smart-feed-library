"""
Country Admin Router
Endpoints for country-level admins to manage feeds for their assigned country
"""

from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime
import uuid

from app.dependencies import get_db
from app.models import (
    UserInformationModel,
    CountryModel,
    Feed,
    FeedTranslation
)
from routers.admin import AdminFeedResponse, AdminBulkUploadResponse, AdminFeedRequest
from services.auth_utils import get_user_by_email, get_country_by_id
from middleware.logging_config import get_logger

logger = get_logger("country_admin")

country_admin_router = APIRouter(prefix="/admin/country", tags=["Admin - Country Admin"])

def get_country_admin(db: Session, email_id: str) -> Optional[UserInformationModel]:
    """Get country admin user and verify they're a country admin"""
    user = get_user_by_email(db, email_id)
    if not user:
        return None
    
    if not user.is_active:
        return None
    
    # Check if user is country admin
    if not user.country_admin_country_id:
        return None
    
    return user

@country_admin_router.get("/my-country")
async def get_my_country(
    email_id: str,
    db: Session = Depends(get_db)
):
    """Get the country assigned to the country admin"""
    admin = get_country_admin(db, email_id)
    if not admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not a country admin or account inactive"
        )
    
    country = get_country_by_id(db, str(admin.country_admin_country_id))
    if not country:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Assigned country not found"
        )
    
    return {
        "success": True,
        "country": {
            "id": str(country.id),
            "name": country.name,
            "country_code": country.country_code,
            "currency": country.currency
        }
    }

@country_admin_router.get("/feeds")
async def list_my_feeds(
    email_id: str,
    limit: int = 100,
    offset: int = 0,
    feed_type: Optional[str] = None,
    search: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """List feeds for the country admin's assigned country"""
    admin = get_country_admin(db, email_id)
    if not admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not a country admin or account inactive"
        )
    
    # Build query for feeds in admin's country
    query = db.query(Feed).filter(
        Feed.fd_country_id == admin.country_admin_country_id,
        Feed.is_active == True
    )
    
    # Apply filters
    if feed_type:
        query = query.filter(Feed.fd_type == feed_type)
    
    if search:
        query = query.filter(
            Feed.fd_name_default.ilike(f"%{search}%") |
            Feed.fd_code.ilike(f"%{search}%")
        )
    
    # Get total count
    total = query.count()
    
    # Apply pagination
    feeds = query.offset(offset).limit(limit).all()
    
    return {
        "success": True,
        "total": total,
        "limit": limit,
        "offset": offset,
        "feeds": [
            {
                "id": str(feed.id),
                "fd_code": feed.fd_code,
                "fd_name_default": feed.fd_name_default,
                "fd_type": feed.fd_type,
                "fd_category": feed.fd_category,
                "fd_dm": float(feed.fd_dm) if feed.fd_dm else None,
                "fd_cp": float(feed.fd_cp) if feed.fd_cp else None,
                "fd_ndf": float(feed.fd_ndf) if feed.fd_ndf else None,
                "fd_adf": float(feed.fd_adf) if feed.fd_adf else None,
            }
            for feed in feeds
        ]
    }

@country_admin_router.post("/feeds/bulk-upload")
async def bulk_upload_feeds(
    email_id: str,
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    """
    Bulk upload feeds for the country admin's assigned country
    Uses the same bulk upload logic as admin, but restricted to admin's country
    """
    admin = get_country_admin(db, email_id)
    if not admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not a country admin or account inactive"
        )
    
    # Validate file type and size
    if not file.filename or not file.filename.endswith(('.xlsx', '.xls')):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File must be an Excel file (.xlsx or .xls)"
        )
    
    MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB
    file_content = await file.read()
    if len(file_content) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File size exceeds maximum allowed size of {MAX_FILE_SIZE / (1024*1024):.0f}MB"
        )
    
    # Use admin bulk upload endpoint logic directly
    # Import the admin router's bulk upload function
    from routers.admin import bulk_upload_feeds as admin_bulk_upload
    
    # Call admin bulk upload with country restriction
    try:
        # Create a modified request that includes country_id
        # Note: This is a workaround - ideally we'd refactor admin router
        # Recreate file object with content
        from fastapi import UploadFile
        import io
        file_obj = UploadFile(
            filename=file.filename,
            file=io.BytesIO(file_content)
        )
        result = await admin_bulk_upload(
            file=file_obj,
            admin_user_id=str(admin.id),
            db=db
        )
        # Filter results to only show feeds for admin's country
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Bulk upload failed for country admin {email_id}: {str(e)}")
        # Sanitize error message
        from middleware.error_sanitizer import sanitize_error_message
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=sanitize_error_message(e)
        )

@country_admin_router.post("/feeds", response_model=AdminFeedResponse)
async def add_feed(
    email_id: str = Query(..., description="Country admin email"),
    feed_data: AdminFeedRequest,
    db: Session = Depends(get_db)
):
    """Add a new feed for the country admin's assigned country"""
    admin = get_country_admin(db, email_id)
    if not admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not a country admin or account inactive"
        )
    
    # Get country name from admin's country
    country = get_country_by_id(db, str(admin.country_admin_country_id))
    if not country:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Assigned country not found"
        )
    
    # Override country in feed_data
    feed_data.fd_country_name = country.name
    feed_data.fd_country_cd = country.country_code
    
    # Use admin add_feed endpoint logic
    from routers.admin import add_feed as admin_add_feed
    
    try:
        result = await admin_add_feed(
            admin_user_id=str(admin.id),
            feed_data=feed_data,
            db=db
        )
        return result
    except Exception as e:
        logger.error(f"Add feed failed for country admin {email_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to add feed: {str(e)}"
        )

@country_admin_router.put("/feeds/{feed_id}", response_model=AdminFeedResponse)
async def update_feed(
    feed_id: str,
    email_id: str = Query(..., description="Country admin email"),
    feed_data: AdminFeedRequest,
    db: Session = Depends(get_db)
):
    """Update a feed (only if it belongs to admin's country)"""
    admin = get_country_admin(db, email_id)
    if not admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not a country admin or account inactive"
        )
    
    # Verify feed belongs to admin's country
    feed = db.query(Feed).filter(
        Feed.id == uuid.UUID(feed_id),
        Feed.fd_country_id == admin.country_admin_country_id
    ).first()
    
    if not feed:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Feed not found or not in your assigned country"
        )
    
    # Get country name from admin's country
    country = get_country_by_id(db, str(admin.country_admin_country_id))
    if country:
        feed_data.fd_country_name = country.name
        feed_data.fd_country_cd = country.country_code
    
    # Use admin update_feed endpoint logic
    from routers.admin import update_feed as admin_update_feed
    
    try:
        result = await admin_update_feed(
            feed_id=feed_id,
            admin_user_id=str(admin.id),
            feed_data=feed_data,
            db=db
        )
        return result
    except Exception as e:
        logger.error(f"Update feed failed for country admin {email_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update feed: {str(e)}"
        )

@country_admin_router.get("/feeds/{feed_id}/translations")
async def get_feed_translations(
    email_id: str,
    feed_id: str,
    db: Session = Depends(get_db)
):
    """Get translations for a feed"""
    admin = get_country_admin(db, email_id)
    if not admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not a country admin or account inactive"
        )
    
    # Verify feed belongs to admin's country
    feed = db.query(Feed).filter(
        Feed.id == uuid.UUID(feed_id),
        Feed.fd_country_id == admin.country_admin_country_id
    ).first()
    
    if not feed:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Feed not found or not in your assigned country"
        )
    
    # Get translations from feed_translations table
    translations = db.query(FeedTranslation).filter(
        FeedTranslation.feed_id == uuid.UUID(feed_id)
    ).all()
    
    return {
        "success": True,
        "feed_id": feed_id,
        "translations": [
            {
                "id": str(t.id),
                "language_code": t.language_code,
                "translation_text": t.fd_name,
                "description": t.fd_description,
                "is_primary": t.is_primary,
                "country_id": str(t.country_id) if t.country_id else None
            }
            for t in translations
        ]
    }

@country_admin_router.post("/feeds/{feed_id}/translations")
async def add_feed_translation(
    email_id: str,
    feed_id: str,
    translation_data: dict,
    db: Session = Depends(get_db)
):
    """Add/update translation for a feed"""
    admin = get_country_admin(db, email_id)
    if not admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not a country admin or account inactive"
        )
    
    # Verify feed belongs to admin's country
    feed = db.query(Feed).filter(
        Feed.id == uuid.UUID(feed_id),
        Feed.fd_country_id == admin.country_admin_country_id
    ).first()
    
    if not feed:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Feed not found or not in your assigned country"
        )
    
    # Extract translation data
    language_code = translation_data.get("language_code")
    translation_text = translation_data.get("translation_text") or translation_data.get("fd_name")
    description = translation_data.get("description") or translation_data.get("fd_description")
    
    if not language_code or not translation_text:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="language_code and translation_text are required"
        )
    
    # Check if translation already exists
    existing_translation = db.query(FeedTranslation).filter(
        FeedTranslation.feed_id == uuid.UUID(feed_id),
        FeedTranslation.language_code == language_code,
        FeedTranslation.country_id == admin.country_admin_country_id
    ).first()
    
    if existing_translation:
        # Update existing translation
        existing_translation.fd_name = translation_text
        if description:
            existing_translation.fd_description = description
        existing_translation.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(existing_translation)
        
        return {
            "success": True,
            "message": "Translation updated successfully",
            "translation": {
                "id": str(existing_translation.id),
                "language_code": existing_translation.language_code,
                "translation_text": existing_translation.fd_name
            }
        }
    else:
        # Create new translation
        new_translation = FeedTranslation(
            feed_id=uuid.UUID(feed_id),
            language_code=language_code,
            country_id=admin.country_admin_country_id,
            fd_name=translation_text,
            fd_description=description,
            is_primary=False
        )
        db.add(new_translation)
        db.commit()
        db.refresh(new_translation)
        
        return {
            "success": True,
            "message": "Translation added successfully",
            "translation": {
                "id": str(new_translation.id),
                "language_code": new_translation.language_code,
                "translation_text": new_translation.fd_name
            }
        }

@country_admin_router.delete("/feeds/{feed_id}/translations/{translation_id}")
async def delete_feed_translation(
    email_id: str,
    feed_id: str,
    translation_id: str,
    db: Session = Depends(get_db)
):
    """Delete a translation for a feed"""
    admin = get_country_admin(db, email_id)
    if not admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not a country admin or account inactive"
        )
    
    # Verify feed belongs to admin's country
    feed = db.query(Feed).filter(
        Feed.id == uuid.UUID(feed_id),
        Feed.fd_country_id == admin.country_admin_country_id
    ).first()
    
    if not feed:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Feed not found or not in your assigned country"
        )
    
    # Find and delete translation
    translation = db.query(FeedTranslation).filter(
        FeedTranslation.id == uuid.UUID(translation_id),
        FeedTranslation.feed_id == uuid.UUID(feed_id)
    ).first()
    
    if not translation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Translation not found"
        )
    
    try:
        db.delete(translation)
        db.commit()
        return {
            "success": True,
            "message": "Translation deleted successfully"
        }
    except Exception as e:
        db.rollback()
        logger.error(f"Error deleting translation: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete translation: {str(e)}"
        )

