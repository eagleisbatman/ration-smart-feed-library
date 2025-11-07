#!/usr/bin/env python3
"""
Evaluation Support Methods
Handles report ID generation, PDF generation, and database operations for diet evaluation
"""

import uuid
import random
import string
import time
from datetime import datetime
from typing import Optional, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import desc

from app.models import Report, UserInformationModel, CountryModel
from middleware.logging_config import get_logger
from services.aws_service import aws_service
from weasyprint import HTML

logger = get_logger("eval_support_methods")

def generate_eval_report_id(db: Session) -> str:
    """
    Generate a unique evaluation report ID in format 'eval-xxxxxxxxxx'
    where xxxxxxxxxx is a 10-character alphanumeric string with timestamp component
    
    Args:
        db (Session): Database session for uniqueness check
        
    Returns:
        str: Unique evaluation report ID
    """
    max_attempts = 10
    for attempt in range(max_attempts):
        # Generate timestamp-based component (last 4 digits of timestamp)
        timestamp_suffix = str(int(time.time() * 1000))[-4:]
        
        # Generate 6-character random alphanumeric string
        chars = string.ascii_lowercase + string.digits
        random_suffix = ''.join(random.choice(chars) for _ in range(6))
        
        # Combine timestamp and random components
        report_id = f"eval-{timestamp_suffix}{random_suffix}"
        
        # Check for uniqueness in database
        existing_report = db.query(Report).filter(Report.report_id == report_id).first()
        if not existing_report:
            logger.info(f"Generated unique evaluation report ID: {report_id}")
            return report_id
        
        logger.warning(f"Report ID {report_id} already exists, generating new one...")
    
    # Fallback: use UUID if all attempts fail
    fallback_id = f"eval-{str(uuid.uuid4())[:10]}"
    logger.warning(f"Using fallback report ID: {fallback_id}")
    return fallback_id

def get_user_name_by_id(user_id: str, db: Session) -> str:
    """
    Get user name by user ID
    
    Args:
        user_id (str): User ID
        db (Session): Database session
        
    Returns:
        str: User name or "Unknown User" if not found
    """
    try:
        if not user_id:
            return "Unknown User"
            
        user_info = db.query(UserInformationModel).filter(
            UserInformationModel.id == uuid.UUID(user_id)
        ).first()
        
        if user_info and user_info.name:
            return user_info.name
        else:
            logger.warning(f"User information not found for user_id: {user_id}")
            return "Unknown User"
    except Exception as e:
        logger.error(f"Error getting user name for user_id {user_id}: {str(e)}")
        return "Unknown User"

def get_country_name_by_id(country_id: str, db: Session) -> str:
    """
    Get country name by country ID
    
    Args:
        country_id (str): Country ID
        db (Session): Database session
        
    Returns:
        str: Country name or "Unknown Country" if not found
    """
    try:
        if not country_id:
            return "Unknown Country"
            
        country_info = db.query(CountryModel).filter(
            CountryModel.id == uuid.UUID(country_id)
        ).first()
        
        if country_info and country_info.name:
            return country_info.name
        else:
            logger.warning(f"Country information not found for country_id: {country_id}")
            return "Unknown Country"
    except Exception as e:
        logger.error(f"Error getting country name for country_id {country_id}: {str(e)}")
        return "Unknown Country"

def eval_pdf_generator(html_file_path: str, report_id: str) -> Optional[str]:
    """
    Generate PDF from HTML file and upload to AWS S3
    
    Args:
        html_file_path (str): Path to the HTML file
        report_id (str): Report ID for naming the PDF file
        
    Returns:
        Optional[str]: S3 URL of the uploaded PDF, or None if failed
    """
    try:
        logger.info(f"Generating PDF for report_id: {report_id}")
        
        # Generate PDF file name
        pdf_filename = f"diet_eval_{report_id}.pdf"
        
        # Convert HTML to PDF using WeasyPrint
        html_doc = HTML(filename=html_file_path)
        pdf_bytes = html_doc.write_pdf()
        
        # Upload to AWS S3
        success, bucket_url, error_message = aws_service.upload_pdf_to_s3(
            pdf_data=pdf_bytes,
            user_id="",  # Not used in current implementation
            report_id=report_id
        )
        
        if success and bucket_url:
            logger.info(f"PDF successfully generated and uploaded to S3: {bucket_url}")
            return bucket_url
        else:
            logger.error(f"Failed to upload PDF to S3 for report_id: {report_id}, Error: {error_message}")
            return None
            
    except Exception as e:
        logger.error(f"Error generating PDF for report_id {report_id}: {str(e)}")
        return None

def insert_evaluation_report_record(
    report_id: str,
    user_id: str,
    simulation_id: str,
    pdf_url: Optional[str],
    db: Session
) -> bool:
    """
    Insert evaluation report record into the reports table
    
    Args:
        report_id (str): Report ID
        user_id (str): User ID
        simulation_id (str): Simulation ID
        pdf_url (Optional[str]): S3 URL of the PDF file
        db (Session): Database session
        
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        logger.info(f"Inserting evaluation report record: {report_id}")
        
        # Create new report record
        # For evaluation reports, use a default user ID if none provided
        if not user_id:
            # Use a default user ID for evaluation reports
            default_user_id = "00000000-0000-0000-0000-000000000000"
            user_id = default_user_id
        
        report_record = Report(
            report_id=report_id,
            user_id=uuid.UUID(user_id),
            simulation_id=simulation_id,
            report_type="evl",
            bucket_url=pdf_url,  # Use bucket_url instead of pdf_url
            json_result=None,  # Can be added later if needed
            saved_to_bucket=bool(pdf_url),  # True if PDF was uploaded
            save_report=False,  # Default to False
            report=None,  # No binary data stored
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
            is_active=True
        )
        
        # Add to database
        db.add(report_record)
        db.commit()
        
        logger.info(f"Successfully inserted evaluation report record: {report_id}")
        return True
        
    except Exception as e:
        logger.error(f"Error inserting evaluation report record {report_id}: {str(e)}")
        db.rollback()
        return False

def get_evaluation_report_metadata(report_id: str, db: Session) -> Optional[Dict[str, Any]]:
    """
    Get evaluation report metadata from database
    
    Args:
        report_id (str): Report ID
        db (Session): Database session
        
    Returns:
        Optional[Dict[str, Any]]: Report metadata or None if not found
    """
    try:
        report = db.query(Report).filter(
            Report.report_id == report_id,
            Report.report_type == "evl"
        ).first()
        
        if report:
            return {
                "report_id": report.report_id,
                "user_id": str(report.user_id) if report.user_id else None,
                "simulation_id": report.simulation_id,
                "report_type": report.report_type,
                "pdf_url": report.pdf_url,
                "created_at": report.created_at,
                "is_active": report.is_active
            }
        else:
            logger.warning(f"Evaluation report not found: {report_id}")
            return None
            
    except Exception as e:
        logger.error(f"Error getting evaluation report metadata {report_id}: {str(e)}")
        return None
