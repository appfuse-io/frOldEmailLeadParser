"""
Retry mechanisms and circuit breaker patterns for robust error handling.
"""
import time
import random
from typing import Callable, Any, Optional, Type, Union, List
from functools import wraps
from dataclasses import dataclass
from enum import Enum

from .logger import get_logger
from .exceptions import RetryExhaustedError, ProcessingTimeoutError, BaseEmailParserException, ErrorCode

logger = get_logger(__name__)


class BackoffStrategy(str, Enum):
    """Backoff strategies for retry attempts."""
    FIXED = "fixed"
    LINEAR = "linear"
    EXPONENTIAL = "exponential"
    EXPONENTIAL_JITTER = "exponential_jitter"


@dataclass
class RetryConfig:
    """Configuration for retry behavior."""
    max_attempts: int = 3
    base_delay: float = 1.0  # seconds
    max_delay: float = 60.0  # seconds
    backoff_strategy: BackoffStrategy = BackoffStrategy.EXPONENTIAL_JITTER
    retryable_exceptions: tuple = (Exception,)
    non_retryable_exceptions: tuple = ()


class RetryHandler:
    """
    Handles retry logic with configurable backoff strategies.
    """
    
    def __init__(self, config: RetryConfig):
        self.config = config
    
    def calculate_delay(self, attempt: int) -> float:
        """
        Calculate delay for the given attempt number.
        
        Args:
            attempt: Current attempt number (1-based)
            
        Returns:
            Delay in seconds
        """
        if self.config.backoff_strategy == BackoffStrategy.FIXED:
            delay = self.config.base_delay
        
        elif self.config.backoff_strategy == BackoffStrategy.LINEAR:
            delay = self.config.base_delay * attempt
        
        elif self.config.backoff_strategy == BackoffStrategy.EXPONENTIAL:
            delay = self.config.base_delay * (2 ** (attempt - 1))
        
        elif self.config.backoff_strategy == BackoffStrategy.EXPONENTIAL_JITTER:
            base_delay = self.config.base_delay * (2 ** (attempt - 1))
            # Add jitter to prevent thundering herd
            jitter = random.uniform(0.1, 0.5) * base_delay
            delay = base_delay + jitter
        
        else:
            delay = self.config.base_delay
        
        # Cap at max delay
        return min(delay, self.config.max_delay)
    
    def should_retry(self, exception: Exception, attempt: int) -> bool:
        """
        Determine if an exception should trigger a retry.
        
        Args:
            exception: The exception that occurred
            attempt: Current attempt number
            
        Returns:
            True if should retry
        """
        # Check if we've exceeded max attempts
        if attempt >= self.config.max_attempts:
            return False
        
        # Check if exception is non-retryable
        if isinstance(exception, self.config.non_retryable_exceptions):
            return False
        
        # Check if exception is retryable
        if isinstance(exception, self.config.retryable_exceptions):
            return True
        
        return False
    
    def execute_with_retry(
        self,
        func: Callable,
        *args,
        **kwargs
    ) -> Any:
        """
        Execute a function with retry logic.
        
        Args:
            func: Function to execute
            *args: Function arguments
            **kwargs: Function keyword arguments
            
        Returns:
            Function result
            
        Raises:
            RetryExhaustedError: If all retry attempts are exhausted
        """
        last_exception = None
        
        for attempt in range(1, self.config.max_attempts + 1):
            try:
                logger.debug(
                    f"Executing function with retry, attempt {attempt}",
                    function=func.__name__,
                    attempt=attempt,
                    max_attempts=self.config.max_attempts
                )
                
                result = func(*args, **kwargs)
                
                if attempt > 1:
                    logger.info(
                        f"Function succeeded after {attempt} attempts",
                        function=func.__name__,
                        attempt=attempt
                    )
                
                return result
                
            except Exception as e:
                last_exception = e
                
                logger.warning(
                    f"Function failed on attempt {attempt}",
                    function=func.__name__,
                    attempt=attempt,
                    error=str(e),
                    error_type=type(e).__name__
                )
                
                if not self.should_retry(e, attempt):
                    logger.error(
                        f"Not retrying function after attempt {attempt}",
                        function=func.__name__,
                        attempt=attempt,
                        error=e,
                        reason="non_retryable_or_max_attempts"
                    )
                    break
                
                if attempt < self.config.max_attempts:
                    delay = self.calculate_delay(attempt)
                    logger.info(
                        f"Retrying function in {delay:.2f} seconds",
                        function=func.__name__,
                        attempt=attempt,
                        delay_seconds=delay
                    )
                    time.sleep(delay)
        
        # All attempts exhausted
        raise RetryExhaustedError(
            message=f"Function {func.__name__} failed after {self.config.max_attempts} attempts",
            max_attempts=self.config.max_attempts,
            last_error=last_exception
        )


