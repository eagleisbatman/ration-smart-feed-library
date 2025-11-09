from pydantic import BaseModel,Field, EmailStr, validator
from typing import List, Optional, Dict, Any, Union
from sqlalchemy import Column, Integer, String, Numeric, Date, Boolean, ForeignKey, Text, DateTime, DECIMAL, JSON
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from datetime import date
from datetime import datetime
# from typing import Any
import re
import uuid
from sqlalchemy.orm import Session
from sqlalchemy import LargeBinary

# Define the SQLAlchemy base
Base = declarative_base()

# New Country Model for Authentication System
class CountryModel(Base):
    __tablename__ = 'countries'

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, unique=True, nullable=False)
    name = Column(String(100), nullable=False, unique=True)
    country_code = Column(String(3), nullable=False, unique=True)
    currency = Column(String(10), nullable=True)  # New currency column
    is_active = Column(Boolean, default=False, nullable=False)  # Flag to control if country is active for registration
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # Relationships
    users = relationship("UserInformationModel", back_populates="country_rel")
    feeds = relationship("Feed", back_populates="country_rel")
    languages = relationship("CountryLanguage", back_populates="country", cascade="all, delete-orphan")

class UserInformationModel(Base):
    __tablename__ = 'users'

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, unique=True, nullable=False)
    name = Column(String(100), nullable=False)
    
    # Authentication fields
    email_id = Column(String(255), nullable=False, unique=True)
    pin_hash = Column(String(255), nullable=True)  # Made nullable for OTP-only users
    country_id = Column(UUID(as_uuid=True), ForeignKey('countries.id'), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # Relationship to country
    country_rel = relationship("CountryModel", back_populates="users")
    
    # Admin flags
    is_admin = Column(Boolean, default=False, nullable=False)
    is_superadmin = Column(Boolean, default=False, nullable=False)  # Superadmin can create country admins
    country_admin_country_id = Column(UUID(as_uuid=True), ForeignKey('countries.id'), nullable=True)  # Country-level admin
    
    # User status flag for admin management
    is_active = Column(Boolean, default=True, nullable=False)
    
    # Multi-tenant support: Optional organization association
    organization_id = Column(UUID(as_uuid=True), ForeignKey('organizations.id'), nullable=True)
    organization_admin_org_id = Column(UUID(as_uuid=True), ForeignKey('organizations.id'), nullable=True)  # Organization admin
    
    # Relationship to user feedback
    feedbacks = relationship("UserFeedback", back_populates="user")
    
    # Relationship to organization (for multi-tenant support)
    # Note: This relationship is defined in multi_tenant_models.py to avoid circular imports



# New Authentication Pydantic Models

class Country(BaseModel):
    id: Optional[str] = Field(None, description="Country UUID")
    name: str = Field(..., max_length=100, description="Country name")
    country_code: str = Field(..., max_length=3, description="ISO 3-letter country code")
    currency: Optional[str] = Field(None, max_length=10, description="Country currency code (e.g., USD, EUR, INR)")
    is_active: bool = Field(..., description="Flag indicating if country is active for registration")
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        orm_mode = True

class UserRegistration(BaseModel):
    name: str = Field(..., min_length=1, max_length=100, description="User's full name")
    email_id: str = Field(..., max_length=255, description="User's email address")
    country_id: str = Field(..., description="Country UUID")
    otp_code: str = Field(..., min_length=6, max_length=6, description="6-digit OTP code sent to email")

    @validator('email_id')
    def validate_email_format(cls, v):
        """Validate email format using regex"""
        email_regex = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        if not re.match(email_regex, v):
            raise ValueError('Invalid email format')
        return v.lower().strip()

    @validator('otp_code')
    def validate_otp(cls, v):
        """Validate OTP is exactly 6 digits"""
        if not v.isdigit():
            raise ValueError('OTP must contain only digits')
        if len(v) != 6:
            raise ValueError('OTP must be exactly 6 digits')
        return v

    @validator('name')
    def validate_name(cls, v):
        """Validate name is not empty after stripping"""
        v = v.strip()
        if not v:
            raise ValueError('Name cannot be empty')
        return v

class UserLogin(BaseModel):
    email_id: str = Field(..., max_length=255, description="User's email address")
    otp_code: str = Field(..., min_length=6, max_length=6, description="6-digit OTP code sent to email")

    @validator('email_id')
    def validate_email_format(cls, v):
        """Validate email format using regex"""
        email_regex = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        if not re.match(email_regex, v):
            raise ValueError('Invalid email format')
        return v.lower().strip()

    @validator('otp_code')
    def validate_otp(cls, v):
        """Validate OTP is exactly 6 digits"""
        if not v.isdigit():
            raise ValueError('OTP must contain only digits')
        if len(v) != 6:
            raise ValueError('OTP must be exactly 6 digits')
        return v

# Legacy PIN-based models (for backward compatibility during migration)
class UserRegistrationLegacy(BaseModel):
    name: str = Field(..., min_length=1, max_length=100, description="User's full name")
    email_id: str = Field(..., max_length=255, description="User's email address")
    pin: str = Field(..., min_length=4, max_length=4, description="4-digit PIN (legacy)")
    country_id: str = Field(..., description="Country UUID")

    @validator('email_id')
    def validate_email_format(cls, v):
        email_regex = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        if not re.match(email_regex, v):
            raise ValueError('Invalid email format')
        return v.lower().strip()

    @validator('pin')
    def validate_pin(cls, v):
        if not v.isdigit():
            raise ValueError('PIN must contain only digits')
        if len(v) != 4:
            raise ValueError('PIN must be exactly 4 digits')
        return v

class UserLoginLegacy(BaseModel):
    email_id: str = Field(..., max_length=255, description="User's email address")
    pin: str = Field(..., min_length=4, max_length=4, description="4-digit PIN (legacy)")

    @validator('email_id')
    def validate_email_format(cls, v):
        email_regex = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        if not re.match(email_regex, v):
            raise ValueError('Invalid email format')
        return v.lower().strip()

    @validator('pin')
    def validate_pin(cls, v):
        if not v.isdigit():
            raise ValueError('PIN must contain only digits')
        if len(v) != 4:
            raise ValueError('PIN must be exactly 4 digits')
        return v

class UserResponse(BaseModel):
    id: str = Field(..., description="User UUID")
    name: str = Field(..., description="User's name")
    email_id: str = Field(..., description="User's email address")
    country_id: Optional[str] = Field(None, description="Country UUID")
    country: Optional[Country] = Field(None, description="Country information")
    is_admin: bool = Field(False, description="Admin status flag")
    is_superadmin: bool = Field(False, description="Superadmin status flag")
    country_admin_country_id: Optional[str] = Field(None, description="Country admin assignment")
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        orm_mode = True

class AuthenticationResponse(BaseModel):
    success: bool = Field(..., description="Authentication success status")
    message: str = Field(..., description="Response message")
    user: Optional[UserResponse] = Field(None, description="User information if successful")

class OTPRequest(BaseModel):
    email_id: str = Field(..., max_length=255, description="Email address to send OTP")
    purpose: str = Field(default='login', description="OTP purpose: 'login', 'registration', 'password_reset'")

    @validator('email_id')
    def validate_email_format(cls, v):
        email_regex = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        if not re.match(email_regex, v):
            raise ValueError('Invalid email format')
        return v.lower().strip()

    @validator('purpose')
    def validate_purpose(cls, v):
        allowed = ['login', 'registration', 'password_reset']
        if v not in allowed:
            raise ValueError(f'Purpose must be one of: {", ".join(allowed)}')
        return v

class OTPResponse(BaseModel):
    success: bool = Field(..., description="Request success status")
    message: str = Field(..., description="Response message")
    otp_code: Optional[str] = Field(None, description="OTP code (only in development mode)")

class ForgotPinRequest(BaseModel):
    email_id: str = Field(..., max_length=255, description="User's registered email address")

    @validator('email_id')
    def validate_email_format(cls, v):
        """Validate email format using regex"""
        email_regex = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        if not re.match(email_regex, v):
            raise ValueError('Invalid email format')
        return v.lower().strip()

class ForgotPinResponse(BaseModel):
    success: bool = Field(..., description="Request success status")
    message: str = Field(..., description="Response message")
    new_pin: Optional[str] = Field(None, description="New 4-digit PIN (only in response)")

class ChangePinRequest(BaseModel):
    email_id: str = Field(..., max_length=255, description="User's email address")
    current_pin: str = Field(..., min_length=4, max_length=4, description="Current 4-digit PIN")
    new_pin: str = Field(..., min_length=4, max_length=4, description="New 4-digit PIN")

    @validator('email_id')
    def validate_email_format(cls, v):
        """Validate email format using regex"""
        email_regex = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        if not re.match(email_regex, v):
            raise ValueError('Invalid email format')
        return v.lower().strip()

    @validator('current_pin', 'new_pin')
    def validate_pins(cls, v):
        """Validate PIN is exactly 4 digits"""
        if not v.isdigit():
            raise ValueError('PIN must contain only digits')
        if len(v) != 4:
            raise ValueError('PIN must be exactly 4 digits')
        return v

class ChangePinResponse(BaseModel):
    success: bool = Field(..., description="Change success status")
    message: str = Field(..., description="Response message")

# Updated UserInformation model (now using email-based authentication)
class UserInformation(BaseModel):
    name: str = Field(..., max_length=100, description="User's name")
    email_id: str = Field(..., max_length=255, description="User's email address")
    country_id: str = Field(..., description="Country UUID")

    @validator('email_id')
    def validate_email_format(cls, v):
        """Validate email format using regex"""
        email_regex = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        if not re.match(email_regex, v):
            raise ValueError('Invalid email format')
        return v.lower().strip()

    @validator('name')
    def validate_name(cls, v):
        """Validate name is not empty after stripping"""
        v = v.strip()
        if not v:
            raise ValueError('Name cannot be empty')
        return v

    class Config:
        orm_mode = True

# Pydantic Models
class AnimalCharacteristics(BaseModel):
    name: str
    country: str
    location: str
    language: str
    lactating: bool
    body_weight: float
    # mature_body_weight: float
    breed: str
    tp_milk: float
    fat_milk: float
    lactose_milk: float
    days_in_milk: int
    milk_production: float
    days_of_pregnancy: int
    calving_interval: int
    parity: int
    topography: str
    housing: str
    temperature: float
    feeds: List



# SQLAlchemy Models

class Feed(Base):
    __tablename__ = 'feeds'

    # Primary Key
    id = Column(UUID(as_uuid=True), default=uuid.uuid4, primary_key=True, nullable=False)

    # Feed Code (format: 'IND-1223' - country_code + '-' + unique number)
    fd_code = Column(Text, nullable=False)  # Database stores as text

    # Country Information
    fd_country_id = Column(UUID(as_uuid=True), ForeignKey('countries.id'), nullable=False)
    fd_country_name = Column(Text, nullable=True)
    fd_country_cd = Column(Text, nullable=True)

    # Feed Information
    fd_name = Column(Text, nullable=True)  # Legacy field, kept for backward compatibility
    fd_name_default = Column(String(255), nullable=False)  # Default name (English, for reference/search)
    fd_category = Column(Text, nullable=True)
    fd_type = Column(Text, nullable=True)
    fd_category_id = Column(UUID(as_uuid=True), ForeignKey('feed_categories.id'), nullable=True)

    # Nutritional Data (stored as DECIMAL(10,2) for precision control)
    fd_dm = Column(DECIMAL(10,2), nullable=True)  # Dry matter
    fd_ash = Column(DECIMAL(10,2), nullable=True)  # Ash
    fd_cp = Column(DECIMAL(10,2), nullable=True)   # Crude protein
    fd_npn_cp = Column(Integer, nullable=True)  # Non-protein nitrogen (keep as integer)
    fd_ee = Column(DECIMAL(10,2), nullable=True)   # Ether extract
    fd_cf = Column(DECIMAL(10,2), nullable=True)   # Crude fiber
    fd_nfe = Column(DECIMAL(10,2), nullable=True) # Nitrogen free extract
    fd_st = Column(DECIMAL(10,2), nullable=True)   # Starch
    fd_ndf = Column(DECIMAL(10,2), nullable=True)  # Neutral detergent fiber
    fd_hemicellulose = Column(DECIMAL(10,2), nullable=True)  # Hemicellulose
    fd_adf = Column(DECIMAL(10,2), nullable=True)  # Acid detergent fiber
    fd_cellulose = Column(DECIMAL(10,2), nullable=True)  # Cellulose
    fd_lg = Column(DECIMAL(10,2), nullable=True)   # Lignin
    fd_ndin = Column(DECIMAL(10,2), nullable=True) # Neutral detergent insoluble nitrogen
    fd_adin = Column(DECIMAL(10,2), nullable=True) # Acid detergent insoluble nitrogen
    fd_ca = Column(DECIMAL(10,2), nullable=True)   # Calcium
    fd_p = Column(DECIMAL(10,2), nullable=True)    # Phosphorus

    # Additional Fields
    # fd_country = Column(Text, nullable=True)  # DEPRECATED: Use fd_country_name instead
    fd_season = Column(Text, nullable=True)
    fd_orginin = Column(Text, nullable=True)
    fd_ipb_local_lab = Column(Text, nullable=True)
    
    # Status flag
    is_active = Column(Boolean, default=True, nullable=False)

    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    country_rel = relationship("CountryModel", back_populates="feeds")
    feed_category_rel = relationship("FeedCategory", foreign_keys=[fd_category_id])
    translations = relationship("FeedTranslation", back_populates="feed", cascade="all, delete-orphan")


class FeedTranslation(Base):
    """Feed Translation model for multi-language feed names"""
    __tablename__ = 'feed_translations'

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, nullable=False)
    feed_id = Column(UUID(as_uuid=True), ForeignKey('feeds.id', ondelete='CASCADE'), nullable=False)
    language_code = Column(String(10), nullable=False)  # ISO 639-1 or 639-2
    country_id = Column(UUID(as_uuid=True), ForeignKey('countries.id'), nullable=True)  # NULL = global translation
    fd_name = Column(String(255), nullable=False)
    fd_description = Column(Text, nullable=True)
    is_primary = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    feed = relationship("Feed", back_populates="translations")
    country = relationship("CountryModel", foreign_keys=[country_id])


