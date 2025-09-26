"""
Parser registry for dynamic parser loading and management.
"""
from typing import Dict, List, Optional, Type
import importlib
from pathlib import Path

from .base_parser import BaseParser
from .lead_source_detector import LeadSourceDetector
from ..models.lead_data import ParsedEmail
from ..utils.logger import get_logger
from ..utils.exceptions import LeadParsingError, ErrorCode

logger = get_logger(__name__)


class ParserRegistry:
    """
    Registry for managing email parsers with dynamic loading capabilities.
    """
    
    def __init__(self):
        self._parsers: Dict[str, BaseParser] = {}
        self._parser_classes: Dict[str, Type[BaseParser]] = {}
        self.lead_detector = LeadSourceDetector()
        self.logger = get_logger(__name__)
        
        # Auto-register built-in parsers
        self._register_builtin_parsers()
    
    def _register_builtin_parsers(self):
        """Register all built-in parser implementations."""
        try:
            # Import and register each parser (only existing ones)
            parser_modules = [
                ('rightbiz', 'src.parsers.implementations.rightbiz_parser', 'RightbizParser'),
                ('daltons', 'src.parsers.implementations.daltons_parser', 'DaltonsParser'),
                ('b4s', 'src.parsers.implementations.b4s_parser', 'B4sParser'),
                # Note: homecare_parser and nda_parser don't exist yet
            ]
            
            for lead_source, module_path, class_name in parser_modules:
                try:
                    self._register_parser_from_module(lead_source, module_path, class_name)
                except ImportError as e:
                    self.logger.warning(
                        f"Could not import parser {class_name}",
                        lead_source=lead_source,
                        module=module_path,
                        error=str(e)
                    )
                except Exception as e:
                    self.logger.error(
                        f"Failed to register parser {class_name}",
                        lead_source=lead_source,
                        error=e
                    )
            
            self.logger.info(
                f"Registered {len(self._parser_classes)} parser classes",
                parsers=list(self._parser_classes.keys())
            )
            
        except Exception as e:
            self.logger.error("Failed to register built-in parsers", error=e)
    
    def _register_parser_from_module(self, lead_source: str, module_path: str, class_name: str):
        """
        Register a parser from a module.
        
        Args:
            lead_source: Lead source identifier
            module_path: Python module path
            class_name: Parser class name
        """
        try:
            module = importlib.import_module(module_path)
            parser_class = getattr(module, class_name)
            
            if not issubclass(parser_class, BaseParser):
                raise ValueError(f"{class_name} is not a subclass of BaseParser")
            
            self._parser_classes[lead_source] = parser_class
            
            self.logger.debug(
                f"Registered parser class {class_name}",
                lead_source=lead_source,
                class_name=class_name
            )
            
        except ImportError as e:
            raise ImportError(f"Could not import {module_path}: {e}")
        except AttributeError as e:
            raise AttributeError(f"Class {class_name} not found in {module_path}: {e}")
    
    def register_parser(self, lead_source: str, parser_class: Type[BaseParser]):
        """
        Register a parser class for a lead source.
        
        Args:
            lead_source: Lead source identifier
            parser_class: Parser class (must inherit from BaseParser)
            
        Raises:
            ValueError: If parser_class is not a BaseParser subclass
        """
        if not issubclass(parser_class, BaseParser):
            raise ValueError(f"Parser class must inherit from BaseParser")
        
        self._parser_classes[lead_source] = parser_class
        
        # Clear cached instance if exists
        if lead_source in self._parsers:
            del self._parsers[lead_source]
        
        self.logger.info(
            f"Registered parser for {lead_source}",
            lead_source=lead_source,
            parser_class=parser_class.__name__
        )
    
    def get_parser(self, lead_source: str) -> Optional[BaseParser]:
        """
        Get parser instance for a lead source.
        
        Args:
            lead_source: Lead source identifier
            
        Returns:
            Parser instance or None if not found
        """
        # Return cached instance if available
        if lead_source in self._parsers:
            return self._parsers[lead_source]
        
        # Create new instance if class is registered
        if lead_source in self._parser_classes:
            try:
                parser_class = self._parser_classes[lead_source]
                parser_instance = parser_class(lead_source)
                self._parsers[lead_source] = parser_instance
                
                self.logger.debug(
                    f"Created parser instance for {lead_source}",
                    lead_source=lead_source,
                    parser_class=parser_class.__name__
                )
                
                return parser_instance
                
            except Exception as e:
                self.logger.error(
                    f"Failed to create parser instance for {lead_source}",
                    lead_source=lead_source,
                    error=e
                )
                return None
        
        self.logger.warning(f"No parser registered for {lead_source}", lead_source=lead_source)
        return None
    
    def detect_and_get_parser(self, email: ParsedEmail) -> tuple[str, Optional[BaseParser]]:
        """
        Detect lead source and return appropriate parser.
        
        Args:
            email: Parsed email data
            
        Returns:
            Tuple of (lead_source, parser_instance)
        """
        lead_source = self.lead_detector.detect_lead_source(email)
        parser = self.get_parser(lead_source)
        
        self.logger.debug(
            f"Detected lead source and retrieved parser",
            lead_source=lead_source,
            parser_available=parser is not None,
            sender=email.sender,
            subject=email.subject
        )
        
        return lead_source, parser
    
    def get_available_parsers(self) -> List[str]:
        """
        Get list of available parser lead sources.
        
        Returns:
            List of lead source identifiers
        """
        return list(self._parser_classes.keys())
    
    def is_parser_available(self, lead_source: str) -> bool:
        """
        Check if parser is available for a lead source.
        
        Args:
            lead_source: Lead source identifier
            
        Returns:
            True if parser is available
        """
        return lead_source in self._parser_classes
    
    def get_parser_info(self, lead_source: str) -> Optional[Dict[str, str]]:
        """
        Get information about a registered parser.
        
        Args:
            lead_source: Lead source identifier
            
        Returns:
            Parser information dictionary or None
        """
        if lead_source not in self._parser_classes:
            return None
        
        parser_class = self._parser_classes[lead_source]
        
        return {
            'lead_source': lead_source,
            'class_name': parser_class.__name__,
            'module': parser_class.__module__,
            'doc': parser_class.__doc__ or "No description available"
        }
    
    def validate_parser(self, lead_source: str, email: ParsedEmail) -> bool:
        """
        Validate that a parser can handle a specific email.
        
        Args:
            lead_source: Lead source identifier
            email: Email to validate against
            
        Returns:
            True if parser can handle the email
        """
        parser = self.get_parser(lead_source)
        if not parser:
            return False
        
        try:
            return parser.can_parse(email)
        except Exception as e:
            self.logger.warning(
                f"Parser validation failed for {lead_source}",
                lead_source=lead_source,
                error=e
            )
            return False
    
    def clear_cache(self):
        """Clear all cached parser instances."""
        self._parsers.clear()
        self.logger.info("Cleared parser instance cache")
    
    def reload_parsers(self):
        """Reload all parser modules (useful for development)."""
        self.clear_cache()
        
        # Reload parser modules
        for lead_source in self._parser_classes:
            parser_class = self._parser_classes[lead_source]
            module = importlib.import_module(parser_class.__module__)
            importlib.reload(module)
        
        self.logger.info("Reloaded all parser modules")


# Global registry instance
_parser_registry: Optional[ParserRegistry] = None


def get_parser_registry() -> ParserRegistry:
    """
    Get the global parser registry instance.
    
    Returns:
        ParserRegistry instance
    """
    global _parser_registry
    if _parser_registry is None:
        _parser_registry = ParserRegistry()
    return _parser_registry


def register_parser(lead_source: str, parser_class: Type[BaseParser]):
    """
    Register a parser class globally.
    
    Args:
        lead_source: Lead source identifier
        parser_class: Parser class
    """
    registry = get_parser_registry()
    registry.register_parser(lead_source, parser_class)


def get_parser(lead_source: str) -> Optional[BaseParser]:
    """
    Get parser for a lead source.
    
    Args:
        lead_source: Lead source identifier
        
    Returns:
        Parser instance or None
    """
    registry = get_parser_registry()
    return registry.get_parser(lead_source)