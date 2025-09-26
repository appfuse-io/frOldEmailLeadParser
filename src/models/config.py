"""
Configuration management with environment-specific settings and validation.
"""
import os
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field, validator
from enum import Enum


class Environment(str, Enum):
    """Supported environments."""
    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"


class AWSConfig(BaseModel):
    """AWS service configuration."""
    region_name: str = Field(default="eu-west-2")
    access_key_id: Optional[str] = None
    secret_access_key: Optional[str] = None
    s3_bucket: str = Field(..., min_length=1)
    sqs_queue_url: str = Field(..., min_length=1)
    
    @validator('sqs_queue_url')
    def validate_sqs_url(cls, v):
        """Validate SQS queue URL format."""
        if not v.startswith('https://sqs.'):
            raise ValueError('Invalid SQS queue URL format')
        return v


class LoggingConfig(BaseModel):
    """Logging configuration."""
    level: str = Field(default="INFO")
    format: str = Field(default="json")
    include_request_id: bool = Field(default=True)
    
    @validator('level')
    def validate_log_level(cls, v):
        """Validate log level."""
        valid_levels = {'DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'}
        if v.upper() not in valid_levels:
            raise ValueError(f'Invalid log level: {v}')
        return v.upper()


class ParsingConfig(BaseModel):
    """Email parsing configuration."""
    max_email_size_mb: int = Field(default=10)
    timeout_seconds: int = Field(default=30)
    retry_attempts: int = Field(default=3)
    enable_fallback_parsing: bool = Field(default=True)
    
    @validator('max_email_size_mb')
    def validate_max_size(cls, v):
        """Validate maximum email size."""
        if v <= 0 or v > 100:
            raise ValueError('Max email size must be between 1 and 100 MB')
        return v


class MonitoringConfig(BaseModel):
    """Monitoring and metrics configuration."""
    enable_custom_metrics: bool = Field(default=True)
    metric_namespace: str = Field(default="FranchiseResales/EmailParser")
    enable_detailed_logging: bool = Field(default=False)


class AppConfig(BaseModel):
    """Main application configuration."""
    environment: Environment = Field(default=Environment.DEVELOPMENT)
    aws: AWSConfig
    logging: LoggingConfig = Field(default_factory=LoggingConfig)
    parsing: ParsingConfig = Field(default_factory=ParsingConfig)
    monitoring: MonitoringConfig = Field(default_factory=MonitoringConfig)
    
    class Config:
        """Pydantic configuration."""
        use_enum_values = True


def load_config() -> AppConfig:
    """
    Load configuration from environment variables.
    
    Returns:
        AppConfig: Validated application configuration
        
    Raises:
        ValueError: If required configuration is missing or invalid
    """
    try:
        # AWS Configuration
        aws_config = AWSConfig(
            region_name=os.getenv('AWS_REGION', 'eu-west-2'),
            access_key_id=os.getenv('AWS_ACCESS_KEY_ID'),
            secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY'),
            s3_bucket=os.getenv('AWS_S3_BUCKET', ''),
            sqs_queue_url=os.getenv('SQS_QUEUE_URL', '')
        )
        
        # Logging Configuration
        logging_config = LoggingConfig(
            level=os.getenv('LOG_LEVEL', 'INFO'),
            format=os.getenv('LOG_FORMAT', 'json'),
            include_request_id=os.getenv('LOG_INCLUDE_REQUEST_ID', 'true').lower() == 'true'
        )
        
        # Parsing Configuration
        parsing_config = ParsingConfig(
            max_email_size_mb=int(os.getenv('MAX_EMAIL_SIZE_MB', '10')),
            timeout_seconds=int(os.getenv('PARSING_TIMEOUT_SECONDS', '30')),
            retry_attempts=int(os.getenv('PARSING_RETRY_ATTEMPTS', '3')),
            enable_fallback_parsing=os.getenv('ENABLE_FALLBACK_PARSING', 'true').lower() == 'true'
        )
        
        # Monitoring Configuration
        monitoring_config = MonitoringConfig(
            enable_custom_metrics=os.getenv('ENABLE_CUSTOM_METRICS', 'true').lower() == 'true',
            metric_namespace=os.getenv('METRIC_NAMESPACE', 'FranchiseResales/EmailParser'),
            enable_detailed_logging=os.getenv('ENABLE_DETAILED_LOGGING', 'false').lower() == 'true'
        )
        
        # Main Configuration
        config = AppConfig(
            environment=Environment(os.getenv('ENVIRONMENT', 'development')),
            aws=aws_config,
            logging=logging_config,
            parsing=parsing_config,
            monitoring=monitoring_config
        )
        
        return config
        
    except Exception as e:
        raise ValueError(f"Failed to load configuration: {str(e)}")


def get_config() -> AppConfig:
    """
    Get cached configuration instance.
    
    Returns:
        AppConfig: Application configuration
    """
    if not hasattr(get_config, '_config'):
        get_config._config = load_config()
    return get_config._config