class CountryLanguage(Base):
    """Country Language mapping model"""
    __tablename__ = 'country_languages'

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, nullable=False)
    country_id = Column(UUID(as_uuid=True), ForeignKey('countries.id', ondelete='CASCADE'), nullable=False)
    language_code = Column(String(10), nullable=False)  # ISO 639-1 or 639-2
    language_name = Column(String(100), nullable=False)  # 'English', 'Afan Oromo', 'Amharic'
    is_default = Column(Boolean, default=False, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    country = relationship("CountryModel", back_populates="languages")


class CustomFeed(Base):
    __tablename__ = 'custom_feeds'

    # Primary Key
    id = Column(UUID(as_uuid=True), default=uuid.uuid4, primary_key=True, nullable=False)

    # User Foreign Key
    user_id = Column(UUID(as_uuid=True), ForeignKey('users.id'), nullable=False)

    # Feed Code (format: 'CUST-XXXX' - custom feed sequential number)
    fd_code = Column(String(20), unique=True, nullable=False)

    # Country Information
    fd_country_id = Column(UUID(as_uuid=True), ForeignKey('countries.id'), nullable=True)
    fd_country_name = Column(String(100), nullable=True)  # Maps to old Fd_Country
    fd_country_cd = Column(String(10), nullable=True)

    # Feed Information
    fd_name = Column(String(100), nullable=False)
    fd_category = Column(String(50), nullable=True)
    fd_type = Column(String(50), nullable=True)
    # Nutritional Data (stored as DECIMAL(10,2) for precision control)
    fd_dm = Column(DECIMAL(10,2), nullable=True)  # Dry matter
    fd_ash = Column(DECIMAL(10,2), nullable=True)  # Ash
    fd_cp = Column(DECIMAL(10,2), nullable=True)   # Crude protein
    fd_npn_cp = Column(Integer, nullable=True)  # Non-protein nitrogen (keep as integer)
    fd_ee = Column(DECIMAL(10,2), nullable=True)   # Ether extract
    fd_cf = Column(DECIMAL(10,2), nullable=True)   # Crude fiber
    fd_nfe = Column(DECIMAL(10,2), nullable=True) # Nitrogen free extract
    fd_st = Column(DECIMAL(10,2), nullable=True)   # Starch (aligned with Feed model)
    fd_ndf = Column(DECIMAL(10,2), nullable=True)  # Neutral detergent fiber
    fd_hemicellulose = Column(DECIMAL(10,2), nullable=True)  # Hemicellulose
    fd_adf = Column(DECIMAL(10,2), nullable=True)  # Acid detergent fiber
    fd_cellulose = Column(DECIMAL(10,2), nullable=True)  # Cellulose
    fd_lg = Column(DECIMAL(10,2), nullable=True)   # Lignin (aligned with Feed model)
    fd_ndin = Column(DECIMAL(10,2), nullable=True) # Neutral detergent insoluble nitrogen
    fd_adin = Column(DECIMAL(10,2), nullable=True) # Acid detergent insoluble nitrogen
    fd_ca = Column(DECIMAL(10,2), nullable=True)   # Calcium (aligned with Feed model)
    fd_p = Column(DECIMAL(10,2), nullable=True)    # Phosphorus (aligned with Feed model)

    # Additional Fields
    fd_season = Column(String(50), nullable=True)
    fd_orginin = Column(String(50), nullable=True)
    fd_ipb_local_lab = Column(String(50), nullable=True)

    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    user_rel = relationship("UserInformationModel", backref="custom_feeds")
    country_rel = relationship("CountryModel", backref="custom_feeds")


def generate_next_custom_feed_code(db: Session) -> str:
    """
    Generate the next available custom feed code in format CUST-XXXX
    where XXXX is a 4-digit sequential number starting from 0001
    
    Args:
        db: Database session
        
    Returns:
        str: Next available feed code in format CUST-XXXX
    """
    # Query for the highest existing CUST-XXXX code
    result = db.query(CustomFeed.fd_code).filter(
        CustomFeed.fd_code.like('CUST-%')
    ).all()
    
    if not result:
        # No existing CUST codes, start with CUST-0001
        return "CUST-0001"
    
    # Extract numbers from existing codes and find the highest
    max_number = 0
    for row in result:
        feed_code = row[0]
        if feed_code.startswith('CUST-'):
            try:
                number_part = feed_code[5:]  # Remove 'CUST-' prefix
                number = int(number_part)
                max_number = max(max_number, number)
            except ValueError:
                # Skip invalid codes
                continue
    
    # Generate next number
    next_number = max_number + 1
    
    # Format as CUST-XXXX with leading zeros
    return f"CUST-{next_number:04d}"


class FeedAnalytics(Base):
    __tablename__ = 'feed_analytics'
    
    # Primary key (UUID-based, consistent with other tables)
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, unique=True, nullable=False)
    
    # Business fields (all required except farmer_adopted)
    da_name = Column(String(100), nullable=False)
    da_phone_num = Column(String(100), nullable=False)
    country_cd = Column(String(3), nullable=False)
    country_name = Column(String(100), nullable=False)
    animal_info = Column(Text, nullable=False)
    sys_rcmd = Column(Text, nullable=False)
    cust_rcmd = Column(Text, nullable=False)
    farmer_name = Column(Text, nullable=False)
    farmer_phone_num = Column(String(100), nullable=False)
    rcmd_dt = Column(Date, default=datetime.today, nullable=False)
    farmer_adopted = Column(Boolean, nullable=True)  # Optional field
    
    # Audit trail
    created_on = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_on = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

