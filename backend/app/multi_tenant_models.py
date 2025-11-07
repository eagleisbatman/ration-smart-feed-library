"""
Multi-Tenant Authentication Models
Adds organization and API key support for MCP server backend
"""

from sqlalchemy import Column, Integer, String, Boolean, ForeignKey, DateTime, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid
from app.models import Base

class Organization(Base):
    """Organization/Tenant model for multi-tenant support"""
    __tablename__ = 'organizations'

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, unique=True, nullable=False)
    name = Column(String(255), nullable=False)
    slug = Column(String(100), unique=True, nullable=False)  # URL-friendly identifier
    contact_email = Column(String(255), nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    rate_limit_per_hour = Column(Integer, default=1000, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # Relationships
    api_keys = relationship("APIKey", back_populates="organization", cascade="all, delete-orphan")
    # Note: users relationship defined separately to avoid circular imports
    usage_records = relationship("APIUsage", back_populates="organization")

class APIKey(Base):
    """API Key model for organization authentication"""
    __tablename__ = 'api_keys'

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, unique=True, nullable=False)
    organization_id = Column(UUID(as_uuid=True), ForeignKey('organizations.id', ondelete='CASCADE'), nullable=False)
    key_hash = Column(String(255), unique=True, nullable=False)  # Hashed API key
    key_prefix = Column(String(20), nullable=False)  # First 8 chars for display
    name = Column(String(255), nullable=True)  # Friendly name
    is_active = Column(Boolean, default=True, nullable=False)
    last_used_at = Column(DateTime, nullable=True)
    expires_at = Column(DateTime, nullable=True)  # Optional expiration
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    created_by = Column(UUID(as_uuid=True), ForeignKey('user_information.id'), nullable=True)  # Admin who created it
    
    # Relationships
    organization = relationship("Organization", back_populates="api_keys")
    creator = relationship("UserInformationModel", foreign_keys=[created_by])
    usage_records = relationship("APIUsage", back_populates="api_key")

class APIUsage(Base):
    """API Usage tracking model"""
    __tablename__ = 'api_usage'

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, unique=True, nullable=False)
    organization_id = Column(UUID(as_uuid=True), ForeignKey('organizations.id', ondelete='CASCADE'), nullable=False)
    api_key_id = Column(UUID(as_uuid=True), ForeignKey('api_keys.id'), nullable=True)
    endpoint = Column(String(255), nullable=False)
    method = Column(String(10), nullable=False)  # GET, POST, etc.
    response_status = Column(Integer, nullable=True)
    response_time_ms = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    # Relationships
    organization = relationship("Organization", back_populates="usage_records")
    api_key = relationship("APIKey", back_populates="usage_records")

