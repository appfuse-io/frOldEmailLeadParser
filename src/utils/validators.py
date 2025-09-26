"""
Data validation utilities for email parsing and lead data validation.
"""
import re
from typing import Optional, List, Dict, Any, Tuple
from datetime import datetime
from email_validator import validate_email, EmailNotValidError

from .logger import get_logger
from .exceptions import ValidationError

logger = get_logger(__name__)


class DataValidator:
    """
    Comprehensive data validator for lead information.
    """
    
    # Regex patterns for validation
    PHONE_PATTERN = re.compile(r'^[\+]?[\d\s\-\(\)]{7,20}$')
    NAME_PATTERN = re.compile(r'^[a-zA-Z\s\-\'\.]{1,100}$')
    REFERENCE_PATTERN = re.compile(r'^[a-zA-Z0-9\-_]{1,50}$')
    
    # Known lead sources
    VALID_LEAD_SOURCES = {
        'rightbiz', 'daltons', 'homecare', 'b4s', 
        'businesses for sale', 'nda', 'registerinterest'
    }
    
    @classmethod
    def validate_email_address(cls, email: str) -> Tuple[bool, Optional[str]]:
        """
        Validate email address format and deliverability.
        
        Args:
            email: Email address to validate
            
        Returns:
            Tuple of (is_valid, normalized_email)
        """
        if not email or not isinstance(email, str):
            return False, None
        
        try:
            # Use email-validator library for comprehensive validation
            validated_email = validate_email(email.strip())
            return True, validated_email.email
        except EmailNotValidError as e:
            logger.debug(f"Email validation failed: {email}", error=str(e))
            return False, None
        except Exception as e:
            logger.warning(f"Unexpected error validating email: {email}", error=e)
            return False, None
    
    @classmethod
    def validate_phone_number(cls, phone: str) -> Tuple[bool, Optional[str]]:
        """
        Validate and normalize phone number.
        
        Args:
            phone: Phone number to validate
            
        Returns:
            Tuple of (is_valid, normalized_phone)
        """
        if not phone or not isinstance(phone, str):
            return False, None
        
        # Clean the phone number
        cleaned = re.sub(r'[^\d\+]', '', phone.strip())
        
        # Basic validation
        if len(cleaned) < 7 or len(cleaned) > 20:
            return False, None
        
        # Check pattern
        if not cls.PHONE_PATTERN.match(phone.strip()):
            return False, None
        
        return True, cleaned
    
    @classmethod
    def validate_name(cls, name: str) -> Tuple[bool, Optional[str]]:
        """
        Validate and normalize person name.
        
        Args:
            name: Name to validate
            
        Returns:
            Tuple of (is_valid, normalized_name)
        """
        if not name or not isinstance(name, str):
            return False, None
        
        # Clean and normalize
        cleaned = name.strip()
        if not cleaned:
            return False, None
        
        # Check pattern
        if not cls.NAME_PATTERN.match(cleaned):
            return False, None
        
        # Title case normalization
        normalized = ' '.join(word.capitalize() for word in cleaned.split())
        
        return True, normalized
    
    @classmethod
    def validate_reference(cls, reference: str) -> Tuple[bool, Optional[str]]:
        """
        Validate business reference/ID.
        
        Args:
            reference: Reference to validate
            
        Returns:
            Tuple of (is_valid, normalized_reference)
        """
        if not reference or not isinstance(reference, str):
            return False, None
        
        cleaned = reference.strip().upper()
        
        if not cls.REFERENCE_PATTERN.match(cleaned):
            return False, None
        
        return True, cleaned
    
    @classmethod
    def validate_lead_source(cls, lead_source: str) -> Tuple[bool, Optional[str]]:
        """
        Validate lead source.
        
        Args:
            lead_source: Lead source to validate
            
        Returns:
            Tuple of (is_valid, normalized_lead_source)
        """
        if not lead_source or not isinstance(lead_source, str):
            return False, None
        
        normalized = lead_source.lower().strip()
        
        if normalized not in cls.VALID_LEAD_SOURCES:
            return False, None
        
        return True, normalized
    
    @classmethod
    def validate_lead_data(cls, lead_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate and normalize complete lead data.
        
        Args:
            lead_data: Raw lead data dictionary
            
        Returns:
            Validated and normalized lead data
            
        Raises:
            ValidationError: If validation fails
        """
        errors = {}
        validated_data = {}
        
        # Validate required fields
        required_fields = ['first_name', 'last_name', 'email', 'lead_source']
        for field in required_fields:
            if field not in lead_data or not lead_data[field]:
                errors[field] = f"{field} is required"
        
        # Validate lead source
        if 'lead_source' in lead_data:
            is_valid, normalized = cls.validate_lead_source(lead_data['lead_source'])
            if is_valid:
                validated_data['lead_source'] = normalized
            else:
                errors['lead_source'] = f"Invalid lead source: {lead_data['lead_source']}"
        
        # Validate names
        for name_field in ['first_name', 'last_name']:
            if name_field in lead_data:
                is_valid, normalized = cls.validate_name(lead_data[name_field])
                if is_valid:
                    validated_data[name_field] = normalized
                elif lead_data[name_field]:  # Only error if not empty
                    errors[name_field] = f"Invalid {name_field}: {lead_data[name_field]}"
        
        # Validate email
        if 'email' in lead_data:
            is_valid, normalized = cls.validate_email_address(lead_data['email'])
            if is_valid:
                validated_data['email'] = normalized
            else:
                errors['email'] = f"Invalid email address: {lead_data['email']}"
        
        # Validate phone numbers (optional)
        for phone_field in ['telephone', 'mobile']:
            if phone_field in lead_data and lead_data[phone_field]:
                is_valid, normalized = cls.validate_phone_number(lead_data[phone_field])
                if is_valid:
                    validated_data[phone_field] = normalized
                else:
                    errors[phone_field] = f"Invalid {phone_field}: {lead_data[phone_field]}"
        
        # Validate reference (optional)
        if 'resale_reference' in lead_data and lead_data['resale_reference']:
            is_valid, normalized = cls.validate_reference(lead_data['resale_reference'])
            if is_valid:
                validated_data['resale_reference'] = normalized
            else:
                errors['resale_reference'] = f"Invalid reference: {lead_data['resale_reference']}"
        
        # Add receipt date if not present
        if 'receipt_date' not in lead_data:
            validated_data['receipt_date'] = datetime.utcnow()
        else:
            validated_data['receipt_date'] = lead_data['receipt_date']
        
        # Copy other fields
        for key, value in lead_data.items():
            if key not in validated_data and key not in errors:
                validated_data[key] = value
        
        # Raise validation error if any errors found
        if errors:
            raise ValidationError(
                message="Lead data validation failed",
                field_errors=errors
            )
        
        return validated_data


class EmailContentValidator:
    """
    Validator for email content and structure.
    """
    
    MAX_EMAIL_SIZE_MB = 10
    MIN_CONTENT_LENGTH = 10
    
    @classmethod
    def validate_email_size(cls, content: str, max_size_mb: Optional[int] = None) -> bool:
        """
        Validate email content size.
        
        Args:
            content: Email content
            max_size_mb: Maximum size in MB (default: 10)
            
        Returns:
            True if size is acceptable
        """
        max_size = (max_size_mb or cls.MAX_EMAIL_SIZE_MB) * 1024 * 1024
        content_size = len(content.encode('utf-8'))
        
        return content_size <= max_size
    
    @classmethod
    def validate_email_content(cls, content: str) -> Tuple[bool, List[str]]:
        """
        Validate email content structure and quality.
        
        Args:
            content: Email content to validate
            
        Returns:
            Tuple of (is_valid, list_of_issues)
        """
        issues = []
        
        if not content or not isinstance(content, str):
            issues.append("Email content is empty or invalid")
            return False, issues
        
        # Check minimum content length
        if len(content.strip()) < cls.MIN_CONTENT_LENGTH:
            issues.append("Email content too short")
        
        # Check for suspicious content
        suspicious_patterns = [
            r'<script[^>]*>',  # Script tags
            r'javascript:',     # JavaScript URLs
            r'data:text/html',  # Data URLs
        ]
        
        for pattern in suspicious_patterns:
            if re.search(pattern, content, re.IGNORECASE):
                issues.append(f"Suspicious content detected: {pattern}")
        
        # Check encoding issues
        try:
            content.encode('utf-8')
        except UnicodeEncodeError:
            issues.append("Content contains invalid characters")
        
        return len(issues) == 0, issues


def validate_and_normalize_lead(raw_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Convenience function to validate and normalize lead data.
    
    Args:
        raw_data: Raw lead data from parser
        
    Returns:
        Validated and normalized lead data
        
    Raises:
        ValidationError: If validation fails
    """
    return DataValidator.validate_lead_data(raw_data)


def is_valid_email_content(content: str, max_size_mb: int = 10) -> bool:
    """
    Convenience function to check if email content is valid.
    
    Args:
        content: Email content
        max_size_mb: Maximum size in MB
        
    Returns:
        True if content is valid
    """
    if not EmailContentValidator.validate_email_size(content, max_size_mb):
        return False
    
    is_valid, _ = EmailContentValidator.validate_email_content(content)
    return is_valid