def retry(
    max_attempts: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 60.0,
    backoff_strategy: BackoffStrategy = BackoffStrategy.EXPONENTIAL_JITTER,
    retryable_exceptions: tuple = (Exception,),
    non_retryable_exceptions: tuple = ()
):
    """
    Decorator for adding retry logic to functions.
    
    Args:
        max_attempts: Maximum number of retry attempts
        base_delay: Base delay between retries in seconds
        max_delay: Maximum delay between retries in seconds
        backoff_strategy: Strategy for calculating delays
        retryable_exceptions: Exceptions that should trigger retries
        non_retryable_exceptions: Exceptions that should not trigger retries
        
    Returns:
        Decorated function with retry logic
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            config = RetryConfig(
                max_attempts=max_attempts,
                base_delay=base_delay,
                max_delay=max_delay,
                backoff_strategy=backoff_strategy,
                retryable_exceptions=retryable_exceptions,
                non_retryable_exceptions=non_retryable_exceptions
            )
            
            handler = RetryHandler(config)
            return handler.execute_with_retry(func, *args, **kwargs)
        
        return wrapper
    return decorator


class CircuitBreakerState(str, Enum):
    """Circuit breaker states."""
    CLOSED = "closed"      # Normal operation
    OPEN = "open"          # Failing, rejecting requests
    HALF_OPEN = "half_open"  # Testing if service recovered


@dataclass
class CircuitBreakerConfig:
    """Configuration for circuit breaker."""
    failure_threshold: int = 5  # Failures before opening
    recovery_timeout: float = 60.0  # Seconds before trying half-open
    success_threshold: int = 3  # Successes needed to close from half-open
    timeout: float = 30.0  # Request timeout in seconds


class CircuitBreaker:
    """
    Circuit breaker implementation for preventing cascading failures.
    """
    
    def __init__(self, name: str, config: CircuitBreakerConfig):
        self.name = name
        self.config = config
        self.state = CircuitBreakerState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time = 0
        self.logger = get_logger(f"{__name__}.{name}")
    
    def can_execute(self) -> bool:
        """Check if execution is allowed based on circuit breaker state."""
        if self.state == CircuitBreakerState.CLOSED:
            return True
        
        if self.state == CircuitBreakerState.OPEN:
            # Check if recovery timeout has passed
            if time.time() - self.last_failure_time >= self.config.recovery_timeout:
                self.state = CircuitBreakerState.HALF_OPEN
                self.success_count = 0
                self.logger.info(f"Circuit breaker {self.name} transitioning to HALF_OPEN")
                return True
            return False
        
        if self.state == CircuitBreakerState.HALF_OPEN:
            return True
        
        return False
    
    def record_success(self):
        """Record a successful execution."""
        if self.state == CircuitBreakerState.HALF_OPEN:
            self.success_count += 1
            if self.success_count >= self.config.success_threshold:
                self.state = CircuitBreakerState.CLOSED
                self.failure_count = 0
                self.logger.info(f"Circuit breaker {self.name} transitioning to CLOSED")
        elif self.state == CircuitBreakerState.CLOSED:
            self.failure_count = 0
    
    def record_failure(self):
        """Record a failed execution."""
        self.failure_count += 1
        self.last_failure_time = time.time()
        
        if self.state == CircuitBreakerState.CLOSED:
            if self.failure_count >= self.config.failure_threshold:
                self.state = CircuitBreakerState.OPEN
                self.logger.warning(f"Circuit breaker {self.name} transitioning to OPEN")
        elif self.state == CircuitBreakerState.HALF_OPEN:
            self.state = CircuitBreakerState.OPEN
            self.logger.warning(f"Circuit breaker {self.name} transitioning back to OPEN")
    
    def execute(self, func: Callable, *args, **kwargs) -> Any:
        """
        Execute a function with circuit breaker protection.
        
        Args:
            func: Function to execute
            *args: Function arguments
            **kwargs: Function keyword arguments
            
        Returns:
            Function result
            
        Raises:
            Exception: If circuit breaker is open or function fails
        """
        if not self.can_execute():
            raise BaseEmailParserException(
                message=f"Circuit breaker {self.name} is OPEN",
                error_code=ErrorCode.UNKNOWN_ERROR
            )
        
        try:
            # Execute with timeout
            start_time = time.time()
            result = func(*args, **kwargs)
            execution_time = time.time() - start_time
            
            if execution_time > self.config.timeout:
                raise ProcessingTimeoutError(
                    message=f"Function execution exceeded timeout",
                    timeout_seconds=int(self.config.timeout)
                )
            
            self.record_success()
            return result
            
        except Exception as e:
            self.record_failure()
            raise


# Global circuit breakers registry
_circuit_breakers: dict = {}


def get_circuit_breaker(
    name: str,
    config: Optional[CircuitBreakerConfig] = None
) -> CircuitBreaker:
    """
    Get or create a circuit breaker instance.
    
    Args:
        name: Circuit breaker name
        config: Configuration (uses default if not provided)
        
    Returns:
        CircuitBreaker instance
    """
    if name not in _circuit_breakers:
        _circuit_breakers[name] = CircuitBreaker(
            name=name,
            config=config or CircuitBreakerConfig()
        )
    return _circuit_breakers[name]