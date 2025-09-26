"""
Smart lead source detection with multiple strategies.
"""
import re
from typing import Optional, Dict, List, Tuple
from dataclasses import dataclass

from ..models.lead_data import ParsedEmail
from ..utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class DetectionRule:
    """Rule for detecting lead sources."""
    lead_source: str
    priority: int  # Lower number = higher priority
    sender_domains: Optional[List[str]] = None
    sender_patterns: Optional[List[str]] = None
    subject_patterns: Optional[List[str]] = None
    content_patterns: Optional[List[str]] = None
    
    def __post_init__(self):
        self.sender_domains = self.sender_domains or []
        self.sender_patterns = self.sender_patterns or []
        self.subject_patterns = self.subject_patterns or []
        self.content_patterns = self.content_patterns or []


class LeadSourceDetector:
    """
    Intelligent lead source detection using multiple strategies.
    """
    
    def __init__(self):
        self.detection_rules = self._initialize_rules()
        self.logger = get_logger(__name__)
    
    def _initialize_rules(self) -> List[DetectionRule]:
        """Initialize detection rules for all known lead sources."""
        return [
            # RightBiz
            DetectionRule(
                lead_source="rightbiz",
                priority=1,
                sender_domains=["rightbiz.co.uk"],
                sender_patterns=[r".*@rightbiz\.co\.uk"],
                subject_patterns=[r"enquiry.*rightbiz", r"rightbiz.*enquiry"],
                content_patterns=[r"rightbiz\.co\.uk", r"Ref:\s*[A-Z0-9]+"]
            ),
            
            # Daltons
            DetectionRule(
                lead_source="daltons",
                priority=1,
                sender_domains=["daltonssupportmail.com"],
                sender_patterns=[r".*@daltonssupportmail\.com"],
                subject_patterns=[r"more details.*required", r"daltons.*enquiry"],
                content_patterns=[
                    r"daltonssupportmail\.com",
                    r"More Details are required for business with reference:",
                    r"Contact details:- Name :"
                ]
            ),
            
            # Homecare
            DetectionRule(
                lead_source="homecare",
                priority=1,
                sender_domains=["homecare.co.uk"],
                sender_patterns=[r".*@homecare\.co\.uk"],
                subject_patterns=[r"homecare.*enquiry", r"enquiry.*homecare"],
                content_patterns=[
                    r"homecare\.co\.uk",
                    r"Your Reference:\s*[A-Z0-9]+",
                    r"First Name:",
                    r"Last Name:"
                ]
            ),
            
            # BusinessesForSale (B4S)
            DetectionRule(
                lead_source="b4s",
                priority=1,
                sender_domains=["businessesforsale.com"],
                sender_patterns=[r".*@businessesforsale\.com"],
                subject_patterns=[
                    r"interested in your listing",
                    r"listing.*BFS\d+",
                    r"businessesforsale.*enquiry"
                ],
                content_patterns=[
                    r"BusinessesForSale\.com",
                    r"Your listing ref:\s*[A-Z0-9]+",
                    r"has received the following message:",
                    r"Reply directly to this email"
                ]
            ),
            
            # NDA Submissions
            DetectionRule(
                lead_source="nda",
                priority=2,
                subject_patterns=[r"NDA Submission", r"nda.*submission"],
                content_patterns=[r"NDA Submission", r"confidentiality agreement"]
            ),
            
            # Register Interest
            DetectionRule(
                lead_source="registerinterest",
                priority=3,
                subject_patterns=[r"register.*interest", r"mailing list"],
                content_patterns=[r"Register my interest", r"mailing list subscription"]
            )
        ]
    
    def detect_lead_source(self, email: ParsedEmail) -> str:
        """
        Detect lead source from email using multiple strategies.
        
        Args:
            email: Parsed email data
            
        Returns:
            Detected lead source or 'unknown'
        """
        content = self._get_combined_content(email)
        
        # Score each rule
        rule_scores = []
        for rule in self.detection_rules:
            score = self._score_rule(rule, email, content)
            if score > 0:
                rule_scores.append((rule, score))
                self.logger.debug(
                    f"Rule {rule.lead_source} scored {score}",
                    rule=rule.lead_source,
                    score=score
                )
        
        if not rule_scores:
            self.logger.warning("No matching rules found", sender=email.sender, subject=email.subject)
            return "unknown"
        
        # Sort by score (descending) then by priority (ascending)
        rule_scores.sort(key=lambda x: (-x[1], x[0].priority))
        
        best_rule, best_score = rule_scores[0]
        
        self.logger.info(
            f"Detected lead source: {best_rule.lead_source}",
            lead_source=best_rule.lead_source,
            score=best_score,
            sender=email.sender,
            subject=email.subject
        )
        
        return best_rule.lead_source
    
    def _score_rule(self, rule: DetectionRule, email: ParsedEmail, content: str) -> int:
        """
        Score a detection rule against an email.
        
        Args:
            rule: Detection rule to score
            email: Email to check
            content: Combined email content
            
        Returns:
            Score (higher is better match)
        """
        score = 0
        
        # Check sender domain (high weight)
        if email.sender and rule.sender_domains:
            sender_domain = self._extract_domain(email.sender)
            if sender_domain in rule.sender_domains:
                score += 10
                
            # Check sender patterns
            if rule.sender_patterns:
                for pattern in rule.sender_patterns:
                    if re.search(pattern, email.sender, re.IGNORECASE):
                        score += 8
        
        # Check subject patterns (medium weight)
        if email.subject and rule.subject_patterns:
            for pattern in rule.subject_patterns:
                if re.search(pattern, email.subject, re.IGNORECASE):
                    score += 5
        
        # Check content patterns (lower weight but multiple matches)
        if rule.content_patterns:
            for pattern in rule.content_patterns:
                matches = len(re.findall(pattern, content, re.IGNORECASE))
                score += matches * 2
        
        return score
    
    def _extract_domain(self, email_address: str) -> str:
        """
        Extract domain from email address.
        
        Args:
            email_address: Email address
            
        Returns:
            Domain part or empty string
        """
        if '@' in email_address:
            # Handle cases like "Name <email@domain.com>"
            email_match = re.search(r'([^<>\s]+@[^<>\s]+)', email_address)
            if email_match:
                return email_match.group(1).split('@')[1].lower()
        return ""
    
    def _get_combined_content(self, email: ParsedEmail) -> str:
        """
        Get combined email content for pattern matching.
        
        Args:
            email: Parsed email data
            
        Returns:
            Combined content string
        """
        content_parts = []
        
        if email.subject:
            content_parts.append(email.subject)
        
        if email.sender:
            content_parts.append(email.sender)
        
        if email.text_content:
            content_parts.extend(email.text_content)
        
        return "\n".join(content_parts)
    
    def get_confidence_score(self, email: ParsedEmail, lead_source: str) -> float:
        """
        Get confidence score for a specific lead source detection.
        
        Args:
            email: Parsed email data
            lead_source: Lead source to check
            
        Returns:
            Confidence score between 0.0 and 1.0
        """
        content = self._get_combined_content(email)
        
        # Find the rule for this lead source
        rule = next((r for r in self.detection_rules if r.lead_source == lead_source), None)
        if not rule:
            return 0.0
        
        score = self._score_rule(rule, email, content)
        
        # Normalize score to 0-1 range (max possible score is roughly 30)
        max_possible_score = 30
        confidence = min(score / max_possible_score, 1.0)
        
        return confidence
    
    def add_custom_rule(self, rule: DetectionRule):
        """
        Add a custom detection rule.
        
        Args:
            rule: Custom detection rule
        """
        self.detection_rules.append(rule)
        # Re-sort by priority
        self.detection_rules.sort(key=lambda r: r.priority)
        
        self.logger.info(f"Added custom rule for {rule.lead_source}", lead_source=rule.lead_source)