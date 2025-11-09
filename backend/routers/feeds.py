"""
Public Feeds Router
Provides public endpoints for searching and retrieving feeds
Used by MCP server and frontend
"""

from fastapi import APIRouter, Depends, HTTPException, status, Query, Header
from sqlalchemy.orm import Session
from typing import List, Optional
import uuid

from app.dependencies import get_db, verify_api_key_optional
from app.models import Feed, CountryModel
from middleware.logging_config import get_logger

logger = get_logger("feeds")

router = APIRouter(prefix="/feeds", tags=["Feeds"])

@router.get("/")
async def search_feeds(
    country_id: Optional[str] = Query(None, description="Filter by country UUID"),
    feed_type: Optional[str] = Query(None, description="Filter by feed type (Forage/Concentrate)"),
    feed_category: Optional[str] = Query(None, description="Filter by feed category"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of feeds to return"),
    offset: int = Query(0, ge=0, description="Number of feeds to skip"),
    db: Session = Depends(get_db)
):
    """
    Search and retrieve feeds with optional filters
    
    Returns list of feeds matching the criteria with:
    - Basic feed information
    - Nutritional values
    - Country information
    """
    try:
        query = db.query(Feed).filter(Feed.is_active == True)
        
        # Apply filters
        if country_id:
            try:
                country_uuid = uuid.UUID(country_id)
                query = query.filter(Feed.fd_country_id == country_uuid)
            except ValueError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid country_id format"
                )
        
        if feed_type:
            query = query.filter(Feed.fd_type == feed_type)
        
        if feed_category:
            query = query.filter(Feed.fd_category == feed_category)
        
        # Get total count
        total = query.count()
        
        # Apply pagination
        feeds = query.order_by(Feed.fd_name_default).offset(offset).limit(limit).all()
        
        # Format response
        result = []
        for feed in feeds:
            feed_dict = {
                "feed_id": str(feed.id),  # Primary ID field (matches FeedDetails interface)
                "id": str(feed.id),  # Alias for compatibility
                "fd_code": feed.fd_code,
                "fd_name": feed.fd_name_default if feed.fd_name_default else (feed.fd_name or ""),
                "fd_name_default": feed.fd_name_default,
                "fd_type": feed.fd_type,
                "fd_category": feed.fd_category,
                "fd_country_id": str(feed.fd_country_id),
                "fd_country_name": feed.fd_country_name,
                "fd_country_cd": feed.fd_country_cd,
                # Nutritional values
                "fd_dm": float(feed.fd_dm) if feed.fd_dm else None,
                "fd_ash": float(feed.fd_ash) if feed.fd_ash else None,
                "fd_cp": float(feed.fd_cp) if feed.fd_cp else None,
                "fd_ee": float(feed.fd_ee) if feed.fd_ee else None,
                "fd_st": float(feed.fd_st) if feed.fd_st else None,
                "fd_ndf": float(feed.fd_ndf) if feed.fd_ndf else None,
                "fd_adf": float(feed.fd_adf) if feed.fd_adf else None,
                "fd_lg": float(feed.fd_lg) if feed.fd_lg else None,
                "fd_ca": float(feed.fd_ca) if feed.fd_ca else None,
                "fd_p": float(feed.fd_p) if feed.fd_p else None,
                "fd_cf": float(feed.fd_cf) if feed.fd_cf else None,
                "fd_nfe": float(feed.fd_nfe) if feed.fd_nfe else None,
                "fd_hemicellulose": float(feed.fd_hemicellulose) if feed.fd_hemicellulose else None,
                "fd_cellulose": float(feed.fd_cellulose) if feed.fd_cellulose else None,
                "fd_ndin": float(feed.fd_ndin) if feed.fd_ndin else None,
                "fd_adin": float(feed.fd_adin) if feed.fd_adin else None,
                "fd_npn_cp": int(feed.fd_npn_cp) if feed.fd_npn_cp else None,
                # Metadata
                "fd_season": feed.fd_season,
                "fd_orginin": feed.fd_orginin,
                "fd_ipb_local_lab": feed.fd_ipb_local_lab,
                "is_active": feed.is_active,
                "created_at": feed.created_at.isoformat() if feed.created_at else None,
                "updated_at": feed.updated_at.isoformat() if feed.updated_at else None,
            }
            result.append(feed_dict)
        
        return {
            "total": total,
            "limit": limit,
            "offset": offset,
            "feeds": result
        }
        
    except Exception as e:
        logger.error(f"Error searching feeds: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to search feeds: {str(e)}"
        )

