"""
Data models for the email parser system.
"""

from .lead_data import (
    ContactInfo,
    LeadData,
    ParsedEmail,
    ProcessingResult
)
from .config import (
    AppConfig,
    AWSConfig,
    LoggingConfig,
    ParsingConfig,
    MonitoringConfig,
    Environment,
    load_config,
    get_config
)

__all__ = [
    'ContactInfo',
    'LeadData', 
    'ParsedEmail',
    'ProcessingResult',
    'AppConfig',
    'AWSConfig',
    'LoggingConfig',
    'ParsingConfig',
    'MonitoringConfig',
    'Environment',
    'load_config',
    'get_config'
]