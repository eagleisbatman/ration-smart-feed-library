"""
Admin Router for Feed Formulation Backend
Handles admin-specific operations including user management
"""

from fastapi import APIRouter, Depends, HTTPException, status, Query, File, UploadFile
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy import func
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
import uuid
import pandas as pd
import io
from app.utils import round_numeric_value, clean_data_for_json, round_feed_data
from app.bulk_import_logger import BulkImportLogger
from services.aws_service import AWSService

from app.dependencies import get_db
from app.models import (
    UserInformationModel,
    CountryModel,
    AdminUserListItem,
    AdminUserListResponse,
    AdminUserToggleRequest,
    AdminUserToggleResponse,
    FeedType,
    FeedCategory,
    Feed,
    CustomFeed,
    AdminFeedTypeRequest,
    AdminFeedTypeResponse,
    AdminFeedCategoryRequest,
    AdminFeedCategoryResponse,
    AdminFeedRequest,
    AdminFeedResponse,
    AdminFeedListResponse,
    AdminBulkUploadResponse,
    AdminExportResponse,
    AdminBulkLogResponse,
    FeedTypeResponse,
    FeedCategoryResponse,
    FeedDetailsResponse,
    UserFeedback,
    AdminFeedbackResponse,
    AdminFeedbackListResponse,
    FeedbackStatsResponse,
    Report,
    AdminGetAllReportsRequest,
    AdminGetAllReportsResponse,
    AdminReportItem
)
from services.auth_utils import is_admin_user
from middleware.logging_config import get_logger, log_error

# Helper function for optimized admin verification
def verify_admin_user(db: Session, admin_user_id: str) -> bool:
    """
    Optimized admin user verification that only selects required fields.
    Returns True if user is admin, False otherwise.
    """
    try:
        # Convert string to UUID
        admin_uuid = uuid.UUID(admin_user_id)
        admin_user = db.query(UserInformationModel.id, UserInformationModel.is_admin).filter(
            UserInformationModel.id == admin_uuid,
            UserInformationModel.is_admin == True
        ).first()
        return admin_user is not None
    except (ValueError, TypeError) as e:
        logger.error(f"Invalid UUID format for admin_user_id: {admin_user_id}, error: {e}")
        return False
    except Exception as e:
        logger.error(f"Error verifying admin user: {e}")
        return False

# Initialize logger
logger = get_logger("admin.router")

# Create router instance
admin_router = APIRouter(prefix="/admin", tags=["Admin"])

@admin_router.get("/users", response_model=AdminUserListResponse, tags=["Admin - User Management"])
async def get_all_users(
    admin_user_id: str = Query(..., description="Admin user UUID for authentication"),
    page: int = Query(1, ge=1, description="Page number (starts from 1)"),
    page_size: int = Query(20, ge=1, le=100, description="Number of users per page (max 100)"),
    country_filter: Optional[str] = Query(None, description="Filter by country name"),
    status_filter: Optional[str] = Query(None, description="Filter by status: 'active' or 'inactive'"),
    search: Optional[str] = Query(None, description="Search by name or email"),
    db: Session = Depends(get_db)
):
    """
    Get all registered users (Admin only)
    
    - **admin_user_id**: Admin user UUID for authentication
    - **page**: Page number for pagination (default: 1)
    - **page_size**: Number of users per page (default: 20, max: 100)
    - **country_filter**: Filter users by country name
    - **status_filter**: Filter users by status ('active' or 'inactive')
    - **search**: Search users by name or email (case-insensitive)
    """
    logger.info(f"Admin user list request by admin: {admin_user_id}")
    
    try:
        # Verify admin user exists and has admin privileges
        admin_user = db.query(UserInformationModel).filter(
            UserInformationModel.id == uuid.UUID(admin_user_id),
            UserInformationModel.is_admin == True
        ).first()
        
        if not admin_user:
            logger.warning(f"Unauthorized access attempt to admin endpoint: {admin_user_id}")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Admin privileges required"
            )
        
        # Build query with joins
        query = db.query(
            UserInformationModel,
            CountryModel.name.label('country_name')
        ).join(
            CountryModel,
            UserInformationModel.country_id == CountryModel.id
        )
        
        # Apply filters
        if country_filter:
            query = query.filter(CountryModel.name.ilike(f"%{country_filter}%"))
        
        if status_filter:
            if status_filter.lower() == 'active':
                query = query.filter(UserInformationModel.is_active == True)
            elif status_filter.lower() == 'inactive':
                query = query.filter(UserInformationModel.is_active == False)
        
        if search:
            search_term = f"%{search}%"
            query = query.filter(
                (UserInformationModel.name.ilike(search_term)) |
                (UserInformationModel.email_id.ilike(search_term))
            )
        
        # Get total count for pagination
        total_count = query.count()
        
        # Apply pagination
        offset = (page - 1) * page_size
        query = query.offset(offset).limit(page_size)
        
        # Execute query
        results = query.all()
        
        # Convert to response format
        users = []
        for user, country_name in results:
            users.append(AdminUserListItem(
                id=str(user.id),
                name=user.name,
                email_id=user.email_id,
                country=country_name,
                is_active=user.is_active,
                is_admin=user.is_admin,
                created_at=user.created_at
            ))
        
        # Calculate pagination info
        total_pages = (total_count + page_size - 1) // page_size
        
        logger.info(f"Admin user list retrieved successfully. Total users: {total_count}, Page: {page}/{total_pages}")
        
        return AdminUserListResponse(
            success=True,
            message=f"Retrieved {len(users)} users successfully",
            users=users,
            total_count=total_count,
            page=page,
            page_size=page_size,
            total_pages=total_pages
        )
        
    except SQLAlchemyError as e:
        logger.error(f"Database error during admin user list: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve users"
        )
    except Exception as e:
        logger.error(f"Unexpected error during admin user list: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )

@admin_router.put("/update-feed/{feed_id}", response_model=AdminFeedResponse, tags=["Admin - Feed Management"])
async def update_feed(
    feed_id: str,
    feed_data: AdminFeedRequest,
    admin_user_id: str = Query(..., description="Admin user UUID for authentication"),
    db: Session = Depends(get_db)
):
    """
    Update an existing feed (Admin only)
    
    - **feed_id**: Feed UUID to update
    - **feed_data**: Updated feed details
    - **admin_user_id**: Admin user UUID for authentication
    """
    logger.info(f"Update feed request by admin: {admin_user_id} for feed: {feed_id}")
    
    try:
        # Verify admin user exists and has admin privileges
        admin_user = db.query(UserInformationModel).filter(
            UserInformationModel.id == uuid.UUID(admin_user_id),
            UserInformationModel.is_admin == True
        ).first()
        
        if not admin_user:
            logger.warning(f"Unauthorized access attempt to admin endpoint: {admin_user_id}")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Admin privileges required"
            )
        
        # Get existing feed
        feed = db.query(Feed).filter(Feed.id == uuid.UUID(feed_id)).first()
        
        if not feed:
            logger.warning(f"Feed not found: {feed_id}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Feed not found"
            )
        
        # Check if updated combination already exists (excluding current feed)
        existing_feed = db.query(Feed).filter(
            Feed.fd_name_default == feed_data.fd_name,  # Use fd_name_default for new schema
            Feed.fd_type == feed_data.fd_type,
            Feed.fd_category == feed_data.fd_category,
            Feed.fd_country_name == feed_data.fd_country_name,
            Feed.id != uuid.UUID(feed_id)
        ).first()
        
        if existing_feed:
            logger.warning(f"Feed already exists with updated combination: {feed_data.fd_name}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Feed already exists with this name, type, category, and country combination"
            )
        
        # Get country ID from country name
        country = db.query(CountryModel).filter(
            CountryModel.name == feed_data.fd_country_name
        ).first()
        
        if not country:
            logger.warning(f"Country not found: {feed_data.fd_country_name}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Country not found"
            )
        
        # Update feed attributes
        feed.fd_code = feed_data.fd_code
        feed.fd_name = feed_data.fd_name  # Legacy field
        feed.fd_name_default = feed_data.fd_name  # Map to new schema field
        feed.fd_category = feed_data.fd_category
        feed.fd_type = feed_data.fd_type
        feed.fd_country_id = country.id
        feed.fd_country_name = feed_data.fd_country_name
        feed.fd_country_cd = feed_data.fd_country_cd
        feed.fd_dm = str(feed_data.fd_dm) if feed_data.fd_dm is not None else None
        feed.fd_ash = str(feed_data.fd_ash) if feed_data.fd_ash is not None else None
        feed.fd_cp = str(feed_data.fd_cp) if feed_data.fd_cp is not None else None
        feed.fd_npn_cp = feed_data.fd_npn_cp
        feed.fd_ee = str(feed_data.fd_ee) if feed_data.fd_ee is not None else None
        feed.fd_cf = str(feed_data.fd_cf) if feed_data.fd_cf is not None else None
        feed.fd_nfe = str(feed_data.fd_nfe) if feed_data.fd_nfe is not None else None
        feed.fd_st = str(feed_data.fd_st) if feed_data.fd_st is not None else None
        feed.fd_ndf = str(feed_data.fd_ndf) if feed_data.fd_ndf is not None else None
        feed.fd_hemicellulose = str(feed_data.fd_hemicellulose) if feed_data.fd_hemicellulose is not None else None
        feed.fd_adf = str(feed_data.fd_adf) if feed_data.fd_adf is not None else None
        feed.fd_cellulose = str(feed_data.fd_cellulose) if feed_data.fd_cellulose is not None else None
        feed.fd_lg = str(feed_data.fd_lg) if feed_data.fd_lg is not None else None
        feed.fd_ndin = str(feed_data.fd_ndin) if feed_data.fd_ndin is not None else None
        feed.fd_adin = str(feed_data.fd_adin) if feed_data.fd_adin is not None else None
        feed.fd_ca = str(feed_data.fd_ca) if feed_data.fd_ca is not None else None
        feed.fd_p = str(feed_data.fd_p) if feed_data.fd_p is not None else None
        feed.fd_season = feed_data.fd_season
        feed.fd_orginin = feed_data.fd_orginin
        feed.fd_ipb_local_lab = feed_data.fd_ipb_local_lab
        feed.updated_at = datetime.utcnow()
        
        db.commit()
        db.refresh(feed)
        
        logger.info(f"Feed updated successfully: {feed.fd_name}")
        
        # Create response
        feed_response = FeedDetailsResponse(
            feed_id=str(feed.id),
            fd_code=feed.fd_code,
            fd_name=feed.fd_name_default if hasattr(feed, 'fd_name_default') and feed.fd_name_default else feed.fd_name,  # Use fd_name_default if available
            fd_type=feed.fd_type,
            fd_category=feed.fd_category,
            fd_country_id=str(feed.fd_country_id) if feed.fd_country_id else None,
            fd_country_name=feed.fd_country_name,
            fd_country_cd=feed.fd_country_cd,
            fd_dm=float(feed.fd_dm) if feed.fd_dm is not None else None,
            fd_ash=float(feed.fd_ash) if feed.fd_ash is not None else None,
            fd_cp=float(feed.fd_cp) if feed.fd_cp is not None else None,
            fd_ee=float(feed.fd_ee) if feed.fd_ee is not None else None,
            fd_st=float(feed.fd_st) if feed.fd_st is not None else None,
            fd_ndf=float(feed.fd_ndf) if feed.fd_ndf is not None else None,
            fd_adf=float(feed.fd_adf) if feed.fd_adf is not None else None,
            fd_lg=float(feed.fd_lg) if feed.fd_lg is not None else None,
            fd_ndin=float(feed.fd_ndin) if feed.fd_ndin is not None else None,
            fd_adin=float(feed.fd_adin) if feed.fd_adin is not None else None,
            fd_ca=float(feed.fd_ca) if feed.fd_ca is not None else None,
            fd_p=float(feed.fd_p) if feed.fd_p is not None else None,
            fd_cf=float(feed.fd_cf) if feed.fd_cf is not None else None,
            fd_nfe=float(feed.fd_nfe) if feed.fd_nfe is not None else None,
            fd_hemicellulose=float(feed.fd_hemicellulose) if feed.fd_hemicellulose is not None else None,
            fd_cellulose=float(feed.fd_cellulose) if feed.fd_cellulose is not None else None,
            fd_npn_cp=feed.fd_npn_cp,
            fd_season=feed.fd_season,
            fd_orginin=feed.fd_orginin,
            fd_ipb_local_lab=feed.fd_ipb_local_lab,
            created_at=feed.created_at,
            updated_at=feed.updated_at
        )
        
        return AdminFeedResponse(
            success=True,
            message=f"Feed '{feed.fd_name}' updated successfully",
            feed=feed_response
        )
        
    except HTTPException:
        raise
    except SQLAlchemyError as e:
        logger.error(f"Database error during feed update: {str(e)}")
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update feed"
        )
    except Exception as e:
        logger.error(f"Unexpected error during feed update: {str(e)}")
        if 'db' in locals():
            db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )

