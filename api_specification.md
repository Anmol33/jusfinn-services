# JusFinn API Specification
**Version:** 1.0  
**Base URL:** `https://api.jusfinn.com/v1`  
**Authentication:** Bearer Token (JWT)

## Overview
This document lists all REST API endpoints for the JusFinn GST-compliant sales workflow system. All APIs follow RESTful conventions and return JSON responses.

## Authentication
All API requests require authentication using JWT tokens in the Authorization header:
```
Authorization: Bearer <jwt_token>
```

## Response Format
All APIs follow a consistent response format:
```json
{
  "success": true,
  "data": { ... },
  "message": "Operation completed successfully",
  "errors": [],
  "meta": {
    "timestamp": "2024-03-01T10:30:00Z",
    "request_id": "req_123456789"
  }
}
```

---

## 1. Company Management APIs

### 1.1 Company Registration & Setup
```http
POST /companies
```
Register a new company in the system.

**Request Body:**
```json
{
  "company_code": "COMP001",
  "legal_name": "Sample Trading Company Ltd",
  "trade_name": "Sample Trading",
  "gstin": "07AAACT2727Q1ZZ",
  "pan": "AAACT2727Q",
  "email": "admin@sample.com",
  "phone": "+919876543210",
  "address": {
    "line1": "123 Business Street",
    "line2": "Business District",
    "city": "New Delhi",
    "state_id": 1,
    "pincode": "110001"
  },
  "subscription_plan": "PROFESSIONAL"
}
```

### 1.2 Get Company Details
```http
GET /companies/{company_id}
```

### 1.3 Update Company Information
```http
PUT /companies/{company_id}
```

### 1.4 Get Company GST Configuration
```http
GET /companies/{company_id}/gst-config
```

---

## 2. User Management APIs

### 2.1 User Registration
```http
POST /users
```
**Request Body:**
```json
{
  "email": "accountant@sample.com",
  "full_name": "John Doe",
  "user_role": "ACCOUNTANT",
  "company_id": "uuid",
  "permissions": {
    "can_create_invoices": true,
    "can_approve_orders": false
  }
}
```

### 2.2 User Authentication
```http
POST /auth/login
```

### 2.3 Grant Company Access
```http
POST /users/{user_id}/company-access
```

### 2.4 List Users
```http
GET /companies/{company_id}/users
```

---

## 3. Customer Management APIs

### 3.1 Create Customer
```http
POST /companies/{company_id}/customers
```
**Request Body:**
```json
{
  "business_name": "Customer Business Ltd",
  "contact_person": "Jane Smith",
  "gstin": "01AAAAP1208Q1ZS",
  "customer_category": "REGULAR",
  "email": "customer@business.com",
  "phone": "+919876543211",
  "address": {
    "line1": "456 Customer Street",
    "city": "Mumbai",
    "state_id": 2,
    "pincode": "400001"
  },
  "credit_limit": 100000.00,
  "payment_terms": "NET_30"
}
```

### 3.2 List Customers
```http
GET /companies/{company_id}/customers
```
**Query Parameters:**
- `page`: Page number (default: 1)
- `limit`: Items per page (default: 20)
- `search`: Search by name or GSTIN
- `customer_category`: Filter by category

### 3.3 Get Customer Details
```http
GET /companies/{company_id}/customers/{customer_id}
```

### 3.4 Update Customer
```http
PUT /companies/{company_id}/customers/{customer_id}
```

### 3.5 Customer Outstanding
```http
GET /companies/{company_id}/customers/{customer_id}/outstanding
```

---

## 4. Items & Services Management APIs

### 4.1 Create Item/Service
```http
POST /companies/{company_id}/items
```
**Request Body:**
```json
{
  "item_code": "ITEM001",
  "name": "Sample Product",
  "type": "PRODUCT",
  "hsn_sac_code": "1001",
  "gst_rate": 18.00,
  "unit_of_measure": "PCS",
  "unit_price": 1000.00,
  "description": "Sample product description",
  "reorder_level": 10,
  "max_stock_level": 100
}
```

### 4.2 List Items
```http
GET /companies/{company_id}/items
```
**Query Parameters:**
- `type`: PRODUCT or SERVICE
- `category`: Item category
- `search`: Search by name or code

### 4.3 Get Item Details
```http
GET /companies/{company_id}/items/{item_id}
```

