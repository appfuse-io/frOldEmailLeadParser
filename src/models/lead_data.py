"""
Lead data models using Pydantic for validation and type safety.
"""
from datetime import datetime
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, EmailStr, validator, Field
import re


class ContactInfo(BaseModel):
    """Base contact information model with validation."""
    first_name: str = Field(..., min_length=1, max_length=100)
    last_name: str = Field(..., min_length=1, max_length=100)
    email: EmailStr
    telephone: Optional[str] = Field(None, max_length=20)
    mobile: Optional[str] = Field(None, max_length=20)
    
    @validator('first_name', 'last_name')
    def validate_names(cls, v):
        """Validate and clean name fields."""
        if not v or not v.strip():
            raise ValueError('Name cannot be empty')
        # Clean and title case
        cleaned = re.sub(r'[^\w\s-]', '', v.strip())
        return cleaned.title()
    
    @validator('telephone', 'mobile')
    def validate_phone(cls, v):
        """Validate and normalize phone numbers."""
        if not v:
            return None
        # Remove all non-digit characters except +
        cleaned = re.sub(r'[^\d+]', '', v.strip())
        if len(cleaned) < 7:  # Minimum phone number length
            return None
        return cleaned


class LeadData(BaseModel):
    """Complete lead data model."""
    lead_source: str = Field(..., min_length=1)
    resale_reference: Optional[str] = Field(None, max_length=50)
    contact_info: ContactInfo
    receipt_date: datetime
    raw_email_content: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
    
    @validator('lead_source')
    def validate_lead_source(cls, v):
        """Validate lead source against known sources."""
        valid_sources = {
            'rightbiz', 'daltons', 'homecare', 'b4s', 
            'businesses for sale', 'nda', 'registerinterest'
        }
        if v.lower() not in valid_sources:
            raise ValueError(f'Invalid lead source: {v}')
        return v.lower()


class ParsedEmail(BaseModel):
    """Parsed email data structure."""
    subject: Optional[str] = None
    sender: Optional[str] = None
    recipient: Optional[str] = None
    date: Optional[datetime] = None
    text_content: List[str] = Field(default_factory=list)
    html_content: Optional[str] = None
    attachments: List[Dict[str, Any]] = Field(default_factory=list)


class ProcessingResult(BaseModel):
    """Result of email processing."""
    success: bool
    lead_data: Optional[LeadData] = None
    error_message: Optional[str] = None
    processing_time_ms: Optional[int] = None
    parser_used: Optional[str] = None