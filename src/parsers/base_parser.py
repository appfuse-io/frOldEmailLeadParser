"""
Abstract base parser for all email lead parsers.
"""
from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional, Tuple
import re
from datetime import datetime

from ..models.lead_data import LeadData, ContactInfo, ParsedEmail
from ..utils.logger import get_logger
from ..utils.exceptions import LeadParsingError, ErrorCode
from ..utils.validators import DataValidator

logger = get_logger(__name__)


class BaseParser(ABC):
    """
    Abstract base class for all lead parsers.
    
    Provides common functionality and enforces interface for specific parsers.
    """
    
    def __init__(self, lead_source: str):
        self.lead_source = lead_source
        self.logger = get_logger(f"{__name__}.{lead_source}")
    
    @abstractmethod
    def can_parse(self, email: ParsedEmail) -> bool:
        """
        Determine if this parser can handle the given email.
        
        Args:
            email: Parsed email data
            
        Returns:
            True if this parser can handle the email
        """
        pass
    
    @abstractmethod
    def parse(self, email: ParsedEmail) -> LeadData:
        """
        Parse email content into structured lead data.
        
        Args:
            email: Parsed email data
            
        Returns:
            Structured lead data
            
        Raises:
            LeadParsingError: If parsing fails
        """
        pass
    
    def extract_contact_info(self, content: str) -> ContactInfo:
        """
        Extract contact information from email content.
        
        Args:
            content: Email text content
            
        Returns:
            Contact information
            
        Raises:
            LeadParsingError: If required contact info cannot be extracted
        """
        try:
            # Extract name
            first_name, last_name = self._extract_name(content)
            
            # Extract email
            email = self._extract_email(content)
            
            # Extract phone numbers
            telephone = self._extract_telephone(content)
            mobile = self._extract_mobile(content)
            
            # Validate required fields
            if not first_name or not email:
                raise LeadParsingError(
                    message="Missing required contact information",
                    error_code=ErrorCode.LEAD_MISSING_REQUIRED_FIELDS,
                    lead_source=self.lead_source,
                    missing_fields=[f for f in ['first_name', 'email'] 
                                  if not locals()[f]]
                )
            
            return ContactInfo(
                first_name=first_name,
                last_name=last_name or "",
                email=email,
                telephone=telephone,
                mobile=mobile
            )
            
        except Exception as e:
            if isinstance(e, LeadParsingError):
                raise
            
            raise LeadParsingError(
                message=f"Failed to extract contact info: {str(e)}",
                error_code=ErrorCode.LEAD_DATA_INVALID,
                lead_source=self.lead_source,
                cause=e
            )
    
    def _extract_name(self, content: str) -> Tuple[Optional[str], Optional[str]]:
        """
        Extract first and last name from content.
        
        Args:
            content: Email content
            
        Returns:
            Tuple of (first_name, last_name)
        """
        # Common name patterns
        name_patterns = [
            r'Name:\s*(.+)',
            r'Contact Name:\s*(.+)',
            r'Full Name:\s*(.+)',
            r'First Name:\s*(.+?)(?:\r?\n|\s+Last Name:\s*(.+))',
        ]
        
        for pattern in name_patterns:
            match = re.search(pattern, content, re.IGNORECASE | re.MULTILINE)
            if match:
                if len(match.groups()) == 2:  # First and last name separately
                    return match.group(1).strip(), match.group(2).strip()
                else:  # Full name
                    full_name = match.group(1).strip()
                    name_parts = full_name.split()
                    if len(name_parts) >= 2:
                        return name_parts[0], " ".join(name_parts[1:])
                    else:
                        return name_parts[0] if name_parts else None, None
        
        return None, None
    
    def _extract_email(self, content: str) -> Optional[str]:
        """
        Extract email address from content.
        
        Args:
            content: Email content
            
        Returns:
            Email address or None
        """
        # Email patterns
        email_patterns = [
            r'Email:\s*([^\s\r\n]+@[^\s\r\n]+)',
            r'Email Address:\s*([^\s\r\n]+@[^\s\r\n]+)',
            r'E-mail:\s*([^\s\r\n]+@[^\s\r\n]+)',
        ]
        
        for pattern in email_patterns:
            match = re.search(pattern, content, re.IGNORECASE)
            if match:
                email = match.group(1).strip()
                # Validate email format
                is_valid, normalized = DataValidator.validate_email_address(email)
                if is_valid:
                    return normalized
        
        # Fallback: find any email-like pattern
        email_match = re.search(r'([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})', content)
        if email_match:
            email = email_match.group(1)
            is_valid, normalized = DataValidator.validate_email_address(email)
            if is_valid:
                return normalized
        
        return None
    
    def _extract_telephone(self, content: str) -> Optional[str]:
        """
        Extract telephone number from content.
        
        Args:
            content: Email content
            
        Returns:
            Telephone number or None
        """
        phone_patterns = [
            r'Tel(?:ephone)?:\s*([^\r\n]+)',
            r'Phone:\s*([^\r\n]+)',
            r'Contact Phone:\s*([^\r\n]+)',
            r'Telephone Number:\s*([^\r\n]+)',
        ]
        
        for pattern in phone_patterns:
            match = re.search(pattern, content, re.IGNORECASE)
            if match:
                phone = match.group(1).strip()
                is_valid, normalized = DataValidator.validate_phone_number(phone)
                if is_valid:
                    return normalized
        
        return None
    
    def _extract_mobile(self, content: str) -> Optional[str]:
        """
        Extract mobile number from content.
        
        Args:
            content: Email content
            
        Returns:
            Mobile number or None
        """
        mobile_patterns = [
            r'Mobile:\s*([^\r\n]+)',
            r'Cell:\s*([^\r\n]+)',
            r'Mobile Phone:\s*([^\r\n]+)',
        ]
        
        for pattern in mobile_patterns:
            match = re.search(pattern, content, re.IGNORECASE)
            if match:
                mobile = match.group(1).strip()
                is_valid, normalized = DataValidator.validate_phone_number(mobile)
                if is_valid:
                    return normalized
        
        return None
    
    def _extract_reference(self, content: str, patterns: List[str]) -> Optional[str]:
        """
        Extract reference using provided patterns.
        
        Args:
            content: Email content
            patterns: List of regex patterns to try
            
        Returns:
            Reference or None
        """
        for pattern in patterns:
            match = re.search(pattern, content, re.IGNORECASE)
            if match:
                reference = match.group(1).strip()
                is_valid, normalized = DataValidator.validate_reference(reference)
                if is_valid:
                    return normalized
        
        return None
    
    def _get_email_content(self, email: ParsedEmail) -> str:
        """
        Get combined email content for parsing.
        
        Args:
            email: Parsed email data
            
        Returns:
            Combined email content
        """
        content_parts = []
        
        if email.subject:
            content_parts.append(f"Subject: {email.subject}")
        
        if email.text_content:
            content_parts.extend(email.text_content)
        
        return "\n".join(content_parts)
    
    def validate_parsed_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate and normalize parsed data.
        
        Args:
            data: Raw parsed data
            
        Returns:
            Validated and normalized data
            
        Raises:
            LeadParsingError: If validation fails
        """
        try:
            return DataValidator.validate_lead_data(data)
        except Exception as e:
            raise LeadParsingError(
                message=f"Data validation failed: {str(e)}",
                error_code=ErrorCode.VALIDATION_FAILED,
                lead_source=self.lead_source,
                cause=e
            )