### 4.4 Update Item
```http
PUT /companies/{company_id}/items/{item_id}
```

### 4.5 Bulk Import Items
```http
POST /companies/{company_id}/items/bulk-import
```

---

## 5. Sales Quotation APIs

### 5.1 Create Quotation
```http
POST /companies/{company_id}/quotations
```
**Request Body:**
```json
{
  "customer_id": "uuid",
  "quotation_date": "2024-03-01",
  "valid_until": "2024-03-31",
  "items": [
    {
      "item_service_id": "uuid",
      "quantity": 10,
      "unit_price": 1000.00,
      "discount_percent": 5.00
    }
  ],
  "terms_conditions": [
    {
      "term_type": "PAYMENT",
      "description": "Payment within 30 days"
    }
  ],
  "notes": "Sample quotation notes"
}
```

### 5.2 List Quotations
```http
GET /companies/{company_id}/quotations
```
**Query Parameters:**
- `status`: DRAFT, SENT, ACCEPTED, etc.
- `customer_id`: Filter by customer
- `date_from`, `date_to`: Date range filter

### 5.3 Get Quotation Details
```http
GET /companies/{company_id}/quotations/{quotation_id}
```

### 5.4 Update Quotation Status
```http
PATCH /companies/{company_id}/quotations/{quotation_id}/status
```
**Request Body:**
```json
{
  "status": "APPROVED",
  "notes": "Approved by manager"
}
```

### 5.5 Convert to Sales Order
```http
POST /companies/{company_id}/quotations/{quotation_id}/convert-to-order
```

### 5.6 Generate Quotation PDF
```http
GET /companies/{company_id}/quotations/{quotation_id}/pdf
```

---

## 6. Sales Order APIs

### 6.1 Create Sales Order
```http
POST /companies/{company_id}/sales-orders
```

### 6.2 List Sales Orders
```http
GET /companies/{company_id}/sales-orders
```

### 6.3 Get Order Details
```http
GET /companies/{company_id}/sales-orders/{order_id}
```

### 6.4 Update Order Status
```http
PATCH /companies/{company_id}/sales-orders/{order_id}/status
```

### 6.5 Reserve Stock
```http
POST /companies/{company_id}/sales-orders/{order_id}/reserve-stock
```

### 6.6 Check Stock Availability
```http
POST /companies/{company_id}/sales-orders/check-stock
```
**Request Body:**
```json
{
  "items": [
    {
      "item_id": "uuid",
      "quantity": 10,
      "warehouse_id": "uuid"
    }
  ]
}
```

---

## 7. Delivery Challan APIs

### 7.1 Create Delivery Challan
```http
POST /companies/{company_id}/delivery-challans
```
**Request Body:**
```json
{
  "customer_id": "uuid",
  "sales_order_id": "uuid",
  "challan_date": "2024-03-01",
  "supply_type": "GOODS",
  "transportation": {
    "transporter_name": "ABC Logistics",
    "transporter_id": "07AAATG1234R1ZG",
    "vehicle_number": "DL01AB1234",
    "transportation_mode": "ROAD",
    "transportation_distance": 150
  },
  "dispatch_address": "123 Warehouse Street, Delhi",
  "delivery_address": "456 Customer Street, Mumbai",
  "items": [
    {
      "item_service_id": "uuid",
      "quantity": 5,
      "unit_price": 1000.00
    }
  ]
}
```

### 7.2 List Delivery Challans
```http
GET /companies/{company_id}/delivery-challans
```

### 7.3 Update Challan Status
```http
PATCH /companies/{company_id}/delivery-challans/{challan_id}/status
```

### 7.4 Generate E-Way Bill
```http
POST /companies/{company_id}/delivery-challans/{challan_id}/generate-eway-bill
```

### 7.5 Update Vehicle Details
```http
PUT /companies/{company_id}/delivery-challans/{challan_id}/vehicle
```

---

## 8. Tax Invoice APIs

### 8.1 Create Tax Invoice
```http
POST /companies/{company_id}/tax-invoices
```
**Request Body:**
```json
{
  "customer_id": "uuid",
  "sales_order_id": "uuid",
  "delivery_challan_id": "uuid",
  "invoice_date": "2024-03-01",
  "place_of_supply_state_id": 1,
  "supply_type": "GOODS",
  "items": [
    {
      "item_service_id": "uuid",
      "quantity": 5,
      "unit_price": 1000.00,
      "discount_percent": 0.00
    }
  ],
  "payment_terms": "NET_30",
  "notes": "Invoice notes"
}
```

