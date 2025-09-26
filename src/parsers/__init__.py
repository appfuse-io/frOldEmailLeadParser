"""
Email parser framework with plugin architecture.
"""

from .base_parser import BaseParser
from .lead_source_detector import LeadSourceDetector, DetectionRule
from .parser_registry import (
    ParserRegistry,
    get_parser_registry,
    register_parser,
    get_parser
)

__all__ = [
    'BaseParser',
    'LeadSourceDetector',
    'DetectionRule',
    'ParserRegistry',
    'get_parser_registry',
    'register_parser',
    'get_parser'
]