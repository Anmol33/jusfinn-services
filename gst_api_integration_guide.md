# GST Filing API Integration Guide

## Overview
This guide provides comprehensive recommendations for integrating GST filing APIs, covering various service providers, implementation strategies, and best practices for seamless GST compliance automation.

## 1. GST API Service Providers Comparison

### 1.1 Direct GSTN APIs
**Pros:**
- Official government APIs
- No intermediary costs
- Complete control over data
- Real-time updates

**Cons:**
- Complex authentication process
- Requires GSP (GST Suvidha Provider) registration
- Limited support and documentation
- High technical complexity

**Use Case:** Large enterprises with dedicated development teams

### 1.2 MasterGST
**Pros:**
- Simple REST APIs
- Comprehensive documentation
- Supports all GST returns (GSTR-1, GSTR-2B, GSTR-3B)
- E-Invoice and E-Way Bill integration
- Good customer support

**Cons:**
- Monthly subscription costs
- API rate limits
- Dependency on third-party service

**Pricing:** ₹500-2000/month per GSTIN
**Recommended for:** SMEs and mid-market businesses

### 1.3 ClearTax APIs
**Pros:**
- Robust API infrastructure
- Advanced features (bulk operations, reconciliation)
- Good error handling and validation
- Integration with accounting software

**Cons:**
- Higher cost structure
- Complex pricing model
- Enterprise-focused

**Pricing:** ₹1000-5000/month per GSTIN
**Recommended for:** Large businesses and enterprises

### 1.4 IRIS GST APIs
**Pros:**
- Government-approved GSP
- Direct GSTN connectivity
- Comprehensive compliance features
- Strong security measures

**Cons:**
- More expensive than alternatives
- Enterprise-focused features
- Complex integration process

**Pricing:** Custom enterprise pricing
**Recommended for:** Large corporations

### 1.5 Tally Solutions APIs
**Pros:**
- Integrated with popular accounting software
- Familiar interface for accountants
- Good support for Indian businesses

**Cons:**
- Limited to Tally ecosystem
- Less flexible for custom integrations

## 2. Recommended Integration Architecture

### 2.1 Multi-Provider Strategy
```python
from enum import Enum
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional

class GSTProvider(Enum):
    MASTERGST = "mastergst"
    CLEARTAX = "cleartax"
    IRIS = "iris"
    DIRECT_GSTN = "gstn"

class GSTAPIInterface(ABC):
    """Abstract interface for GST API providers"""
    
    @abstractmethod
    def authenticate(self) -> bool:
        pass
    
    @abstractmethod
    def submit_gstr1(self, data: Dict[str, Any], period: str) -> Dict[str, Any]:
        pass
    
    @abstractmethod
    def generate_einvoice(self, invoice_data: Dict[str, Any]) -> Dict[str, Any]:
        pass
    
    @abstractmethod
    def create_eway_bill(self, challan_data: Dict[str, Any]) -> Dict[str, Any]:
        pass
    
    @abstractmethod
    def get_gstr2b(self, period: str) -> Dict[str, Any]:
        pass

class GSTAPIManager:
    """Manager for multiple GST API providers with failover"""
    
    def __init__(self):
        self.providers = {}
        self.primary_provider = None
        self.fallback_providers = []
    
    def register_provider(
        self, 
        provider_type: GSTProvider, 
        api_instance: GSTAPIInterface,
        is_primary: bool = False
    ):
        self.providers[provider_type] = api_instance
        if is_primary:
            self.primary_provider = provider_type
        else:
            self.fallback_providers.append(provider_type)
    
    def execute_with_failover(self, method: str, *args, **kwargs) -> Dict[str, Any]:
        """Execute API call with automatic failover"""
        providers_to_try = [self.primary_provider] + self.fallback_providers
        
        for provider_type in providers_to_try:
            try:
                provider = self.providers[provider_type]
                method_func = getattr(provider, method)
                result = method_func(*args, **kwargs)
                
                if result.get('success'):
                    return {
                        **result,
                        'provider_used': provider_type.value
                    }
            except Exception as e:
                print(f"Provider {provider_type.value} failed: {str(e)}")
                continue
        
        return {
            'success': False,
            'error': 'All providers failed',
            'provider_used': None
        }
```