@admin_router.delete("/delete-feed/{feed_id}", response_model=AdminFeedResponse, tags=["Admin - Feed Management"])
async def delete_feed(
    feed_id: str,
    admin_user_id: str = Query(..., description="Admin user UUID for authentication"),
    db: Session = Depends(get_db)
):
    """
    Delete a feed (Admin only)
    
    - **feed_id**: Feed UUID to delete
    - **admin_user_id**: Admin user UUID for authentication
    """
    logger.info(f"Delete feed request by admin: {admin_user_id} for feed: {feed_id}")
    
    try:
        # Verify admin user exists and has admin privileges
        admin_user = db.query(UserInformationModel).filter(
            UserInformationModel.id == uuid.UUID(admin_user_id),
            UserInformationModel.is_admin == True
        ).first()
        
        if not admin_user:
            logger.warning(f"Unauthorized access attempt to admin endpoint: {admin_user_id}")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Admin privileges required"
            )
        
        # Get feed
        feed = db.query(Feed).filter(Feed.id == uuid.UUID(feed_id)).first()
        
        if not feed:
            logger.warning(f"Feed not found: {feed_id}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Feed not found"
            )
        
        # Delete feed (hard delete)
        feed_name = feed.fd_name
        db.delete(feed)
        db.commit()
        
        logger.info(f"Feed deleted successfully: {feed_name}")
        
        return AdminFeedResponse(
            success=True,
            message=f"Feed '{feed_name}' deleted successfully",
            feed=None
        )
        
    except HTTPException:
        raise
    except SQLAlchemyError as e:
        logger.error(f"Database error during feed deletion: {str(e)}")
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete feed"
        )
    except Exception as e:
        logger.error(f"Unexpected error during feed deletion: {str(e)}")
        if 'db' in locals():
            db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )

@admin_router.get("/list-feeds", response_model=AdminFeedListResponse, tags=["Admin - Feed Management"])
async def list_feeds(
    admin_user_id: str = Query(..., description="Admin user UUID for authentication"),
    page: int = Query(1, ge=1, description="Page number (starts from 1)"),
    page_size: int = Query(20, ge=1, le=100, description="Number of feeds per page (max 100)"),
    feed_type: Optional[str] = Query(None, description="Filter by feed type"),
    feed_category: Optional[str] = Query(None, description="Filter by feed category"),
    country_name: Optional[str] = Query(None, description="Filter by country name"),
    search: Optional[str] = Query(None, description="Search by feed name or code"),
    db: Session = Depends(get_db)
):
    """
    List all feeds with filtering and pagination (Admin only)
    
    - **admin_user_id**: Admin user UUID for authentication
    - **page**: Page number for pagination (default: 1)
    - **page_size**: Number of feeds per page (default: 20, max: 100)
    - **feed_type**: Filter feeds by type
    - **feed_category**: Filter feeds by category
    - **country_name**: Filter feeds by country name
    - **search**: Search feeds by name or code
    """
    logger.info(f"List feeds request by admin: {admin_user_id}")
    
    try:
        # Verify admin user exists and has admin privileges
        admin_user = db.query(UserInformationModel).filter(
            UserInformationModel.id == uuid.UUID(admin_user_id),
            UserInformationModel.is_admin == True
        ).first()
        
        if not admin_user:
            logger.warning(f"Unauthorized access attempt to admin endpoint: {admin_user_id}")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Admin privileges required"
            )
        
        # Build query
        query = db.query(Feed)
        
        # Apply filters
        if feed_type:
            query = query.filter(Feed.fd_type == feed_type)
        
        if feed_category:
            query = query.filter(Feed.fd_category == feed_category)
        
        if country_name:
            query = query.filter(Feed.fd_country_name.ilike(f"%{country_name}%"))
        
        if search:
            search_term = f"%{search}%"
            query = query.filter(
                (Feed.fd_name_default.ilike(search_term)) |  # Use fd_name_default for new schema
                (Feed.fd_code.ilike(search_term))
            )
        
        # Get total count for pagination
        total_count = query.count()
        
        # Apply pagination
        offset = (page - 1) * page_size
        query = query.offset(offset).limit(page_size)
        
        # Execute query
        feeds = query.all()
        
        # Convert to response format
        feed_responses = []
        for feed in feeds:
            feed_responses.append(FeedDetailsResponse(
                feed_id=str(feed.id),
                fd_code=feed.fd_code,
                fd_name=feed.fd_name_default if hasattr(feed, 'fd_name_default') and feed.fd_name_default else feed.fd_name,  # Use fd_name_default if available
                fd_type=feed.fd_type,
                fd_category=feed.fd_category,
                fd_country_id=str(feed.fd_country_id) if feed.fd_country_id else None,
                fd_country_name=feed.fd_country_name,
                fd_country_cd=feed.fd_country_cd,
                fd_dm=float(feed.fd_dm) if feed.fd_dm is not None else None,
                fd_ash=float(feed.fd_ash) if feed.fd_ash is not None else None,
                fd_cp=float(feed.fd_cp) if feed.fd_cp is not None else None,
                fd_ee=float(feed.fd_ee) if feed.fd_ee is not None else None,
                fd_st=float(feed.fd_st) if feed.fd_st is not None else None,
                fd_ndf=float(feed.fd_ndf) if feed.fd_ndf is not None else None,
                fd_adf=float(feed.fd_adf) if feed.fd_adf is not None else None,
                fd_lg=float(feed.fd_lg) if feed.fd_lg is not None else None,
                fd_ndin=float(feed.fd_ndin) if feed.fd_ndin is not None else None,
                fd_adin=float(feed.fd_adin) if feed.fd_adin is not None else None,
                fd_ca=float(feed.fd_ca) if feed.fd_ca is not None else None,
                fd_p=float(feed.fd_p) if feed.fd_p is not None else None,
                fd_cf=float(feed.fd_cf) if feed.fd_cf is not None else None,
                fd_nfe=float(feed.fd_nfe) if feed.fd_nfe is not None else None,
                fd_hemicellulose=float(feed.fd_hemicellulose) if feed.fd_hemicellulose is not None else None,
                fd_cellulose=float(feed.fd_cellulose) if feed.fd_cellulose is not None else None,
                fd_npn_cp=feed.fd_npn_cp,
                fd_season=feed.fd_season,
                fd_orginin=feed.fd_orginin,
                fd_ipb_local_lab=feed.fd_ipb_local_lab,
                created_at=feed.created_at,
                updated_at=feed.updated_at
            ))
        
        # Calculate pagination info
        total_pages = (total_count + page_size - 1) // page_size
        
        logger.info(f"Feeds returned: {len(feed_responses)} feeds, Total: {total_count}")
        
        return AdminFeedListResponse(
            success=True,
            message=f"Retrieved {len(feed_responses)} feeds successfully",
            feeds=feed_responses,
            total_count=total_count,
            page=page,
            page_size=page_size,
            total_pages=total_pages
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting feeds: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve feeds"
        )