# Pydantic Models for Feed Analytics
class FeedAnalyticsBase(BaseModel):
    da_name: str = Field(..., max_length=100, description="Data analyst name")
    da_phone_num: str = Field(..., max_length=100, description="Data analyst phone number")
    country_cd: str = Field(..., max_length=3, description="Country code")
    country_name: str = Field(..., max_length=100, description="Country name")
    animal_info: str = Field(..., description="Animal information")
    sys_rcmd: str = Field(..., description="System recommendation")
    cust_rcmd: str = Field(..., description="Custom recommendation")
    farmer_name: str = Field(..., description="Farmer name")
    farmer_phone_num: str = Field(..., max_length=100, description="Farmer phone number")
    rcmd_dt: date = Field(..., description="Recommendation date")
    farmer_adopted: Optional[bool] = Field(None, description="Whether farmer adopted the recommendation")

class FeedAnalyticsCreate(FeedAnalyticsBase):
    pass

class FeedAnalyticsUpdate(BaseModel):
    da_name: Optional[str] = Field(None, max_length=100, description="Data analyst name")
    da_phone_num: Optional[str] = Field(None, max_length=100, description="Data analyst phone number")
    country_cd: Optional[str] = Field(None, max_length=3, description="Country code")
    country_name: Optional[str] = Field(None, max_length=100, description="Country name")
    animal_info: Optional[str] = Field(None, description="Animal information")
    sys_rcmd: Optional[str] = Field(None, description="System recommendation")
    cust_rcmd: Optional[str] = Field(None, description="Custom recommendation")
    farmer_name: Optional[str] = Field(None, description="Farmer name")
    farmer_phone_num: Optional[str] = Field(None, max_length=100, description="Farmer phone number")
    rcmd_dt: Optional[date] = Field(None, description="Recommendation date")
    farmer_adopted: Optional[bool] = Field(None, description="Whether farmer adopted the recommendation")

class FeedAnalyticsResponse(FeedAnalyticsBase):
    id: str
    created_on: datetime
    updated_on: datetime

    @validator('id', pre=True)
    def convert_uuid_to_str(cls, v):
        return str(v) if v else v

    @validator('rcmd_dt', pre=True)
    def convert_date_to_str(cls, v):
        if isinstance(v, date):
            return v.isoformat()
        return v

    class Config:
        orm_mode = True