### 2.2 MasterGST Implementation
```python
import requests
import json
from datetime import datetime
from typing import Dict, Any, Optional

class MasterGSTAPI(GSTAPIInterface):
    def __init__(self, email: str, username: str, password: str):
        self.base_url = "https://api.mastergst.com/gstapi/v1.1"
        self.email = email
        self.username = username
        self.password = password
        self.auth_token = None
        self.session = requests.Session()
    
    def authenticate(self) -> bool:
        """Authenticate with MasterGST API"""
        auth_data = {
            "email": self.email,
            "username": self.username,
            "password": self.password
        }
        
        try:
            response = self.session.post(
                f"{self.base_url}/auth",
                json=auth_data,
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                self.auth_token = result.get("auth_token")
                self.session.headers.update({
                    "Authorization": f"Bearer {self.auth_token}",
                    "Content-Type": "application/json"
                })
                return True
            return False
        except Exception as e:
            print(f"Authentication failed: {str(e)}")
            return False
    
    def submit_gstr1(self, data: Dict[str, Any], period: str) -> Dict[str, Any]:
        """Submit GSTR-1 data"""
        if not self.auth_token:
            if not self.authenticate():
                return {"success": False, "error": "Authentication failed"}
        
        payload = {
            "gstin": data["gstin"],
            "ret_period": period,
            "data": data
        }
        
        try:
            response = self.session.post(
                f"{self.base_url}/gstr1/save",
                json=payload,
                timeout=60
            )
            
            result = response.json()
            return {
                "success": response.status_code == 200,
                "response": result,
                "reference_id": result.get("reference_id"),
                "status": result.get("status")
            }
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def generate_einvoice(self, invoice_data: Dict[str, Any]) -> Dict[str, Any]:
        """Generate E-Invoice"""
        try:
            response = self.session.post(
                f"{self.base_url}/einvoice/generate",
                json=invoice_data,
                timeout=60
            )
            
            result = response.json()
            return {
                "success": response.status_code == 200,
                "irn": result.get("irn"),
                "ack_no": result.get("ack_no"),
                "ack_dt": result.get("ack_dt"),
                "qr_code": result.get("qr_code"),
                "response": result
            }
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def create_eway_bill(self, challan_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create E-Way Bill"""
        try:
            response = self.session.post(
                f"{self.base_url}/ewaybill/generate",
                json=challan_data,
                timeout=60
            )
            
            result = response.json()
            return {
                "success": response.status_code == 200,
                "eway_bill_no": result.get("ewayBillNo"),
                "eway_bill_date": result.get("ewayBillDate"),
                "valid_upto": result.get("validUpto"),
                "response": result
            }
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def get_gstr2b(self, period: str) -> Dict[str, Any]:
        """Download GSTR-2B data"""
        try:
            response = self.session.get(
                f"{self.base_url}/gstr2b/get/{period}",
                timeout=60
            )
            
            result = response.json()
            return {
                "success": response.status_code == 200,
                "data": result.get("data"),
                "response": result
            }
        except Exception as e:
            return {"success": False, "error": str(e)}
```

## 3. Database Integration Layer

### 3.1 API Configuration Management
```sql
-- Store API configurations
CREATE TABLE gst_api_configurations (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    company_id UUID NOT NULL REFERENCES companies(id),
    
    -- Provider Details
    provider_name VARCHAR(50) NOT NULL CHECK (provider_name IN ('MASTERGST', 'CLEARTAX', 'IRIS', 'GSTN')),
    is_primary BOOLEAN DEFAULT FALSE,
    is_active BOOLEAN DEFAULT TRUE,
    
    -- API Credentials (encrypted)
    api_endpoint VARCHAR(255) NOT NULL,
    client_id VARCHAR(100),
    client_secret VARCHAR(255), -- Encrypted
    username VARCHAR(100),
    password VARCHAR(255), -- Encrypted
    additional_config JSONB DEFAULT '{}',
    
    -- Rate Limiting
    max_requests_per_minute INTEGER DEFAULT 60,
    max_requests_per_day INTEGER DEFAULT 10000,
    
    -- Status
    last_authentication TIMESTAMP WITH TIME ZONE,
    authentication_expires TIMESTAMP WITH TIME ZONE,
    is_authenticated BOOLEAN DEFAULT FALSE,
    
    -- Audit
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    UNIQUE(company_id, provider_name)
);

-- API request logging
CREATE TABLE gst_api_logs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    company_id UUID NOT NULL REFERENCES companies(id),
    configuration_id UUID REFERENCES gst_api_configurations(id),
    
    -- Request Details
    api_type VARCHAR(20) NOT NULL CHECK (api_type IN ('GSTR1', 'GSTR2B', 'GSTR3B', 'EINVOICE', 'EWAY_BILL')),
    request_method VARCHAR(10) NOT NULL,
    request_url VARCHAR(500),
    request_payload JSONB,
    
    -- Response Details
    response_status_code INTEGER,
    response_payload JSONB,
    response_time_ms INTEGER,
    
    -- Status
    is_successful BOOLEAN,
    error_message TEXT,
    retry_count INTEGER DEFAULT 0,
    
    -- Reference
    reference_id VARCHAR(100), -- Document ID that triggered the API call
    reference_type VARCHAR(20), -- Type of document
    
    -- Timing
    requested_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    completed_at TIMESTAMP WITH TIME ZONE,
    
    -- Index for performance
    INDEX(company_id, api_type, requested_at),
    INDEX(reference_id, reference_type)
);
```