# Bulk Operations
@admin_router.post("/bulk-upload-feeds", response_model=AdminBulkUploadResponse, tags=["Admin - Bulk Operations"])
async def bulk_upload_feeds(
    file: UploadFile = File(..., description="Excel file with feed data"),
    admin_user_id: str = Query(..., description="Admin user UUID for authentication"),
    db: Session = Depends(get_db)
):
    """
    Bulk upload feeds from Excel file (Admin only)
    
    - **file**: Excel file with feed data
    - **admin_user_id**: Admin user UUID for authentication
    """
    logger.info(f"Bulk upload feeds request by admin: {admin_user_id}")
    
    # Initialize bulk import logger
    bulk_logger = BulkImportLogger()
    bulk_logger.start_logging()
    
    try:
        # Verify admin user exists and has admin privileges
        admin_user = db.query(UserInformationModel).filter(
            UserInformationModel.id == uuid.UUID(admin_user_id),
            UserInformationModel.is_admin == True
        ).first()
        
        if not admin_user:
            logger.warning(f"Unauthorized access attempt to admin endpoint: {admin_user_id}")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Admin privileges required"
            )
        
        # Validate file type
        if not file.filename or not file.filename.endswith(('.xlsx', '.xls')):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="File must be an Excel file (.xlsx or .xls)"
            )
        
        # Validate file size (max 50MB)
        MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB
        file_content = await file.read()
        if len(file_content) > MAX_FILE_SIZE:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"File size exceeds maximum allowed size of {MAX_FILE_SIZE / (1024*1024):.0f}MB"
            )
        
        # Validate content type
        if file.content_type not in [
            'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            'application/vnd.ms-excel',
            'application/octet-stream'  # Some browsers send this for .xls
        ]:
            # Allow if filename suggests Excel file (content-type can be unreliable)
            if not file.filename.endswith(('.xlsx', '.xls')):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid file type. Only Excel files (.xlsx, .xls) are allowed"
                )
        
        # Read Excel file
        try:
            # Create a BytesIO object for pandas
            df = pd.read_excel(io.BytesIO(file_content))
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Failed to read Excel file: {str(e)}"
            )
        
        # Validate required columns
        required_columns = ['fd_name', 'fd_category', 'fd_type', 'fd_country_name']
        missing_columns = [col for col in required_columns if col not in df.columns]
        
        if missing_columns:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Missing required columns: {', '.join(missing_columns)}"
            )
        
        # Initialize counters
        total_records = len(df)
        successful_uploads = 0
        failed_uploads = 0
        existing_records = 0
        updated_records = 0
        failed_records = []
        
        # Helper function to round numeric values in feed data
        def round_feed_row_data(row_data):
            """Round numeric values in feed data to 2 decimal places"""
            return round_feed_data(row_data.to_dict())
        
        # Process each row
        for index, row in df.iterrows():
            try:
                # Check for mandatory fields
                if pd.isna(row['fd_name']) or pd.isna(row['fd_category']) or pd.isna(row['fd_type']) or pd.isna(row['fd_country_name']):
                    failed_records.append({
                        'row': index + 2,  # Excel row number (1-based + header)
                        'reason': 'Missing mandatory fields',
                        'data': clean_data_for_json(row.to_dict())
                    })
                    failed_uploads += 1
                    continue
                
                # Check if feed already exists (case-insensitive fd_name_default, case-sensitive others)
                existing_feed = db.query(Feed).filter(
                    func.lower(Feed.fd_name_default) == func.lower(str(row['fd_name'])),
                    Feed.fd_type == str(row['fd_type']),
                    Feed.fd_category == str(row['fd_category']),
                    Feed.fd_country_name == str(row['fd_country_name'])
                ).first()
                
                # Get country ID from country name
                country = db.query(CountryModel).filter(
                    CountryModel.name == str(row['fd_country_name'])
                ).first()
                
                if not country:
                    failed_records.append({
                        'row': index + 2,
                        'reason': f"Country not found: {row['fd_country_name']}",
                        'data': clean_data_for_json(row.to_dict())
                    })
                    failed_uploads += 1
                    continue
                
                # NEW: Enhanced validation for feed type and category relationships
                # Validate feed type exists and is active
                feed_type = db.query(FeedType).filter(
                    FeedType.type_name == str(row['fd_type']),
                    FeedType.is_active == True
                ).first()
                
                if not feed_type:
                    failed_records.append({
                        'row': index + 2,
                        'reason': f"Feed type not found or inactive: {row['fd_type']}",
                        'data': clean_data_for_json(row.to_dict())
                    })
                    failed_uploads += 1
                    continue
                
                # Validate feed category exists and is active
                feed_category = db.query(FeedCategory).filter(
                    FeedCategory.category_name == str(row['fd_category']),
                    FeedCategory.is_active == True
                ).first()
                
                if not feed_category:
                    failed_records.append({
                        'row': index + 2,
                        'reason': f"Feed category not found or inactive: {row['fd_category']}",
                        'data': clean_data_for_json(row.to_dict())
                    })
                    failed_uploads += 1
                    continue
                
                # Validate parent-child relationship between feed type and category
                if feed_category.feed_type_id != feed_type.id:
                    failed_records.append({
                        'row': index + 2,
                        'reason': f"Invalid relationship: Category '{row['fd_category']}' does not belong to type '{row['fd_type']}'",
                        'data': clean_data_for_json(row.to_dict())
                    })
                    failed_uploads += 1
                    continue
                
                # Round numeric values to 2 decimal places
                rounded_data = round_feed_row_data(row)
                
                if existing_feed:
                    # UPDATE existing feed with new data
                    existing_feed.fd_code = str(row.get('fd_code', '')) if not pd.isna(row.get('fd_code', '')) else None
                    existing_feed.fd_name = str(row['fd_name'])  # Legacy field
                    existing_feed.fd_name_default = str(row['fd_name'])  # Map to new schema field
                    existing_feed.fd_category = str(row['fd_category'])
                    existing_feed.fd_type = str(row['fd_type'])
                    existing_feed.fd_category_id = feed_category.id
                    existing_feed.fd_country_id = country.id
                    existing_feed.fd_country_name = str(row['fd_country_name'])
                    existing_feed.fd_country_cd = str(row.get('fd_country_cd', '')) if not pd.isna(row.get('fd_country_cd', '')) else None
                    existing_feed.fd_dm = rounded_data.get('fd_dm')
                    existing_feed.fd_ash = rounded_data.get('fd_ash')
                    existing_feed.fd_cp = rounded_data.get('fd_cp')
                    existing_feed.fd_npn_cp = int(row.get('fd_npn_cp', 0)) if not pd.isna(row.get('fd_npn_cp', 0)) else None
                    existing_feed.fd_ee = rounded_data.get('fd_ee')
                    existing_feed.fd_cf = rounded_data.get('fd_cf')
                    existing_feed.fd_nfe = rounded_data.get('fd_nfe')
                    existing_feed.fd_st = rounded_data.get('fd_st')
                    existing_feed.fd_ndf = rounded_data.get('fd_ndf')
                    existing_feed.fd_hemicellulose = rounded_data.get('fd_hemicellulose')
                    existing_feed.fd_adf = rounded_data.get('fd_adf')
                    existing_feed.fd_cellulose = rounded_data.get('fd_cellulose')
                    existing_feed.fd_lg = rounded_data.get('fd_lg')
                    existing_feed.fd_ndin = rounded_data.get('fd_ndin')
                    existing_feed.fd_adin = rounded_data.get('fd_adin')
                    existing_feed.fd_ca = rounded_data.get('fd_ca')
                    existing_feed.fd_p = rounded_data.get('fd_p')
                    existing_feed.fd_season = str(row.get('fd_season', '')) if not pd.isna(row.get('fd_season', '')) else None
                    existing_feed.fd_orginin = str(row.get('fd_orginin', '')) if not pd.isna(row.get('fd_orginin', '')) else None
                    existing_feed.fd_ipb_local_lab = str(row.get('fd_ipb_local_lab', '')) if not pd.isna(row.get('fd_ipb_local_lab', '')) else None
                    existing_feed.updated_at = datetime.utcnow()
                    
                    updated_records += 1
                else:
                    # CREATE new feed
                    new_feed = Feed(
                        fd_code=str(row.get('fd_code', '')) if not pd.isna(row.get('fd_code', '')) else None,
                        fd_name=str(row['fd_name']),  # Legacy field
                        fd_name_default=str(row['fd_name']),  # Map to new schema field
                        fd_category=str(row['fd_category']),
                        fd_type=str(row['fd_type']),
                        fd_category_id=feed_category.id,
                        fd_country_id=country.id,
                        fd_country_name=str(row['fd_country_name']),
                        fd_country_cd=str(row.get('fd_country_cd', '')) if not pd.isna(row.get('fd_country_cd', '')) else None,
                        fd_dm=rounded_data.get('fd_dm'),
                        fd_ash=rounded_data.get('fd_ash'),
                        fd_cp=rounded_data.get('fd_cp'),
                        fd_npn_cp=int(row.get('fd_npn_cp', 0)) if not pd.isna(row.get('fd_npn_cp', 0)) else None,
                        fd_ee=rounded_data.get('fd_ee'),
                        fd_cf=rounded_data.get('fd_cf'),
                        fd_nfe=rounded_data.get('fd_nfe'),
                        fd_st=rounded_data.get('fd_st'),
                        fd_ndf=rounded_data.get('fd_ndf'),
                        fd_hemicellulose=rounded_data.get('fd_hemicellulose'),
                        fd_adf=rounded_data.get('fd_adf'),
                        fd_cellulose=rounded_data.get('fd_cellulose'),
                        fd_lg=rounded_data.get('fd_lg'),
                        fd_ndin=rounded_data.get('fd_ndin'),
                        fd_adin=rounded_data.get('fd_adin'),
                        fd_ca=rounded_data.get('fd_ca'),
                        fd_p=rounded_data.get('fd_p'),
                        fd_season=str(row.get('fd_season', '')) if not pd.isna(row.get('fd_season', '')) else None,
                        fd_orginin=str(row.get('fd_orginin', '')) if not pd.isna(row.get('fd_orginin', '')) else None,
                        fd_ipb_local_lab=str(row.get('fd_ipb_local_lab', '')) if not pd.isna(row.get('fd_ipb_local_lab', '')) else None
                    )
                    
                    db.add(new_feed)
                    successful_uploads += 1
                
            except Exception as e:
                failed_records.append({
                    'row': index + 2,
                    'reason': f"Error processing row: {str(e)}",
                    'data': clean_data_for_json(row.to_dict())
                })
                failed_uploads += 1
        
        # Commit all successful uploads
        db.commit()
        
        # Stop logging and generate log content
        bulk_logger.stop_logging()
        log_content = bulk_logger.generate_log_content(
            total_records=total_records,
            successful_uploads=successful_uploads,
            failed_uploads=failed_uploads,
            existing_records=existing_records,
            updated_records=updated_records,
            failed_records=failed_records
        )
        
        # Generate log filename and upload to S3
        log_filename = bulk_logger.generate_filename()
        bulk_import_log_url = None
        
        try:
            # Initialize AWS service and upload log
            aws_service = AWSService()
            success, bucket_url, error_message = aws_service.upload_bulk_import_log_to_s3(
                log_content=log_content,
                filename=log_filename
            )
            
            if success:
                bulk_import_log_url = bucket_url
                logger.info(f"Bulk import log uploaded to S3: {bucket_url}")
            else:
                logger.warning(f"Failed to upload bulk import log to S3: {error_message}")
                
        except Exception as e:
            logger.error(f"Error uploading bulk import log to S3: {str(e)}")
        
        logger.info(f"Bulk upload completed. Total: {total_records}, Successful: {successful_uploads}, Failed: {failed_uploads}, Existing: {existing_records}, Updated: {updated_records}")
        
        return AdminBulkUploadResponse(
            success=True,
            message=f"Bulk upload completed. {successful_uploads} feeds uploaded successfully, {updated_records} feeds updated.",
            total_records=total_records,
            successful_uploads=successful_uploads,
            failed_uploads=failed_uploads,
            existing_records=existing_records,
            updated_records=updated_records,
            failed_records=failed_records,
            bulk_import_log=bulk_import_log_url
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error during bulk upload: {str(e)}")
        if 'db' in locals():
            db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error during bulk upload"
        )

