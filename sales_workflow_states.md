# GST-Compliant Sales Workflow States & Transitions

## 1. Sales Quotation Workflow

### States & Transitions

| State | Description | Allowed Transitions | Validation Rules |
|-------|-------------|-------------------|------------------|
| `DRAFT` | Initial quotation creation | → `PENDING_APPROVAL` | • Customer required<br>• Items with valid HSN/SAC<br>• Basic calculations |
| `PENDING_APPROVAL` | Awaiting internal approval | → `APPROVED`<br>→ `DRAFT` (reject) | • Approval hierarchy check<br>• Credit limit validation |
| `APPROVED` | Ready to send to customer | → `SENT` | • Final pricing validation<br>• Terms & conditions added |
| `SENT` | Quotation sent to customer | → `ACCEPTED`<br>→ `REJECTED`<br>→ `EXPIRED` | • Customer acknowledgment<br>• Validity period tracking |
| `ACCEPTED` | Customer accepted quotation | → `CONVERTED` | • Ready for sales order conversion |
| `REJECTED` | Customer rejected quotation | → End state | • Reason for rejection recorded |
| `EXPIRED` | Validity period ended | → `DRAFT` (new version) | • Auto-transition after validity date |

### Business Rules
- **Versioning**: Each revision creates new version with reference to parent
- **Validity**: Default 30 days from quotation date
- **Approval**: Required for quotations above ₹1,00,000
- **HSN/SAC**: Mandatory for all items as per GST rules

## 2. Sales Order Workflow

### States & Transitions

| State | Description | Allowed Transitions | Validation Rules |
|-------|-------------|-------------------|------------------|
| `DRAFT` | Order created from quotation | → `APPROVED` | • Stock availability check<br>• Customer credit validation |
| `APPROVED` | Order approved for processing | → `PARTIAL`<br>→ `PROCESSING` | • Inventory reservation<br>• Delivery date confirmation |
| `PROCESSING` | Order being fulfilled | → `PARTIAL`<br>→ `COMPLETED` | • Delivery challan creation<br>• Stock allocation |
| `PARTIAL` | Partially fulfilled order | → `PROCESSING`<br>→ `COMPLETED` | • Track pending quantities |
| `COMPLETED` | Fully fulfilled order | → End state | • All items delivered<br>• Ready for invoicing |

### Business Rules
- **Stock Reservation**: Reserve stock on approval
- **Partial Delivery**: Support multiple delivery challans
- **Credit Check**: Validate customer credit limit before approval

## 3. Delivery Challan Workflow

### States & Transitions

| State | Description | Allowed Transitions | Validation Rules |
|-------|-------------|-------------------|------------------|
| `DRAFT` | Challan being prepared | → `DISPATCHED` | • Transportation details<br>• E-Way Bill requirements |
| `DISPATCHED` | Goods dispatched | → `IN_TRANSIT` | • E-Way Bill generated<br>• Vehicle details captured |
| `IN_TRANSIT` | Goods in transit | → `DELIVERED`<br>→ `CANCELLED` | • GPS tracking (optional)<br>• Expected delivery date |
| `DELIVERED` | Goods delivered | → End state | • Delivery confirmation<br>• Customer signature |
| `CANCELLED` | Delivery cancelled | → End state | • Return to inventory |

### Business Rules
- **E-Way Bill**: Mandatory for inter-state movement >₹50,000 or intra-state >₹1,00,000
- **Distance Validation**: Calculate distance between dispatch and delivery locations
- **Vehicle Tracking**: Maintain vehicle number and transporter details

## 4. Tax Invoice Workflow

### States & Transitions

| State | Description | Allowed Transitions | Validation Rules |
|-------|-------------|-------------------|------------------|
| `DRAFT` | Invoice being prepared | → `APPROVED` | • GST calculations<br>• Customer billing details |
| `APPROVED` | Ready for E-Invoice check | → `EINVOICE_PENDING`<br>→ `SENT` | • Amount threshold check<br>• Customer GST status |
| `EINVOICE_PENDING` | Awaiting E-Invoice generation | → `EINVOICE_GENERATED`<br>→ `EINVOICE_CANCELLED` | • API connectivity<br>• JSON schema validation |
| `EINVOICE_GENERATED` | E-Invoice generated | → `SENT` | • IRN obtained<br>• QR code generated |
| `SENT` | Invoice sent to customer | → `PARTIALLY_PAID`<br>→ `PAID`<br>→ `OVERDUE` | • Customer receipt confirmation |
| `PARTIALLY_PAID` | Partial payment received | → `PAID`<br>→ `OVERDUE` | • Outstanding amount tracking |
| `PAID` | Fully paid invoice | → End state | • Payment reconciliation |
| `OVERDUE` | Payment overdue | → `PAID`<br>→ `CREDIT_NOTE_ISSUED` | • Interest calculation<br>• Follow-up actions |

### Business Rules
- **E-Invoice Threshold**: ₹5,00,000 for B2B transactions
- **Company Turnover**: All invoices if turnover >₹100 crores
- **Export Invoices**: E-Invoice mandatory regardless of amount
- **IRN Validity**: 24 hours to cancel after generation

## 5. Sales Return Workflow

### States & Transitions

| State | Description | Allowed Transitions | Validation Rules |
|-------|-------------|-------------------|------------------|
| `DRAFT` | Return request initiated | → `APPROVED`<br>→ `REJECTED` | • Return reason validation<br>• Return period check |
| `APPROVED` | Return approved | → `CREDIT_NOTE_ISSUED` | • Quality inspection<br>• Restocking feasibility |
| `CREDIT_NOTE_ISSUED` | Credit note generated | → `REFUNDED` | • E-Invoice for credit note<br>• GSTR-1 inclusion |
| `REFUNDED` | Amount refunded | → End state | • Payment processing |
| `REJECTED` | Return rejected | → End state | • Rejection reason documented |