class FeedDetailsResponse(BaseModel):
    """Response model for feed details API endpoint"""
    feed_id: str = Field(..., description="Feed UUID")
    fd_code: Union[float, str] = Field(..., description="Feed code (float for feeds, str for custom_feeds)")
    fd_name: str = Field(..., description="Feed name")
    fd_type: Optional[str] = Field(None, description="Feed type")
    fd_category: Optional[str] = Field(None, description="Feed category")
    fd_country_id: Optional[str] = Field(None, description="Country UUID")
    fd_country_name: Optional[str] = Field(None, description="Country name")
    fd_country_cd: Optional[str] = Field(None, description="Country code")
    
    # Nutrient fields (using exact database column names)
    fd_dm: Optional[float] = Field(None, description="Dry Matter %")
    fd_ash: Optional[float] = Field(None, description="Ash %")
    fd_cp: Optional[float] = Field(None, description="Crude Protein %")
    fd_ee: Optional[float] = Field(None, description="Ether Extract %")
    fd_st: Optional[float] = Field(None, description="Starch %")
    fd_ndf: Optional[float] = Field(None, description="Neutral Detergent Fiber %")
    fd_adf: Optional[float] = Field(None, description="Acid Detergent Fiber %")
    fd_lg: Optional[float] = Field(None, description="Lignin %")
    
    # Additional nutrient fields
    fd_ndin: Optional[float] = Field(None, description="Neutral Detergent Insoluble Nitrogen %")
    fd_adin: Optional[float] = Field(None, description="Acid Detergent Insoluble Nitrogen %")
    fd_ca: Optional[float] = Field(None, description="Calcium %")
    fd_p: Optional[float] = Field(None, description="Phosphorus %")
    
    # More nutrient fields
    fd_cf: Optional[float] = Field(None, description="Crude Fiber %")
    fd_nfe: Optional[float] = Field(None, description="Nitrogen Free Extract %")
    fd_hemicellulose: Optional[float] = Field(None, description="Hemicellulose %")
    fd_cellulose: Optional[float] = Field(None, description="Cellulose %")
    
    # Additional fields
    fd_npn_cp: Optional[int] = Field(None, description="Non-protein nitrogen")

    fd_season: Optional[str] = Field(None, description="Season")
    fd_orginin: Optional[str] = Field(None, description="Origin ID")
    fd_ipb_local_lab: Optional[str] = Field(None, description="IPB Local Lab ID")
    created_at: Optional[datetime] = Field(None, description="Creation timestamp")
    updated_at: Optional[datetime] = Field(None, description="Last update timestamp")

    class Config:
        orm_mode = True

