# Deployment Guide - Testing New System Alongside Existing

## 🎯 **Safe Testing Strategy**

This guide shows you how to test the new email parser system alongside your existing one without causing duplicate SQS messages.

## 📋 **Prerequisites**

1. Your existing `lambda_function.py` continues to work as normal
2. New system will run in **DRY-RUN mode** (logs only, no SQS messages)
3. Both systems can process the same emails safely

## 🚀 **Step 1: Deploy New System**

### **1.1 Create New Lambda Function**
```bash
# Create a new Lambda function called "email-parser-new" or similar
# Use the provided new_lambda_function.py as the entry point
```

### **1.2 Upload Code**
Package and upload these files to your new Lambda:
```
new_lambda_function.py          # Entry point
src/                           # All the new system code
requirements.txt               # Dependencies
```

### **1.3 Set Environment Variables**
Configure these environment variables in your new Lambda:

**Required:**
```
DRY_RUN_MODE=true                    # 🔑 This prevents SQS messages!
AWS_S3_BUCKET=adminify-fr
SQS_QUEUE_URL=https://sqs.eu-west-2.amazonaws.com/420219040634/franchiseResalesFreshsalesLeadCreateOrUpdate.fifo
```

**Optional:**
```
LOG_LEVEL=INFO
ENVIRONMENT=testing
ENABLE_CUSTOM_METRICS=false          # Disable metrics during testing
```

## 🔧 **Step 2: Configure S3 Event Notifications**

### **Option A: Separate S3 Prefix (Recommended)**
1. Create a test folder in your S3 bucket: `test-emails/`
2. Configure S3 to trigger your new Lambda for `test-emails/` prefix
3. Copy some existing emails to `test-emails/` folder
4. Monitor new Lambda logs

### **Option B: Dual Triggers (Advanced)**
1. Configure S3 to trigger BOTH Lambda functions
2. Your existing Lambda processes normally
3. New Lambda runs in dry-run mode (logs only)
4. Compare results in CloudWatch logs

## 📊 **Step 3: Test with Your Email Examples**

### **Test Email 1: BusinessesForSale.com**
Upload an email like:
```
Subject: Dildo Baggins is interested in your listing BFS125
Content: Your listing ref:BFS125 ... Name: Dildo Baggins ... Email: jrshorton.wow@live.co.uk
```

**Expected Log Output:**
```json
{
  "message": "DRY-RUN: Would send lead message to SQS",
  "lead_source": "b4s",
  "reference": "BFS125",
  "first_name": "Dildo",
  "last_name": "Baggins",
  "email": "jrshorton.wow@live.co.uk",
  "message_body": "{...full lead data...}",
  "dry_run": true
}
```

### **Test Email 2: Daltons**
Upload a Daltons email and verify it extracts:
- Reference: "DAL137"
- Name: "Bilbo Daggins"
- Email and phone correctly

### **Test Email 3: RightBiz**
Upload a RightBiz email and verify it extracts:
- Reference: "RB150"
- Name: "Sandeep Shah"
- Both telephone and mobile fields

## 🔍 **Step 4: Compare Results**

### **Check CloudWatch Logs**
1. **Old System Logs**: Look for your existing Lambda's logs
2. **New System Logs**: Look for structured JSON logs with correlation IDs

### **Verify Data Quality**
The new system should show:
- ✅ Better data extraction (handles edge cases)
- ✅ Data validation and normalization
- ✅ Quality scores and enrichment
- ✅ Structured error handling

### **Performance Comparison**
- **Old**: Processes all emails in batch
- **New**: Processes individual emails with detailed timing

## ⚡ **Step 5: Switch to Production**

Once you're confident the new system works correctly:

### **5.1 Update Environment Variables**
```
DRY_RUN_MODE=false               # 🔑 Enable real SQS sending
ENVIRONMENT=production
ENABLE_CUSTOM_METRICS=true
```

### **5.2 Switch S3 Triggers**
1. Remove S3 trigger from old Lambda
2. Configure S3 to trigger new Lambda for all emails
3. Keep old Lambda as backup (don't delete yet)

### **5.3 Monitor Production**
- Watch CloudWatch logs for any issues
- Monitor SQS queue for proper message delivery
- Check Freshsales for lead creation

## 🛡️ **Rollback Plan**

If anything goes wrong:
1. Set `DRY_RUN_MODE=true` on new Lambda (stops SQS messages)
2. Re-enable S3 trigger on old Lambda
3. Investigate issues in new system logs

## 📈 **Benefits You'll See**

### **Immediate Improvements:**
- ✅ **Zero crashes** - Robust error handling
- ✅ **Better data quality** - Validation and normalization
- ✅ **Detailed logging** - Easy debugging with correlation IDs
- ✅ **Performance monitoring** - Timing and success metrics

### **Long-term Benefits:**
- ✅ **Easy maintenance** - Plugin architecture for new parsers
- ✅ **Scalability** - Event-driven processing
- ✅ **Reliability** - Retry logic and circuit breakers
- ✅ **Observability** - CloudWatch metrics and structured logs

## 🔧 **Troubleshooting**

### **Common Issues:**

**"Import errors"**
- Ensure all `src/` files are uploaded
- Check `requirements.txt` is installed

**"No logs appearing"**
- Verify S3 trigger is configured correctly
- Check Lambda execution role has S3 permissions

**"SQS messages still being sent in dry-run"**
- Double-check `DRY_RUN_MODE=true` environment variable
- Look for "DRY-RUN:" prefix in logs

**"Parser not detecting lead source"**
- Check email content in logs
- Verify lead source detection patterns match your emails

## 📞 **Support**

The new system provides detailed error messages and structured logging. If you encounter issues:
1. Check CloudWatch logs for correlation ID
2. Look for structured error messages with context
3. All errors include detailed information for debugging

This deployment strategy ensures you can safely test and validate the new system without any risk to your existing email processing workflow.