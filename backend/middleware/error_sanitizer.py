"""
Error Sanitization Utilities
Prevents information leakage in error messages
"""
from typing import Any, Dict
import traceback
from middleware.logging_config import get_logger

logger = get_logger("error_sanitizer")

# List of sensitive patterns that should not appear in error messages
SENSITIVE_PATTERNS = [
    'password',
    'api_key',
    'api-key',
    'secret',
    'token',
    'credential',
    'connection string',
    'database url',
    'postgresql://',
    'mysql://',
    'mongodb://',
]

def sanitize_error_message(error: Exception, include_details: bool = False) -> str:
    """
    Sanitize error message to prevent information leakage
    
    Args:
        error: The exception that occurred
        include_details: Whether to include sanitized details (for debugging)
    
    Returns:
        Safe error message for client
    """
    error_msg = str(error)
    error_type = type(error).__name__
    
    # Check for sensitive information
    error_lower = error_msg.lower()
    has_sensitive_info = any(pattern in error_lower for pattern in SENSITIVE_PATTERNS)
    
    if has_sensitive_info:
        # Log full error server-side
        logger.error(f"Error with sensitive information detected: {error_type}", exc_info=True)
        # Return generic message
        return "An internal error occurred. Please contact support if the issue persists."
    
    # For common errors, provide helpful but safe messages
    if "not found" in error_lower or "does not exist" in error_lower:
        return "The requested resource was not found."
    
    if "permission" in error_lower or "forbidden" in error_lower or "unauthorized" in error_lower:
        return "You do not have permission to perform this action."
    
    if "validation" in error_lower or "invalid" in error_lower:
        return "Invalid input provided. Please check your request and try again."
    
    if "timeout" in error_lower:
        return "The request timed out. Please try again."
    
    if "connection" in error_lower or "network" in error_lower:
        return "A network error occurred. Please try again later."
    
    # Generic fallback
    if include_details:
        # In development, include sanitized details
        return f"Error: {error_type} - {error_msg[:200]}"  # Truncate long messages
    else:
        return "An error occurred processing your request. Please try again or contact support."

def sanitize_exception_response(exception: Exception, context: Dict[str, Any] = None) -> Dict[str, Any]:
    """
    Create a sanitized error response
    
    Args:
        exception: The exception that occurred
        context: Additional context (request ID, etc.)
    
    Returns:
        Sanitized error response dictionary
    """
    # Log full error server-side
    logger.error(
        f"Exception occurred: {type(exception).__name__}",
        exc_info=True,
        extra=context or {}
    )
    
    return {
        "error": "An error occurred",
        "message": sanitize_error_message(exception, include_details=False),
        "request_id": context.get("request_id") if context else None
    }

