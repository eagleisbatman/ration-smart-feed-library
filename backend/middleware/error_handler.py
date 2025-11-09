"""
Global Error Handler Middleware
Catches all exceptions and sanitizes error messages
"""
from fastapi import Request, status
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware
from middleware.error_sanitizer import sanitize_exception_response
from middleware.logging_config import get_logger
import uuid

logger = get_logger("error_handler")

class ErrorHandlerMiddleware(BaseHTTPMiddleware):
    """Middleware to catch and sanitize all errors"""
    
    async def dispatch(self, request: Request, call_next):
        request_id = str(uuid.uuid4())
        
        try:
            response = await call_next(request)
            return response
        except HTTPException as e:
            # HTTPExceptions are already formatted, but sanitize detail if it's a string
            if isinstance(e.detail, str):
                from middleware.error_sanitizer import sanitize_error_message
                sanitized_detail = sanitize_error_message(e, include_details=False)
            else:
                sanitized_detail = e.detail
            
            return JSONResponse(
                status_code=e.status_code,
                content={
                    "error": "Request failed",
                    "message": sanitized_detail if isinstance(sanitized_detail, str) else sanitized_detail.get("message", "An error occurred"),
                    "request_id": request_id
                },
                headers=e.headers
            )
        except RequestValidationError as e:
            # Validation errors - return sanitized version
            logger.warning(f"Validation error: {str(e)}")
            return JSONResponse(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                content={
                    "error": "Validation error",
                    "message": "Invalid input provided. Please check your request and try again.",
                    "request_id": request_id
                }
            )
        except Exception as e:
            # Catch-all for unexpected errors
            error_response = sanitize_exception_response(e, {"request_id": request_id})
            return JSONResponse(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                content=error_response
            )

