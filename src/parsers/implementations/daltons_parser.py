"""
Daltons Business email parser implementation.
"""
import re
from typing import Optional
from datetime import datetime

from ..base_parser import BaseParser
from ...models.lead_data import LeadData, ContactInfo, ParsedEmail
from ...utils.logger import get_logger
from ...utils.exceptions import LeadParsingError, ErrorCode

logger = get_logger(__name__)


class DaltonsParser(BaseParser):
    """
    Parser for Daltons Business lead emails.
    
    Handles emails with format:
    - From: "Daltons Business <info@daltonssupportmail.com>"
    - Subject: "DaltonsBusiness - Business Ref.: DAL137"
    - Content contains: "Contact details:- Name : Bilbo Daggins", "More Details are required for business with reference: DAL137"
    """
    
    def __init__(self, lead_source: str = "daltons"):
        super().__init__(lead_source)
        
        # Reference extraction patterns
        self.reference_patterns = [
            r'More Details are required for business with reference:\s*([A-Z0-9]+)',
            r'Business Ref\.:\s*([A-Z0-9]+)',
            r'DAL(\d+)',
            r'reference:\s*([A-Z0-9]+)',
        ]
        
        # Name extraction patterns (Daltons specific format)
        self.name_patterns = [
            r'Contact details:-\s*Name\s*:\s*(.+?)(?:\r?\n|$)',
            r'Name\s*:\s*(.+?)(?:\r?\n|$)',
        ]
        
        # Email extraction patterns
        self.email_patterns = [
            r'Email Address\s*:\s*([^\s\r\n<]+@[^\s\r\n<>]+)',
            r'Email\s*:\s*([^\s\r\n<]+@[^\s\r\n<>]+)',
        ]
        
        # Phone extraction patterns
        self.phone_patterns = [
            r'Contact Phone\s*:\s*([^\r\n]+)',
            r'Phone\s*:\s*([^\r\n]+)',
            r'Telephone\s*:\s*([^\r\n]+)',
        ]
    
    def can_parse(self, email: ParsedEmail) -> bool:
        """
        Check if this parser can handle the email.
        
        Args:
            email: Parsed email data
            
        Returns:
            True if this parser can handle the email
        """
        content = self._get_email_content(email)
        
        # Check for Daltons indicators
        indicators = [
            r'@daltonssupportmail\.com',
            r'DaltonsBusiness',
            r'Daltons Business',
            r'Contact details:-\s*Name\s*:',
            r'More Details are required for business with reference:',
        ]
        
        matches = 0
        for indicator in indicators:
            if re.search(indicator, content, re.IGNORECASE):
                matches += 1
        
        # Need at least 2 indicators to be confident
        can_parse = matches >= 2
        
        self.logger.debug(
            f"Daltons parser can_parse check",
            can_parse=can_parse,
            matches=matches,
            sender=email.sender,
            subject=email.subject
        )
        
        return can_parse
    
    def parse(self, email: ParsedEmail) -> LeadData:
        """
        Parse Daltons email into structured lead data.
        
        Args:
            email: Parsed email data
            
        Returns:
            Structured lead data
            
        Raises:
            LeadParsingError: If parsing fails
        """
        try:
            content = self._get_email_content(email)
            
            self.logger.debug(
                "Starting Daltons email parsing",
                sender=email.sender,
                subject=email.subject,
                content_length=len(content)
            )
            
            # Extract reference
            reference = self._extract_daltons_reference(content)
            
            # Extract contact information
            contact_info = self._extract_daltons_contact_info(content)
            
            # Create lead data
            lead_data = LeadData(
                lead_source=self.lead_source,
                resale_reference=reference,
                contact_info=contact_info,
                receipt_date=email.date or datetime.utcnow(),
                raw_email_content=content,
                metadata={
                    'parser_used': self.__class__.__name__,
                    'email_subject': email.subject,
                    'email_sender': email.sender,
                    'reference_found': bool(reference),
                    'parsing_timestamp': datetime.utcnow().isoformat()
                }
            )
            
            self.logger.info(
                "Successfully parsed Daltons email",
                reference=reference,
                email=contact_info.email,
                first_name=contact_info.first_name,
                last_name=contact_info.last_name
            )
            
            return lead_data
            
        except Exception as e:
            if isinstance(e, LeadParsingError):
                raise
            
            raise LeadParsingError(
                message=f"Failed to parse Daltons email: {str(e)}",
                error_code=ErrorCode.LEAD_DATA_INVALID,
                lead_source=self.lead_source,
                cause=e
            )
    
    def _extract_daltons_reference(self, content: str) -> Optional[str]:
        """
        Extract business reference from Daltons email.
        
        Args:
            content: Email content
            
        Returns:
            Reference or None
        """
        reference = self._extract_reference(content, self.reference_patterns)
        
        if reference:
            self.logger.debug(f"Extracted Daltons reference: {reference}")
        else:
            self.logger.warning("Could not extract Daltons reference from email")
        
        return reference
    
    def _extract_daltons_contact_info(self, content: str) -> ContactInfo:
        """
        Extract contact information from Daltons email.
        
        Args:
            content: Email content
            
        Returns:
            Contact information
            
        Raises:
            LeadParsingError: If required contact info cannot be extracted
        """
        # Extract name using Daltons specific patterns
        first_name, last_name = self._extract_daltons_name(content)
        
        # Extract email
        email = self._extract_daltons_email(content)
        
        # Extract phone
        telephone = self._extract_daltons_phone(content)
        
        # Validate required fields
        if not first_name or not email:
            missing_fields = []
            if not first_name:
                missing_fields.append('first_name')
            if not email:
                missing_fields.append('email')
            
            raise LeadParsingError(
                message="Missing required contact information in Daltons email",
                error_code=ErrorCode.LEAD_MISSING_REQUIRED_FIELDS,
                lead_source=self.lead_source,
                missing_fields=missing_fields
            )
        
        return ContactInfo(
            first_name=first_name,
            last_name=last_name or "",
            email=email,
            telephone=telephone
        )
    
    def _extract_daltons_name(self, content: str) -> tuple[Optional[str], Optional[str]]:
        """
        Extract name from Daltons email content.
        
        Args:
            content: Email content
            
        Returns:
            Tuple of (first_name, last_name)
        """
        # Try Daltons specific patterns first
        for pattern in self.name_patterns:
            match = re.search(pattern, content, re.IGNORECASE | re.MULTILINE)
            if match:
                full_name = match.group(1).strip()
                if full_name:
                    name_parts = full_name.split()
                    if len(name_parts) >= 2:
                        first_name = name_parts[0]
                        last_name = " ".join(name_parts[1:])
                        self.logger.debug(f"Extracted Daltons name: {first_name} {last_name}")
                        return first_name, last_name
                    else:
                        self.logger.debug(f"Extracted Daltons first name only: {name_parts[0]}")
                        return name_parts[0], None
        
        # Fallback to base parser method
        return self._extract_name(content)
    
    def _extract_daltons_email(self, content: str) -> Optional[str]:
        """
        Extract email from Daltons email content.
        
        Args:
            content: Email content
            
        Returns:
            Email address or None
        """
        # Try Daltons specific patterns first
        for pattern in self.email_patterns:
            match = re.search(pattern, content, re.IGNORECASE)
            if match:
                email = match.group(1).strip()
                # Remove any trailing characters like <mailto:...>
                email = re.sub(r'<.*$', '', email)
                self.logger.debug(f"Extracted Daltons email: {email}")
                return email
        
        # Fallback to base parser method
        return self._extract_email(content)
    
    def _extract_daltons_phone(self, content: str) -> Optional[str]:
        """
        Extract phone number from Daltons email content.
        
        Args:
            content: Email content
            
        Returns:
            Phone number or None
        """
        # Try Daltons specific patterns first
        for pattern in self.phone_patterns:
            match = re.search(pattern, content, re.IGNORECASE)
            if match:
                phone = match.group(1).strip()
                self.logger.debug(f"Extracted Daltons phone: {phone}")
                return phone
        
        # Fallback to base parser method
        return self._extract_telephone(content)