@admin_router.get("/export-feeds", response_model=AdminExportResponse, tags=["Admin - Bulk Operations"])
async def export_feeds(
    admin_user_id: str = Query(..., description="Admin user UUID for authentication"),
    db: Session = Depends(get_db)
):
    """
    Export all feeds to Excel file and upload to AWS S3 (Admin only)
    
    - **admin_user_id**: Admin user UUID for authentication
    """
    logger.info(f"Export feeds request by admin: {admin_user_id}")
    
    try:
        # Verify admin user exists and has admin privileges
        admin_user = db.query(UserInformationModel).filter(
            UserInformationModel.id == uuid.UUID(admin_user_id),
            UserInformationModel.is_admin == True
        ).first()
        
        if not admin_user:
            logger.warning(f"Unauthorized access attempt to admin endpoint: {admin_user_id}")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Admin privileges required"
            )
        
        # Get all feeds
        feeds = db.query(Feed).all()
        
        if not feeds:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No feeds found to export"
            )
        
        # Convert to DataFrame with precision control
        feed_data = []
        for feed in feeds:
            # Apply precision control to numeric values
            feed_dict = {
                'fd_code': feed.fd_code,
                'fd_name': feed.fd_name,
                'fd_category': feed.fd_category,
                'fd_type': feed.fd_type,
                'fd_country_name': feed.fd_country_name,
                'fd_country_cd': feed.fd_country_cd,
                'fd_npn_cp': feed.fd_npn_cp,  # Integer field, no rounding needed
                'fd_season': feed.fd_season,
                'fd_orginin': feed.fd_orginin,
                'fd_ipb_local_lab': feed.fd_ipb_local_lab
            }
            
            # Apply rounding to numeric fields
            numeric_fields = [
                'fd_dm', 'fd_ash', 'fd_cp', 'fd_ee', 'fd_cf', 'fd_nfe', 'fd_st', 
                'fd_ndf', 'fd_hemicellulose', 'fd_adf', 'fd_cellulose', 'fd_lg', 
                'fd_ndin', 'fd_adin', 'fd_ca', 'fd_p'
            ]
            
            for field in numeric_fields:
                value = getattr(feed, field)
                if value is not None:
                    # Convert Decimal to float and round to 2 decimal places
                    if hasattr(value, '__float__'):
                        feed_dict[field] = round(float(value), 2)
                    else:
                        feed_dict[field] = round_numeric_value(str(value), 2)
                else:
                    feed_dict[field] = None
            
            feed_data.append(feed_dict)
        
        df = pd.DataFrame(feed_data)
        
        # Create Excel file
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"feeds_export_{timestamp}.xlsx"
        
        # Save to temporary file
        temp_file_path = f"/tmp/{filename}"
        df.to_excel(temp_file_path, index=False)
        
        # Read file as bytes
        with open(temp_file_path, 'rb') as f:
            file_bytes = f.read()
        
        # Upload to AWS S3
        from services.aws_service import AWSService
        aws_service = AWSService()
        
        success, bucket_url, error_message = aws_service.upload_export_to_s3(
            file_bytes, 
            admin_user_id, 
            f"feeds_export_{timestamp}",
            "xlsx"
        )
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to upload to AWS S3: {error_message}"
            )
        
        # Clean up temporary file
        import os
        os.remove(temp_file_path)
        
        # Delete old export files of the same type
        delete_success, delete_message, deleted_count = aws_service.delete_old_export_files("feeds_export")
        if delete_success:
            logger.info(f"Cleanup completed: {delete_message}")
        else:
            logger.warning(f"Cleanup failed: {delete_message}")
        
        logger.info(f"Feeds exported successfully. Total records: {len(feeds)}, File: {filename}")
        
        return AdminExportResponse(
            success=True,
            message=f"Feeds exported successfully. {len(feeds)} records exported.",
            file_url=bucket_url,
            file_name=filename,
            total_records=len(feeds)
        )
        
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        error_traceback = traceback.format_exc()
        logger.error(f"Unexpected error during export: {str(e)}")
        logger.error(f"Full traceback: {error_traceback}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal server error during export: {str(e)}"
        )

