"""
CloudWatch metrics and monitoring utilities for the email parser system.
"""
import time
from datetime import datetime
from typing import Dict, Any, Optional, List
from contextlib import contextmanager
from dataclasses import dataclass, field
import boto3
from botocore.exceptions import ClientError

from .logger import get_logger
from .exceptions import AWSServiceError, ErrorCode

logger = get_logger(__name__)


@dataclass
class MetricData:
    """Container for metric data."""
    name: str
    value: float
    unit: str = "Count"
    dimensions: Dict[str, str] = field(default_factory=dict)
    timestamp: Optional[datetime] = None


class MetricsCollector:
    """
    CloudWatch metrics collector with batching and error handling.
    """
    
    def __init__(
        self,
        namespace: str = "FranchiseResales/EmailParser",
        region_name: str = "eu-west-2",
        batch_size: int = 20
    ):
        self.namespace = namespace
        self.batch_size = batch_size
        self._metrics_buffer: List[MetricData] = []
        
        try:
            self.cloudwatch = boto3.client('cloudwatch', region_name=region_name)
        except Exception as e:
            logger.warning(
                "Failed to initialize CloudWatch client, metrics will be logged only",
                error=str(e)
            )
            self.cloudwatch = None
    
    def put_metric(
        self,
        name: str,
        value: float,
        unit: str = "Count",
        dimensions: Optional[Dict[str, str]] = None,
        timestamp: Optional[datetime] = None
    ):
        """
        Add a metric to the buffer for batch sending.
        
        Args:
            name: Metric name
            value: Metric value
            unit: Metric unit (Count, Seconds, Bytes, etc.)
            dimensions: Metric dimensions for filtering
            timestamp: Metric timestamp (defaults to now)
        """
        metric = MetricData(
            name=name,
            value=value,
            unit=unit,
            dimensions=dimensions or {},
            timestamp=timestamp or datetime.utcnow()
        )
        
        self._metrics_buffer.append(metric)
        
        # Log the metric
        logger.debug(
            f"Metric recorded: {name}",
            metric_name=name,
            metric_value=value,
            metric_unit=unit,
            metric_dimensions=dimensions
        )
        
        # Send batch if buffer is full
        if len(self._metrics_buffer) >= self.batch_size:
            self.flush()
    
    def flush(self):
        """Send all buffered metrics to CloudWatch."""
        if not self._metrics_buffer:
            return
        
        if not self.cloudwatch:
            logger.warning(
                f"CloudWatch client not available, discarding {len(self._metrics_buffer)} metrics"
            )
            self._metrics_buffer.clear()
            return
        
        try:
            # Convert metrics to CloudWatch format
            metric_data = []
            for metric in self._metrics_buffer:
                data = {
                    'MetricName': metric.name,
                    'Value': metric.value,
                    'Unit': metric.unit,
                    'Timestamp': metric.timestamp
                }
                
                if metric.dimensions:
                    data['Dimensions'] = [
                        {'Name': k, 'Value': v}
                        for k, v in metric.dimensions.items()
                    ]
                
                metric_data.append(data)
            
            # Send to CloudWatch
            self.cloudwatch.put_metric_data(
                Namespace=self.namespace,
                MetricData=metric_data
            )
            
            logger.debug(
                f"Successfully sent {len(metric_data)} metrics to CloudWatch",
                namespace=self.namespace,
                metric_count=len(metric_data)
            )
            
        except ClientError as e:
            logger.error(
                "Failed to send metrics to CloudWatch",
                error=e,
                namespace=self.namespace,
                metric_count=len(self._metrics_buffer)
            )
            raise AWSServiceError(
                message=f"Failed to send metrics: {str(e)}",
                error_code=ErrorCode.UNKNOWN_ERROR,
                service="CloudWatch",
                operation="put_metric_data",
                cause=e
            )
        except Exception as e:
            logger.error(
                "Unexpected error sending metrics",
                error=e,
                namespace=self.namespace,
                metric_count=len(self._metrics_buffer)
            )
        finally:
            self._metrics_buffer.clear()
    
    @contextmanager
    def timer(
        self,
        metric_name: str,
        dimensions: Optional[Dict[str, str]] = None
    ):
        """
        Context manager for timing operations.
        
        Args:
            metric_name: Name of the timing metric
            dimensions: Additional dimensions for the metric
        """
        start_time = time.time()
        try:
            yield
        finally:
            duration = (time.time() - start_time) * 1000  # Convert to milliseconds
            self.put_metric(
                name=metric_name,
                value=duration,
                unit="Milliseconds",
                dimensions=dimensions
            )
    
    def increment_counter(
        self,
        metric_name: str,
        value: int = 1,
        dimensions: Optional[Dict[str, str]] = None
    ):
        """
        Increment a counter metric.
        
        Args:
            metric_name: Name of the counter metric
            value: Value to increment by (default: 1)
            dimensions: Additional dimensions for the metric
        """
        self.put_metric(
            name=metric_name,
            value=float(value),
            unit="Count",
            dimensions=dimensions
        )
    
    def record_gauge(
        self,
        metric_name: str,
        value: float,
        unit: str = "None",
        dimensions: Optional[Dict[str, str]] = None
    ):
        """
        Record a gauge metric (point-in-time value).
        
        Args:
            metric_name: Name of the gauge metric
            value: Current value
            unit: Unit of measurement
            dimensions: Additional dimensions for the metric
        """
        self.put_metric(
            name=metric_name,
            value=value,
            unit=unit,
            dimensions=dimensions
        )


