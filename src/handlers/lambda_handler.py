"""
Modern Lambda handler with event-driven processing and comprehensive error handling.
"""
import json
import uuid
from typing import Dict, Any, List, Optional
import time
from datetime import datetime

from ..models.config import get_config
from ..processors.email_processor import get_email_processor
from ..services.s3_service import get_s3_service
from ..services.sqs_service import get_sqs_service
from ..utils.logger import get_logger, LoggerFactory
from ..utils.metrics import initialize_metrics, get_email_parser_metrics, flush_metrics
from ..utils.exceptions import (
    BaseEmailParserException,
    EmailProcessingError,
    AWSServiceError,
    handle_exception,
    ErrorCode
)

# Initialize logger
logger = get_logger(__name__)


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Main Lambda handler for processing email leads.
    
    Supports both S3 event-driven processing and direct invocation.
    
    Args:
        event: Lambda event data
        context: Lambda context
        
    Returns:
        Response dictionary with processing results
    """
    # Generate correlation ID for request tracking
    correlation_id = str(uuid.uuid4())
    
    # Initialize systems
    start_time = time.time()
    
    try:
        # Initialize configuration and logging
        config = get_config()
        LoggerFactory.configure(
            level=config.logging.level,
            format_type=config.logging.format
        )
        
        # Set correlation ID for tracking
        logger.set_correlation_id(correlation_id)
        
        # Initialize metrics
        if config.monitoring.enable_custom_metrics:
            initialize_metrics(
                namespace=config.monitoring.metric_namespace,
                region_name=config.aws.region_name
            )
        
        with logger.operation_context("lambda_handler", correlation_id=correlation_id):
            
            logger.info(
                "Lambda handler started",
                correlation_id=correlation_id,
                event_type=_get_event_type(event),
                aws_request_id=getattr(context, 'aws_request_id', 'unknown')
            )
            
            # Determine processing mode based on event type
            if _is_s3_event(event):
                result = _process_s3_event(event, context, correlation_id)
            elif _is_direct_invocation(event):
                result = _process_direct_invocation(event, context, correlation_id)
            else:
                raise EmailProcessingError(
                    message=f"Unsupported event type: {_get_event_type(event)}",
                    error_code=ErrorCode.UNKNOWN_ERROR
                )
            
            # Record Lambda metrics
            duration_ms = int((time.time() - start_time) * 1000)
            memory_used_mb = _get_memory_usage(context)
            
            metrics = get_email_parser_metrics()
            if metrics:
                metrics.record_lambda_invocation(duration_ms, memory_used_mb)
            
            logger.info(
                "Lambda handler completed successfully",
                correlation_id=correlation_id,
                duration_ms=duration_ms,
                memory_used_mb=memory_used_mb,
                processed_count=result.get('processed_count', 0)
            )
            
            return result
            
    except BaseEmailParserException as e:
        duration_ms = int((time.time() - start_time) * 1000)
        
        logger.error(
            "Lambda handler failed with structured error",
            error=e,
            correlation_id=correlation_id,
            duration_ms=duration_ms
        )
        
        return {
            'statusCode': 500,
            'body': json.dumps({
                'error': e.error_code.value,
                'message': e.message,
                'correlation_id': correlation_id,
                'details': e.details
            })
        }
        
    except Exception as e:
        duration_ms = int((time.time() - start_time) * 1000)
        
        # Handle unexpected errors
        structured_error = handle_exception(e, context={'correlation_id': correlation_id})
        
        logger.error(
            "Lambda handler failed with unexpected error",
            error=structured_error,
            correlation_id=correlation_id,
            duration_ms=duration_ms
        )
        
        return {
            'statusCode': 500,
            'body': json.dumps({
                'error': 'UNEXPECTED_ERROR',
                'message': str(structured_error),
                'correlation_id': correlation_id
            })
        }
    
    finally:
        # Flush metrics before Lambda terminates
        try:
            flush_metrics()
        except Exception as e:
            logger.warning("Failed to flush metrics", error=e)


def _process_s3_event(event: Dict[str, Any], context: Any, correlation_id: str) -> Dict[str, Any]:
    """
    Process S3 event notifications (event-driven processing).
    
    Args:
        event: S3 event data
        context: Lambda context
        correlation_id: Request correlation ID
        
    Returns:
        Processing results
    """
    logger.info("Processing S3 event", record_count=len(event.get('Records', [])))
    
    email_processor = get_email_processor()
    s3_service = get_s3_service()
    sqs_service = get_sqs_service()
    
    processed_count = 0
    failed_count = 0
    results = []
    
    for record in event.get('Records', []):
        try:
            # Extract S3 information
            s3_info = record.get('s3', {})
            bucket_name = s3_info.get('bucket', {}).get('name', '')
            object_key = s3_info.get('object', {}).get('key', '')
            
            if not bucket_name or not object_key:
                logger.warning("Invalid S3 record, skipping", record=record)
                failed_count += 1
                continue
            
            logger.info(
                "Processing S3 object",
                bucket=bucket_name,
                key=object_key,
                correlation_id=correlation_id
            )
            
            # Get email content from S3
            email_bytes = s3_service.get_object(object_key, bucket_name)
            
            # Process email
            processing_result = email_processor.process_email_from_bytes(
                email_bytes=email_bytes,
                email_key=object_key,
                correlation_id=correlation_id
            )
            
            if processing_result.success and processing_result.lead_data:
                # Send to SQS
                message_id = sqs_service.send_lead_message(
                    lead_data=processing_result.lead_data,
                    message_group_id=correlation_id
                )
                
                # Delete processed email from S3
                s3_service.delete_object(object_key, bucket_name)
                
                processed_count += 1
                results.append({
                    'object_key': object_key,
                    'status': 'success',
                    'message_id': message_id,
                    'lead_source': processing_result.lead_data.lead_source,
                    'processing_time_ms': processing_result.processing_time_ms
                })
                
                logger.info(
                    "Successfully processed email",
                    object_key=object_key,
                    lead_source=processing_result.lead_data.lead_source,
                    message_id=message_id
                )
                
            else:
                failed_count += 1
                results.append({
                    'object_key': object_key,
                    'status': 'failed',
                    'error': processing_result.error_message,
                    'processing_time_ms': processing_result.processing_time_ms
                })
                
                logger.warning(
                    "Failed to process email",
                    object_key=object_key,
                    error=processing_result.error_message
                )
                
                # Still delete the failed email to prevent reprocessing
                # In production, you might want to move to a "failed" folder instead
                s3_service.delete_object(object_key, bucket_name)
                
        except Exception as e:
            failed_count += 1
            structured_error = handle_exception(e, context={'record': record})
            
            logger.error(
                "Failed to process S3 record",
                error=structured_error,
                record=record
            )
            
            results.append({
                'object_key': record.get('s3', {}).get('object', {}).get('key', 'unknown'),
                'status': 'error',
                'error': str(structured_error)
            })
    
    return {
        'statusCode': 200,
        'body': json.dumps({
            'message': 'S3 event processing completed',
            'correlation_id': correlation_id,
            'processed_count': processed_count,
            'failed_count': failed_count,
            'results': results
        })
    }


def _process_direct_invocation(event: Dict[str, Any], context: Any, correlation_id: str) -> Dict[str, Any]:
    """
    Process direct Lambda invocation (backward compatibility).
    
    Args:
        event: Direct invocation event data
        context: Lambda context
        correlation_id: Request correlation ID
        
    Returns:
        Processing results
    """
    logger.info("Processing direct invocation")
    
    # This provides backward compatibility with the old polling approach
    # You can implement batch processing here if needed
    
    return {
        'statusCode': 200,
        'body': json.dumps({
            'message': 'Direct invocation not yet implemented',
            'correlation_id': correlation_id
        })
    }


def _is_s3_event(event: Dict[str, Any]) -> bool:
    """Check if event is from S3."""
    records = event.get('Records', [])
    if not records:
        return False
    
    first_record = records[0]
    return first_record.get('eventSource') == 'aws:s3'


def _is_direct_invocation(event: Dict[str, Any]) -> bool:
    """Check if event is direct invocation."""
    return 'Records' not in event


def _get_event_type(event: Dict[str, Any]) -> str:
    """Get event type for logging."""
    if _is_s3_event(event):
        return 's3_event'
    elif _is_direct_invocation(event):
        return 'direct_invocation'
    else:
        return 'unknown'


def _get_memory_usage(context: Any) -> float:
    """
    Get memory usage from Lambda context.
    
    Args:
        context: Lambda context
        
    Returns:
        Memory usage in MB
    """
    try:
        memory_limit = getattr(context, 'memory_limit_in_mb', 0)
        # This is an approximation - actual memory usage tracking would require additional tools
        return float(memory_limit) * 0.5  # Assume 50% usage as estimate
    except:
        return 0.0