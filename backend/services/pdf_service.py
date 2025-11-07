"""
Minimal PDF Service Stub for MCP Server Fork
PDF generation is not needed for MCP server, so this provides minimal stubs
"""

import uuid
from sqlalchemy.orm import Session
from app.models import Report
from middleware.logging_config import get_logger

logger = get_logger("pdf_service")

def generate_report_id(prefix: str, db: Session) -> str:
    """
    Generate a unique report ID for MCP server fork
    Format: {prefix}-{random_string}
    
    For MCP fork, we use simple UUID-based IDs without database checks
    since PDF generation is disabled.
    
    Args:
        prefix: Prefix for report ID ('rec' or 'eval')
        db: Database session (not used in MCP fork)
        
    Returns:
        str: Unique report ID
    """
    # Generate simple report ID (no database check needed for MCP)
    random_suffix = uuid.uuid4().hex[:8]
    report_id = f"{prefix}-{random_suffix}"
    logger.info(f"Generated report ID for MCP fork: {report_id}")
    return report_id

def rec_pdf_report_generator(api_response_data: dict, user_id: str, simulation_id: str, report_id: str, db: Session):
    """
    Stub for PDF generation - not needed for MCP server
    This function does nothing for MCP fork (PDF generation disabled)
    
    Args:
        api_response_data: API response data (ignored)
        user_id: User ID (ignored)
        simulation_id: Simulation ID (ignored)
        report_id: Report ID (ignored)
        db: Database session (ignored)
    """
    # PDF generation disabled for MCP server fork
    logger.info(f"PDF generation skipped for MCP fork (report_id: {report_id})")
    pass

class PDFService:
    """Stub PDF Service class - not used in MCP fork"""
    pass