@admin_router.get("/export-custom-feeds", response_model=AdminExportResponse, tags=["Admin - Bulk Operations"])
async def export_custom_feeds(
    admin_user_id: str = Query(..., description="Admin user UUID for authentication"),
    db: Session = Depends(get_db)
):
    """
    Export all custom feeds to Excel file and upload to AWS S3 (Admin only)
    
    - **admin_user_id**: Admin user UUID for authentication
    """
    logger.info(f"Export custom feeds request by admin: {admin_user_id}")
    
    try:
        # Verify admin user exists and has admin privileges
        admin_user = db.query(UserInformationModel).filter(
            UserInformationModel.id == uuid.UUID(admin_user_id),
            UserInformationModel.is_admin == True
        ).first()
        
        if not admin_user:
            logger.warning(f"Unauthorized access attempt to admin endpoint: {admin_user_id}")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Admin privileges required"
            )
        
        # Get all custom feeds
        custom_feeds = db.query(CustomFeed).all()
        
        if not custom_feeds:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No custom feeds found to export"
            )
        
        # Convert to DataFrame with precision control
        custom_feed_data = []
        for custom_feed in custom_feeds:
            # Apply precision control to numeric values
            custom_feed_dict = {
                'fd_code': custom_feed.fd_code,
                'fd_name': custom_feed.fd_name,
                'fd_category': custom_feed.fd_category,
                'fd_type': custom_feed.fd_type,
                'fd_country_name': custom_feed.fd_country_name,
                'fd_country_cd': custom_feed.fd_country_cd,
                'fd_orginin': custom_feed.fd_orginin,
                'fd_ipb_local_lab': custom_feed.fd_ipb_local_lab
            }
            
            # Apply rounding to numeric fields
            numeric_fields = [
                'fd_dm', 'fd_ash', 'fd_cp', 'fd_ee', 'fd_cf', 'fd_nfe', 'fd_st', 
                'fd_ndf', 'fd_hemicellulose', 'fd_adf', 'fd_cellulose', 'fd_lg', 
                'fd_ndin', 'fd_adin', 'fd_ca', 'fd_p'
            ]
            
            for field in numeric_fields:
                value = getattr(custom_feed, field)
                if value is not None:
                    # Convert Decimal to float and round to 2 decimal places
                    if hasattr(value, '__float__'):
                        custom_feed_dict[field] = round(float(value), 2)
                    else:
                        custom_feed_dict[field] = round_numeric_value(str(value), 2)
                else:
                    custom_feed_dict[field] = None
            
            custom_feed_data.append(custom_feed_dict)
        
        df = pd.DataFrame(custom_feed_data)
        
        # Create Excel file
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"custom_feeds_export_{timestamp}.xlsx"
        
        # Save to temporary file
        temp_file_path = f"/tmp/{filename}"
        df.to_excel(temp_file_path, index=False)
        
        # Read file as bytes
        with open(temp_file_path, 'rb') as f:
            file_bytes = f.read()
        
        # Upload to AWS S3
        from services.aws_service import AWSService
        aws_service = AWSService()
        
        success, bucket_url, error_message = aws_service.upload_export_to_s3(
            file_bytes, 
            admin_user_id, 
            f"custom_feeds_export_{timestamp}",
            "xlsx"
        )
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to upload to AWS S3: {error_message}"
            )
        
        # Clean up temporary file
        import os
        os.remove(temp_file_path)
        
        # Delete old export files of the same type
        delete_success, delete_message, deleted_count = aws_service.delete_old_export_files("custom_feeds_export")
        if delete_success:
            logger.info(f"Cleanup completed: {delete_message}")
        else:
            logger.warning(f"Cleanup failed: {delete_message}")
        
        logger.info(f"Custom feeds exported successfully. Total records: {len(custom_feeds)}, File: {filename}")
        
        return AdminExportResponse(
            success=True,
            message=f"Custom feeds exported successfully. {len(custom_feeds)} records exported.",
            file_url=bucket_url,
            file_name=filename,
            total_records=len(custom_feeds)
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error during custom feeds export: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error during custom feeds export"
        )

# ============================================================================
# ADMIN FEEDBACK MANAGEMENT ENDPOINTS
# ============================================================================

@admin_router.get("/user-feedback/all", response_model=AdminFeedbackListResponse, tags=["Admin - Feedback Management"])
async def get_all_feedback(
    admin_user_id: str = Query(..., description="Admin user UUID for authentication"),
    limit: int = Query(50, ge=1, le=100, description="Number of feedback entries to return"),
    offset: int = Query(0, ge=0, description="Number of feedback entries to skip"),
    db: Session = Depends(get_db)
):
    """
    Get all feedback entries (Admin only)
    
    - **admin_user_id**: Admin user UUID for authentication
    - **limit**: Number of feedback entries to return (1-100)
    - **offset**: Number of feedback entries to skip for pagination
    """
    logger.info(f"All feedback retrieval attempt by admin user: {admin_user_id}")
    
    try:
        # Verify admin user exists and has admin privileges
        admin_user = db.query(UserInformationModel).filter(
            UserInformationModel.id == uuid.UUID(admin_user_id),
            UserInformationModel.is_admin == True
        ).first()
        
        if not admin_user:
            logger.warning(f"Unauthorized access attempt to admin endpoint: {admin_user_id}")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Admin privileges required"
            )
        
        # Get all feedback with pagination
        feedbacks = db.query(UserFeedback).join(UserInformationModel).order_by(
            UserFeedback.created_at.desc()
        ).offset(offset).limit(limit).all()
        
        # Get total count
        total_count = db.query(UserFeedback).count()
        
        logger.info(f"Admin retrieved {len(feedbacks)} feedback entries")
        
        # Convert to admin response models
        feedback_responses = [
            AdminFeedbackResponse(
                id=str(feedback.id),
                user_name=feedback.user.name,
                user_email=feedback.user.email_id,
                overall_rating=feedback.overall_rating,
                text_feedback=feedback.text_feedback,
                feedback_type=feedback.feedback_type,
                created_at=feedback.created_at
            )
            for feedback in feedbacks
        ]
        
        return AdminFeedbackListResponse(
            feedbacks=feedback_responses,
            total_count=total_count
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving all feedback: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve feedback"
        )

@admin_router.get("/user-feedback/stats", response_model=FeedbackStatsResponse, tags=["Admin - Feedback Management"])
async def get_feedback_stats(
    admin_user_id: str = Query(..., description="Admin user UUID for authentication"),
    db: Session = Depends(get_db)
):
    """
    Get feedback statistics (Admin only)
    
    - **admin_user_id**: Admin user UUID for authentication
    """
    logger.info(f"Feedback stats retrieval attempt by admin user: {admin_user_id}")
    
    try:
        # Verify admin user exists and has admin privileges (optimized)
        if not verify_admin_user(db, admin_user_id):
            logger.warning(f"Unauthorized access attempt to admin endpoint: {admin_user_id}")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Admin privileges required"
            )
        
        # Get total feedback count
        total_feedbacks = db.query(UserFeedback).count()
        
        if total_feedbacks == 0:
            # Return empty stats if no feedback exists
            return FeedbackStatsResponse(
                total_feedbacks=0,
                average_rating=0.0,
                rating_distribution={"5": "0%", "4": "0%", "3": "0%", "2": "0%", "1": "0%"},
                feedback_type_distribution={"General": 0, "Defect": 0, "Feature Request": 0},
                recent_feedbacks=0
            )
        
        # Calculate average rating (handle NULL ratings)
        avg_rating_result = db.query(UserFeedback.overall_rating).all()
        # Filter out None values and sum only valid ratings
        valid_ratings = [rating[0] for rating in avg_rating_result if rating[0] is not None]
        if valid_ratings:
            total_rating = sum(valid_ratings)
            average_rating = round(total_rating / len(valid_ratings), 2)
        else:
            average_rating = 0.0
        
        # Get rating distribution as percentages (ordered from 5 to 1 for positive psychology)
        rating_distribution = {}
        for rating in range(5, 0, -1):  # Start from 5, go down to 1
            count = db.query(UserFeedback).filter(UserFeedback.overall_rating == rating).count()
            percentage = round((count / total_feedbacks) * 100) if total_feedbacks > 0 else 0
            rating_distribution[str(rating)] = f"{percentage}%"
        
        # Get feedback type distribution
        feedback_type_distribution = {}
        for feedback_type in ["General", "Defect", "Feature Request"]:
            count = db.query(UserFeedback).filter(UserFeedback.feedback_type == feedback_type).count()
            feedback_type_distribution[feedback_type] = count
        
        # Get recent feedbacks (last 30 days)
        thirty_days_ago = datetime.utcnow() - timedelta(days=30)
        recent_feedbacks = db.query(UserFeedback).filter(
            UserFeedback.created_at >= thirty_days_ago
        ).count()
        
        logger.info(f"Admin retrieved feedback stats - Total: {total_feedbacks}, Avg Rating: {average_rating}")
        
        return FeedbackStatsResponse(
            total_feedbacks=total_feedbacks,
            average_rating=average_rating,
            rating_distribution=rating_distribution,
            feedback_type_distribution=feedback_type_distribution,
            recent_feedbacks=recent_feedbacks
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving feedback stats: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve feedback statistics"
        )

# ============================================================================
# ADMIN FEED MANAGEMENT ENDPOINTS
# ============================================================================