### 8.2 List Tax Invoices
```http
GET /companies/{company_id}/tax-invoices
```
**Query Parameters:**
- `status`: DRAFT, APPROVED, SENT, PAID, etc.
- `customer_id`: Filter by customer
- `date_from`, `date_to`: Date range
- `einvoice_status`: E-Invoice status filter

### 8.3 Get Invoice Details
```http
GET /companies/{company_id}/tax-invoices/{invoice_id}
```

### 8.4 Update Invoice Status
```http
PATCH /companies/{company_id}/tax-invoices/{invoice_id}/status
```

### 8.5 Generate E-Invoice
```http
POST /companies/{company_id}/tax-invoices/{invoice_id}/generate-einvoice
```

### 8.6 Cancel E-Invoice
```http
POST /companies/{company_id}/tax-invoices/{invoice_id}/cancel-einvoice
```
**Request Body:**
```json
{
  "cancel_reason": "Duplicate invoice",
  "cancel_remarks": "Invoice created by mistake"
}
```

### 8.7 Generate Invoice PDF
```http
GET /companies/{company_id}/tax-invoices/{invoice_id}/pdf
```

### 8.8 Record Payment
```http
POST /companies/{company_id}/tax-invoices/{invoice_id}/payments
```
**Request Body:**
```json
{
  "payment_amount": 5900.00,
  "payment_date": "2024-03-15",
  "payment_method": "BANK_TRANSFER",
  "reference_number": "TXN123456789",
  "notes": "Payment received"
}
```

---

## 9. Sales Return & Credit Notes APIs

### 9.1 Create Sales Return
```http
POST /companies/{company_id}/sales-returns
```
**Request Body:**
```json
{
  "invoice_id": "uuid",
  "return_date": "2024-03-10",
  "return_type": "DEFECTIVE",
  "return_reason": "Product quality issues",
  "items": [
    {
      "invoice_item_id": "uuid",
      "return_quantity": 2,
      "condition_notes": "Damaged packaging"
    }
  ]
}
```

### 9.2 Approve Sales Return
```http
PATCH /companies/{company_id}/sales-returns/{return_id}/approve
```

### 9.3 Create Credit Note
```http
POST /companies/{company_id}/credit-notes
```

### 9.4 List Credit Notes
```http
GET /companies/{company_id}/credit-notes
```

---

## 10. Inventory Management APIs

### 10.1 Get Stock Levels
```http
GET /companies/{company_id}/inventory/stock-levels
```
**Query Parameters:**
- `warehouse_id`: Filter by warehouse
- `item_id`: Filter by item
- `low_stock`: Show only low stock items

### 10.2 Stock Movement History
```http
GET /companies/{company_id}/inventory/movements
```

### 10.3 Stock Adjustment
```http
POST /companies/{company_id}/inventory/adjustments
```
**Request Body:**
```json
{
  "warehouse_id": "uuid",
  "adjustment_date": "2024-03-01",
  "reason": "Physical stock verification",
  "items": [
    {
      "item_id": "uuid",
      "current_quantity": 50,
      "adjusted_quantity": 48,
      "unit_cost": 1000.00
    }
  ]
}
```

### 10.4 Stock Reservations
```http
GET /companies/{company_id}/inventory/reservations
```

### 10.5 Stock Alerts
```http
GET /companies/{company_id}/inventory/alerts
```

### 10.6 Inventory Reconciliation
```http
POST /companies/{company_id}/inventory/reconciliation
```

---

## 11. GSTR-1 & Compliance APIs

### 11.1 Generate GSTR-1 Data
```http
POST /companies/{company_id}/gstr1/generate
```
**Request Body:**
```json
{
  "period": "03-2024",
  "include_amendments": false
}
```

### 11.2 Validate GSTR-1 Data
```http
POST /companies/{company_id}/gstr1/validate
```

### 11.3 Submit GSTR-1
```http
POST /companies/{company_id}/gstr1/submit
```

### 11.4 Get GSTR-1 Status
```http
GET /companies/{company_id}/gstr1/{period}/status
```