@router.get("/{feed_id}")
async def get_feed_by_id(
    feed_id: str,
    db: Session = Depends(get_db)
):
    """
    Get detailed information for a specific feed by ID
    
    Returns complete feed information including:
    - Basic feed information
    - Nutritional values
    - Country information
    - Translations (if available)
    """
    try:
        feed = db.query(Feed).filter(
            Feed.id == uuid.UUID(feed_id),
            Feed.is_active == True
        ).first()
        
        if not feed:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Feed not found"
            )
        
        # Format response
        feed_dict = {
            "feed_id": str(feed.id),  # Primary ID field (matches FeedDetails interface)
            "id": str(feed.id),  # Alias for compatibility
            "fd_code": feed.fd_code,
            "fd_name": feed.fd_name_default if feed.fd_name_default else (feed.fd_name or ""),
            "fd_name_default": feed.fd_name_default,
            "fd_type": feed.fd_type,
            "fd_category": feed.fd_category,
            "fd_country_id": str(feed.fd_country_id),
            "fd_country_name": feed.fd_country_name,
            "fd_country_cd": feed.fd_country_cd,
            # Nutritional values
            "fd_dm": float(feed.fd_dm) if feed.fd_dm else None,
            "fd_ash": float(feed.fd_ash) if feed.fd_ash else None,
            "fd_cp": float(feed.fd_cp) if feed.fd_cp else None,
            "fd_ee": float(feed.fd_ee) if feed.fd_ee else None,
            "fd_st": float(feed.fd_st) if feed.fd_st else None,
            "fd_ndf": float(feed.fd_ndf) if feed.fd_ndf else None,
            "fd_adf": float(feed.fd_adf) if feed.fd_adf else None,
            "fd_lg": float(feed.fd_lg) if feed.fd_lg else None,
            "fd_ca": float(feed.fd_ca) if feed.fd_ca else None,
            "fd_p": float(feed.fd_p) if feed.fd_p else None,
            "fd_cf": float(feed.fd_cf) if feed.fd_cf else None,
            "fd_nfe": float(feed.fd_nfe) if feed.fd_nfe else None,
            "fd_hemicellulose": float(feed.fd_hemicellulose) if feed.fd_hemicellulose else None,
            "fd_cellulose": float(feed.fd_cellulose) if feed.fd_cellulose else None,
            "fd_ndin": float(feed.fd_ndin) if feed.fd_ndin else None,
            "fd_adin": float(feed.fd_adin) if feed.fd_adin else None,
            "fd_npn_cp": int(feed.fd_npn_cp) if feed.fd_npn_cp else None,
            # Metadata
            "fd_season": feed.fd_season,
            "fd_orginin": feed.fd_orginin,
            "fd_ipb_local_lab": feed.fd_ipb_local_lab,
            "is_active": feed.is_active,
            "created_at": feed.created_at.isoformat() if feed.created_at else None,
            "updated_at": feed.updated_at.isoformat() if feed.updated_at else None,
        }
        
        # Include translations if available
        if feed.translations:
            feed_dict["translations"] = [
                {
                    "id": str(t.id),
                    "language_code": t.language_code,
                    "fd_name": t.fd_name,
                    "fd_description": t.fd_description,
                    "is_primary": t.is_primary
                }
                for t in feed.translations
            ]
        
        return feed_dict
        
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid feed_id format"
        )
    except Exception as e:
        logger.error(f"Error getting feed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get feed: {str(e)}"
        )

