#!/bin/bash

# AWS Lambda Deployment Script
# This script creates a deployment package for AWS Lambda with proper binary dependencies

set -e  # Exit on any error

# Configuration
FUNCTION_NAME="email-lead-parser"
PYTHON_VERSION="3.13"
LAMBDA_RUNTIME="python3.13"
ARCHITECTURE="x86_64"  # Lambda architecture
BUILD_DIR="lambda_build"
ZIP_FILE="lambda_function.zip"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}Starting AWS Lambda deployment package creation...${NC}"

# Clean up previous builds
if [ -d "$BUILD_DIR" ]; then
    echo -e "${YELLOW}Cleaning up previous build directory...${NC}"
    rm -rf "$BUILD_DIR"
fi

if [ -f "$ZIP_FILE" ]; then
    echo -e "${YELLOW}Removing existing zip file...${NC}"
    rm -f "$ZIP_FILE"
fi

# Create build directory
echo -e "${GREEN}Creating build directory...${NC}"
mkdir -p "$BUILD_DIR"

# Create production requirements file (excluding dev dependencies and AWS SDK)
echo -e "${GREEN}Creating production requirements file...${NC}"
cat > requirements_prod.txt << EOF
# Core dependencies for Lambda (boto3/botocore excluded - provided by AWS runtime)
pydantic>=1.10.0
mail-parser>=1.4.0
email-validator>=1.3.0
EOF

# Install dependencies with Lambda-compatible architecture
echo -e "${GREEN}Installing dependencies for Lambda architecture...${NC}"
pip install \
    --target "$BUILD_DIR" \
    --platform linux_x86_64 \
    --implementation cp \
    --python-version "$PYTHON_VERSION" \
    --only-binary=:all: \
    --upgrade \
    -r requirements_prod.txt

# Handle any packages that might need special treatment
echo -e "${GREEN}Checking for binary dependencies...${NC}"

# Some packages might have native extensions that need special handling
# mailparser might have dependencies that need to be handled carefully
if [ -d "$BUILD_DIR/mailparser" ]; then
    echo -e "${GREEN}Found mailparser - ensuring compatibility...${NC}"
fi

# Copy application code
echo -e "${GREEN}Copying application code...${NC}"
cp lambda_function.py "$BUILD_DIR/"

# Copy the entire src directory structure
if [ -d "src" ]; then
    echo -e "${GREEN}Copying src directory structure...${NC}"
    cp -r src "$BUILD_DIR/"
else
    echo -e "${RED}Warning: src directory not found!${NC}"
fi

# Copy legacy leadParser.py if it exists (for backward compatibility)
if [ -f "leadParser.py" ]; then
    cp leadParser.py "$BUILD_DIR/"
fi

# Remove unnecessary files to reduce package size
echo -e "${GREEN}Optimizing package size...${NC}"
find "$BUILD_DIR" -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
find "$BUILD_DIR" -type d -name "*.dist-info" -exec rm -rf {} + 2>/dev/null || true
find "$BUILD_DIR" -type d -name "tests" -exec rm -rf {} + 2>/dev/null || true
find "$BUILD_DIR" -type f -name "*.pyc" -delete 2>/dev/null || true
find "$BUILD_DIR" -type f -name "*.pyo" -delete 2>/dev/null || true
find "$BUILD_DIR" -type f -name "*.so" -exec strip {} \; 2>/dev/null || true

# Remove development and testing files
rm -rf "$BUILD_DIR"/*/tests/ 2>/dev/null || true
rm -rf "$BUILD_DIR"/pytest* 2>/dev/null || true
rm -rf "$BUILD_DIR"/black* 2>/dev/null || true
rm -rf "$BUILD_DIR"/mypy* 2>/dev/null || true

# Create the deployment package
echo -e "${GREEN}Creating deployment package...${NC}"
cd "$BUILD_DIR"
zip -r "../$ZIP_FILE" . -q

cd ..

# Get package size
PACKAGE_SIZE=$(du -h "$ZIP_FILE" | cut -f1)
echo -e "${GREEN}Deployment package created: $ZIP_FILE (${PACKAGE_SIZE})${NC}"

# Verify package contents
echo -e "${GREEN}Verifying package contents...${NC}"
echo "Main files in package:"
unzip -l "$ZIP_FILE" | grep -E "(lambda_function\.py|src/|mailparser|pydantic)" | head -15

# Check if package is within Lambda limits
PACKAGE_SIZE_BYTES=$(stat -f%z "$ZIP_FILE" 2>/dev/null || stat -c%s "$ZIP_FILE" 2>/dev/null)
LAMBDA_LIMIT=52428800  # 50MB limit for direct upload

if [ "$PACKAGE_SIZE_BYTES" -gt "$LAMBDA_LIMIT" ]; then
    echo -e "${RED}Warning: Package size ($PACKAGE_SIZE) exceeds Lambda direct upload limit (50MB)${NC}"
    echo -e "${YELLOW}You'll need to upload via S3 or reduce package size${NC}"
else
    echo -e "${GREEN}Package size is within Lambda direct upload limits${NC}"
fi

# Create deployment instructions
cat > DEPLOYMENT_INSTRUCTIONS.md << EOF
# Lambda Deployment Instructions

## Package Information
- **File**: $ZIP_FILE
- **Size**: $PACKAGE_SIZE
- **Runtime**: $LAMBDA_RUNTIME
- **Architecture**: $ARCHITECTURE

## Deployment Options

### Option 1: AWS CLI
\`\`\`bash
# Create function (first time)
aws lambda create-function \\
    --function-name $FUNCTION_NAME \\
    --runtime $LAMBDA_RUNTIME \\
    --role arn:aws:iam::YOUR_ACCOUNT:role/lambda-execution-role \\
    --handler lambda_function.lambda_handler \\
    --zip-file fileb://$ZIP_FILE \\
    --timeout 300 \\
    --memory-size 512 \\
    --architecture $ARCHITECTURE

# Update function code (subsequent deployments)
aws lambda update-function-code \\
    --function-name $FUNCTION_NAME \\
    --zip-file fileb://$ZIP_FILE
\`\`\`

### Option 2: AWS Console
1. Go to AWS Lambda Console
2. Create new function or select existing function
3. Upload $ZIP_FILE
4. Set handler to: lambda_function.lambda_handler
5. Set runtime to: $LAMBDA_RUNTIME
6. Set architecture to: $ARCHITECTURE

### Option 3: Terraform/CloudFormation
Use the $ZIP_FILE in your infrastructure as code templates.

## Required Environment Variables
Make sure to set these environment variables in your Lambda function:
- \`region_name\`: AWS region (default: eu-west-2)
- \`aws_s3_bucket\`: S3 bucket name (default: adminify-fr)
- \`queue_url_franchise_resales_lead_create_or_update\`: SQS queue URL

## Required IAM Permissions
Your Lambda execution role needs:
- S3: GetObject, ListObjects, DeleteObject
- SQS: SendMessage
- CloudWatch: CreateLogGroup, CreateLogStream, PutLogEvents
EOF

echo -e "${GREEN}Deployment instructions created: DEPLOYMENT_INSTRUCTIONS.md${NC}"

# Clean up build directory
echo -e "${GREEN}Cleaning up build directory...${NC}"
rm -rf "$BUILD_DIR"

echo -e "${GREEN}✅ Deployment package ready!${NC}"
echo -e "${GREEN}📦 Package: $ZIP_FILE${NC}"
echo -e "${GREEN}📄 Instructions: DEPLOYMENT_INSTRUCTIONS.md${NC}"