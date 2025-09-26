"""
Utility modules for the email parser system.
"""

from .logger import (
    StructuredLogger,
    LoggerFactory,
    get_logger
)
from .exceptions import (
    BaseEmailParserException,
    ConfigurationError,
    EmailProcessingError,
    LeadParsingError,
    AWSServiceError,
    ValidationError,
    ProcessingTimeoutError,
    RetryExhaustedError,
    ErrorCode,
    handle_exception
)
from .metrics import (
    MetricsCollector,
    EmailParserMetrics,
    initialize_metrics,
    get_metrics_collector,
    get_email_parser_metrics,
    flush_metrics
)
from .validators import (
    DataValidator,
    EmailContentValidator,
    validate_and_normalize_lead,
    is_valid_email_content
)
from .retry import (
    RetryHandler,
    RetryConfig,
    BackoffStrategy,
    CircuitBreaker,
    CircuitBreakerConfig,
    CircuitBreakerState,
    retry,
    get_circuit_breaker
)

__all__ = [
    # Logger
    'StructuredLogger',
    'LoggerFactory', 
    'get_logger',
    
    # Exceptions
    'BaseEmailParserException',
    'ConfigurationError',
    'EmailProcessingError',
    'LeadParsingError',
    'AWSServiceError',
    'ValidationError',
    'ProcessingTimeoutError',
    'RetryExhaustedError',
    'ErrorCode',
    'handle_exception',
    
    # Metrics
    'MetricsCollector',
    'EmailParserMetrics',
    'initialize_metrics',
    'get_metrics_collector',
    'get_email_parser_metrics',
    'flush_metrics',
    
    # Validators
    'DataValidator',
    'EmailContentValidator',
    'validate_and_normalize_lead',
    'is_valid_email_content',
    
    # Retry & Circuit Breaker
    'RetryHandler',
    'RetryConfig',
    'BackoffStrategy',
    'CircuitBreaker',
    'CircuitBreakerConfig',
    'CircuitBreakerState',
    'retry',
    'get_circuit_breaker'
]