"""
Lead data enrichment and enhancement utilities.
"""
from typing import Dict, Any, Optional
from datetime import datetime
import re

from ..models.lead_data import LeadData
from ..utils.logger import get_logger

logger = get_logger(__name__)


class LeadEnricher:
    """
    Enriches lead data with additional metadata and cleaned information.
    """
    
    def __init__(self):
        self.logger = get_logger(__name__)
    
    def enrich_lead(self, lead_data: LeadData) -> LeadData:
        """
        Enrich lead data with additional metadata and processing.
        
        Args:
            lead_data: Original lead data
            
        Returns:
            Enriched lead data
        """
        try:
            # Create enriched metadata
            enriched_metadata = self._create_enriched_metadata(lead_data)
            
            # Add data quality scores
            quality_scores = self._calculate_quality_scores(lead_data)
            enriched_metadata.update(quality_scores)
            
            # Add processing timestamp
            enriched_metadata['enrichment_timestamp'] = datetime.utcnow().isoformat()
            
            # Create new lead data with enriched metadata
            enriched_lead_data = LeadData(
                lead_source=lead_data.lead_source,
                resale_reference=lead_data.resale_reference,
                contact_info=lead_data.contact_info,
                receipt_date=lead_data.receipt_date,
                raw_email_content=lead_data.raw_email_content,
                metadata={**lead_data.metadata, **enriched_metadata}
            )
            
            self.logger.debug(
                "Successfully enriched lead data",
                lead_source=lead_data.lead_source,
                reference=lead_data.resale_reference,
                enrichments_added=len(enriched_metadata)
            )
            
            return enriched_lead_data
            
        except Exception as e:
            self.logger.warning(
                "Failed to enrich lead data, returning original",
                error=e,
                lead_source=lead_data.lead_source
            )
            return lead_data
    
    def _create_enriched_metadata(self, lead_data: LeadData) -> Dict[str, Any]:
        """
        Create enriched metadata for the lead.
        
        Args:
            lead_data: Lead data to enrich
            
        Returns:
            Dictionary of enriched metadata
        """
        metadata = {}
        
        # Add contact completeness information
        contact_fields = {
            'has_first_name': bool(lead_data.contact_info.first_name),
            'has_last_name': bool(lead_data.contact_info.last_name),
            'has_email': bool(lead_data.contact_info.email),
            'has_telephone': bool(lead_data.contact_info.telephone),
            'has_mobile': bool(lead_data.contact_info.mobile),
        }
        metadata.update(contact_fields)
        
        # Calculate contact completeness score
        total_fields = len(contact_fields)
        filled_fields = sum(contact_fields.values())
        metadata['contact_completeness_score'] = filled_fields / total_fields
        
        # Add reference information
        metadata['has_reference'] = bool(lead_data.resale_reference)
        
        # Extract additional info from raw content if available
        if lead_data.raw_email_content:
            content_metadata = self._extract_content_metadata(lead_data.raw_email_content)
            metadata.update(content_metadata)
        
        # Add lead source specific enrichments
        source_metadata = self._get_source_specific_metadata(lead_data)
        metadata.update(source_metadata)
        
        return metadata
    
    def _calculate_quality_scores(self, lead_data: LeadData) -> Dict[str, float]:
        """
        Calculate data quality scores for the lead.
        
        Args:
            lead_data: Lead data to score
            
        Returns:
            Dictionary of quality scores
        """
        scores = {}
        
        # Email quality score
        email = lead_data.contact_info.email
        if email:
            email_score = 1.0
            # Deduct for suspicious patterns
            if re.search(r'test|example|dummy', email, re.IGNORECASE):
                email_score -= 0.3
            if not re.search(r'\.[a-z]{2,}$', email):  # Valid TLD
                email_score -= 0.2
            scores['email_quality_score'] = max(0.0, email_score)
        else:
            scores['email_quality_score'] = 0.0
        
        # Name quality score
        first_name = lead_data.contact_info.first_name
        last_name = lead_data.contact_info.last_name
        
        name_score = 0.0
        if first_name:
            name_score += 0.5
            # Check for realistic name patterns
            if re.match(r'^[A-Za-z\s\-\'\.]+$', first_name):
                name_score += 0.2
        
        if last_name:
            name_score += 0.3
            if re.match(r'^[A-Za-z\s\-\'\.]+$', last_name):
                name_score += 0.2
        
        scores['name_quality_score'] = min(1.0, name_score)
        
        # Phone quality score
        phone = lead_data.contact_info.telephone or lead_data.contact_info.mobile
        if phone:
            phone_score = 1.0
            # Check for valid phone patterns
            if not re.search(r'[\d\+\-\s\(\)]{7,}', phone):
                phone_score -= 0.5
            scores['phone_quality_score'] = phone_score
        else:
            scores['phone_quality_score'] = 0.0
        
        # Overall quality score
        scores['overall_quality_score'] = (
            scores['email_quality_score'] * 0.4 +
            scores['name_quality_score'] * 0.3 +
            scores['phone_quality_score'] * 0.3
        )
        
        return scores
    
    def _extract_content_metadata(self, content: str) -> Dict[str, Any]:
        """
        Extract metadata from raw email content.
        
        Args:
            content: Raw email content
            
        Returns:
            Dictionary of content metadata
        """
        metadata = {}
        
        # Content length and structure
        metadata['content_length'] = len(content)
        metadata['line_count'] = len(content.splitlines())
        
        # Check for common patterns
        patterns = {
            'has_url': bool(re.search(r'https?://[^\s]+', content)),
            'has_address': bool(re.search(r'(?:address|street|road|avenue)', content, re.IGNORECASE)),
            'has_postcode': bool(re.search(r'[A-Z]{1,2}\d{1,2}\s?\d[A-Z]{2}', content)),
            'has_company_info': bool(re.search(r'(?:company|ltd|limited|inc)', content, re.IGNORECASE)),
        }
        metadata.update(patterns)
        
        # Extract mentioned locations
        uk_cities = ['london', 'manchester', 'birmingham', 'leeds', 'glasgow', 'liverpool', 
                    'bristol', 'sheffield', 'edinburgh', 'leicester', 'coventry', 'bradford',
                    'cardiff', 'belfast', 'nottingham', 'kingston', 'plymouth', 'stoke',
                    'wolverhampton', 'derby', 'swansea', 'southampton', 'salford', 'aberdeen',
                    'westminster', 'reading', 'luton', 'york', 'stockport', 'brighton',
                    'oxford', 'cambridge', 'bath', 'bedford', 'stevenage', 'st. albans']
        
        mentioned_cities = []
        for city in uk_cities:
            if re.search(rf'\b{re.escape(city)}\b', content, re.IGNORECASE):
                mentioned_cities.append(city.title())
        
        if mentioned_cities:
            metadata['mentioned_locations'] = mentioned_cities
        
        return metadata
    
    def _get_source_specific_metadata(self, lead_data: LeadData) -> Dict[str, Any]:
        """
        Get lead source specific metadata.
        
        Args:
            lead_data: Lead data
            
        Returns:
            Source-specific metadata
        """
        metadata = {}
        source = lead_data.lead_source.lower()
        
        if source == 'b4s':
            metadata['source_display_name'] = 'BusinessesForSale.com'
            metadata['source_category'] = 'business_marketplace'
            
        elif source == 'rightbiz':
            metadata['source_display_name'] = 'RightBiz'
            metadata['source_category'] = 'business_marketplace'
            
        elif source == 'daltons':
            metadata['source_display_name'] = 'Daltons Business'
            metadata['source_category'] = 'business_broker'
            
        elif source == 'homecare':
            metadata['source_display_name'] = 'Homecare.co.uk'
            metadata['source_category'] = 'franchise_portal'
            
        elif source == 'nda':
            metadata['source_display_name'] = 'NDA Submission'
            metadata['source_category'] = 'direct_inquiry'
            
        else:
            metadata['source_display_name'] = source.title()
            metadata['source_category'] = 'unknown'
        
        return metadata