# Feed Classification Models
class FeedType(Base):
    __tablename__ = 'feed_types'

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, unique=True, nullable=False)
    type_name = Column(String(100), nullable=False)  # e.g., 'Forage', 'Concentrate'
    description = Column(Text, nullable=True)
    sort_order = Column(Integer, default=0, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # Relationships
    categories = relationship("FeedCategory", back_populates="feed_type", cascade="all, delete-orphan")

class FeedCategory(Base):
    __tablename__ = 'feed_categories'

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, unique=True, nullable=False)
    category_name = Column(String(100), nullable=False)  # e.g., 'Grain Crop Forage'
    feed_type_id = Column(UUID(as_uuid=True), ForeignKey('feed_types.id'), nullable=False)
    description = Column(Text, nullable=True)
    sort_order = Column(Integer, default=0, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # Relationships
    feed_type = relationship("FeedType", back_populates="categories")

# Pydantic Models for Feed Classification
class FeedTypeBase(BaseModel):
    type_name: str = Field(..., max_length=100, description="Display name for feed type")
    description: Optional[str] = Field(None, description="Optional description")
    sort_order: Optional[int] = Field(0, description="Display order")

class FeedTypeCreate(FeedTypeBase):
    pass

class FeedTypeUpdate(BaseModel):
    type_name: Optional[str] = Field(None, max_length=100, description="Display name for feed type")
    description: Optional[str] = Field(None, description="Optional description")
    sort_order: Optional[int] = Field(None, description="Display order")

class FeedTypeResponse(FeedTypeBase):
    id: str = Field(..., description="Feed type UUID")
    is_active: bool = Field(..., description="Active status")
    created_at: Optional[datetime] = Field(None, description="Creation timestamp")
    updated_at: Optional[datetime] = Field(None, description="Last update timestamp")

    class Config:
        orm_mode = True

class FeedCategoryBase(BaseModel):
    category_name: str = Field(..., max_length=100, description="Display name for feed category")
    feed_type_id: str = Field(..., description="Feed type UUID")
    description: Optional[str] = Field(None, description="Optional description")
    sort_order: Optional[int] = Field(0, description="Display order")

class FeedCategoryCreate(FeedCategoryBase):
    pass

class FeedCategoryUpdate(BaseModel):
    category_name: Optional[str] = Field(None, max_length=100, description="Display name for feed category")
    feed_type_id: Optional[str] = Field(None, description="Feed type UUID")
    description: Optional[str] = Field(None, description="Optional description")
    sort_order: Optional[int] = Field(None, description="Display order")

class FeedCategoryResponse(FeedCategoryBase):
    id: str = Field(..., description="Feed category UUID")
    is_active: bool = Field(..., description="Active status")
    created_at: Optional[datetime] = Field(None, description="Creation timestamp")
    updated_at: Optional[datetime] = Field(None, description="Last update timestamp")
    feed_type: Optional[FeedTypeResponse] = Field(None, description="Associated feed type")

    class Config:
        orm_mode = True

class FeedClassificationStructure(BaseModel):
    """Response model for complete feed classification structure"""
    types: List[FeedTypeResponse] = Field(..., description="List of feed types with their categories")

    class Config:
        orm_mode = True

class FeedClassificationStructureResponse(BaseModel):
    """New response model for feed classification structure with nested format"""
    feed_classification: List[Dict[str, Any]] = Field(..., description="List of feed types with their categories")

    class Config:
        orm_mode = True

# Cattle Info Model
class CattleInfo(BaseModel):
    """Cattle information for feed calculation"""
    body_weight: float = Field(..., description="Body weight in kg", example=650)
    breed: str = Field(..., description="Cattle breed", example="Holstein cross")
    lactating: bool = Field(..., description="Whether the cow is lactating", example=True)
    milk_production: float = Field(..., description="Milk production in liters per day", example=25.0)
    days_in_milk: int = Field(..., description="Days in milk", example=100)
    parity: int = Field(..., description="Parity number", example=2)
    days_of_pregnancy: int = Field(..., description="Days of pregnancy", example=0)
    tp_milk: float = Field(..., description="True protein percentage in milk", example=3.2)
    fat_milk: float = Field(..., description="Fat percentage in milk", example=3.8)
    temperature: float = Field(..., description="Environmental temperature in Celsius", example=20.0)
    topography: str = Field(..., description="Topography (Flat/Hilly)", example="Flat")
    distance: float = Field(..., description="Distance in km", example=1.0)
    calving_interval: int = Field(..., description="Calving interval in days", example=370)
    bw_gain: float = Field(0.2, description="Body weight gain (kg/day)", example=0.2)
    bc_score: float = Field(3.0, description="Body condition score (1-5)", example=3.0)

# Diet Evaluation Models
class FeedEvaluationItem(BaseModel):
    """Individual feed item for diet evaluation"""
    feed_id: str = Field(..., description="Feed UUID from feeds or custom_feeds table")
    quantity_as_fed: float = Field(..., gt=0, description="Quantity in kg/day (as-fed basis)")
    price_per_kg: float = Field(..., ge=0, description="Price per kg in local currency")

    @validator('feed_id')
    def validate_feed_id(cls, v):
        """Validate feed_id is a valid UUID"""
        try:
            uuid.UUID(v)
            return v
        except ValueError:
            raise ValueError('feed_id must be a valid UUID')

class DietEvaluationRequest(BaseModel):
    """Request model for diet evaluation endpoint"""
    user_id: str = Field(..., description="User UUID who is requesting the diet evaluation")
    country_id: str = Field(..., description="Country UUID for the evaluation context")
    simulation_id: str = Field(..., description="Simulation identifier", example="sim-1234")
    currency: str = Field(..., max_length=3, description="Currency code (e.g., INR, USD, EUR)", example="INR")
    cattle_info: CattleInfo = Field(..., description="Cattle characteristics and requirements")
    feed_evaluation: List[FeedEvaluationItem] = Field(..., min_items=1, description="List of feeds with quantities and prices")

    @validator('user_id')
    def validate_user_id(cls, v):
        """Validate user_id is a valid UUID"""
        try:
            uuid.UUID(v)
            return v
        except ValueError:
            raise ValueError('user_id must be a valid UUID format (e.g., 954683d9-500d-40e8-9fb0-dc6e30998fa4)')

    @validator('country_id')
    def validate_country_id(cls, v):
        """Validate country_id is a valid UUID"""
        try:
            uuid.UUID(v)
            return v
        except ValueError:
            raise ValueError('country_id must be a valid UUID format (e.g., 6c2a0573-1500-4603-8795-633ff80f1b00)')

    @validator('currency')
    def validate_currency(cls, v):
        """Validate currency code format"""
        if not re.match(r'^[A-Z]{3}$', v):
            raise ValueError('currency must be a 3-letter currency code (e.g., INR, USD, EUR)')
        return v

class MilkProductionAnalysis(BaseModel):
    """Milk production analysis results"""
    target_production_kg_per_day: float = Field(..., description="Target milk production")
    milk_supported_by_energy_kg_per_day: float = Field(..., description="Milk supported by energy")
    milk_supported_by_protein_kg_per_day: float = Field(..., description="Milk supported by protein")
    actual_milk_supported_kg_per_day: float = Field(..., description="Actual milk production supported")
    limiting_nutrient: str = Field(..., description="Limiting nutrient (Energy/Protein)")
    energy_available_mcal: float = Field(..., description="Energy available for milk production")
    protein_available_g: float = Field(..., description="Protein available for milk production")
    warnings: List[str] = Field(default_factory=list, description="Warnings related to milk production")
    recommendations: List[str] = Field(default_factory=list, description="Recommendations for milk production")

class IntakeEvaluation(BaseModel):
    """Dry matter intake evaluation results"""
    intake_status: str = Field(..., description="Intake status (Adequate/Below target/Above target)")
    actual_intake_kg_per_day: float = Field(..., description="Actual dry matter intake")
    target_intake_kg_per_day: float = Field(..., description="Target dry matter intake")
    intake_difference_kg_per_day: float = Field(..., description="Difference between actual and target intake")
    intake_percentage: float = Field(..., description="Actual intake as percentage of target")
    warnings: List[str] = Field(default_factory=list, description="Warnings related to intake")
    recommendations: List[str] = Field(default_factory=list, description="Recommendations for intake")

class CostAnalysis(BaseModel):
    """Cost analysis results"""
    total_diet_cost_as_fed: float = Field(..., description="Total diet cost (as-fed basis)")
    feed_cost_per_kg_milk: float = Field(..., description="Feed cost per kg of milk produced")
    currency: str = Field(..., description="Currency code")
    warnings: List[str] = Field(default_factory=list, description="Warnings related to cost")
    recommendations: List[str] = Field(default_factory=list, description="Recommendations for cost optimization")

class MethaneAnalysis(BaseModel):
    """Methane emission analysis results"""
    methane_emission_mj_per_day: float = Field(..., description="Methane emission in MJ per day")
    methane_production_g_per_day: float = Field(..., description="Methane production in grams per day")
    methane_yield_g_per_kg_dmi: float = Field(..., description="Methane yield in g per kg DMI")
    methane_intensity_g_per_kg_ecm: float = Field(..., description="Methane intensity in g per kg ECM")
    methane_conversion_rate_percent: float = Field(..., description="Methane conversion rate percentage")
    methane_conversion_range: str = Field(..., description="Methane conversion range category")
    warnings: List[str] = Field(default_factory=list, description="Warnings related to methane emissions")
    recommendations: List[str] = Field(default_factory=list, description="Recommendations for methane reduction")

class NutrientBalance(BaseModel):
    """Nutrient balance analysis results"""
    energy_balance_mcal: float = Field(..., description="Energy balance (supply - requirement)")
    protein_balance_kg: float = Field(..., description="Protein balance (supply - requirement)")
    calcium_balance_kg: float = Field(..., description="Calcium balance (supply - requirement)")
    phosphorus_balance_kg: float = Field(..., description="Phosphorus balance (supply - requirement)")
    ndf_balance_kg: float = Field(..., description="NDF balance (supply - requirement)")
    warnings: List[str] = Field(default_factory=list, description="Warnings related to nutrient balance")
    recommendations: List[str] = Field(default_factory=list, description="Recommendations for nutrient balance")

class FeedBreakdownItem(BaseModel):
    """Individual feed breakdown in diet evaluation"""
    feed_id: str = Field(..., description="Feed UUID")
    feed_name: str = Field(..., description="Feed name")
    feed_type: str = Field(..., description="Feed type (Forage/Concentrate/Mineral)")
    quantity_as_fed_kg_per_day: float = Field(..., description="Quantity as-fed in kg per day")
    quantity_dm_kg_per_day: float = Field(..., description="Quantity dry matter in kg per day")
    price_per_kg: float = Field(..., description="Price per kg")
    total_cost: float = Field(..., description="Total cost for this feed")
    contribution_percent: float = Field(..., description="Contribution percentage to total diet")

class DietEvaluationSummary(BaseModel):
    """Overall diet evaluation summary"""
    overall_status: str = Field(..., description="Overall diet status (Adequate/Marginal/Inadequate)")
    limiting_factor: str = Field(..., description="Main limiting factor")

class DietEvaluationResponse(BaseModel):
    """Response model for diet evaluation endpoint"""
    simulation_id: str = Field(..., description="Simulation identifier")
    report_id: str = Field(..., description="Report identifier")
    currency: str = Field(..., description="Currency code")
    country: str = Field(..., description="Country name")
    evaluation_summary: DietEvaluationSummary = Field(..., description="Overall evaluation summary")
    milk_production_analysis: MilkProductionAnalysis = Field(..., description="Milk production analysis")
    intake_evaluation: IntakeEvaluation = Field(..., description="Intake evaluation")
    cost_analysis: CostAnalysis = Field(..., description="Cost analysis")
    methane_analysis: MethaneAnalysis = Field(..., description="Methane emission analysis")
    nutrient_balance: NutrientBalance = Field(..., description="Nutrient balance analysis")
    feed_breakdown: List[FeedBreakdownItem] = Field(..., description="Detailed feed breakdown")

    class Config:
        orm_mode = True

class FeedWithPrice(BaseModel):
    """Individual feed with price for diet recommendation"""
    feed_id: str = Field(..., description="Feed UUID")
    price_per_kg: float = Field(..., ge=0, description="Price per kg in local currency")

    @validator('feed_id')
    def validate_feed_id(cls, v):
        """Validate feed ID is a valid UUID"""
        try:
            uuid.UUID(v)
            return v
        except ValueError:
            raise ValueError('feed_id must be a valid UUID')

class DietRecommendationRequest(BaseModel):
    """Request model for diet recommendation with feed prices"""
    simulation_id: str = Field(..., description="Simulation identifier", example="sim-1234")
    user_id: str = Field(..., description="User UUID who is requesting the diet recommendation")
    cattle_info: CattleInfo = Field(..., description="Cattle characteristics and requirements")
    feed_selection: List[FeedWithPrice] = Field(..., description="Array of feeds with prices to include in calculation", example=[{"feed_id": "3ae5820c-4f5e-4227-b564-2e19147e07cc", "price_per_kg": 2.5}])

class AnimalCharacteristicItem(BaseModel):
    """Individual animal characteristic item"""
    characteristic: str = Field(..., description="Characteristic name")
    value: Union[str, float, int] = Field(..., description="Characteristic value")
    unit: str = Field(..., description="Unit of measurement")

class AnimalCharacteristicsData(BaseModel):
    """Detailed animal characteristics data"""
    characteristics: List[AnimalCharacteristicItem] = Field(..., description="Basic animal characteristics")
    requirements: List[AnimalCharacteristicItem] = Field(..., description="Calculated nutritional requirements")

class SelectedFeedItem(BaseModel):
    """Individual selected feed item"""
    name: str = Field(..., description="Feed name")
    category: str = Field(..., description="Feed category")
    type: str = Field(..., description="Feed type")
    dm_kg: float = Field(..., description="Dry matter amount in kg")
    af_kg: float = Field(..., description="As-fed amount in kg")
    dm_pct: float = Field(..., description="Dry matter percentage")
    cost_per_kg: float = Field(..., description="Cost per kg")
    total_cost: float = Field(..., description="Total cost for this feed")

class CategoryBreakdownItem(BaseModel):
    """Category breakdown item"""
    category: str = Field(..., description="Feed category")
    dm_kg: float = Field(..., description="Total DM in kg for this category")
    percentage: float = Field(..., description="Percentage of total DM")
    cost: float = Field(..., description="Total cost for this category")

class DietSummaryDetailed(BaseModel):
    """Detailed diet summary data"""
    selected_feeds: List[SelectedFeedItem] = Field(..., description="List of selected feeds")
    total_dm: float = Field(..., description="Total dry matter in kg")
    total_cost: float = Field(..., description="Total diet cost")
    category_breakdown: List[CategoryBreakdownItem] = Field(..., description="Breakdown by feed category")

class DietRecommendationResponse(BaseModel):
    """Response model for diet recommendation endpoint"""
    simulation_id: str = Field(..., description="Simulation identifier")
    report_id: str = Field(..., description="Unique report identifier for the generated PDF", example="rec-abc123")
    
    # New detailed sections
    animal_characteristics: AnimalCharacteristicsData = Field(..., description="Detailed animal characteristics and requirements")
    diet_summary_detailed: DietSummaryDetailed = Field(..., description="Detailed diet summary with feed breakdown")
    
    # Existing sections
    diet_summary: Dict[str, Any] = Field(..., description="Diet summary with feed amounts and costs")
    nutrient_comparison: Dict[str, Any] = Field(..., description="Nutrient comparison table")
    animal_requirements: Dict[str, Any] = Field(..., description="Detailed animal requirements")
    solution_status: str = Field(..., description="Solution status (PERFECT/GOOD/MARGINAL/INFEASIBLE)")
    confidence_level: str = Field(..., description="Confidence level of the solution")
    total_cost: float = Field(..., description="Total diet cost")
    water_intake: float = Field(..., description="Estimated daily water intake")
    methane_emissions: Dict[str, Any] = Field(..., description="Methane emission calculations")
    warnings: List[str] = Field(default_factory=list, description="Warnings related to the diet")
    recommendations: List[str] = Field(default_factory=list, description="Recommendations for improvement")
    optimization_details: Dict[str, Any] = Field(..., description="Optimization algorithm details")
    ration_evaluation: Dict[str, Any] = Field(..., description="Ration evaluation summary")

    class Config:
        orm_mode = True

class DietReport(Base):
    __tablename__ = 'diet_reports'

    # Primary Key
    id = Column(UUID(as_uuid=True), default=uuid.uuid4, primary_key=True, nullable=False)
    
    # Foreign Keys
    user_id = Column(UUID(as_uuid=True), ForeignKey('users.id'), nullable=False)
    
    # Report Information
    simulation_id = Column(String(20), nullable=False, index=True)  # e.g., "sim-1234"
    report_name = Column(String(255), nullable=False)  # e.g., "Diet Recommendation Report - abc-1234"
    file_name = Column(String(255), nullable=False)  # e.g., "diet_report_abc1234_20240810.pdf"
    
    # PDF Data
    pdf_data = Column(LargeBinary, nullable=False)  # The actual PDF file as bytes
    file_size = Column(Integer, nullable=False)  # Size in bytes
    
    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # Relationships
    user_rel = relationship("UserInformationModel", backref="diet_reports")

    class Config:
        orm_mode = True

# PDF Report Models
class PDFReportMetadata(BaseModel):
    id: str
    user_id: str
    simulation_id: str
    report_name: str
    file_name: str
    file_size: int
    created_at: Optional[str]
    updated_at: Optional[str]

    class Config:
        orm_mode = True

class PDFReportList(BaseModel):
    reports: List[PDFReportMetadata]
    total_count: int

    class Config:
        orm_mode = True

class PDFReportResponse(BaseModel):
    success: bool
    message: str
    report_id: Optional[str] = None
    report_metadata: Optional[PDFReportMetadata] = None

    class Config:
        orm_mode = True

# Reports Table Model
class Report(Base):
    __tablename__ = 'reports'

    # Primary Key
    id = Column(UUID(as_uuid=True), default=uuid.uuid4, primary_key=True, nullable=False)
    
    # Report Information
    report_id = Column(String(50), nullable=False, unique=True, index=True)  # e.g., "rec-abc123"
    report_type = Column(String(10), nullable=False, index=True)  # 'rec' or 'eval'
    
    # Foreign Keys
    user_id = Column(UUID(as_uuid=True), ForeignKey('users.id'), nullable=False)
    
    # AWS and Data Storage
    bucket_url = Column(Text, nullable=True)  # URL of PDF in AWS S3 bucket
    json_result = Column(JSON, nullable=True)  # Complete API response JSON
    saved_to_bucket = Column(Boolean, default=False, nullable=False)  # Flag for AWS upload status
    save_report = Column(Boolean, default=False, nullable=False)  # Flag for user explicitly saving report
    report = Column(LargeBinary, nullable=True)  # Binary PDF file data
    
    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # Relationships
    user_rel = relationship("UserInformationModel", backref="reports")

    class Config:
        orm_mode = True

# Pydantic Models for Reports
class ReportBase(BaseModel):
    report_id: str = Field(..., description="Unique report identifier")
    report_type: str = Field(..., description="Type of report: 'rec' or 'eval'")
    user_id: str = Field(..., description="User UUID")
    bucket_url: Optional[str] = Field(None, description="AWS S3 bucket URL")
    saved_to_bucket: bool = Field(False, description="AWS upload status")
    save_report: bool = Field(False, description="User explicitly saved report flag")

class ReportCreate(ReportBase):
    json_result: Optional[str] = Field(None, description="Complete API response JSON")
    report: Optional[bytes] = Field(None, description="Binary PDF data")

class ReportResponse(ReportBase):
    id: str = Field(..., description="Report UUID")
    json_result: Optional[str] = Field(None, description="Complete API response JSON")
    created_at: Optional[datetime] = Field(None, description="Creation timestamp")
    updated_at: Optional[datetime] = Field(None, description="Last update timestamp")

    class Config:
        orm_mode = True

# Save Report Models
class SaveReportRequest(BaseModel):
    """Request model for saving report by user"""
    report_id: str = Field(..., description="Report ID to save", example="rec-abc123")
    user_id: str = Field(..., description="User UUID who owns the report")

class SaveReportResponse(BaseModel):
    """Response model for save report endpoint"""
    success: bool = Field(..., description="Operation success status")
    message: str = Field(..., description="Response message")
    bucket_url: Optional[str] = Field(None, description="S3 bucket URL if successful")
    error_message: Optional[str] = Field(None, description="Additional error message for user guidance")

# User Feedback SQLAlchemy Model
class UserFeedback(Base):
    __tablename__ = 'user_feedback'
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey('users.id'), nullable=False)
    overall_rating = Column(Integer, nullable=True)
    text_feedback = Column(Text)
    feedback_type = Column(String(50), default='General')
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationship to user
    user = relationship("UserInformationModel", back_populates="feedbacks")

