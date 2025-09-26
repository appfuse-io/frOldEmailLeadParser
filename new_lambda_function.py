"""
Compatibility wrapper for the new email parser system.
This allows you to test the new system alongside your existing lambda_function.py
"""

# Import the new system
from src.handlers.lambda_handler import lambda_handler as new_lambda_handler

def lambda_handler(event, context):
    """
    Wrapper function that calls the new system.
    
    To use this:
    1. Deploy this as a separate Lambda function
    2. Set environment variable: DRY_RUN_MODE=true
    3. Configure the same S3 bucket to trigger this Lambda
    4. Monitor logs to see the new system working without sending SQS messages
    """
    return new_lambda_handler(event, context)