### Business Rules
- **Return Period**: Within 30 days of delivery
- **Quality Check**: Mandatory for all returns
- **Credit Note E-Invoice**: Same threshold as original invoice

## 6. GSTR-1 Compilation Workflow

### States & Transitions

| State | Description | Allowed Transitions | Validation Rules |
|-------|-------------|-------------------|------------------|
| `DRAFT` | Data compilation started | → `READY` | • All invoices included<br>• HSN summary prepared |
| `READY` | Ready for review | → `FILED`<br>→ `DRAFT` (corrections) | • Data validation complete<br>• Reconciliation done |
| `FILED` | GSTR-1 filed | → End state | • Acknowledgment received<br>• Reference number obtained |

## Mandatory GST Validations by Document Type

### Sales Quotation
- [ ] Customer GSTIN format validation (if provided)
- [ ] HSN/SAC codes for all items
- [ ] Place of supply determination
- [ ] Tax rate validation per HSN/SAC

### Sales Order
- [ ] All quotation validations
- [ ] Stock availability
- [ ] Credit limit check
- [ ] Delivery terms clarity

### Delivery Challan
- [ ] Transportation details
- [ ] E-Way Bill threshold check
- [ ] Vehicle number format
- [ ] Distance calculation
- [ ] Consignee details

### Tax Invoice
- [ ] **Mandatory Fields per GST Rules:**
  - Supplier GSTIN, name, address
  - Customer GSTIN (if registered), name, address
  - Invoice number (sequential)
  - Invoice date
  - Place of supply
  - HSN/SAC codes
  - Quantity, unit, rate
  - Taxable value
  - Tax rates and amounts (CGST/SGST/IGST)
  - Total amount
  - Reverse charge indicator
  - Signature/digital signature

- [ ] **E-Invoice Specific:**
  - IRN (64-character alphanumeric)
  - QR code
  - Acknowledgment number and date
  - JSON schema compliance

### Credit/Debit Notes
- [ ] Reference to original invoice
- [ ] Reason for credit/debit
- [ ] Same GST treatment as original
- [ ] E-Invoice if applicable

## State Transition Functions

```sql
-- Function to transition quotation state
CREATE OR REPLACE FUNCTION transition_quotation_state(
    p_quotation_id UUID,
    p_new_state sales_document_status,
    p_user_id UUID,
    p_notes TEXT DEFAULT NULL
) RETURNS BOOLEAN AS $$
DECLARE
    v_current_state sales_document_status;
    v_valid_transition BOOLEAN := FALSE;
BEGIN
    -- Get current state
    SELECT status INTO v_current_state 
    FROM sales_quotations 
    WHERE id = p_quotation_id;
    
    -- Validate transition
    CASE v_current_state
        WHEN 'DRAFT' THEN
            v_valid_transition := p_new_state IN ('PENDING_APPROVAL');
        WHEN 'PENDING_APPROVAL' THEN
            v_valid_transition := p_new_state IN ('APPROVED', 'DRAFT');
        WHEN 'APPROVED' THEN
            v_valid_transition := p_new_state IN ('SENT');
        WHEN 'SENT' THEN
            v_valid_transition := p_new_state IN ('ACCEPTED', 'REJECTED', 'EXPIRED');
        WHEN 'ACCEPTED' THEN
            v_valid_transition := p_new_state IN ('CONVERTED');
        ELSE
            v_valid_transition := FALSE;
    END CASE;
    
    IF NOT v_valid_transition THEN
        RAISE EXCEPTION 'Invalid state transition from % to %', v_current_state, p_new_state;
    END IF;
    
    -- Update state
    UPDATE sales_quotations 
    SET 
        status = p_new_state,
        updated_at = NOW(),
        approved_by = CASE WHEN p_new_state = 'APPROVED' THEN p_user_id END,
        approved_at = CASE WHEN p_new_state = 'APPROVED' THEN NOW() END,
        sent_at = CASE WHEN p_new_state = 'SENT' THEN NOW() END
    WHERE id = p_quotation_id;
    
    -- Log state change
    INSERT INTO document_state_log (
        document_type, document_id, from_state, to_state, 
        changed_by, change_reason, changed_at
    ) VALUES (
        'QUOTATION', p_quotation_id, v_current_state::VARCHAR, 
        p_new_state::VARCHAR, p_user_id, p_notes, NOW()
    );
    
    RETURN TRUE;
END;
$$ LANGUAGE plpgsql;
```

## Integration Points

### With E-Invoice API
- **Trigger**: Invoice approval with amount ≥ ₹5L
- **Payload**: Standard GST JSON schema
- **Response**: IRN, QR code, acknowledgment
- **Error Handling**: Retry mechanism with exponential backoff

### With E-Way Bill API
- **Trigger**: Delivery challan with transportation
- **Payload**: Consignment details
- **Response**: E-Way Bill number and validity
- **Updates**: Vehicle tracking updates

### With GSTR-1 API
- **Trigger**: Monthly compilation
- **Data Sources**: Tax invoices, credit notes, amendments
- **Validation**: Schema compliance, HSN summary
- **Filing**: Direct API submission with acknowledgment

This workflow ensures complete GST compliance while maintaining operational efficiency and audit trails. 