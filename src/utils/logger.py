"""
Structured logging system with CloudWatch integration and correlation tracking.
"""
import json
import logging
import sys
import uuid
from datetime import datetime
from typing import Dict, Any, Optional
from contextlib import contextmanager
import traceback


class StructuredLogger:
    """
    Structured logger with JSON formatting and correlation ID tracking.
    """
    
    def __init__(self, name: str, level: str = "INFO", format_type: str = "json"):
        self.name = name
        self.logger = logging.getLogger(name)
        self.logger.setLevel(getattr(logging, level.upper()))
        
        # Remove existing handlers to avoid duplicates
        self.logger.handlers.clear()
        
        # Create handler
        handler = logging.StreamHandler(sys.stdout)
        
        if format_type.lower() == "json":
            handler.setFormatter(JSONFormatter())
        else:
            handler.setFormatter(logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            ))
        
        self.logger.addHandler(handler)
        self._correlation_id = None
    
    def set_correlation_id(self, correlation_id: str):
        """Set correlation ID for request tracking."""
        self._correlation_id = correlation_id
    
    def get_correlation_id(self) -> Optional[str]:
        """Get current correlation ID."""
        return self._correlation_id
    
    def _log(self, level: str, message: str, **kwargs):
        """Internal logging method with structured data."""
        extra_data = {
            'correlation_id': self._correlation_id,
            'timestamp': datetime.utcnow().isoformat(),
            'service': 'email-parser',
            **kwargs
        }
        
        # Filter out None values
        extra_data = {k: v for k, v in extra_data.items() if v is not None}
        
        getattr(self.logger, level.lower())(message, extra=extra_data)
    
    def debug(self, message: str, **kwargs):
        """Log debug message."""
        self._log('DEBUG', message, **kwargs)
    
    def info(self, message: str, **kwargs):
        """Log info message."""
        self._log('INFO', message, **kwargs)
    
    def warning(self, message: str, **kwargs):
        """Log warning message."""
        self._log('WARNING', message, **kwargs)
    
    def error(self, message: str, error: Optional[Exception] = None, **kwargs):
        """Log error message with optional exception details."""
        if error:
            kwargs.update({
                'error_type': type(error).__name__,
                'error_message': str(error),
                'traceback': traceback.format_exc()
            })
        self._log('ERROR', message, **kwargs)
    
    def critical(self, message: str, **kwargs):
        """Log critical message."""
        self._log('CRITICAL', message, **kwargs)
    
    @contextmanager
    def operation_context(self, operation: str, **context_data):
        """Context manager for operation logging with timing."""
        start_time = datetime.utcnow()
        operation_id = str(uuid.uuid4())
        
        self.info(
            f"Starting operation: {operation}",
            operation=operation,
            operation_id=operation_id,
            **context_data
        )
        
        try:
            yield operation_id
            duration_ms = int((datetime.utcnow() - start_time).total_seconds() * 1000)
            self.info(
                f"Completed operation: {operation}",
                operation=operation,
                operation_id=operation_id,
                duration_ms=duration_ms,
                status="success"
            )
        except Exception as e:
            duration_ms = int((datetime.utcnow() - start_time).total_seconds() * 1000)
            self.error(
                f"Failed operation: {operation}",
                error=e,
                operation=operation,
                operation_id=operation_id,
                duration_ms=duration_ms,
                status="error"
            )
            raise


class JSONFormatter(logging.Formatter):
    """Custom JSON formatter for structured logging."""
    
    def format(self, record):
        """Format log record as JSON."""
        log_data = {
            'timestamp': datetime.utcfromtimestamp(record.created).isoformat(),
            'level': record.levelname,
            'logger': record.name,
            'message': record.getMessage(),
            'log_module': record.module,  # Renamed to avoid conflict
            'function': record.funcName,
            'line': record.lineno
        }
        
        # Add extra data if present
        if hasattr(record, '__dict__'):
            for key, value in record.__dict__.items():
                if key not in ['name', 'msg', 'args', 'levelname', 'levelno',
                              'pathname', 'filename', 'module', 'lineno',
                              'funcName', 'created', 'msecs', 'relativeCreated',
                              'thread', 'threadName', 'processName', 'process',
                              'getMessage', 'exc_info', 'exc_text', 'stack_info']:
                    log_data[key] = value
        
        return json.dumps(log_data, default=str)


class LoggerFactory:
    """Factory for creating configured loggers."""
    
    _loggers: Dict[str, StructuredLogger] = {}
    _default_level = "INFO"
    _default_format = "json"
    
    @classmethod
    def configure(cls, level: str = "INFO", format_type: str = "json"):
        """Configure default logger settings."""
        cls._default_level = level
        cls._default_format = format_type
    
    @classmethod
    def get_logger(cls, name: str) -> StructuredLogger:
        """Get or create a logger instance."""
        if name not in cls._loggers:
            cls._loggers[name] = StructuredLogger(
                name=name,
                level=cls._default_level,
                format_type=cls._default_format
            )
        return cls._loggers[name]


# Convenience function for getting logger
def get_logger(name: str) -> StructuredLogger:
    """Get a structured logger instance."""
    return LoggerFactory.get_logger(name)


# Module-level logger for this file
logger = get_logger(__name__)