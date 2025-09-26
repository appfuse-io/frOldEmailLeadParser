# Phase 2: Core Functionality Implementation

## 🎯 **What Phase 2 Will Build**

Phase 2 takes the foundation we built in Phase 1 and creates the actual working system that replaces your current brittle email parser.

### **Phase 2 Components:**

## 1. **Abstract Parser Framework** (`src/parsers/`)
```
src/parsers/
├── base_parser.py           # Abstract base class for all parsers
├── parser_registry.py      # Dynamic parser loading system
├── lead_source_detector.py  # Smart lead source detection
└── implementations/         # Specific parser implementations
    ├── rightbiz_parser.py
    ├── daltons_parser.py
    ├── homecare_parser.py
    ├── b4s_parser.py
    └── nda_parser.py
```

**What it does:**
- Creates a plugin system where each lead source has its own parser
- Eliminates the duplicate code in your current system
- Makes it easy to add new lead sources without touching existing code
- Provides fallback parsing when primary patterns fail

## 2. **Email Processing Engine** (`src/processors/`)
```
src/processors/
├── email_processor.py      # Main email processing orchestrator
├── lead_enricher.py        # Data enrichment and cleanup
└── result_formatter.py     # Format data for SQS/Freshsales
```

**What it does:**
- Orchestrates the entire email → lead conversion process
- Handles email parsing, lead source detection, data extraction, validation
- Enriches lead data with additional metadata
- Formats results for downstream systems

## 3. **AWS Service Layer** (`src/services/`)
```
src/services/
├── s3_service.py           # S3 operations with retry/circuit breaker
├── sqs_service.py          # SQS operations with batching
└── email_service.py        # Email parsing and handling
```

**What it does:**
- Abstracts AWS operations with proper error handling
- Implements retry logic and circuit breakers for AWS calls
- Handles S3 event notifications (replacing polling)
- Manages SQS message batching and error handling

## 4. **New Lambda Handler** (`src/handlers/`)
```
src/handlers/
├── lambda_handler.py       # New main entry point
└── event_handler.py        # S3 event processing
```

**What it does:**
- Replaces your current `lambda_function.py` with modern, robust handler
- Processes S3 events individually instead of batch polling
- Implements proper error handling, logging, and metrics
- Handles Lambda lifecycle and resource management

## 5. **Event-Driven Architecture**

**Current System:**
```python
# Polls S3 for ALL objects every time
objects = s3_client.list_objects_v2(Bucket=aws_s3_bucket)
for obj in objects['Contents']:  # Process everything at once
    # Risk of timeout, memory issues, partial failures
```

**New System:**
```python
# Triggered by S3 events for individual emails
def lambda_handler(event, context):
    for record in event['Records']:
        if record['eventName'].startswith('ObjectCreated'):
            # Process single email with full error handling
            process_single_email(record['s3']['object']['key'])
```

## 🔄 **How Phase 2 Transforms Your System**

### **Your Current Flow:**
1. Lambda starts → List ALL S3 objects
2. Create ALL parser instances
3. Process ALL emails in one batch
4. If ANY email fails → Entire batch may fail
5. Delete objects after processing
6. Send ALL results to SQS

### **New Phase 2 Flow:**
1. Email arrives in S3 → Triggers Lambda automatically
2. Process SINGLE email with full error handling
3. Smart lead source detection
4. Dynamic parser selection
5. Robust data extraction with fallbacks
6. Validation and enrichment
7. Send to SQS with retry logic
8. Delete only after successful processing

## 📊 **Specific Improvements for Your Use Case**

### **For BusinessesForSale.com emails:**
```python
# Current brittle parsing:
if line.startswith('Your listing ref:'):
    reference = line.split(':')[1].split()[0].strip()

# New robust parsing:
class B4sParser(BaseParser):
    REFERENCE_PATTERNS = [
        r'Your listing ref:\s*([A-Z0-9]+)',
        r'listing\s+ref:\s*([A-Z0-9]+)', 
        r'BFS(\d+)',
        r'ref:\s*([A-Z0-9]+)'
    ]
    
    def extract_reference(self, content):
        for pattern in self.REFERENCE_PATTERNS:
            match = re.search(pattern, content, re.IGNORECASE)
            if match:
                return match.group(1)
        return self.fallback_reference_extraction(content)
```

### **Error Handling:**
```python
# Current: Crash on any error
enquiry_payload = b4s.get_contact_payload(mail.text_plain, mail.date)

# New: Graceful error handling
try:
    lead_data = parser.parse(email)
    validated_data = validator.validate(lead_data)
    enriched_data = enricher.enrich(validated_data)
    
except ValidationError as e:
    logger.warning("Validation failed, using fallback", error=e)
    # Try alternative parsing or mark for manual review
    
except ParsingError as e:
    logger.error("Parsing failed", error=e)
    # Continue processing, don't crash entire system
```

## 🚀 **Phase 2 Deliverables**

1. **Complete Parser Framework** - All your current parsers rebuilt as robust, testable plugins
2. **Event-Driven Lambda** - Replaces polling with efficient S3 event processing  
3. **Service Abstractions** - Proper AWS service handling with retry/circuit breaker
4. **Email Processing Pipeline** - End-to-end email → validated lead data flow
5. **Migration Guide** - Step-by-step instructions to deploy the new system
6. **Test Suite** - Unit and integration tests for all components

## 🎯 **End Result**

After Phase 2, you'll have:
- **Zero crashes** - Comprehensive error handling
- **Better performance** - Event-driven instead of polling
- **Easy maintenance** - Plugin architecture for parsers
- **Full observability** - Detailed logging and metrics
- **Data quality** - Validation and enrichment
- **Scalability** - Handles high email volumes efficiently

Phase 2 transforms your current fragile system into a production-ready, enterprise-grade email processing pipeline that can handle any email format changes, scale with your business, and provide complete visibility into operations.