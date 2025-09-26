"""
Parser implementations for different lead sources.
"""

# Import all parser implementations
try:
    from .b4s_parser import B4sParser
except ImportError:
    B4sParser = None

# Add other parsers as they're implemented
# from .rightbiz_parser import RightbizParser
# from .daltons_parser import DaltonsParser
# from .homecare_parser import HomecareParser
# from .nda_parser import NdaParser

__all__ = [
    'B4sParser',
    # Add other parsers here as they're implemented
]