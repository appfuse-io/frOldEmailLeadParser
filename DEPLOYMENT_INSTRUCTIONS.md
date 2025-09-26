# Lambda Deployment Instructions

## Package Information
- **File**: lambda_function.zip
- **Size**: 648K
- **Runtime**: python3.13
- **Architecture**: x86_64

## Deployment Options

### Option 1: AWS CLI
```bash
# Create function (first time)
aws lambda create-function \
    --function-name email-lead-parser \
    --runtime python3.13 \
    --role arn:aws:iam::YOUR_ACCOUNT:role/lambda-execution-role \
    --handler lambda_function.lambda_handler \
    --zip-file fileb://lambda_function.zip \
    --timeout 300 \
    --memory-size 512 \
    --architecture x86_64

# Update function code (subsequent deployments)
aws lambda update-function-code \
    --function-name email-lead-parser \
    --zip-file fileb://lambda_function.zip
```

### Option 2: AWS Console
1. Go to AWS Lambda Console
2. Create new function or select existing function
3. Upload lambda_function.zip
4. Set handler to: lambda_function.lambda_handler
5. Set runtime to: python3.13
6. Set architecture to: x86_64

### Option 3: Terraform/CloudFormation
Use the lambda_function.zip in your infrastructure as code templates.

## Required Environment Variables
Make sure to set these environment variables in your Lambda function:
- `region_name`: AWS region (default: eu-west-2)
- `aws_s3_bucket`: S3 bucket name (default: adminify-fr)
- `queue_url_franchise_resales_lead_create_or_update`: SQS queue URL

## Required IAM Permissions
Your Lambda execution role needs:
- S3: GetObject, ListObjects, DeleteObject
- SQS: SendMessage
- CloudWatch: CreateLogGroup, CreateLogStream, PutLogEvents