class EmailParserMetrics:
    """
    High-level metrics interface for email parser operations.
    """
    
    def __init__(self, collector: MetricsCollector):
        self.collector = collector
    
    def record_email_processed(self, lead_source: str, success: bool):
        """Record email processing result."""
        status = "success" if success else "failure"
        
        self.collector.increment_counter(
            "EmailsProcessed",
            dimensions={
                "LeadSource": lead_source,
                "Status": status
            }
        )
    
    def record_parsing_time(self, lead_source: str, duration_ms: float):
        """Record parsing duration."""
        self.collector.put_metric(
            "ParsingDuration",
            value=duration_ms,
            unit="Milliseconds",
            dimensions={"LeadSource": lead_source}
        )
    
    def record_validation_error(self, lead_source: str, error_type: str):
        """Record validation error."""
        self.collector.increment_counter(
            "ValidationErrors",
            dimensions={
                "LeadSource": lead_source,
                "ErrorType": error_type
            }
        )
    
    def record_sqs_message_sent(self, success: bool):
        """Record SQS message sending result."""
        status = "success" if success else "failure"
        
        self.collector.increment_counter(
            "SQSMessagesSent",
            dimensions={"Status": status}
        )
    
    def record_s3_operation(self, operation: str, success: bool):
        """Record S3 operation result."""
        status = "success" if success else "failure"
        
        self.collector.increment_counter(
            "S3Operations",
            dimensions={
                "Operation": operation,
                "Status": status
            }
        )
    
    def record_lambda_invocation(self, duration_ms: float, memory_used_mb: float):
        """Record Lambda invocation metrics."""
        self.collector.put_metric(
            "LambdaDuration",
            value=duration_ms,
            unit="Milliseconds"
        )
        
        self.collector.put_metric(
            "LambdaMemoryUsed",
            value=memory_used_mb,
            unit="Megabytes"
        )


# Global metrics instance
_metrics_collector: Optional[MetricsCollector] = None
_email_parser_metrics: Optional[EmailParserMetrics] = None


def initialize_metrics(
    namespace: str = "FranchiseResales/EmailParser",
    region_name: str = "eu-west-2"
):
    """Initialize global metrics collector."""
    global _metrics_collector, _email_parser_metrics
    
    _metrics_collector = MetricsCollector(
        namespace=namespace,
        region_name=region_name
    )
    _email_parser_metrics = EmailParserMetrics(_metrics_collector)


def get_metrics_collector() -> Optional[MetricsCollector]:
    """Get the global metrics collector."""
    return _metrics_collector


def get_email_parser_metrics() -> Optional[EmailParserMetrics]:
    """Get the email parser metrics interface."""
    return _email_parser_metrics


def flush_metrics():
    """Flush all pending metrics."""
    if _metrics_collector:
        _metrics_collector.flush()