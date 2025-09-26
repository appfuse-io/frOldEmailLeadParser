"""
SQS service layer with retry logic and circuit breaker protection.
"""
import boto3
from botocore.exceptions import ClientError, NoCredentialsError
from typing import Optional, Dict, Any, List
import json
import uuid
import time

from ..models.config import get_config
from ..models.lead_data import LeadData
from ..utils.logger import get_logger
from ..utils.exceptions import AWSServiceError, ErrorCode, handle_exception
from ..utils.retry import retry, BackoffStrategy
from ..utils.metrics import get_email_parser_metrics

logger = get_logger(__name__)


class SQSService:
    """
    SQS service with robust error handling and monitoring.
    """
    
    def __init__(self, config=None):
        app_config = get_config()
        self.config = config or app_config.aws
        self.metrics = get_email_parser_metrics()
        self.logger = get_logger(__name__)
        
        # Initialize SQS client
        self._client = None
        self._initialize_client()
    
    def _initialize_client(self):
        """Initialize SQS client with configuration."""
        try:
            client_config = {
                'region_name': self.config.region_name
            }
            
            # Add credentials if provided
            if self.config.access_key_id and self.config.secret_access_key:
                client_config.update({
                    'aws_access_key_id': self.config.access_key_id,
                    'aws_secret_access_key': self.config.secret_access_key
                })
            
            self._client = boto3.client('sqs', **client_config)
            
            self.logger.info(
                "SQS client initialized successfully",
                region=self.config.region_name,
                queue_url=self.config.sqs_queue_url
            )
            
        except Exception as e:
            raise AWSServiceError(
                message=f"Failed to initialize SQS client: {str(e)}",
                error_code=ErrorCode.UNKNOWN_ERROR,
                service="SQS",
                operation="initialize_client",
                cause=e
            )
    
    @retry(
        max_attempts=3,
        backoff_strategy=BackoffStrategy.EXPONENTIAL_JITTER,
        retryable_exceptions=(ClientError,),
        non_retryable_exceptions=(NoCredentialsError,)
    )
    def send_lead_message(
        self, 
        lead_data: LeadData, 
        queue_url: Optional[str] = None,
        message_group_id: Optional[str] = None
    ) -> str:
        """
        Send lead data to SQS queue.
        
        Args:
            lead_data: Lead data to send
            queue_url: SQS queue URL (uses config default if not provided)
            message_group_id: Message group ID for FIFO queues
            
        Returns:
            Message ID
            
        Raises:
            AWSServiceError: If operation fails
        """
        queue_url = queue_url or self.config.sqs_queue_url
        
        try:
            start_time = time.time()
            
            # Convert lead data to message payload
            message_body = self._prepare_message_body(lead_data)
            
            # Prepare message parameters
            message_params = {
                'QueueUrl': queue_url,
                'MessageBody': message_body,
                'MessageAttributes': self._create_message_attributes(lead_data)
            }
            
            # Add FIFO queue specific parameters
            if queue_url.endswith('.fifo'):
                message_params['MessageGroupId'] = message_group_id or str(uuid.uuid4().hex)
                # Use lead data as deduplication ID to prevent duplicates
                dedup_id = self._generate_deduplication_id(lead_data)
                message_params['MessageDeduplicationId'] = dedup_id
            
            self.logger.debug(
                "Sending lead message to SQS",
                queue_url=queue_url,
                lead_source=lead_data.lead_source,
                reference=lead_data.resale_reference
            )
            
            response = self._client.send_message(**message_params)
            
            duration_ms = int((time.time() - start_time) * 1000)
            message_id = response.get('MessageId', '')
            
            # Record success metrics
            if self.metrics:
                self.metrics.record_sqs_message_sent(success=True)
            
            self.logger.info(
                "Successfully sent lead message to SQS",
                queue_url=queue_url,
                message_id=message_id,
                lead_source=lead_data.lead_source,
                reference=lead_data.resale_reference,
                duration_ms=duration_ms
            )
            
            return message_id
            
        except ClientError as e:
            error_code = e.response.get('Error', {}).get('Code', 'Unknown')
            
            # Record failure metrics
            if self.metrics:
                self.metrics.record_sqs_message_sent(success=False)
            
            raise AWSServiceError(
                message=f"Failed to send SQS message: {str(e)}",
                error_code=ErrorCode.SQS_SEND_FAILED,
                service="SQS",
                operation="send_message",
                cause=e
            )
        
        except Exception as e:
            # Record failure metrics
            if self.metrics:
                self.metrics.record_sqs_message_sent(success=False)
            
            structured_error = handle_exception(
                e, 
                context={
                    'queue_url': queue_url,
                    'lead_source': lead_data.lead_source
                }
            )
            raise structured_error
    
    def _prepare_message_body(self, lead_data: LeadData) -> str:
        """
        Prepare message body from lead data.
        
        Args:
            lead_data: Lead data to convert
            
        Returns:
            JSON string message body
        """
        try:
            # Convert to dictionary and ensure JSON serializable
            message_data = {
                'lead_source': lead_data.lead_source,
                'resale_reference': lead_data.resale_reference,
                'contact_info': {
                    'first_name': lead_data.contact_info.first_name,
                    'last_name': lead_data.contact_info.last_name,
                    'email': lead_data.contact_info.email,
                    'telephone': lead_data.contact_info.telephone,
                    'mobile': lead_data.contact_info.mobile,
                },
                'receipt_date': lead_data.receipt_date.isoformat() if lead_data.receipt_date else None,
                'metadata': lead_data.metadata or {}
            }
            
            return json.dumps(message_data, default=str)
            
        except Exception as e:
            raise AWSServiceError(
                message=f"Failed to prepare message body: {str(e)}",
                error_code=ErrorCode.UNKNOWN_ERROR,
                service="SQS",
                operation="prepare_message_body",
                cause=e
            )
    
    def _create_message_attributes(self, lead_data: LeadData) -> Dict[str, Dict[str, str]]:
        """
        Create SQS message attributes from lead data.
        
        Args:
            lead_data: Lead data
            
        Returns:
            Message attributes dictionary
        """
        attributes = {
            'LeadSource': {
                'StringValue': lead_data.lead_source,
                'DataType': 'String'
            }
        }
        
        if lead_data.resale_reference:
            attributes['ResaleReference'] = {
                'StringValue': lead_data.resale_reference,
                'DataType': 'String'
            }
        
        if lead_data.contact_info.email:
            attributes['ContactEmail'] = {
                'StringValue': lead_data.contact_info.email,
                'DataType': 'String'
            }
        
        # Add parser information if available
        parser_used = lead_data.metadata.get('parser_used')
        if parser_used:
            attributes['ParserUsed'] = {
                'StringValue': parser_used,
                'DataType': 'String'
            }
        
        return attributes
    
    def _generate_deduplication_id(self, lead_data: LeadData) -> str:
        """
        Generate deduplication ID for FIFO queues.
        
        Args:
            lead_data: Lead data
            
        Returns:
            Deduplication ID
        """
        # Create a unique ID based on lead content to prevent duplicates
        dedup_components = [
            lead_data.lead_source,
            lead_data.contact_info.email or '',
            lead_data.resale_reference or '',
            lead_data.receipt_date.isoformat() if lead_data.receipt_date else ''
        ]
        
        dedup_string = '|'.join(dedup_components)
        
        # Use hash of the string as deduplication ID (truncated to fit SQS limits)
        import hashlib
        dedup_hash = hashlib.sha256(dedup_string.encode()).hexdigest()
        
        return dedup_hash[:80]  # SQS deduplication ID max length is 128 chars
    
    @retry(
        max_attempts=3,
        backoff_strategy=BackoffStrategy.EXPONENTIAL_JITTER,
        retryable_exceptions=(ClientError,),
        non_retryable_exceptions=(NoCredentialsError,)
    )
    def send_batch_messages(
        self, 
        lead_data_list: List[LeadData], 
        queue_url: Optional[str] = None
    ) -> List[str]:
        """
        Send multiple lead messages in batch.
        
        Args:
            lead_data_list: List of lead data to send
            queue_url: SQS queue URL (uses config default if not provided)
            
        Returns:
            List of message IDs
            
        Raises:
            AWSServiceError: If operation fails
        """
        queue_url = queue_url or self.config.sqs_queue_url
        
        if not lead_data_list:
            return []
        
        # SQS batch limit is 10 messages
        batch_size = 10
        all_message_ids = []
        
        for i in range(0, len(lead_data_list), batch_size):
            batch = lead_data_list[i:i + batch_size]
            batch_message_ids = self._send_message_batch(batch, queue_url)
            all_message_ids.extend(batch_message_ids)
        
        return all_message_ids
    
    def _send_message_batch(self, lead_data_batch: List[LeadData], queue_url: str) -> List[str]:
        """
        Send a single batch of messages.
        
        Args:
            lead_data_batch: Batch of lead data (max 10 items)
            queue_url: SQS queue URL
            
        Returns:
            List of message IDs
        """
        try:
            start_time = time.time()
            
            # Prepare batch entries
            entries = []
            for idx, lead_data in enumerate(lead_data_batch):
                entry = {
                    'Id': str(idx),
                    'MessageBody': self._prepare_message_body(lead_data),
                    'MessageAttributes': self._create_message_attributes(lead_data)
                }
                
                # Add FIFO queue specific parameters
                if queue_url.endswith('.fifo'):
                    entry['MessageGroupId'] = str(uuid.uuid4().hex)
                    entry['MessageDeduplicationId'] = self._generate_deduplication_id(lead_data)
                
                entries.append(entry)
            
            self.logger.debug(
                "Sending batch messages to SQS",
                queue_url=queue_url,
                batch_size=len(entries)
            )
            
            response = self._client.send_message_batch(
                QueueUrl=queue_url,
                Entries=entries
            )
            
            duration_ms = int((time.time() - start_time) * 1000)
            
            # Extract message IDs from successful sends
            message_ids = []
            successful = response.get('Successful', [])
            failed = response.get('Failed', [])
            
            for success in successful:
                message_ids.append(success.get('MessageId', ''))
            
            # Log any failures
            if failed:
                self.logger.warning(
                    "Some messages in batch failed to send",
                    failed_count=len(failed),
                    failures=failed
                )
            
            # Record metrics
            if self.metrics:
                for _ in successful:
                    self.metrics.record_sqs_message_sent(success=True)
                for _ in failed:
                    self.metrics.record_sqs_message_sent(success=False)
            
            self.logger.info(
                "Batch messages sent to SQS",
                queue_url=queue_url,
                successful_count=len(successful),
                failed_count=len(failed),
                duration_ms=duration_ms
            )
            
            return message_ids
            
        except Exception as e:
            # Record failure metrics for entire batch
            if self.metrics:
                for _ in lead_data_batch:
                    self.metrics.record_sqs_message_sent(success=False)
            
            raise AWSServiceError(
                message=f"Failed to send batch messages: {str(e)}",
                error_code=ErrorCode.SQS_SEND_FAILED,
                service="SQS",
                operation="send_message_batch",
                cause=e
            )


# Global SQS service instance
_sqs_service: Optional[SQSService] = None


def get_sqs_service() -> SQSService:
    """
    Get the global SQS service instance.
    
    Returns:
        SQSService instance
    """
    global _sqs_service
    if _sqs_service is None:
        _sqs_service = SQSService()
    return _sqs_service