"""
S3 service layer with retry logic and circuit breaker protection.
"""
import boto3
from botocore.exceptions import ClientError, NoCredentialsError
from typing import Optional, Dict, Any, List
import time

from ..models.config import get_config
from ..utils.logger import get_logger
from ..utils.exceptions import AWSServiceError, ErrorCode, handle_exception
from ..utils.retry import retry, BackoffStrategy
from ..utils.metrics import get_email_parser_metrics

logger = get_logger(__name__)


class S3Service:
    """
    S3 service with robust error handling and monitoring.
    """
    
    def __init__(self, config=None):
        app_config = get_config()
        self.config = config or app_config.aws
        self.metrics = get_email_parser_metrics()
        self.logger = get_logger(__name__)
        
        # Initialize S3 client
        self._client = None
        self._initialize_client()
    
    def _initialize_client(self):
        """Initialize S3 client with configuration."""
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
            
            self._client = boto3.client('s3', **client_config)
            
            self.logger.info(
                "S3 client initialized successfully",
                region=self.config.region_name,
                bucket=self.config.s3_bucket
            )
            
        except Exception as e:
            raise AWSServiceError(
                message=f"Failed to initialize S3 client: {str(e)}",
                error_code=ErrorCode.S3_ACCESS_DENIED,
                service="S3",
                operation="initialize_client",
                cause=e
            )
    
    @retry(
        max_attempts=3,
        backoff_strategy=BackoffStrategy.EXPONENTIAL_JITTER,
        retryable_exceptions=(ClientError,),
        non_retryable_exceptions=(NoCredentialsError,)
    )
    def get_object(self, key: str, bucket: Optional[str] = None) -> bytes:
        """
        Get object from S3.
        
        Args:
            key: S3 object key
            bucket: S3 bucket name (uses config default if not provided)
            
        Returns:
            Object content as bytes
            
        Raises:
            AWSServiceError: If operation fails
        """
        bucket_name = bucket or self.config.s3_bucket
        
        try:
            start_time = time.time()
            
            self.logger.debug(
                "Getting S3 object",
                bucket=bucket_name,
                key=key
            )
            
            response = self._client.get_object(Bucket=bucket_name, Key=key)
            content = response['Body'].read()
            
            duration_ms = int((time.time() - start_time) * 1000)
            
            # Record success metrics
            if self.metrics:
                self.metrics.record_s3_operation("get_object", success=True)
            
            self.logger.info(
                "Successfully retrieved S3 object",
                bucket=bucket_name,
                key=key,
                size_bytes=len(content),
                duration_ms=duration_ms
            )
            
            return content
            
        except ClientError as e:
            error_code = e.response.get('Error', {}).get('Code', 'Unknown')
            
            # Record failure metrics
            if self.metrics:
                self.metrics.record_s3_operation("get_object", success=False)
            
            if error_code == 'NoSuchKey':
                raise AWSServiceError(
                    message=f"S3 object not found: {key}",
                    error_code=ErrorCode.S3_OBJECT_NOT_FOUND,
                    service="S3",
                    operation="get_object",
                    cause=e
                )
            elif error_code == 'AccessDenied':
                raise AWSServiceError(
                    message=f"Access denied to S3 object: {key}",
                    error_code=ErrorCode.S3_ACCESS_DENIED,
                    service="S3",
                    operation="get_object",
                    cause=e
                )
            else:
                raise AWSServiceError(
                    message=f"Failed to get S3 object: {str(e)}",
                    error_code=ErrorCode.UNKNOWN_ERROR,
                    service="S3",
                    operation="get_object",
                    cause=e
                )
        
        except Exception as e:
            # Record failure metrics
            if self.metrics:
                self.metrics.record_s3_operation("get_object", success=False)
            
            structured_error = handle_exception(e, context={'bucket': bucket_name, 'key': key})
            raise structured_error
    
    @retry(
        max_attempts=3,
        backoff_strategy=BackoffStrategy.EXPONENTIAL_JITTER,
        retryable_exceptions=(ClientError,),
        non_retryable_exceptions=(NoCredentialsError,)
    )
    def delete_object(self, key: str, bucket: Optional[str] = None) -> bool:
        """
        Delete object from S3.
        
        Args:
            key: S3 object key
            bucket: S3 bucket name (uses config default if not provided)
            
        Returns:
            True if deletion was successful
            
        Raises:
            AWSServiceError: If operation fails
        """
        bucket_name = bucket or self.config.s3_bucket
        
        try:
            start_time = time.time()
            
            self.logger.debug(
                "Deleting S3 object",
                bucket=bucket_name,
                key=key
            )
            
            self._client.delete_object(Bucket=bucket_name, Key=key)
            
            duration_ms = int((time.time() - start_time) * 1000)
            
            # Record success metrics
            if self.metrics:
                self.metrics.record_s3_operation("delete_object", success=True)
            
            self.logger.info(
                "Successfully deleted S3 object",
                bucket=bucket_name,
                key=key,
                duration_ms=duration_ms
            )
            
            return True
            
        except ClientError as e:
            error_code = e.response.get('Error', {}).get('Code', 'Unknown')
            
            # Record failure metrics
            if self.metrics:
                self.metrics.record_s3_operation("delete_object", success=False)
            
            if error_code == 'AccessDenied':
                raise AWSServiceError(
                    message=f"Access denied to delete S3 object: {key}",
                    error_code=ErrorCode.S3_ACCESS_DENIED,
                    service="S3",
                    operation="delete_object",
                    cause=e
                )
            else:
                # For delete operations, we might want to be more lenient
                # (e.g., if object doesn't exist, that's still "success")
                if error_code == 'NoSuchKey':
                    self.logger.warning(
                        "Attempted to delete non-existent S3 object",
                        bucket=bucket_name,
                        key=key
                    )
                    return True
                
                raise AWSServiceError(
                    message=f"Failed to delete S3 object: {str(e)}",
                    error_code=ErrorCode.UNKNOWN_ERROR,
                    service="S3",
                    operation="delete_object",
                    cause=e
                )
        
        except Exception as e:
            # Record failure metrics
            if self.metrics:
                self.metrics.record_s3_operation("delete_object", success=False)
            
            structured_error = handle_exception(e, context={'bucket': bucket_name, 'key': key})
            raise structured_error
    
    def list_objects(self, prefix: str = "", bucket: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        List objects in S3 bucket.
        
        Args:
            prefix: Object key prefix to filter by
            bucket: S3 bucket name (uses config default if not provided)
            
        Returns:
            List of object metadata dictionaries
            
        Raises:
            AWSServiceError: If operation fails
        """
        bucket_name = bucket or self.config.s3_bucket
        
        try:
            start_time = time.time()
            
            self.logger.debug(
                "Listing S3 objects",
                bucket=bucket_name,
                prefix=prefix
            )
            
            kwargs = {'Bucket': bucket_name}
            if prefix:
                kwargs['Prefix'] = prefix
            
            response = self._client.list_objects_v2(**kwargs)
            
            objects = response.get('Contents', [])
            duration_ms = int((time.time() - start_time) * 1000)
            
            # Record success metrics
            if self.metrics:
                self.metrics.record_s3_operation("list_objects", success=True)
            
            self.logger.info(
                "Successfully listed S3 objects",
                bucket=bucket_name,
                prefix=prefix,
                object_count=len(objects),
                duration_ms=duration_ms
            )
            
            return objects
            
        except ClientError as e:
            # Record failure metrics
            if self.metrics:
                self.metrics.record_s3_operation("list_objects", success=False)
            
            raise AWSServiceError(
                message=f"Failed to list S3 objects: {str(e)}",
                error_code=ErrorCode.UNKNOWN_ERROR,
                service="S3",
                operation="list_objects",
                cause=e
            )
        
        except Exception as e:
            # Record failure metrics
            if self.metrics:
                self.metrics.record_s3_operation("list_objects", success=False)
            
            structured_error = handle_exception(e, context={'bucket': bucket_name, 'prefix': prefix})
            raise structured_error
    
    def object_exists(self, key: str, bucket: Optional[str] = None) -> bool:
        """
        Check if object exists in S3.
        
        Args:
            key: S3 object key
            bucket: S3 bucket name (uses config default if not provided)
            
        Returns:
            True if object exists
        """
        bucket_name = bucket or self.config.s3_bucket
        
        try:
            self._client.head_object(Bucket=bucket_name, Key=key)
            return True
        except ClientError as e:
            if e.response.get('Error', {}).get('Code') == 'NoSuchKey':
                return False
            # Re-raise other errors
            raise
    
    def get_object_metadata(self, key: str, bucket: Optional[str] = None) -> Dict[str, Any]:
        """
        Get object metadata from S3.
        
        Args:
            key: S3 object key
            bucket: S3 bucket name (uses config default if not provided)
            
        Returns:
            Object metadata dictionary
            
        Raises:
            AWSServiceError: If operation fails
        """
        bucket_name = bucket or self.config.s3_bucket
        
        try:
            response = self._client.head_object(Bucket=bucket_name, Key=key)
            
            return {
                'size': response.get('ContentLength', 0),
                'last_modified': response.get('LastModified'),
                'etag': response.get('ETag', '').strip('"'),
                'content_type': response.get('ContentType', ''),
                'metadata': response.get('Metadata', {})
            }
            
        except ClientError as e:
            error_code = e.response.get('Error', {}).get('Code', 'Unknown')
            
            if error_code == 'NoSuchKey':
                raise AWSServiceError(
                    message=f"S3 object not found: {key}",
                    error_code=ErrorCode.S3_OBJECT_NOT_FOUND,
                    service="S3",
                    operation="head_object",
                    cause=e
                )
            else:
                raise AWSServiceError(
                    message=f"Failed to get S3 object metadata: {str(e)}",
                    error_code=ErrorCode.UNKNOWN_ERROR,
                    service="S3",
                    operation="head_object",
                    cause=e
                )


# Global S3 service instance
_s3_service: Optional[S3Service] = None


def get_s3_service() -> S3Service:
    """
    Get the global S3 service instance.
    
    Returns:
        S3Service instance
    """
    global _s3_service
    if _s3_service is None:
        _s3_service = S3Service()
    return _s3_service