### 3.2 Integration Functions
```sql
-- Function to get active API configuration
CREATE OR REPLACE FUNCTION get_active_gst_api_config(
    p_company_id UUID,
    p_api_type VARCHAR(20)
) RETURNS UUID AS $$
DECLARE
    v_config_id UUID;
BEGIN
    -- Try to get primary provider first
    SELECT id INTO v_config_id
    FROM gst_api_configurations
    WHERE company_id = p_company_id
    AND is_primary = TRUE
    AND is_active = TRUE
    AND is_authenticated = TRUE;
    
    -- If no primary provider, get any active one
    IF v_config_id IS NULL THEN
        SELECT id INTO v_config_id
        FROM gst_api_configurations
        WHERE company_id = p_company_id
        AND is_active = TRUE
        AND is_authenticated = TRUE
        ORDER BY 
            CASE provider_name
                WHEN 'MASTERGST' THEN 1
                WHEN 'CLEARTAX' THEN 2
                WHEN 'IRIS' THEN 3
                ELSE 4
            END
        LIMIT 1;
    END IF;
    
    RETURN v_config_id;
END;
$$ LANGUAGE plpgsql;

-- Function to log API requests
CREATE OR REPLACE FUNCTION log_gst_api_request(
    p_company_id UUID,
    p_config_id UUID,
    p_api_type VARCHAR(20),
    p_request_method VARCHAR(10),
    p_request_url VARCHAR(500),
    p_request_payload JSONB,
    p_reference_id VARCHAR(100) DEFAULT NULL,
    p_reference_type VARCHAR(20) DEFAULT NULL
) RETURNS UUID AS $$
DECLARE
    v_log_id UUID;
BEGIN
    INSERT INTO gst_api_logs (
        company_id, configuration_id, api_type, request_method,
        request_url, request_payload, reference_id, reference_type
    ) VALUES (
        p_company_id, p_config_id, p_api_type, p_request_method,
        p_request_url, p_request_payload, p_reference_id, p_reference_type
    ) RETURNING id INTO v_log_id;
    
    RETURN v_log_id;
END;
$$ LANGUAGE plpgsql;

-- Function to update API response
CREATE OR REPLACE FUNCTION update_gst_api_response(
    p_log_id UUID,
    p_status_code INTEGER,
    p_response_payload JSONB,
    p_response_time_ms INTEGER,
    p_is_successful BOOLEAN,
    p_error_message TEXT DEFAULT NULL
) RETURNS VOID AS $$
BEGIN
    UPDATE gst_api_logs SET
        response_status_code = p_status_code,
        response_payload = p_response_payload,
        response_time_ms = p_response_time_ms,
        is_successful = p_is_successful,
        error_message = p_error_message,
        completed_at = NOW()
    WHERE id = p_log_id;
END;
$$ LANGUAGE plpgsql;
```

## 4. Implementation Strategies