# Feed Type Management
@admin_router.post("/add-feed-type", response_model=AdminFeedTypeResponse, tags=["Admin - Feed Type Management"])
async def add_feed_type(
    feed_type_data: AdminFeedTypeRequest,
    admin_user_id: str = Query(..., description="Admin user UUID for authentication"),
    db: Session = Depends(get_db)
):
    """
    Add a new feed type (Admin only)
    
    - **feed_type_data**: Feed type details
    - **admin_user_id**: Admin user UUID for authentication
    """
    logger.info(f"Add feed type request by admin: {admin_user_id}")
    
    try:
        # Verify admin user exists and has admin privileges
        admin_user = db.query(UserInformationModel).filter(
            UserInformationModel.id == uuid.UUID(admin_user_id),
            UserInformationModel.is_admin == True
        ).first()
        
        if not admin_user:
            logger.warning(f"Unauthorized access attempt to admin endpoint: {admin_user_id}")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Admin privileges required"
            )
        
        # Check if feed type already exists
        existing_type = db.query(FeedType).filter(
            FeedType.type_name == feed_type_data.type_name
        ).first()
        
        if existing_type:
            logger.warning(f"Feed type already exists: {feed_type_data.type_name}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Feed type already exists"
            )
        
        # Create new feed type
        new_feed_type = FeedType(
            type_name=feed_type_data.type_name,
            description=feed_type_data.description,
            sort_order=feed_type_data.sort_order
        )
        
        db.add(new_feed_type)
        db.commit()
        db.refresh(new_feed_type)
        
        logger.info(f"Feed type created successfully: {new_feed_type.type_name}")
        
        # Create response
        feed_type_response = FeedTypeResponse(
            id=str(new_feed_type.id),
            type_name=new_feed_type.type_name,
            description=new_feed_type.description,
            sort_order=new_feed_type.sort_order,
            is_active=new_feed_type.is_active,
            created_at=new_feed_type.created_at,
            updated_at=new_feed_type.updated_at
        )
        
        return AdminFeedTypeResponse(
            success=True,
            message=f"Feed type '{new_feed_type.type_name}' created successfully",
            feed_type=feed_type_response
        )
        
    except HTTPException:
        raise
    except SQLAlchemyError as e:
        logger.error(f"Database error during feed type creation: {str(e)}")
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create feed type"
        )
    except Exception as e:
        logger.error(f"Unexpected error during feed type creation: {str(e)}")
        if 'db' in locals():
            db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )

@admin_router.delete("/delete-feed-type/{type_id}", response_model=AdminFeedTypeResponse, tags=["Admin - Feed Type Management"])
async def delete_feed_type(
    type_id: str,
    admin_user_id: str = Query(..., description="Admin user UUID for authentication"),
    db: Session = Depends(get_db)
):
    """
    Delete a feed type (Admin only)
    
    - **type_id**: Feed type UUID to delete
    - **admin_user_id**: Admin user UUID for authentication
    """
    logger.info(f"Delete feed type request by admin: {admin_user_id} for type: {type_id}")
    
    try:
        # Verify admin user exists and has admin privileges
        admin_user = db.query(UserInformationModel).filter(
            UserInformationModel.id == uuid.UUID(admin_user_id),
            UserInformationModel.is_admin == True
        ).first()
        
        if not admin_user:
            logger.warning(f"Unauthorized access attempt to admin endpoint: {admin_user_id}")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Admin privileges required"
            )
        
        # Get feed type
        feed_type = db.query(FeedType).filter(
            FeedType.id == uuid.UUID(type_id)
        ).first()
        
        if not feed_type:
            logger.warning(f"Feed type not found: {type_id}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Feed type not found"
            )
        
        # Check if feed type is used in feeds table
        feeds_count = db.query(Feed).filter(
            Feed.fd_type == feed_type.type_name
        ).count()
        
        if feeds_count > 0:
            logger.warning(f"Cannot delete feed type: {feeds_count} feeds use this type")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot delete feed type: {feeds_count} feeds use this type"
            )
        
        # Check if feed type is used in feed_categories table
        categories_count = db.query(FeedCategory).filter(
            FeedCategory.feed_type_id == feed_type.id
        ).count()
        
        if categories_count > 0:
            logger.warning(f"Cannot delete feed type: {categories_count} categories use this type")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot delete feed type: {categories_count} categories use this type"
            )
        
        # Delete feed type
        type_name = feed_type.type_name
        db.delete(feed_type)
        db.commit()
        
        logger.info(f"Feed type deleted successfully: {type_name}")
        
        return AdminFeedTypeResponse(
            success=True,
            message=f"Feed type '{type_name}' deleted successfully",
            feed_type=None
        )
        
    except HTTPException:
        raise
    except SQLAlchemyError as e:
        logger.error(f"Database error during feed type deletion: {str(e)}")
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete feed type"
        )
    except Exception as e:
        logger.error(f"Unexpected error during feed type deletion: {str(e)}")
        if 'db' in locals():
            db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )

@admin_router.get("/list-feed-types", response_model=List[FeedTypeResponse], tags=["Admin - Feed Type Management"])
async def list_feed_types(
    admin_user_id: str = Query(..., description="Admin user UUID for authentication"),
    db: Session = Depends(get_db)
):
    """
    List all feed types (Admin only)
    
    - **admin_user_id**: Admin user UUID for authentication
    """
    logger.info(f"List feed types request by admin: {admin_user_id}")
    
    try:
        # Verify admin user exists and has admin privileges
        admin_user = db.query(UserInformationModel).filter(
            UserInformationModel.id == uuid.UUID(admin_user_id),
            UserInformationModel.is_admin == True
        ).first()
        
        if not admin_user:
            logger.warning(f"Unauthorized access attempt to admin endpoint: {admin_user_id}")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Admin privileges required"
            )
        
        # Get all feed types
        feed_types = db.query(FeedType).order_by(FeedType.sort_order, FeedType.type_name).all()
        
        # Convert to response format
        feed_type_responses = []
        for ft in feed_types:
            feed_type_responses.append(FeedTypeResponse(
                id=str(ft.id),
                type_name=ft.type_name,
                description=ft.description,
                sort_order=ft.sort_order,
                is_active=ft.is_active,
                created_at=ft.created_at,
                updated_at=ft.updated_at
            ))
        
        logger.info(f"Feed types returned: {len(feed_type_responses)} types")
        return feed_type_responses
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting feed types: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve feed types"
        )

# Feed Category Management
@admin_router.post("/add-feed-category", response_model=AdminFeedCategoryResponse, tags=["Admin - Feed Category Management"])
async def add_feed_category(
    feed_category_data: AdminFeedCategoryRequest,
    admin_user_id: str = Query(..., description="Admin user UUID for authentication"),
    db: Session = Depends(get_db)
):
    """
    Add a new feed category (Admin only)
    
    - **feed_category_data**: Feed category details
    - **admin_user_id**: Admin user UUID for authentication
    """
    logger.info(f"Add feed category request by admin: {admin_user_id}")
    
    try:
        # Verify admin user exists and has admin privileges
        admin_user = db.query(UserInformationModel).filter(
            UserInformationModel.id == uuid.UUID(admin_user_id),
            UserInformationModel.is_admin == True
        ).first()
        
        if not admin_user:
            logger.warning(f"Unauthorized access attempt to admin endpoint: {admin_user_id}")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Admin privileges required"
            )
        
        # Verify feed type exists
        feed_type = db.query(FeedType).filter(
            FeedType.id == uuid.UUID(feed_category_data.feed_type_id)
        ).first()
        
        if not feed_type:
            logger.warning(f"Feed type not found: {feed_category_data.feed_type_id}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Feed type not found"
            )
        
        # Check if feed category already exists for this type
        existing_category = db.query(FeedCategory).filter(
            FeedCategory.category_name == feed_category_data.category_name,
            FeedCategory.feed_type_id == uuid.UUID(feed_category_data.feed_type_id)
        ).first()
        
        if existing_category:
            logger.warning(f"Feed category already exists: {feed_category_data.category_name}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Feed category already exists for this type"
            )
        
        # Create new feed category
        new_feed_category = FeedCategory(
            category_name=feed_category_data.category_name,
            feed_type_id=uuid.UUID(feed_category_data.feed_type_id),
            description=feed_category_data.description,
            sort_order=feed_category_data.sort_order
        )
        
        db.add(new_feed_category)
        db.commit()
        db.refresh(new_feed_category)
        
        logger.info(f"Feed category created successfully: {new_feed_category.category_name}")
        
        # Create response
        feed_category_response = FeedCategoryResponse(
            id=str(new_feed_category.id),
            category_name=new_feed_category.category_name,
            feed_type_id=feed_category_data.feed_type_id,
            description=new_feed_category.description,
            sort_order=new_feed_category.sort_order,
            is_active=new_feed_category.is_active,
            created_at=new_feed_category.created_at,
            updated_at=new_feed_category.updated_at,
            feed_type=FeedTypeResponse(
                id=str(feed_type.id),
                type_name=feed_type.type_name,
                description=feed_type.description,
                sort_order=feed_type.sort_order,
                is_active=feed_type.is_active,
                created_at=feed_type.created_at,
                updated_at=feed_type.updated_at
            )
        )
        
        return AdminFeedCategoryResponse(
            success=True,
            message=f"Feed category '{new_feed_category.category_name}' created successfully",
            feed_category=feed_category_response
        )
        
    except HTTPException:
        raise
    except SQLAlchemyError as e:
        logger.error(f"Database error during feed category creation: {str(e)}")
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create feed category"
        )
    except Exception as e:
        logger.error(f"Unexpected error during feed category creation: {str(e)}")
        if 'db' in locals():
            db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )

