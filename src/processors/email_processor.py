"""
Main email processing engine that orchestrates the entire email → lead conversion process.
"""
import time
from typing import Optional, Dict, Any
from datetime import datetime
import mailparser

from ..models.lead_data import ParsedEmail, ProcessingResult, LeadData
from ..parsers import get_parser_registry
from ..utils.logger import get_logger
from ..utils.exceptions import (
    EmailProcessingError, 
    LeadParsingError, 
    ValidationError,
    ErrorCode,
    handle_exception
)
from ..utils.validators import validate_and_normalize_lead, is_valid_email_content
from ..utils.metrics import get_email_parser_metrics
from .lead_enricher import LeadEnricher

logger = get_logger(__name__)


class EmailProcessor:
    """
    Main email processing engine that coordinates all steps of email → lead conversion.
    """
    
    def __init__(self):
        self.parser_registry = get_parser_registry()
        self.lead_enricher = LeadEnricher()
        self.metrics = get_email_parser_metrics()
        self.logger = get_logger(__name__)
    
    def process_email_from_bytes(
        self, 
        email_bytes: bytes, 
        email_key: str,
        correlation_id: Optional[str] = None
    ) -> ProcessingResult:
        """
        Process email from raw bytes.
        
        Args:
            email_bytes: Raw email bytes
            email_key: S3 object key or identifier
            correlation_id: Optional correlation ID for tracking
            
        Returns:
            Processing result with lead data or error information
        """
        start_time = time.time()
        
        if correlation_id:
            self.logger.set_correlation_id(correlation_id)
        
        try:
            with self.logger.operation_context("process_email", email_key=email_key):
                # Parse raw email
                parsed_email = self._parse_raw_email(email_bytes, email_key)
                
                # Process the parsed email
                result = self.process_parsed_email(parsed_email, email_key)
                
                # Record success metrics
                if result.success and result.lead_data:
                    if self.metrics:
                        self.metrics.record_email_processed(
                            result.lead_data.lead_source, 
                            success=True
                        )
                
                return result
                
        except Exception as e:
            processing_time_ms = int((time.time() - start_time) * 1000)
            
            # Handle and log the error
            structured_error = handle_exception(e, context={'email_key': email_key})
            
            self.logger.error(
                "Email processing failed",
                error=structured_error,
                email_key=email_key,
                processing_time_ms=processing_time_ms
            )
            
            # Record failure metrics
            if self.metrics:
                self.metrics.record_email_processed("unknown", success=False)
            
            return ProcessingResult(
                success=False,
                error_message=str(structured_error),
                processing_time_ms=processing_time_ms
            )
    
    def process_parsed_email(
        self, 
        parsed_email: ParsedEmail, 
        email_key: str
    ) -> ProcessingResult:
        """
        Process an already parsed email.
        
        Args:
            parsed_email: Parsed email data
            email_key: Email identifier
            
        Returns:
            Processing result
        """
        start_time = time.time()
        
        try:
            with self.logger.operation_context("process_parsed_email", email_key=email_key):
                
                # Validate email content
                self._validate_email_content(parsed_email)
                
                # Detect lead source and get parser
                lead_source, parser = self.parser_registry.detect_and_get_parser(parsed_email)
                
                if not parser:
                    raise LeadParsingError(
                        message=f"No parser available for lead source: {lead_source}",
                        error_code=ErrorCode.LEAD_SOURCE_UNKNOWN,
                        lead_source=lead_source
                    )
                
                # Parse email into lead data
                lead_data = parser.parse(parsed_email)
                
                # Validate and normalize the parsed data
                validated_data = validate_and_normalize_lead(lead_data.dict())
                
                # Create validated lead data object
                validated_lead_data = LeadData(**validated_data)
                
                # Enrich the lead data
                enriched_lead_data = self.lead_enricher.enrich_lead(validated_lead_data)
                
                processing_time_ms = int((time.time() - start_time) * 1000)
                
                # Record parsing time metric
                if self.metrics:
                    self.metrics.record_parsing_time(lead_source, processing_time_ms)
                
                self.logger.info(
                    "Successfully processed email",
                    lead_source=lead_source,
                    email=enriched_lead_data.contact_info.email,
                    reference=enriched_lead_data.resale_reference,
                    processing_time_ms=processing_time_ms
                )
                
                return ProcessingResult(
                    success=True,
                    lead_data=enriched_lead_data,
                    processing_time_ms=processing_time_ms,
                    parser_used=parser.__class__.__name__
                )
                
        except ValidationError as e:
            processing_time_ms = int((time.time() - start_time) * 1000)
            
            self.logger.warning(
                "Email validation failed",
                error=e,
                email_key=email_key,
                field_errors=e.details.get('field_errors', {})
            )
            
            # Record validation error metric
            if self.metrics:
                self.metrics.record_validation_error(
                    lead_source if 'lead_source' in locals() else "unknown",
                    e.error_code.value
                )
            
            return ProcessingResult(
                success=False,
                error_message=f"Validation failed: {e.message}",
                processing_time_ms=processing_time_ms
            )
            
        except LeadParsingError as e:
            processing_time_ms = int((time.time() - start_time) * 1000)
            
            self.logger.error(
                "Lead parsing failed",
                error=e,
                email_key=email_key,
                lead_source=e.details.get('lead_source', 'unknown')
            )
            
            return ProcessingResult(
                success=False,
                error_message=f"Parsing failed: {e.message}",
                processing_time_ms=processing_time_ms
            )
            
        except Exception as e:
            processing_time_ms = int((time.time() - start_time) * 1000)
            
            structured_error = handle_exception(e, context={'email_key': email_key})
            
            self.logger.error(
                "Unexpected error processing email",
                error=structured_error,
                email_key=email_key,
                processing_time_ms=processing_time_ms
            )
            
            return ProcessingResult(
                success=False,
                error_message=str(structured_error),
                processing_time_ms=processing_time_ms
            )
    
    def _parse_raw_email(self, email_bytes: bytes, email_key: str) -> ParsedEmail:
        """
        Parse raw email bytes into structured data.
        
        Args:
            email_bytes: Raw email bytes
            email_key: Email identifier
            
        Returns:
            Parsed email data
            
        Raises:
            EmailProcessingError: If email parsing fails
        """
        try:
            # Parse email using mailparser
            mail = mailparser.parse_from_bytes(email_bytes)
            
            # Extract text content
            text_content = []
            if mail.text_plain:
                if isinstance(mail.text_plain, list):
                    text_content.extend(mail.text_plain)
                else:
                    text_content.append(mail.text_plain)
            
            # Create parsed email object
            parsed_email = ParsedEmail(
                subject=mail.subject,
                sender=mail.from_,
                recipient=mail.to,
                date=mail.date,
                text_content=text_content,
                html_content=mail.text_html,
                attachments=mail.attachments or []
            )
            
            self.logger.debug(
                "Successfully parsed raw email",
                email_key=email_key,
                subject=parsed_email.subject,
                sender=parsed_email.sender,
                text_content_parts=len(parsed_email.text_content)
            )
            
            return parsed_email
            
        except Exception as e:
            raise EmailProcessingError(
                message=f"Failed to parse email: {str(e)}",
                error_code=ErrorCode.EMAIL_PARSE_FAILED,
                email_key=email_key,
                cause=e
            )
    
    def _validate_email_content(self, parsed_email: ParsedEmail):
        """
        Validate email content quality and size.
        
        Args:
            parsed_email: Parsed email data
            
        Raises:
            EmailProcessingError: If email content is invalid
        """
        # Combine all text content for validation
        combined_content = "\n".join(parsed_email.text_content)
        
        if not is_valid_email_content(combined_content):
            raise EmailProcessingError(
                message="Email content failed validation checks",
                error_code=ErrorCode.EMAIL_CORRUPTED
            )
        
        # Check for minimum content
        if len(combined_content.strip()) < 50:
            raise EmailProcessingError(
                message="Email content too short to process",
                error_code=ErrorCode.EMAIL_CORRUPTED
            )
        
        self.logger.debug(
            "Email content validation passed",
            content_length=len(combined_content),
            subject=parsed_email.subject
        )


# Global processor instance
_email_processor: Optional[EmailProcessor] = None


def get_email_processor() -> EmailProcessor:
    """
    Get the global email processor instance.
    
    Returns:
        EmailProcessor instance
    """
    global _email_processor
    if _email_processor is None:
        _email_processor = EmailProcessor()
    return _email_processor


def process_email_from_bytes(
    email_bytes: bytes, 
    email_key: str,
    correlation_id: Optional[str] = None
) -> ProcessingResult:
    """
    Convenience function to process email from bytes.
    
    Args:
        email_bytes: Raw email bytes
        email_key: Email identifier
        correlation_id: Optional correlation ID
        
    Returns:
        Processing result
    """
    processor = get_email_processor()
    return processor.process_email_from_bytes(email_bytes, email_key, correlation_id)