# Get User Reports Models
class UserReportItem(BaseModel):
    """Individual report item for user reports response"""
    bucket_url: str = Field(..., description="S3 bucket URL of the report")
    user_name: str = Field(..., description="Name of the user")
    report_id: str = Field(..., description="Unique report identifier")
    report_type: str = Field(..., description="Type of report: 'Diet Recommendation' or 'Diet Evaluation'")
    report_created_date: str = Field(..., description="Report creation date")
    simulation_id: str = Field(..., description="Simulation ID from the report")

class GetUserReportsResponse(BaseModel):
    """Response model for get user reports endpoint"""
    success: bool = Field(..., description="Operation success status")
    message: str = Field(..., description="Response message")
    reports: List[UserReportItem] = Field(..., description="Array of user reports")

# User Feedback Pydantic Models
class FeedbackSubmitRequest(BaseModel):
    """Request model for submitting user feedback"""
    feedback_type: str = Field(..., description="Type of feedback: General, Defect, or Feature Request")
    overall_rating: Optional[int] = Field(None, ge=1, le=5, description="Optional star rating from 1 to 5")
    text_feedback: Optional[str] = Field(None, max_length=1000, description="Optional text feedback (max 1000 characters)")
    
    @validator('feedback_type')
    def validate_feedback_type(cls, v):
        """Validate feedback type is one of the allowed values"""
        allowed_types = ['General', 'Defect', 'Feature Request']
        if v not in allowed_types:
            raise ValueError(f'feedback_type must be one of: {", ".join(allowed_types)}')
        return v