@admin_router.delete("/delete-feed-category/{category_id}", response_model=AdminFeedCategoryResponse, tags=["Admin - Feed Category Management"])
async def delete_feed_category(
    category_id: str,
    admin_user_id: str = Query(..., description="Admin user UUID for authentication"),
    db: Session = Depends(get_db)
):
    """
    Delete a feed category (Admin only)
    
    - **category_id**: Feed category UUID to delete
    - **admin_user_id**: Admin user UUID for authentication
    """
    logger.info(f"Delete feed category request by admin: {admin_user_id} for category: {category_id}")
    
    try:
        # Verify admin user exists and has admin privileges
        admin_user = db.query(UserInformationModel).filter(
            UserInformationModel.id == uuid.UUID(admin_user_id),
            UserInformationModel.is_admin == True
        ).first()
        
        if not admin_user:
            logger.warning(f"Unauthorized access attempt to admin endpoint: {admin_user_id}")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Admin privileges required"
            )
        
        # Get feed category
        feed_category = db.query(FeedCategory).filter(
            FeedCategory.id == uuid.UUID(category_id)
        ).first()
        
        if not feed_category:
            logger.warning(f"Feed category not found: {category_id}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Feed category not found"
            )
        
        # Check if feed category is used in feeds table
        feeds_count = db.query(Feed).filter(
            Feed.fd_category == feed_category.category_name
        ).count()
        
        if feeds_count > 0:
            logger.warning(f"Cannot delete feed category: {feeds_count} feeds use this category")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot delete feed category: {feeds_count} feeds use this category"
            )
        
        # Delete feed category
        category_name = feed_category.category_name
        db.delete(feed_category)
        db.commit()
        
        logger.info(f"Feed category deleted successfully: {category_name}")
        
        return AdminFeedCategoryResponse(
            success=True,
            message=f"Feed category '{category_name}' deleted successfully",
            feed_category=None
        )
        
    except HTTPException:
        raise
    except SQLAlchemyError as e:
        logger.error(f"Database error during feed category deletion: {str(e)}")
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete feed category"
        )
    except Exception as e:
        logger.error(f"Unexpected error during feed category deletion: {str(e)}")
        if 'db' in locals():
            db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )

@admin_router.get("/list-feed-categories", response_model=List[FeedCategoryResponse], tags=["Admin - Feed Category Management"])
async def list_feed_categories(
    admin_user_id: str = Query(..., description="Admin user UUID for authentication"),
    db: Session = Depends(get_db)
):
    """
    List all feed categories (Admin only)
    
    - **admin_user_id**: Admin user UUID for authentication
    """
    logger.info(f"List feed categories request by admin: {admin_user_id}")
    
    try:
        # Verify admin user exists and has admin privileges
        admin_user = db.query(UserInformationModel).filter(
            UserInformationModel.id == uuid.UUID(admin_user_id),
            UserInformationModel.is_admin == True
        ).first()
        
        if not admin_user:
            logger.warning(f"Unauthorized access attempt to admin endpoint: {admin_user_id}")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Admin privileges required"
            )
        
        # Get all feed categories with their types
        feed_categories = db.query(FeedCategory).join(FeedType).order_by(
            FeedCategory.sort_order, FeedCategory.category_name
        ).all()
        
        # Convert to response format
        feed_category_responses = []
        for fc in feed_categories:
            feed_category_responses.append(FeedCategoryResponse(
                id=str(fc.id),
                category_name=fc.category_name,
                feed_type_id=str(fc.feed_type_id),
                description=fc.description,
                sort_order=fc.sort_order,
                is_active=fc.is_active,
                created_at=fc.created_at,
                updated_at=fc.updated_at,
                feed_type=FeedTypeResponse(
                    id=str(fc.feed_type.id),
                    type_name=fc.feed_type.type_name,
                    description=fc.feed_type.description,
                    sort_order=fc.feed_type.sort_order,
                    is_active=fc.feed_type.is_active,
                    created_at=fc.feed_type.created_at,
                    updated_at=fc.feed_type.updated_at
                )
            ))
        
        logger.info(f"Feed categories returned: {len(feed_category_responses)} categories")
        return feed_category_responses
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting feed categories: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve feed categories"
        )

# Individual Feed Management
@admin_router.post("/add-feed", response_model=AdminFeedResponse, tags=["Admin - Feed Management"])
async def add_feed(
    feed_data: AdminFeedRequest,
    admin_user_id: str = Query(..., description="Admin user UUID for authentication"),
    db: Session = Depends(get_db)
):
    """
    Add a new feed (Admin only)
    
    - **feed_data**: Feed details
    - **admin_user_id**: Admin user UUID for authentication
    """
    logger.info(f"Add feed request by admin: {admin_user_id}")
    
    try:
        # Verify admin user exists and has admin privileges
        admin_user = db.query(UserInformationModel).filter(
            UserInformationModel.id == uuid.UUID(admin_user_id),
            UserInformationModel.is_admin == True
        ).first()
        
        if not admin_user:
            logger.warning(f"Unauthorized access attempt to admin endpoint: {admin_user_id}")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Admin privileges required"
            )
        
        # Check if feed already exists (unique constraint)
        existing_feed = db.query(Feed).filter(
            Feed.fd_name_default == feed_data.fd_name,  # Use fd_name_default for new schema
            Feed.fd_type == feed_data.fd_type,
            Feed.fd_category == feed_data.fd_category,
            Feed.fd_country_name == feed_data.fd_country_name
        ).first()
        
        if existing_feed:
            logger.warning(f"Feed already exists: {feed_data.fd_name}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Feed already exists with this name, type, category, and country combination"
            )
        
        # Get country ID from country name
        country = db.query(CountryModel).filter(
            CountryModel.name == feed_data.fd_country_name
        ).first()
        
        if not country:
            logger.warning(f"Country not found: {feed_data.fd_country_name}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Country not found"
            )
        
        # Create new feed
        new_feed = Feed(
            fd_code=feed_data.fd_code,
            fd_name=feed_data.fd_name,  # Legacy field
            fd_name_default=feed_data.fd_name,  # Map to new schema field
            fd_category=feed_data.fd_category,
            fd_type=feed_data.fd_type,
            fd_country_id=country.id,
            fd_country_name=feed_data.fd_country_name,
            fd_country_cd=feed_data.fd_country_cd,
            fd_dm=str(feed_data.fd_dm) if feed_data.fd_dm is not None else None,
            fd_ash=str(feed_data.fd_ash) if feed_data.fd_ash is not None else None,
            fd_cp=str(feed_data.fd_cp) if feed_data.fd_cp is not None else None,
            fd_npn_cp=feed_data.fd_npn_cp,
            fd_ee=str(feed_data.fd_ee) if feed_data.fd_ee is not None else None,
            fd_cf=str(feed_data.fd_cf) if feed_data.fd_cf is not None else None,
            fd_nfe=str(feed_data.fd_nfe) if feed_data.fd_nfe is not None else None,
            fd_st=str(feed_data.fd_st) if feed_data.fd_st is not None else None,
            fd_ndf=str(feed_data.fd_ndf) if feed_data.fd_ndf is not None else None,
            fd_hemicellulose=str(feed_data.fd_hemicellulose) if feed_data.fd_hemicellulose is not None else None,
            fd_adf=str(feed_data.fd_adf) if feed_data.fd_adf is not None else None,
            fd_cellulose=str(feed_data.fd_cellulose) if feed_data.fd_cellulose is not None else None,
            fd_lg=str(feed_data.fd_lg) if feed_data.fd_lg is not None else None,
            fd_ndin=str(feed_data.fd_ndin) if feed_data.fd_ndin is not None else None,
            fd_adin=str(feed_data.fd_adin) if feed_data.fd_adin is not None else None,
            fd_ca=str(feed_data.fd_ca) if feed_data.fd_ca is not None else None,
            fd_p=str(feed_data.fd_p) if feed_data.fd_p is not None else None,
            fd_season=feed_data.fd_season,
            fd_orginin=feed_data.fd_orginin,
            fd_ipb_local_lab=feed_data.fd_ipb_local_lab
        )
        
        db.add(new_feed)
        db.commit()
        db.refresh(new_feed)
        
        logger.info(f"Feed created successfully: {new_feed.fd_name}")
        
        # Create response
        feed_response = FeedDetailsResponse(
            feed_id=str(new_feed.id),
            fd_code=new_feed.fd_code,
            fd_name=new_feed.fd_name,
            fd_type=new_feed.fd_type,
            fd_category=new_feed.fd_category,
            fd_country_id=str(new_feed.fd_country_id) if new_feed.fd_country_id else None,
            fd_country_name=new_feed.fd_country_name,
            fd_country_cd=new_feed.fd_country_cd,
            fd_dm=float(new_feed.fd_dm) if new_feed.fd_dm is not None else None,
            fd_ash=float(new_feed.fd_ash) if new_feed.fd_ash is not None else None,
            fd_cp=float(new_feed.fd_cp) if new_feed.fd_cp is not None else None,
            fd_ee=float(new_feed.fd_ee) if new_feed.fd_ee is not None else None,
            fd_st=float(new_feed.fd_st) if new_feed.fd_st is not None else None,
            fd_ndf=float(new_feed.fd_ndf) if new_feed.fd_ndf is not None else None,
            fd_adf=float(new_feed.fd_adf) if new_feed.fd_adf is not None else None,
            fd_lg=float(new_feed.fd_lg) if new_feed.fd_lg is not None else None,
            fd_ndin=float(new_feed.fd_ndin) if new_feed.fd_ndin is not None else None,
            fd_adin=float(new_feed.fd_adin) if new_feed.fd_adin is not None else None,
            fd_ca=float(new_feed.fd_ca) if new_feed.fd_ca is not None else None,
            fd_p=float(new_feed.fd_p) if new_feed.fd_p is not None else None,
            fd_cf=float(new_feed.fd_cf) if new_feed.fd_cf is not None else None,
            fd_nfe=float(new_feed.fd_nfe) if new_feed.fd_nfe is not None else None,
            fd_hemicellulose=float(new_feed.fd_hemicellulose) if new_feed.fd_hemicellulose is not None else None,
            fd_cellulose=float(new_feed.fd_cellulose) if new_feed.fd_cellulose is not None else None,
            fd_npn_cp=new_feed.fd_npn_cp,
            fd_season=new_feed.fd_season,
            fd_orginin=new_feed.fd_orginin,
            fd_ipb_local_lab=new_feed.fd_ipb_local_lab,
            created_at=new_feed.created_at,
            updated_at=new_feed.updated_at
        )
        
        return AdminFeedResponse(
            success=True,
            message=f"Feed '{new_feed.fd_name}' created successfully",
            feed=feed_response
        )
        
    except HTTPException:
        raise
    except SQLAlchemyError as e:
        logger.error(f"Database error during feed creation: {str(e)}")
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create feed"
        )
    except Exception as e:
        logger.error(f"Unexpected error during feed creation: {str(e)}")
        if 'db' in locals():
            db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )

