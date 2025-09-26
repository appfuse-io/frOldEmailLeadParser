"""
BusinessesForSale.com email parser implementation.
"""
import re
from typing import Optional, List
from datetime import datetime

from ..base_parser import BaseParser
from ...models.lead_data import LeadData, ContactInfo, ParsedEmail
from ...utils.logger import get_logger
from ...utils.exceptions import LeadParsingError, ErrorCode

logger = get_logger(__name__)


class B4sParser(BaseParser):
    """
    Parser for BusinessesForSale.com lead emails.
    
    Handles emails with format:
    - Subject: "Name is interested in your listing REF123"
    - Content contains: "Your listing ref:REF123", contact details
    """
    
    def __init__(self, lead_source: str = "b4s"):
        super().__init__(lead_source)
        
        # Reference extraction patterns (multiple fallbacks)
        self.reference_patterns = [
            r'Your listing ref:\s*([A-Z0-9]+)',
            r'listing\s+ref:\s*([A-Z0-9]+)',
            r'BFS(\d+)',
            r'ref:\s*([A-Z0-9]+)',
            r'listing\s+([A-Z0-9]+)',
        ]
        
        # Name extraction patterns
        self.name_patterns = [
            r'Name:\s*(.+?)(?:\r?\n|$)',
            r'Contact Name:\s*(.+?)(?:\r?\n|$)',
            r'Full Name:\s*(.+?)(?:\r?\n|$)',
        ]
        
        # Email extraction patterns
        self.email_patterns = [
            r'Email:\s*([^\s\r\n]+@[^\s\r\n]+)',
            r'E-mail:\s*([^\s\r\n]+@[^\s\r\n]+)',
            r'Email Address:\s*([^\s\r\n]+@[^\s\r\n]+)',
        ]
        
        # Phone extraction patterns
        self.phone_patterns = [
            r'Tel:\s*([^\r\n]+)',
            r'Phone:\s*([^\r\n]+)',
            r'Telephone:\s*([^\r\n]+)',
            r'Phone Number:\s*([^\r\n]+)',
            r'Telephone Number:\s*([^\r\n]+)',
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
        
        # Check for BusinessesForSale.com indicators
        indicators = [
            r'BusinessesForSale\.com',
            r'@businessesforsale\.com',
            r'Your listing ref:',
            r'interested in your listing',
            r'Reply directly to this email',
        ]
        
        matches = 0
        for indicator in indicators:
            if re.search(indicator, content, re.IGNORECASE):
                matches += 1
        
        # Need at least 2 indicators to be confident
        can_parse = matches >= 2
        
        self.logger.debug(
            f"B4S parser can_parse check",
            can_parse=can_parse,
            matches=matches,
            sender=email.sender,
            subject=email.subject
        )
        
        return can_parse
    
    def parse(self, email: ParsedEmail) -> LeadData:
        """
        Parse B4S email into structured lead data.
        
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
                "Starting B4S email parsing",
                sender=email.sender,
                subject=email.subject,
                content_length=len(content)
            )
            
            # Extract reference
            reference = self._extract_b4s_reference(content)
            
            # Extract contact information
            contact_info = self._extract_b4s_contact_info(content)
            
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
                "Successfully parsed B4S email",
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
                message=f"Failed to parse B4S email: {str(e)}",
                error_code=ErrorCode.LEAD_DATA_INVALID,
                lead_source=self.lead_source,
                cause=e
            )
    
    def _extract_b4s_reference(self, content: str) -> Optional[str]:
        """
        Extract business reference from B4S email.
        
        Args:
            content: Email content
            
        Returns:
            Reference or None
        """
        reference = self._extract_reference(content, self.reference_patterns)
        
        if reference:
            self.logger.debug(f"Extracted B4S reference: {reference}")
        else:
            self.logger.warning("Could not extract B4S reference from email")
        
        return reference
    
    def _extract_b4s_contact_info(self, content: str) -> ContactInfo:
        """
        Extract contact information from B4S email.
        
        Args:
            content: Email content
            
        Returns:
            Contact information
            
        Raises:
            LeadParsingError: If required contact info cannot be extracted
        """
        # Extract name
        first_name, last_name = self._extract_b4s_name(content)
        
        # Extract email
        email = self._extract_b4s_email(content)
        
        # Extract phone
        telephone = self._extract_b4s_phone(content)
        
        # Validate required fields
        if not first_name or not email:
            missing_fields = []
            if not first_name:
                missing_fields.append('first_name')
            if not email:
                missing_fields.append('email')
            
            raise LeadParsingError(
                message="Missing required contact information in B4S email",
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
    
    def _extract_b4s_name(self, content: str) -> tuple[Optional[str], Optional[str]]:
        """
        Extract name from B4S email content.
        
        Args:
            content: Email content
            
        Returns:
            Tuple of (first_name, last_name)
        """
        # Try specific B4S name patterns first
        for pattern in self.name_patterns:
            match = re.search(pattern, content, re.IGNORECASE | re.MULTILINE)
            if match:
                full_name = match.group(1).strip()
                if full_name:
                    name_parts = full_name.split()
                    if len(name_parts) >= 2:
                        first_name = name_parts[0]
                        last_name = " ".join(name_parts[1:])
                        self.logger.debug(f"Extracted B4S name: {first_name} {last_name}")
                        return first_name, last_name
                    else:
                        self.logger.debug(f"Extracted B4S first name only: {name_parts[0]}")
                        return name_parts[0], None
        
        # Fallback to base parser method
        return self._extract_name(content)
    
    def _extract_b4s_email(self, content: str) -> Optional[str]:
        """
        Extract email from B4S email content.
        
        Args:
            content: Email content
            
        Returns:
            Email address or None
        """
        # Try B4S specific patterns first
        for pattern in self.email_patterns:
            match = re.search(pattern, content, re.IGNORECASE)
            if match:
                email = match.group(1).strip()
                self.logger.debug(f"Extracted B4S email: {email}")
                return email
        
        # Fallback to base parser method
        return self._extract_email(content)
    
    def _extract_b4s_phone(self, content: str) -> Optional[str]:
        """
        Extract phone number from B4S email content.
        
        Args:
            content: Email content
            
        Returns:
            Phone number or None
        """
        # Try B4S specific patterns first
        for pattern in self.phone_patterns:
            match = re.search(pattern, content, re.IGNORECASE)
            if match:
                phone = match.group(1).strip()
                self.logger.debug(f"Extracted B4S phone: {phone}")
                return phone
        
        # Fallback to base parser method
        return self._extract_telephone(content)