### 11.5 Download GSTR-2B
```http
GET /companies/{company_id}/gstr2b/{period}
```

### 11.6 Reconcile GSTR-2B
```http
POST /companies/{company_id}/gstr2b/{period}/reconcile
```

### 11.7 HSN Summary Report
```http
GET /companies/{company_id}/reports/hsn-summary
```
**Query Parameters:**
- `period`: MM-YYYY format
- `format`: JSON or PDF

---

## 12. Reports & Analytics APIs

### 12.1 Sales Reports
```http
GET /companies/{company_id}/reports/sales
```
**Query Parameters:**
- `period`: daily, weekly, monthly, yearly
- `date_from`, `date_to`: Custom date range
- `customer_id`: Filter by customer
- `format`: JSON, PDF, Excel

### 12.2 GST Reports
```http
GET /companies/{company_id}/reports/gst
```

### 12.3 Outstanding Reports
```http
GET /companies/{company_id}/reports/outstanding
```

### 12.4 Inventory Reports
```http
GET /companies/{company_id}/reports/inventory
```

### 12.5 Tax Liability Report
```http
GET /companies/{company_id}/reports/tax-liability
```

### 12.6 Dashboard Analytics
```http
GET /companies/{company_id}/dashboard/analytics
```

---

## 13. Document Templates APIs

### 13.1 List Templates
```http
GET /companies/{company_id}/templates
```

### 13.2 Create Template
```http
POST /companies/{company_id}/templates
```

### 13.3 Update Template
```http
PUT /companies/{company_id}/templates/{template_id}
```

### 13.4 Preview Template
```http
POST /companies/{company_id}/templates/{template_id}/preview
```

---

## 14. Workflow & Approvals APIs

### 14.1 Get Pending Approvals
```http
GET /companies/{company_id}/approvals/pending
```

### 14.2 Approve Document
```http
POST /companies/{company_id}/approvals/{approval_id}/approve
```

### 14.3 Reject Document
```http
POST /companies/{company_id}/approvals/{approval_id}/reject
```

### 14.4 Workflow History
```http
GET /companies/{company_id}/workflow-history
```

---

## 15. Notifications APIs

### 15.1 Get Notifications
```http
GET /notifications
```

### 15.2 Mark as Read
```http
PATCH /notifications/{notification_id}/read
```

### 15.3 Notification Settings
```http
GET /companies/{company_id}/notification-settings
PUT /companies/{company_id}/notification-settings
```

---

## 16. Integration APIs

### 16.1 GST API Configuration
```http
GET /companies/{company_id}/integrations/gst-config
PUT /companies/{company_id}/integrations/gst-config
```

### 16.2 Test API Connection
```http
POST /companies/{company_id}/integrations/test-connection
```

### 16.3 Sync Status
```http
GET /companies/{company_id}/integrations/sync-status
```

---

## 17. Bulk Operations APIs

### 17.1 Bulk Invoice Generation
```http
POST /companies/{company_id}/bulk/generate-invoices
```

### 17.2 Bulk E-Invoice Generation
```http
POST /companies/{company_id}/bulk/generate-einvoices
```

### 17.3 Bulk Status Update
```http
PATCH /companies/{company_id}/bulk/update-status
```

### 17.4 Bulk Operation Status
```http
GET /companies/{company_id}/bulk-operations/{operation_id}/status
```

---

## Error Codes

| Code | Description |
|------|-------------|
| 400 | Bad Request - Invalid input data |
| 401 | Unauthorized - Invalid or missing token |
| 403 | Forbidden - Insufficient permissions |
| 404 | Not Found - Resource doesn't exist |
| 409 | Conflict - Resource already exists |
| 422 | Validation Error - Business rule violation |
| 429 | Rate Limit Exceeded |
| 500 | Internal Server Error |
| 503 | Service Unavailable - External API down |

## Rate Limits
- **Standard Plan**: 1000 requests/hour
- **Professional Plan**: 5000 requests/hour  
- **Enterprise Plan**: 20000 requests/hour

## Webhooks
Configure webhooks to receive real-time notifications:
- Invoice status changes
- E-Invoice generation completed
- GSTR-1 filing status updates
- Payment received notifications

**Webhook Configuration:**
```http
POST /companies/{company_id}/webhooks
```

This comprehensive API specification provides all endpoints needed for the complete GST-compliant sales workflow system. 