@admin_router.put("/users/{user_id}/toggle-status", response_model=AdminUserToggleResponse, tags=["Admin - User Management"])
async def toggle_user_status(
    user_id: str,
    toggle_data: AdminUserToggleRequest,
    admin_user_id: str = Query(..., description="Admin user UUID for authentication"),
    db: Session = Depends(get_db)
):
    """
    Toggle user status (enable/disable) (Admin only)
    
    - **user_id**: Target user UUID to toggle
    - **toggle_data**: Action to perform ('enable' or 'disable')
    - **admin_user_id**: Admin user UUID for authentication
    """
    logger.info(f"User status toggle request by admin: {admin_user_id} for user: {user_id}")
    
    try:
        # Verify admin user exists and has admin privileges
        admin_user = db.query(UserInformationModel).filter(
            UserInformationModel.id == uuid.UUID(admin_user_id),
            UserInformationModel.is_admin == True
        ).first()
        
        if not admin_user:
            logger.warning(f"Unauthorized access attempt to admin endpoint: {admin_user_id}")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Admin privileges required"
            )
        
        # Prevent admin from disabling themselves
        if user_id == admin_user_id:
            logger.warning(f"Admin attempted to disable themselves: {admin_user_id}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot modify your own account status"
            )
        
        # Get target user
        target_user = db.query(UserInformationModel).filter(
            UserInformationModel.id == uuid.UUID(user_id)
        ).first()
        
        if not target_user:
            logger.warning(f"User not found for status toggle: {user_id}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        # Determine new status
        new_status = toggle_data.action == 'enable'
        
        # Update user status
        target_user.is_active = new_status
        target_user.updated_at = datetime.utcnow()
        
        db.commit()
        db.refresh(target_user)
        
        status_text = "active" if new_status else "inactive"
        action_text = "enabled" if new_status else "disabled"
        
        logger.info(f"User status updated successfully. User: {user_id}, New status: {status_text}, Admin: {admin_user_id}")
        
        return AdminUserToggleResponse(
            success=True,
            message=f"User {action_text} successfully",
            user_id=user_id,
            new_status=status_text,
            user_name=target_user.name,
            user_email=target_user.email_id
        )
        
    except SQLAlchemyError as e:
        logger.error(f"Database error during user status toggle: {str(e)}")
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update user status"
        )
    except Exception as e:
        logger.error(f"Unexpected error during user status toggle: {str(e)}")
        if 'db' in locals():
            db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )

# ============================================================================
# ADMIN REPORTS MANAGEMENT ENDPOINTS
# ============================================================================

@admin_router.get("/get-all-reports/", response_model=AdminGetAllReportsResponse, tags=["Admin - Reports Management"])
async def get_all_reports(
    user_id: str = Query(..., description="Admin user UUID for authentication"),
    page: int = Query(1, ge=1, description="Page number (starts from 1)"),
    page_size: int = Query(20, ge=1, le=100, description="Number of reports per page (max 100)"),
    db: Session = Depends(get_db)
):
    """
    Get all saved reports (Admin only)
    
    - **user_id**: Admin user UUID for authentication
    - **page**: Page number for pagination (default: 1)
    - **page_size**: Number of reports per page (default: 20, max: 100)
    """
    logger.info(f"Get all reports request by admin: {user_id}")
    
    try:
        # Verify admin user exists and has admin privileges
        admin_user = db.query(UserInformationModel).filter(
            UserInformationModel.id == uuid.UUID(user_id),
            UserInformationModel.is_admin == True
        ).first()
        
        if not admin_user:
            logger.warning(f"Unauthorized access attempt to admin endpoint: {user_id}")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="The User does not have 'Admin' privileges."
            )
        
        # Build query to get all saved reports with user information
        query = db.query(
            Report,
            UserInformationModel.name.label('user_name')
        ).join(
            UserInformationModel,
            Report.user_id == UserInformationModel.id
        ).filter(
            Report.save_report == True  # Only get saved reports
        ).order_by(
            Report.created_at.desc()  # Order by created_at DESC
        )
        
        # Get total count for pagination
        total_count = query.count()
        
        # Apply pagination
        offset = (page - 1) * page_size
        query = query.offset(offset).limit(page_size)
        
        # Execute query
        results = query.all()
        
        # Convert to response format
        reports = []
        for report, user_name in results:
            # Format created_at to full date and time format
            created_time = report.created_at.strftime("%Y-%m-%d %H:%M:%S") if report.created_at else "0000-00-00 00:00:00"
            
            reports.append(AdminReportItem(
                report_id=str(report.id),
                user_id=str(report.user_id),
                user_name=user_name,
                report_type=report.report_type,
                bucket_url=report.bucket_url,
                created_at=created_time
            ))
        
        # Calculate pagination info
        total_pages = (total_count + page_size - 1) // page_size
        
        # Prepare response message
        if total_count == 0:
            message = "No reports found"
        else:
            message = f"Retrieved {len(reports)} reports successfully"
        
        logger.info(f"Admin reports retrieved successfully. Total reports: {total_count}, Page: {page}/{total_pages}")
        
        return AdminGetAllReportsResponse(
            success=True,
            message=message,
            reports=reports,
            total_count=total_count,
            page=page,
            page_size=page_size,
            total_pages=total_pages
        )
        
    except HTTPException:
        raise
    except SQLAlchemyError as e:
        logger.error(f"Database error during admin reports retrieval: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve reports"
        )
    except Exception as e:
        logger.error(f"Unexpected error during admin reports retrieval: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )

# ============================================================================
# ADMIN BULK OPERATIONS - LOG MANAGEMENT
# ============================================================================

@admin_router.get("/read-bulk-upload-logfile/", response_model=AdminBulkLogResponse, tags=["Admin - Bulk Operations"])
async def read_bulk_upload_logfile(
    admin_user_id: str = Query(..., description="Admin user UUID for authentication"),
    db: Session = Depends(get_db)
):
    """
    Get the latest bulk import log file from S3 (Admin only)
    
    - **admin_user_id**: Admin user UUID for authentication
    
    Returns the URL and metadata of the most recent bulk import log file.
    """
    logger.info(f"Bulk import log request by admin: {admin_user_id}")
    
    try:
        # Verify admin user exists and has admin privileges
        if not verify_admin_user(db, admin_user_id):
            logger.warning(f"Unauthorized access attempt to admin endpoint: {admin_user_id}")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Admin privileges required"
            )
        
        # Initialize AWS service and get latest log file
        aws_service = AWSService()
        success, log_file_url, filename, file_size, error_message, created_at = aws_service.get_latest_bulk_import_log()
        
        if not success:
            logger.error(f"Failed to retrieve bulk import log: {error_message}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to retrieve log file: {error_message}"
            )
        
        if not log_file_url:
            logger.info("No bulk import log files found")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No bulk import log files found"
            )
        
        # Format created_at timestamp
        created_at_str = created_at.strftime('%Y-%m-%d %H:%M:%S UTC') if created_at else None
        
        logger.info(f"Bulk import log retrieved successfully: {filename}")
        
        return AdminBulkLogResponse(
            success=True,
            message="Latest bulk import log file retrieved successfully",
            log_file_url=log_file_url,
            filename=filename,
            file_size=file_size,
            created_at=created_at_str
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error during bulk log retrieval: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error during log retrieval"
        )