### 4.1 Async Processing with Celery
```python
from celery import Celery
from typing import Dict, Any
import asyncio

# Celery configuration
celery_app = Celery('gst_filing', broker='redis://localhost:6379')

@celery_app.task(bind=True, max_retries=3)
def submit_gstr1_async(self, company_id: str, period: str, user_id: str):
    """Async GSTR-1 submission with retry logic"""
    try:
        # Get GSTR-1 data from database
        gstr1_data = get_gstr1_data(company_id, period)
        
        # Get API configuration
        api_manager = GSTAPIManager()
        setup_api_providers(api_manager, company_id)
        
        # Submit GSTR-1
        result = api_manager.execute_with_failover(
            'submit_gstr1', 
            gstr1_data, 
            period
        )
        
        # Update database with result
        update_gstr1_submission_status(company_id, period, result)
        
        return result
        
    except Exception as exc:
        # Retry logic
        if self.request.retries < self.max_retries:
            raise self.retry(countdown=60 * (2 ** self.request.retries))
        else:
            # Log failure and notify user
            log_gstr1_failure(company_id, period, str(exc))
            send_failure_notification(user_id, company_id, period, str(exc))
            raise

@celery_app.task
def generate_einvoice_async(invoice_id: str):
    """Async E-Invoice generation"""
    try:
        invoice_data = get_einvoice_data(invoice_id)
        
        api_manager = GSTAPIManager()
        setup_api_providers(api_manager, invoice_data['company_id'])
        
        result = api_manager.execute_with_failover(
            'generate_einvoice',
            invoice_data
        )
        
        if result['success']:
            update_invoice_einvoice_data(
                invoice_id,
                result['irn'],
                result['ack_no'],
                result['qr_code']
            )
        
        return result
        
    except Exception as exc:
        log_einvoice_failure(invoice_id, str(exc))
        raise
```

### 4.2 Rate Limiting and Circuit Breaker
```python
import time
from functools import wraps
from typing import Callable, Any
import redis

class RateLimiter:
    def __init__(self, redis_client: redis.Redis):
        self.redis = redis_client
    
    def limit(self, key: str, limit: int, window: int):
        """Rate limiting decorator"""
        def decorator(func: Callable) -> Callable:
            @wraps(func)
            def wrapper(*args, **kwargs):
                current_time = int(time.time())
                pipeline = self.redis.pipeline()
                
                # Sliding window rate limiting
                pipeline.zremrangebyscore(key, 0, current_time - window)
                pipeline.zcard(key)
                pipeline.zadd(key, {str(current_time): current_time})
                pipeline.expire(key, window)
                
                results = pipeline.execute()
                current_count = results[1]
                
                if current_count >= limit:
                    raise Exception(f"Rate limit exceeded: {current_count}/{limit}")
                
                return func(*args, **kwargs)
            return wrapper
        return decorator

class CircuitBreaker:
    def __init__(self, failure_threshold: int = 5, timeout: int = 60):
        self.failure_threshold = failure_threshold
        self.timeout = timeout
        self.failure_count = 0
        self.last_failure_time = 0
        self.state = 'CLOSED'  # CLOSED, OPEN, HALF_OPEN
    
    def call(self, func: Callable, *args, **kwargs) -> Any:
        if self.state == 'OPEN':
            if time.time() - self.last_failure_time > self.timeout:
                self.state = 'HALF_OPEN'
            else:
                raise Exception("Circuit breaker is OPEN")
        
        try:
            result = func(*args, **kwargs)
            if self.state == 'HALF_OPEN':
                self.state = 'CLOSED'
                self.failure_count = 0
            return result
        except Exception as e:
            self.failure_count += 1
            self.last_failure_time = time.time()
            
            if self.failure_count >= self.failure_threshold:
                self.state = 'OPEN'
            
            raise e
```

## 5. Error Handling and Monitoring