# Admin Get All Reports Models
class AdminGetAllReportsRequest(BaseModel):
    """Request model for admin get all reports endpoint"""
    user_id: str = Field(..., description="Admin user UUID for authentication")
    page: int = Field(1, ge=1, description="Page number (starts from 1)")
    page_size: int = Field(20, ge=1, le=100, description="Number of reports per page (max 100)")

class AdminReportItem(BaseModel):
    """Individual report item for admin reports response"""
    report_id: str = Field(..., description="Report UUID")
    user_id: str = Field(..., description="User UUID who created the report")
    user_name: str = Field(..., description="Name of the user who created the report")
    report_type: str = Field(..., description="Type of report: 'rec' or 'eval'")
    bucket_url: Optional[str] = Field(None, description="AWS S3 bucket URL of the report")
    created_at: str = Field(..., description="Report creation date and time in YYYY-MM-DD HH:MM:SS format")

class AdminGetAllReportsResponse(BaseModel):
    """Response model for admin get all reports endpoint"""
    success: bool = Field(..., description="Operation success status")
    message: str = Field(..., description="Response message")
    reports: List[AdminReportItem] = Field(..., description="Array of saved reports")
    total_count: int = Field(..., description="Total number of saved reports")
    page: int = Field(..., description="Current page number")
    page_size: int = Field(..., description="Number of reports per page")
    total_pages: int = Field(..., description="Total number of pages")

class UserFeedbackResponse(BaseModel):
    """Response model for user's own feedback (privacy-focused)"""
    id: str = Field(..., description="Feedback ID")
    overall_rating: Optional[int] = Field(None, description="Star rating from 1 to 5")
    text_feedback: Optional[str] = Field(None, description="Text feedback")
    feedback_type: str = Field(..., description="Type of feedback")
    created_at: datetime = Field(..., description="When feedback was submitted")
    
    class Config:
        orm_mode = True

class AdminFeedbackResponse(BaseModel):
    """Response model for admin viewing all feedback (includes user details)"""
    id: str = Field(..., description="Feedback ID")
    user_name: str = Field(..., description="Name of user who submitted feedback")
    user_email: str = Field(..., description="Email of user who submitted feedback")
    overall_rating: Optional[int] = Field(None, description="Star rating from 1 to 5")
    text_feedback: Optional[str] = Field(None, description="Text feedback")
    feedback_type: str = Field(..., description="Type of feedback")
    created_at: datetime = Field(..., description="When feedback was submitted")
    
    class Config:
        orm_mode = True

class FeedbackListResponse(BaseModel):
    """Response model for listing user's own feedback"""
    feedbacks: List[UserFeedbackResponse] = Field(..., description="Array of user's feedback")
    total_count: int = Field(..., description="Total number of feedback entries")

class AdminFeedbackListResponse(BaseModel):
    """Response model for admin listing all feedback"""
    feedbacks: List[AdminFeedbackResponse] = Field(..., description="Array of all feedback with user details")
    total_count: int = Field(..., description="Total number of feedback entries")

class FeedbackStatsResponse(BaseModel):
    """Response model for feedback statistics (admin only)"""
    total_feedbacks: int = Field(..., description="Total number of feedback entries")
    average_rating: float = Field(..., description="Average star rating")
    rating_distribution: Dict[str, str] = Field(..., description="Percentage of each rating (1-5) as strings with %")
    feedback_type_distribution: Dict[str, int] = Field(..., description="Count of each feedback type")
    recent_feedbacks: int = Field(..., description="Number of feedbacks in last 30 days")

# Admin User Management Models
class AdminUserListItem(BaseModel):
    """Individual user item for admin user list response"""
    id: str = Field(..., description="User UUID")
    name: str = Field(..., description="User's full name")
    email_id: str = Field(..., description="User's email address")
    country: str = Field(..., description="User's country name")
    is_active: bool = Field(..., description="Whether user account is active")
    is_admin: bool = Field(..., description="Whether user has admin privileges")
    created_at: Optional[datetime] = Field(None, description="User registration date")
    
    class Config:
        orm_mode = True

class AdminUserListResponse(BaseModel):
    """Response model for admin user list endpoint"""
    success: bool = Field(..., description="Operation success status")
    message: str = Field(..., description="Response message")
    users: List[AdminUserListItem] = Field(..., description="Array of users")
    total_count: int = Field(..., description="Total number of users")
    page: int = Field(..., description="Current page number")
    page_size: int = Field(..., description="Number of users per page")
    total_pages: int = Field(..., description="Total number of pages")

class AdminUserToggleRequest(BaseModel):
    """Request model for toggling user status"""
    action: str = Field(..., description="Action to perform: 'enable' or 'disable'")
    
    @validator('action')
    def validate_action(cls, v):
        """Validate action is either enable or disable"""
        if v.lower() not in ['enable', 'disable']:
            raise ValueError('action must be either "enable" or "disable"')
        return v.lower()

class AdminUserToggleResponse(BaseModel):
    """Response model for user status toggle endpoint"""
    success: bool = Field(..., description="Operation success status")
    message: str = Field(..., description="Response message")
    user_id: str = Field(..., description="User UUID")
    new_status: str = Field(..., description="New user status: 'active' or 'inactive'")
    user_name: str = Field(..., description="User's name")
    user_email: str = Field(..., description="User's email")

