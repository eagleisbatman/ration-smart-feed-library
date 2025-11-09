"""
OTP Service for Email-based Authentication
Generates, validates, and manages OTP codes
Supports both custom OTP generation and Supabase Auth
"""

import secrets
import string
import os
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import and_, func
from typing import Optional
import uuid

from app.models import Base
from sqlalchemy import Column, String, DateTime, Boolean, Integer
from sqlalchemy.dialects.postgresql import UUID

# Try to import Supabase
try:
    from supabase import create_client, Client
    SUPABASE_AVAILABLE = True
except ImportError:
    SUPABASE_AVAILABLE = False

# OTP Code Model
class OTPCode(Base):
    __tablename__ = 'otp_codes'
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email_id = Column(String(255), nullable=False)
    otp_code = Column(String(6), nullable=False)
    purpose = Column(String(50), nullable=False)  # 'login', 'registration', 'password_reset'
    expires_at = Column(DateTime, nullable=False)
    is_used = Column(Boolean, default=False)
    attempts = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)

def generate_otp(length: int = 6) -> str:
    """Generate a random numeric OTP"""
    return ''.join(secrets.choice(string.digits) for _ in range(length))

def get_supabase_client() -> Optional[Client]:
    """Get Supabase client if configured"""
    if not SUPABASE_AVAILABLE:
        return None
    
    supabase_url = os.getenv('SUPABASE_URL', '')
    supabase_key = os.getenv('SUPABASE_ANON_KEY', '')
    
    if not (supabase_url and supabase_key):
        return None
    
    try:
        return create_client(supabase_url, supabase_key)
    except Exception:
        return None

def create_otp(
    db: Session,
    email_id: str,
    purpose: str = 'login',
    expiry_minutes: int = 10,
    use_supabase: bool = None,  # None = auto-detect
    max_otps_per_hour: int = 5  # Rate limiting: max OTP requests per hour per email
) -> str:
    """
    Create a new OTP code for an email
    
    Args:
        db: Database session
        email_id: User's email address
        purpose: Purpose of OTP ('login', 'registration', 'password_reset')
        expiry_minutes: Minutes until OTP expires (default: 10)
        use_supabase: Force Supabase usage (None = auto-detect)
        max_otps_per_hour: Maximum OTP requests per hour per email (default: 5)
    
    Returns:
        The generated OTP code (or empty string if using Supabase)
    
    Raises:
        ValueError: If rate limit exceeded
    """
    # Rate limiting: Check OTP requests in the last hour
    one_hour_ago = datetime.utcnow() - timedelta(hours=1)
    recent_otps = db.query(func.count(OTPCode.id)).filter(
        and_(
            OTPCode.email_id == email_id,
            OTPCode.purpose == purpose,
            OTPCode.created_at >= one_hour_ago
        )
    ).scalar() or 0
    
    if recent_otps >= max_otps_per_hour:
        raise ValueError(
            f"Rate limit exceeded. Maximum {max_otps_per_hour} OTP requests per hour. "
            f"Please wait before requesting another OTP."
        )
    
    # Auto-detect: Use Supabase if configured
    if use_supabase is None:
        use_supabase = bool(os.getenv('SUPABASE_URL') and os.getenv('SUPABASE_ANON_KEY'))
    
    # If using Supabase, send OTP via Supabase Auth
    if use_supabase:
        supabase = get_supabase_client()
        if supabase:
            try:
                if purpose == 'login':
                    supabase.auth.sign_in_with_otp({
                        "email": email_id,
                        "options": {"should_create_user": False}
                    })
                elif purpose == 'registration':
                    supabase.auth.sign_up({
                        "email": email_id,
                        "options": {"email_redirect_to": None}
                    })
                elif purpose == 'password_reset':
                    supabase.auth.reset_password_for_email(email_id)
                
                # Supabase handles OTP internally, but we still create a record for tracking
                otp = generate_otp()  # Generate for our records
                expires_at = datetime.utcnow() + timedelta(minutes=expiry_minutes)
                
                otp_record = OTPCode(
                    email_id=email_id,
                    otp_code=otp,
                    purpose=purpose,
                    expires_at=expires_at
                )
                db.add(otp_record)
                db.commit()
                
                return otp  # Return generated code for our records
            except Exception as e:
                # Fallback to custom OTP if Supabase fails
                pass
    
    # Custom OTP generation (fallback or when Supabase not configured)
    # Invalidate any existing unused OTPs for this email and purpose
    db.query(OTPCode).filter(
        and_(
            OTPCode.email_id == email_id,
            OTPCode.purpose == purpose,
            OTPCode.is_used == False,
            OTPCode.expires_at > datetime.utcnow()
        )
    ).update({'is_used': True})
    
    # Generate new OTP
    otp = generate_otp()
    expires_at = datetime.utcnow() + timedelta(minutes=expiry_minutes)
    
    # Create OTP record
    otp_record = OTPCode(
        email_id=email_id,
        otp_code=otp,
        purpose=purpose,
        expires_at=expires_at
    )
    
    db.add(otp_record)
    db.commit()
    db.refresh(otp_record)
    
    return otp

def verify_otp(
    db: Session,
    email_id: str,
    otp_code: str,
    purpose: str = 'login',
    max_attempts: int = 5
) -> bool:
    """
    Verify an OTP code
    
    Args:
        db: Database session
        email_id: User's email address
        otp_code: OTP code to verify
        purpose: Purpose of OTP
        max_attempts: Maximum verification attempts
    
    Returns:
        True if OTP is valid, False otherwise
    """
    # Find unused, non-expired OTP
    otp_record = db.query(OTPCode).filter(
        and_(
            OTPCode.email_id == email_id,
            OTPCode.otp_code == otp_code,
            OTPCode.purpose == purpose,
            OTPCode.is_used == False,
            OTPCode.expires_at > datetime.utcnow()
        )
    ).first()
    
    if not otp_record:
        # Increment attempts for any recent OTPs (rate limiting)
        recent_otps = db.query(OTPCode).filter(
            and_(
                OTPCode.email_id == email_id,
                OTPCode.purpose == purpose,
                OTPCode.created_at > datetime.utcnow() - timedelta(minutes=10)
            )
        ).all()
        
        for otp in recent_otps:
            otp.attempts += 1
            if otp.attempts >= max_attempts:
                otp.is_used = True  # Lock out after max attempts
        
        db.commit()
        return False
    
    # Mark OTP as used
    otp_record.is_used = True
    db.commit()
    
    return True

def get_latest_otp(
    db: Session,
    email_id: str,
    purpose: str = 'login'
) -> Optional[OTPCode]:
    """Get the latest unused OTP for an email"""
    return db.query(OTPCode).filter(
        and_(
            OTPCode.email_id == email_id,
            OTPCode.purpose == purpose,
            OTPCode.is_used == False,
            OTPCode.expires_at > datetime.utcnow()
        )
    ).order_by(OTPCode.created_at.desc()).first()

def cleanup_expired_otps(db: Session, older_than_hours: int = 24):
    """Clean up expired OTPs older than specified hours"""
    cutoff = datetime.utcnow() - timedelta(hours=older_than_hours)
    db.query(OTPCode).filter(OTPCode.expires_at < cutoff).delete()
    db.commit()