### 5.1 Error Classification
```python
from enum import Enum

class GSTErrorCategory(Enum):
    AUTHENTICATION = "authentication"
    VALIDATION = "validation"
    NETWORK = "network"
    RATE_LIMIT = "rate_limit"
    SERVICE_UNAVAILABLE = "service_unavailable"
    DATA_ERROR = "data_error"
    UNKNOWN = "unknown"

class GSTErrorHandler:
    def __init__(self):
        self.retry_strategies = {
            GSTErrorCategory.NETWORK: {"max_retries": 3, "backoff": "exponential"},
            GSTErrorCategory.RATE_LIMIT: {"max_retries": 5, "backoff": "linear"},
            GSTErrorCategory.SERVICE_UNAVAILABLE: {"max_retries": 3, "backoff": "exponential"},
            GSTErrorCategory.AUTHENTICATION: {"max_retries": 2, "backoff": "immediate"},
        }
    
    def categorize_error(self, error_response: Dict[str, Any]) -> GSTErrorCategory:
        """Categorize error based on response"""
        status_code = error_response.get('status_code', 0)
        error_message = error_response.get('error', '').lower()
        
        if status_code == 401 or 'authentication' in error_message:
            return GSTErrorCategory.AUTHENTICATION
        elif status_code == 429 or 'rate limit' in error_message:
            return GSTErrorCategory.RATE_LIMIT
        elif status_code >= 500:
            return GSTErrorCategory.SERVICE_UNAVAILABLE
        elif status_code == 400 or 'validation' in error_message:
            return GSTErrorCategory.VALIDATION
        elif 'network' in error_message or 'timeout' in error_message:
            return GSTErrorCategory.NETWORK
        else:
            return GSTErrorCategory.UNKNOWN
    
    def should_retry(self, error_category: GSTErrorCategory, attempt: int) -> bool:
        """Determine if request should be retried"""
        strategy = self.retry_strategies.get(error_category)
        if not strategy:
            return False
        
        return attempt < strategy['max_retries']
    
    def get_retry_delay(self, error_category: GSTErrorCategory, attempt: int) -> int:
        """Calculate retry delay"""
        strategy = self.retry_strategies.get(error_category, {})
        backoff = strategy.get('backoff', 'exponential')
        
        if backoff == 'exponential':
            return min(300, 2 ** attempt)  # Max 5 minutes
        elif backoff == 'linear':
            return 60 * attempt  # Linear increase
        else:
            return 30  # Immediate retry after 30 seconds
```

### 5.2 Monitoring and Alerting
```python
import logging
from datetime import datetime, timedelta
from typing import Dict, List

class GSTAPIMonitor:
    def __init__(self):
        self.logger = logging.getLogger('gst_api_monitor')
    
    def track_api_performance(self, provider: str, api_type: str, 
                            response_time: int, success: bool):
        """Track API performance metrics"""
        metric_data = {
            'provider': provider,
            'api_type': api_type,
            'response_time': response_time,
            'success': success,
            'timestamp': datetime.now()
        }
        
        # Store in time-series database (InfluxDB, TimescaleDB, etc.)
        self.store_metric(metric_data)
        
        # Check for performance degradation
        self.check_performance_alerts(provider, api_type)
    
    def check_performance_alerts(self, provider: str, api_type: str):
        """Check for performance issues and send alerts"""
        recent_metrics = self.get_recent_metrics(provider, api_type, minutes=30)
        
        if not recent_metrics:
            return
        
        # Calculate success rate
        success_rate = sum(1 for m in recent_metrics if m['success']) / len(recent_metrics)
        avg_response_time = sum(m['response_time'] for m in recent_metrics) / len(recent_metrics)
        
        # Alert conditions
        if success_rate < 0.9:  # Less than 90% success rate
            self.send_alert(
                f"Low success rate for {provider} {api_type}: {success_rate:.2%}",
                severity="high"
            )
        
        if avg_response_time > 10000:  # More than 10 seconds average
            self.send_alert(
                f"High response time for {provider} {api_type}: {avg_response_time}ms",
                severity="medium"
            )
    
    def send_alert(self, message: str, severity: str = "medium"):
        """Send alert notification"""
        # Implementation depends on your notification system
        # Slack, email, SMS, etc.
        self.logger.warning(f"GST API Alert [{severity}]: {message}")
```

## 6. Cost Optimization Strategies

### 6.1 API Usage Optimization
```python
class GSTAPIOptimizer:
    def __init__(self):
        self.batch_size_limits = {
            'GSTR1': 100,  # invoices per batch
            'EINVOICE': 50,
            'EWAY_BILL': 100
        }
    
    def optimize_gstr1_submission(self, company_id: str, period: str) -> Dict[str, Any]:
        """Optimize GSTR-1 submission by batching and deduplication"""
        
        # Get all invoices for the period
        invoices = get_invoices_for_period(company_id, period)
        
        # Group by customer GSTIN for B2B optimization
        b2b_groups = {}
        for invoice in invoices:
            gstin = invoice.get('customer_gstin')
            if gstin:
                if gstin not in b2b_groups:
                    b2b_groups[gstin] = []
                b2b_groups[gstin].append(invoice)
        
        # Optimize payload size
        optimized_data = {
            'gstin': get_company_gstin(company_id),
            'ret_period': period.replace('-', ''),
            'b2b': self.optimize_b2b_data(b2b_groups),
            # ... other sections
        }
        
        return optimized_data
    
    def should_use_bulk_api(self, data_size: int, api_type: str) -> bool:
        """Determine if bulk API should be used"""
        threshold = self.batch_size_limits.get(api_type, 50)
        return data_size > threshold
    
    def estimate_api_cost(self, operations: Dict[str, int], provider: str) -> float:
        """Estimate API costs for different providers"""
        cost_matrix = {
            'MASTERGST': {
                'GSTR1': 2.0,
                'EINVOICE': 1.0,
                'EWAY_BILL': 0.5,
                'GSTR2B': 1.5
            },
            'CLEARTAX': {
                'GSTR1': 3.0,
                'EINVOICE': 1.5,
                'EWAY_BILL': 1.0,
                'GSTR2B': 2.0
            }
        }
        
        provider_costs = cost_matrix.get(provider, {})
        total_cost = sum(
            operations.get(api_type, 0) * provider_costs.get(api_type, 0)
            for api_type in operations
        )
        
        return total_cost
```

