from fastapi import Request, HTTPException
from fastapi.responses import JSONResponse
import traceback
import json
from datetime import datetime

async def validation_exception_handler(request: Request, exc: Exception):
    """Global handler for validation errors with detailed feedback"""
    
    if isinstance(exc, HTTPException):
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": True,
                "timestamp": datetime.now().isoformat(),
                "code": "HTTP_ERROR",
                "message": exc.detail,
                "path": str(request.url)
            }
        )
    
    # Pydantic validation errors
    if hasattr(exc, 'errors'):
        errors = exc.errors()
        formatted_errors = []
        
        for error in errors:
            formatted_errors.append({
                "field": " -> ".join(str(x) for x in error['loc']),
                "message": error['msg'],
                "type": error['type'],
                "value": str(error.get('input', ''))[:100]  # Truncate long values
            })
        
        return JSONResponse(
            status_code=422,
            content={
                "error": True,
                "timestamp": datetime.now().isoformat(),
                "code": "SCHEMA_VALIDATION_ERROR",
                "message": f"Request schema validation failed with {len(formatted_errors)} errors",
                "details": formatted_errors,
                "suggestion": "Check that all required fields are provided and data types match the schema (e.g., numbers not strings)",
                "documentation": "/docs#/simulate"
            }
        )
    
    # Catch-all for unexpected errors
    return JSONResponse(
        status_code=500,
        content={
            "error": True,
            "timestamp": datetime.now().isoformat(),
            "code": "INTERNAL_ERROR",
            "message": "An unexpected error occurred",
            "detail": str(exc) if False else None,  # Set to True for debug
            "suggestion": "Please try again or contact support with the timestamp"
        }
    )