# User Account Deactivation Models
class UserDeleteAccountResponse(BaseModel):
    """Response model for user account deactivation endpoint"""
    success: bool = Field(..., description="Operation success status")
    message: str = Field(..., description="Response message")
    user_id: str = Field(..., description="User UUID")
    user_name: str = Field(..., description="User's name")
    user_email: str = Field(..., description="User's email")
    deactivated_at: Optional[datetime] = Field(None, description="Account deactivation timestamp")

# Admin Feed Management Models
class AdminFeedTypeRequest(BaseModel):
    """Request model for adding feed type"""
    type_name: str = Field(..., max_length=100, description="Feed type name")
    description: Optional[str] = Field(None, description="Feed type description")
    sort_order: Optional[int] = Field(0, description="Display order")

class AdminFeedTypeResponse(BaseModel):
    """Response model for feed type operations"""
    success: bool = Field(..., description="Operation success status")
    message: str = Field(..., description="Response message")
    feed_type: Optional[FeedTypeResponse] = Field(None, description="Feed type details")

class AdminFeedCategoryRequest(BaseModel):
    """Request model for adding feed category"""
    category_name: str = Field(..., max_length=100, description="Feed category name")
    feed_type_id: str = Field(..., description="Feed type UUID")
    description: Optional[str] = Field(None, description="Feed category description")
    sort_order: Optional[int] = Field(0, description="Display order")

class AdminFeedCategoryResponse(BaseModel):
    """Response model for feed category operations"""
    success: bool = Field(..., description="Operation success status")
    message: str = Field(..., description="Response message")
    feed_category: Optional[FeedCategoryResponse] = Field(None, description="Feed category details")

class AdminFeedRequest(BaseModel):
    """Request model for adding/updating feed"""
    fd_code: str = Field(..., description="Feed code")
    fd_name: str = Field(..., description="Feed name")
    fd_category: str = Field(..., description="Feed category")
    fd_type: str = Field(..., description="Feed type")
    fd_country_name: str = Field(..., description="Country name")
    fd_country_cd: Optional[str] = Field(None, description="Country code")
    fd_dm: Optional[float] = Field(None, description="Dry Matter %")
    fd_ash: Optional[float] = Field(None, description="Ash %")
    fd_cp: Optional[float] = Field(None, description="Crude Protein %")
    fd_npn_cp: Optional[int] = Field(None, description="Non-protein nitrogen")
    fd_ee: Optional[float] = Field(None, description="Ether Extract %")
    fd_cf: Optional[float] = Field(None, description="Crude Fiber %")
    fd_nfe: Optional[float] = Field(None, description="Nitrogen Free Extract %")
    fd_st: Optional[float] = Field(None, description="Starch %")
    fd_ndf: Optional[float] = Field(None, description="Neutral Detergent Fiber %")
    fd_hemicellulose: Optional[float] = Field(None, description="Hemicellulose %")
    fd_adf: Optional[float] = Field(None, description="Acid Detergent Fiber %")
    fd_cellulose: Optional[float] = Field(None, description="Cellulose %")
    fd_lg: Optional[float] = Field(None, description="Lignin %")
    fd_ndin: Optional[float] = Field(None, description="Neutral Detergent Insoluble Nitrogen %")
    fd_adin: Optional[float] = Field(None, description="Acid Detergent Insoluble Nitrogen %")
    fd_ca: Optional[float] = Field(None, description="Calcium %")
    fd_p: Optional[float] = Field(None, description="Phosphorus %")
    fd_season: Optional[str] = Field(None, description="Season")
    fd_orginin: Optional[str] = Field(None, description="Origin ID")
    fd_ipb_local_lab: Optional[str] = Field(None, description="IPB Local Lab ID")

class AdminFeedResponse(BaseModel):
    """Response model for feed operations"""
    success: bool = Field(..., description="Operation success status")
    message: str = Field(..., description="Response message")
    feed: Optional[FeedDetailsResponse] = Field(None, description="Feed details")

class AdminFeedListResponse(BaseModel):
    """Response model for admin feed list endpoint"""
    success: bool = Field(..., description="Operation success status")
    message: str = Field(..., description="Response message")
    feeds: List[FeedDetailsResponse] = Field(..., description="Array of feeds")
    total_count: int = Field(..., description="Total number of feeds")
    page: int = Field(..., description="Current page number")
    page_size: int = Field(..., description="Number of feeds per page")
    total_pages: int = Field(..., description="Total number of pages")

class AdminBulkUploadResponse(BaseModel):
    """Response model for bulk upload endpoint"""
    success: bool = Field(..., description="Operation success status")
    message: str = Field(..., description="Response message")
    total_records: int = Field(..., description="Total records processed")
    successful_uploads: int = Field(..., description="Number of successful uploads")
    failed_uploads: int = Field(..., description="Number of failed uploads")
    existing_records: int = Field(..., description="Number of existing records skipped")
    updated_records: int = Field(..., description="Number of existing records updated")
    failed_records: List[Dict[str, Any]] = Field(..., description="List of failed records with reasons")
    bulk_import_log: Optional[str] = Field(None, description="AWS S3 URL of the bulk import log file")

class AdminExportResponse(BaseModel):
    """Response model for export endpoint"""
    success: bool = Field(..., description="Operation success status")
    message: str = Field(..., description="Response message")
    file_url: str = Field(..., description="AWS S3 URL of exported file")
    file_name: str = Field(..., description="Name of exported file")
    total_records: int = Field(..., description="Total number of records exported")

class AdminBulkLogResponse(BaseModel):
    """Response model for bulk import log endpoint"""
    success: bool = Field(..., description="Operation success status")
    message: str = Field(..., description="Response message")
    log_file_url: Optional[str] = Field(None, description="S3 URL of the latest bulk import log file")
    filename: Optional[str] = Field(None, description="Name of the log file")
    file_size: Optional[str] = Field(None, description="Size of the log file")
    created_at: Optional[str] = Field(None, description="Creation timestamp of the log file")

# Models moved from pydantic_modals.py
class UserUpdateRequest(BaseModel):
    """Request model for updating user information"""
    name: Optional[str] = Field(None, max_length=100, description="User's name")
    country_id: Optional[str] = Field(None, description="Country UUID")

    @validator('name')
    def validate_name(cls, v):
        """Validate name is not empty if provided"""
        if v is not None:
            v = v.strip()
            if not v:
                raise ValueError('Name cannot be empty if provided')
        return v

    @validator('country_id')
    def validate_country_id(cls, v):
        """Validate country_id is a valid UUID if provided"""
        if v is not None:
            try:
                uuid.UUID(v)
                return v
            except ValueError:
                raise ValueError('country_id must be a valid UUID')
        return v

class FeedDescriptionResponse(BaseModel):
    """Response model for feed description"""
    feed_cd: str = Field(..., description="Feed code for display (format: 'IND-1223')")
    row_id: int = Field(..., description="Row ID")
    feed_uuid: str = Field(..., description="Feed UUID")
    feed_name: str = Field(..., description="Feed name")
    feed_category: str = Field(..., description="Feed category")
    feed_type: str = Field(..., description="Feed type")

    class Config:
        orm_mode = True

class UpdateUserInformation(BaseModel):
    """Model for updating user information"""
    name: str = Field(..., description="User's name")
    email_id: str = Field(..., description="User's email")
    country_id: str = Field(..., description="Country UUID")