## 7. Recommended Implementation Roadmap

### Phase 1: Foundation (Weeks 1-2)
1. **Setup Database Schema**
   - API configuration tables
   - Logging and monitoring tables
   - Error tracking system

2. **Basic API Integration**
   - Choose primary provider (recommend MasterGST for SME)
   - Implement authentication and basic operations
   - Setup logging and error handling

### Phase 2: Core Features (Weeks 3-4)
1. **GSTR-1 Integration**
   - Complete JSON generation
   - API submission and status tracking
   - Validation and error handling

2. **E-Invoice Integration**
   - Automatic E-Invoice generation
   - IRN and QR code handling
   - Error recovery mechanisms

### Phase 3: Advanced Features (Weeks 5-6)
1. **E-Way Bill Integration**
   - Automatic E-Way Bill generation
   - Transportation tracking
   - Update mechanisms

2. **GSTR-2B Download**
   - Automatic reconciliation
   - Mismatch reporting
   - Vendor communication

### Phase 4: Optimization (Weeks 7-8)
1. **Performance Optimization**
   - Async processing implementation
   - Rate limiting and circuit breakers
   - Caching strategies

2. **Monitoring and Alerts**
   - Performance monitoring
   - Error alerting
   - Cost tracking

## 8. Security Best Practices

### 8.1 Credential Management
```python
from cryptography.fernet import Fernet
import os

class CredentialManager:
    def __init__(self):
        self.cipher_key = os.environ.get('GST_ENCRYPTION_KEY')
        self.cipher = Fernet(self.cipher_key.encode())
    
    def encrypt_credentials(self, credentials: Dict[str, str]) -> Dict[str, str]:
        """Encrypt API credentials"""
        encrypted = {}
        for key, value in credentials.items():
            if value and key in ['password', 'client_secret', 'api_key']:
                encrypted[key] = self.cipher.encrypt(value.encode()).decode()
            else:
                encrypted[key] = value
        return encrypted
    
    def decrypt_credentials(self, encrypted_creds: Dict[str, str]) -> Dict[str, str]:
        """Decrypt API credentials"""
        decrypted = {}
        for key, value in encrypted_creds.items():
            if value and key in ['password', 'client_secret', 'api_key']:
                decrypted[key] = self.cipher.decrypt(value.encode()).decode()
            else:
                decrypted[key] = value
        return decrypted
```

### 8.2 Audit Trail
```sql
-- Comprehensive audit trail for GST operations
CREATE TABLE gst_operation_audit (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    company_id UUID NOT NULL REFERENCES companies(id),
    user_id UUID REFERENCES users(id),
    
    -- Operation Details
    operation_type VARCHAR(50) NOT NULL,
    operation_category VARCHAR(20) NOT NULL, -- FILING, INVOICE, RECONCILIATION
    
    -- Data
    before_data JSONB,
    after_data JSONB,
    changes JSONB,
    
    -- Context
    ip_address INET,
    user_agent TEXT,
    session_id VARCHAR(100),
    
    -- Result
    status VARCHAR(20) NOT NULL,
    error_message TEXT,
    
    -- Timing
    started_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    completed_at TIMESTAMP WITH TIME ZONE,
    
    -- Compliance
    retention_until DATE DEFAULT (CURRENT_DATE + INTERVAL '7 years')
);
```

This comprehensive guide provides everything needed to implement a robust, scalable, and compliant GST filing API integration system. 