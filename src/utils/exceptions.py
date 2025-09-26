"""
Custom exceptions and error handling utilities for the email parser system.
"""
from typing import Optional, Dict, Any
from enum import Enum


class ErrorCode(str, Enum):
    """Standardized error codes for different failure types."""
    
    # Configuration errors
    CONFIG_MISSING = "CONFIG_MISSING"
    CONFIG_INVALID = "CONFIG_INVALID"
    
    # Email processing errors
    EMAIL_PARSE_FAILED = "EMAIL_PARSE_FAILED"
    EMAIL_TOO_LARGE = "EMAIL_TOO_LARGE"
    EMAIL_CORRUPTED = "EMAIL_CORRUPTED"
    
    # Lead parsing errors
    LEAD_SOURCE_UNKNOWN = "LEAD_SOURCE_UNKNOWN"
    LEAD_DATA_INVALID = "LEAD_DATA_INVALID"
    LEAD_MISSING_REQUIRED_FIELDS = "LEAD_MISSING_REQUIRED_FIELDS"
    
    # AWS service errors
    S3_ACCESS_DENIED = "S3_ACCESS_DENIED"
    S3_OBJECT_NOT_FOUND = "S3_OBJECT_NOT_FOUND"
    SQS_SEND_FAILED = "SQS_SEND_FAILED"
    
    # Processing errors
    TIMEOUT_EXCEEDED = "TIMEOUT_EXCEEDED"
    RETRY_EXHAUSTED = "RETRY_EXHAUSTED"
    VALIDATION_FAILED = "VALIDATION_FAILED"
    
    # System errors
    MEMORY_EXCEEDED = "MEMORY_EXCEEDED"
    UNKNOWN_ERROR = "UNKNOWN_ERROR"


class BaseEmailParserException(Exception):
    """Base exception for all email parser errors."""
    
    def __init__(
        self,
        message: str,
        error_code: ErrorCode,
        details: Optional[Dict[str, Any]] = None,
        cause: Optional[Exception] = None
    ):
        super().__init__(message)
        self.message = message
        self.error_code = error_code
        self.details = details or {}
        self.cause = cause
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert exception to dictionary for logging/serialization."""
        return {
            'error_type': self.__class__.__name__,
            'error_code': self.error_code.value,
            'message': self.message,
            'details': self.details,
            'cause': str(self.cause) if self.cause else None
        }


class ConfigurationError(BaseEmailParserException):
    """Raised when configuration is missing or invalid."""
    
    def __init__(self, message: str, missing_keys: Optional[list] = None):
        super().__init__(
            message=message,
            error_code=ErrorCode.CONFIG_MISSING if missing_keys else ErrorCode.CONFIG_INVALID,
            details={'missing_keys': missing_keys} if missing_keys else {}
        )


class EmailProcessingError(BaseEmailParserException):
    """Raised when email processing fails."""
    
    def __init__(
        self,
        message: str,
        error_code: ErrorCode = ErrorCode.EMAIL_PARSE_FAILED,
        email_key: Optional[str] = None,
        cause: Optional[Exception] = None
    ):
        super().__init__(
            message=message,
            error_code=error_code,
            details={'email_key': email_key} if email_key else {},
            cause=cause
        )


class LeadParsingError(BaseEmailParserException):
    """Raised when lead data parsing fails."""
    
    def __init__(
        self,
        message: str,
        error_code: ErrorCode = ErrorCode.LEAD_DATA_INVALID,
        lead_source: Optional[str] = None,
        missing_fields: Optional[list] = None,
        cause: Optional[Exception] = None
    ):
        details = {}
        if lead_source:
            details['lead_source'] = lead_source
        if missing_fields:
            details['missing_fields'] = missing_fields
            
        super().__init__(
            message=message,
            error_code=error_code,
            details=details,
            cause=cause
        )


class AWSServiceError(BaseEmailParserException):
    """Raised when AWS service operations fail."""
    
    def __init__(
        self,
        message: str,
        error_code: ErrorCode,
        service: str,
        operation: Optional[str] = None,
        cause: Optional[Exception] = None
    ):
        super().__init__(
            message=message,
            error_code=error_code,
            details={
                'service': service,
                'operation': operation
            },
            cause=cause
        )


class ValidationError(BaseEmailParserException):
    """Raised when data validation fails."""
    
    def __init__(
        self,
        message: str,
        field_errors: Optional[Dict[str, str]] = None,
        cause: Optional[Exception] = None
    ):
        super().__init__(
            message=message,
            error_code=ErrorCode.VALIDATION_FAILED,
            details={'field_errors': field_errors} if field_errors else {},
            cause=cause
        )


class ProcessingTimeoutError(BaseEmailParserException):
    """Raised when processing exceeds timeout."""
    
    def __init__(self, message: str, timeout_seconds: int):
        super().__init__(
            message=message,
            error_code=ErrorCode.TIMEOUT_EXCEEDED,
            details={'timeout_seconds': timeout_seconds}
        )


class RetryExhaustedError(BaseEmailParserException):
    """Raised when retry attempts are exhausted."""
    
    def __init__(self, message: str, max_attempts: int, last_error: Optional[Exception] = None):
        super().__init__(
            message=message,
            error_code=ErrorCode.RETRY_EXHAUSTED,
            details={'max_attempts': max_attempts},
            cause=last_error
        )


def handle_exception(
    exception: Exception,
    context: Optional[Dict[str, Any]] = None,
    default_error_code: ErrorCode = ErrorCode.UNKNOWN_ERROR
) -> BaseEmailParserException:
    """
    Convert any exception to a BaseEmailParserException with proper context.
    
    Args:
        exception: The original exception
        context: Additional context information
        default_error_code: Default error code if not a known exception type
        
    Returns:
        BaseEmailParserException: Wrapped exception with proper error code
    """
    if isinstance(exception, BaseEmailParserException):
        return exception
    
    # Map common AWS exceptions
    exception_name = type(exception).__name__
    
    if 'NoCredentialsError' in exception_name or 'AccessDenied' in str(exception):
        return AWSServiceError(
            message=f"AWS access denied: {str(exception)}",
            error_code=ErrorCode.S3_ACCESS_DENIED,
            service="AWS",
            cause=exception
        )
    
    if 'NoSuchKey' in exception_name or 'NotFound' in str(exception):
        return AWSServiceError(
            message=f"AWS resource not found: {str(exception)}",
            error_code=ErrorCode.S3_OBJECT_NOT_FOUND,
            service="AWS",
            cause=exception
        )
    
    if 'TimeoutError' in exception_name or 'timeout' in str(exception).lower():
        return ProcessingTimeoutError(
            message=f"Operation timed out: {str(exception)}",
            timeout_seconds=30  # Default timeout
        )
    
    # Default handling
    return BaseEmailParserException(
        message=f"Unexpected error: {str(exception)}",
        error_code=default_error_code,
        details=context or {},
        cause=exception
    )