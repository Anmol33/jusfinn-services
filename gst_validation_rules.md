# GST Compliance Validations & Mandatory Checks

## Overview
This document outlines all mandatory validations required under GST law for different document types. These validations ensure legal compliance and prevent penalties during GST audits.

## 1. Sales Quotation Validations

### Basic Validations
- [ ] **Customer Information**
  - Customer name and address mandatory
  - GSTIN format validation (if provided): `^\d{2}[A-Z]{5}\d{4}[A-Z]{1}[A-Z\d]{1}[Z]{1}[A-Z\d]{1}$`
  - State code validation against GSTIN state code

- [ ] **Item/Service Validations**
  - HSN/SAC code mandatory for each item
  - HSN format: 4-8 digits for goods
  - SAC format: 6 digits for services
  - Valid GST rate for each HSN/SAC combination

- [ ] **Place of Supply**
  - Determined based on customer location
  - State code validation
  - Interstate vs intrastate classification

### SQL Validation Functions

```sql
-- GSTIN Format Validation
CREATE OR REPLACE FUNCTION validate_gstin(p_gstin VARCHAR(15)) 
RETURNS BOOLEAN AS $$
BEGIN
    IF p_gstin IS NULL OR LENGTH(p_gstin) != 15 THEN
        RETURN FALSE;
    END IF;
    
    -- GSTIN Pattern: 99AAAAA9999A9Z9
    RETURN p_gstin ~ '^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z]{1}[A-Z0-9]{1}[Z]{1}[A-Z0-9]{1}$';
END;
$$ LANGUAGE plpgsql;

-- HSN/SAC Code Validation
CREATE OR REPLACE FUNCTION validate_hsn_sac_rate(
    p_hsn_sac VARCHAR(10), 
    p_item_type VARCHAR(10),
    p_gst_rate DECIMAL(5,2)
) RETURNS BOOLEAN AS $$
DECLARE
    v_valid_rates DECIMAL(5,2)[];
BEGIN
    -- Standard GST rates
    v_valid_rates := ARRAY[0, 0.25, 3, 5, 12, 18, 28];
    
    -- Validate code format
    IF p_item_type = 'GOODS' AND NOT (p_hsn_sac ~ '^[0-9]{4,8}$') THEN
        RETURN FALSE;
    END IF;
    
    IF p_item_type = 'SERVICES' AND NOT (p_hsn_sac ~ '^[0-9]{6}$') THEN
        RETURN FALSE;
    END IF;
    
    -- Validate rate
    RETURN p_gst_rate = ANY(v_valid_rates);
END;
$$ LANGUAGE plpgsql;

-- Place of Supply Validation
CREATE OR REPLACE FUNCTION determine_place_of_supply(
    p_supplier_state_id INTEGER,
    p_customer_state_id INTEGER,
    p_supply_type VARCHAR(10)
) RETURNS RECORD AS $$
DECLARE
    v_result RECORD;
BEGIN
    SELECT 
        CASE 
            WHEN p_supplier_state_id = p_customer_state_id THEN 'INTRASTATE'
            ELSE 'INTERSTATE'
        END as transaction_type,
        CASE 
            WHEN p_supplier_state_id = p_customer_state_id THEN 'CGST_SGST'
            ELSE 'IGST'
        END as tax_type,
        p_customer_state_id as place_of_supply_state_id
    INTO v_result;
    
    RETURN v_result;
END;
$$ LANGUAGE plpgsql;
```

## 2. Sales Order Validations

### Enhanced Validations (All Quotation + Additional)
- [ ] **Stock Availability**
  - Real-time stock check for each item
  - Reserved quantity consideration
  - Negative stock prevention

- [ ] **Credit Limit Validation**
  - Customer outstanding amount check
  - Credit limit vs order value validation
  - Payment terms validation

- [ ] **Delivery Terms**
  - Delivery address completeness
  - Transportation requirements
  - Expected delivery date validation

```sql
-- Stock Availability Check
CREATE OR REPLACE FUNCTION check_stock_availability(
    p_company_id UUID,
    p_items JSONB -- Array of {item_id, quantity, warehouse_id}
) RETURNS TABLE (
    item_id UUID,
    available_quantity DECIMAL(15,3),
    required_quantity DECIMAL(15,3),
    shortage_quantity DECIMAL(15,3),
    is_available BOOLEAN
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        (item->>'item_id')::UUID,
        COALESCE(cs.current_quantity, 0),
        (item->>'quantity')::DECIMAL(15,3),
        GREATEST(0, (item->>'quantity')::DECIMAL(15,3) - COALESCE(cs.current_quantity, 0)),
        COALESCE(cs.current_quantity, 0) >= (item->>'quantity')::DECIMAL(15,3)
    FROM jsonb_array_elements(p_items) AS item
    LEFT JOIN current_stock cs ON cs.item_service_id = (item->>'item_id')::UUID
        AND cs.company_id = p_company_id
        AND cs.warehouse_id = COALESCE((item->>'warehouse_id')::UUID, 
            (SELECT id FROM warehouses WHERE company_id = p_company_id AND is_default = TRUE));
END;
$$ LANGUAGE plpgsql;

-- Credit Limit Check
CREATE OR REPLACE FUNCTION check_credit_limit(
    p_customer_id UUID,
    p_order_amount DECIMAL(15,2)
) RETURNS RECORD AS $$
DECLARE
    v_result RECORD;
    v_outstanding DECIMAL(15,2);
    v_credit_limit DECIMAL(15,2);
BEGIN
    -- Get customer credit limit
    SELECT credit_limit INTO v_credit_limit 
    FROM customers 
    WHERE id = p_customer_id;
    
    -- Calculate outstanding amount
    SELECT COALESCE(SUM(outstanding_amount), 0) INTO v_outstanding
    FROM tax_invoices 
    WHERE customer_id = p_customer_id 
    AND status NOT IN ('PAID', 'CANCELLED');
    
    SELECT 
        v_credit_limit as credit_limit,
        v_outstanding as current_outstanding,
        p_order_amount as order_amount,
        (v_outstanding + p_order_amount) as total_exposure,
        CASE 
            WHEN v_credit_limit IS NULL THEN TRUE -- No limit set
            WHEN (v_outstanding + p_order_amount) <= v_credit_limit THEN TRUE
            ELSE FALSE
        END as credit_approved
    INTO v_result;
    
    RETURN v_result;
END;
$$ LANGUAGE plpgsql;
```

## 3. Delivery Challan Validations

### Transportation & E-Way Bill Requirements
- [ ] **Transportation Details**
  - Transporter name and GSTIN (if applicable)
  - Vehicle number format validation
  - LR number (if applicable)
  - Transportation mode validation

- [ ] **E-Way Bill Mandatory Conditions**
  - Inter-state goods movement >₹50,000
  - Intra-state goods movement >₹1,00,000 (varies by state)
  - Distance >10 km for goods transportation

- [ ] **Consignment Details**
  - Dispatch and delivery addresses
  - HSN-wise quantity and value
  - Proper goods description

```sql
-- E-Way Bill Applicability Check
CREATE OR REPLACE FUNCTION check_eway_bill_requirement(
    p_supplier_state_id INTEGER,
    p_customer_state_id INTEGER,
    p_total_value DECIMAL(15,2),
    p_transportation_distance INTEGER
) RETURNS RECORD AS $$
DECLARE
    v_result RECORD;
    v_is_interstate BOOLEAN;
    v_threshold DECIMAL(15,2);
BEGIN
    v_is_interstate := (p_supplier_state_id != p_customer_state_id);
    
    -- Set threshold based on transaction type
    v_threshold := CASE 
        WHEN v_is_interstate THEN 50000 -- ₹50,000 for interstate
        ELSE 100000 -- ₹1,00,000 for intrastate (varies by state)
    END;
    
    SELECT 
        v_is_interstate as is_interstate,
        v_threshold as threshold_amount,
        p_total_value as invoice_value,
        p_transportation_distance as distance_km,
        CASE 
            WHEN p_total_value >= v_threshold AND p_transportation_distance > 10 THEN TRUE
            ELSE FALSE
        END as eway_bill_required
    INTO v_result;
    
    RETURN v_result;
END;
$$ LANGUAGE plpgsql;

-- Vehicle Number Validation
CREATE OR REPLACE FUNCTION validate_vehicle_number(p_vehicle_number VARCHAR(20)) 
RETURNS BOOLEAN AS $$
BEGIN
    -- Indian vehicle number format: XX99XX9999 or XX99X9999
    RETURN p_vehicle_number ~ '^[A-Z]{2}[0-9]{2}[A-Z]{1,2}[0-9]{4}$';
END;
$$ LANGUAGE plpgsql;
```

## 4. Tax Invoice Validations (Most Critical)

### Mandatory Fields as per Section 31 of CGST Act
- [ ] **Supplier Details (Section 31(3)(a))**
  - Name, address, and GSTIN of supplier
  - State name and state code

- [ ] **Recipient Details (Section 31(3)(b))**
  - Name and address of recipient
  - GSTIN of recipient (if registered)
  - State name and state code of place of supply

- [ ] **Invoice Details (Section 31(3)(c))**
  - Serial number (unique within financial year)
  - Date of issue
  - Value of supply
  - Description of goods/services
  - HSN/SAC code
  - Unit of measurement, quantity, rate per unit
  - Taxable value
  - Tax rate and tax amount (CGST, SGST/IGST, Cess)
  - Place of supply with state name/code
  - Reverse charge indication (if applicable)
  - Signature/digital signature

### E-Invoice Specific Validations
- [ ] **Mandatory for B2B invoices ≥₹5,00,000**
- [ ] **All invoices for companies with turnover >₹100 crores**
- [ ] **JSON Schema compliance with GSTN specifications**
- [ ] **IRN generation within 24 hours**

```sql
-- Comprehensive Invoice Validation
CREATE OR REPLACE FUNCTION validate_tax_invoice(p_invoice_id UUID) 
RETURNS TABLE (
    validation_type VARCHAR(50),
    is_valid BOOLEAN,
    error_message TEXT
) AS $$
DECLARE
    v_invoice RECORD;
    v_supplier RECORD;
    v_customer RECORD;
    v_items_count INTEGER;
BEGIN
    -- Get invoice details
    SELECT ti.*, c.gstin as supplier_gstin, c.legal_name as supplier_name
    INTO v_invoice
    FROM tax_invoices ti
    JOIN companies c ON ti.company_id = c.id
    WHERE ti.id = p_invoice_id;
    
    -- Get customer details
    SELECT * INTO v_customer
    FROM customers
    WHERE id = v_invoice.customer_id;
    
    -- Validation 1: Invoice Number
    RETURN QUERY SELECT 
        'INVOICE_NUMBER'::VARCHAR(50),
        (v_invoice.invoice_number IS NOT NULL AND LENGTH(v_invoice.invoice_number) > 0),
        CASE WHEN v_invoice.invoice_number IS NULL THEN 'Invoice number is mandatory' ELSE NULL END;
    
    -- Validation 2: Invoice Date
    RETURN QUERY SELECT 
        'INVOICE_DATE'::VARCHAR(50),
        (v_invoice.invoice_date IS NOT NULL),
        CASE WHEN v_invoice.invoice_date IS NULL THEN 'Invoice date is mandatory' ELSE NULL END;
    
    -- Validation 3: Supplier GSTIN
    RETURN QUERY SELECT 
        'SUPPLIER_GSTIN'::VARCHAR(50),
        validate_gstin(v_invoice.supplier_gstin),
        CASE WHEN NOT validate_gstin(v_invoice.supplier_gstin) THEN 'Invalid supplier GSTIN format' ELSE NULL END;
    
    -- Validation 4: Customer GSTIN (if provided)
    RETURN QUERY SELECT 
        'CUSTOMER_GSTIN'::VARCHAR(50),
        (v_customer.gstin IS NULL OR validate_gstin(v_customer.gstin)),
        CASE WHEN v_customer.gstin IS NOT NULL AND NOT validate_gstin(v_customer.gstin) 
            THEN 'Invalid customer GSTIN format' ELSE NULL END;
    
    -- Validation 5: Place of Supply
    RETURN QUERY SELECT 
        'PLACE_OF_SUPPLY'::VARCHAR(50),
        (v_invoice.place_of_supply_state_id IS NOT NULL),
        CASE WHEN v_invoice.place_of_supply_state_id IS NULL THEN 'Place of supply is mandatory' ELSE NULL END;
    
    -- Validation 6: HSN/SAC Codes for all items
    SELECT COUNT(*) INTO v_items_count
    FROM tax_invoice_items tii
    JOIN items_services its ON tii.item_service_id = its.id
    WHERE tii.invoice_id = p_invoice_id
    AND (its.hsn_sac_code IS NULL OR LENGTH(its.hsn_sac_code) < 4);
    
    RETURN QUERY SELECT 
        'HSN_SAC_CODES'::VARCHAR(50),
        (v_items_count = 0),
        CASE WHEN v_items_count > 0 THEN 'HSN/SAC codes missing for some items' ELSE NULL END;
    
    -- Validation 7: GST Calculation Accuracy
    RETURN QUERY SELECT 
        'GST_CALCULATION'::VARCHAR(50),
        validate_gst_calculation(p_invoice_id),
        CASE WHEN NOT validate_gst_calculation(p_invoice_id) THEN 'GST calculation errors found' ELSE NULL END;
    
    -- Validation 8: E-Invoice Requirement
    IF is_einvoice_applicable(v_invoice.total_amount, v_customer.gstin, NULL) THEN
        RETURN QUERY SELECT 
            'EINVOICE_REQUIRED'::VARCHAR(50),
            (v_invoice.irn IS NOT NULL),
            CASE WHEN v_invoice.irn IS NULL THEN 'E-Invoice generation mandatory for this transaction' ELSE NULL END;
    END IF;
END;
$$ LANGUAGE plpgsql;

-- GST Calculation Validation
CREATE OR REPLACE FUNCTION validate_gst_calculation(p_invoice_id UUID) 
RETURNS BOOLEAN AS $$
DECLARE
    v_calculated RECORD;
    v_invoice RECORD;
    v_tolerance DECIMAL := 0.01; -- ₹0.01 tolerance for rounding
BEGIN
    -- Get invoice totals
    SELECT * INTO v_invoice FROM tax_invoices WHERE id = p_invoice_id;
    
    -- Calculate expected amounts
    SELECT 
        SUM(tii.taxable_amount) as calc_subtotal,
        SUM(tii.cgst_amount) as calc_cgst,
        SUM(tii.sgst_amount) as calc_sgst,
        SUM(tii.igst_amount) as calc_igst,
        SUM(tii.cess_amount) as calc_cess,
        SUM(tii.total_amount) as calc_total
    INTO v_calculated
    FROM tax_invoice_items tii
    WHERE tii.invoice_id = p_invoice_id;
    
    -- Validate with tolerance
    RETURN (
        ABS(v_invoice.subtotal - v_calculated.calc_subtotal) <= v_tolerance AND
        ABS(v_invoice.cgst_amount - v_calculated.calc_cgst) <= v_tolerance AND
        ABS(v_invoice.sgst_amount - v_calculated.calc_sgst) <= v_tolerance AND
        ABS(v_invoice.igst_amount - v_calculated.calc_igst) <= v_tolerance AND
        ABS(v_invoice.cess_amount - v_calculated.calc_cess) <= v_tolerance AND
        ABS(v_invoice.total_amount - v_calculated.calc_total) <= v_tolerance
    );
END;
$$ LANGUAGE plpgsql;
```

## 5. Credit/Debit Note Validations

### Mandatory Requirements
- [ ] **Reference to Original Invoice**
  - Original invoice number and date
  - Original invoice GSTIN validation
  - Reason for credit/debit note

- [ ] **Same GST Treatment**
  - Same HSN/SAC codes as original
  - Same tax rates as original
  - Correct tax calculation

- [ ] **E-Invoice Applicability**
  - Same threshold rules as invoices
  - IRN generation if required

```sql
-- Credit Note Validation
CREATE OR REPLACE FUNCTION validate_credit_note(p_credit_note_id UUID) 
RETURNS TABLE (
    validation_type VARCHAR(50),
    is_valid BOOLEAN,
    error_message TEXT
) AS $$
DECLARE
    v_credit_note RECORD;
    v_original_invoice RECORD;
BEGIN
    -- Get credit note details
    SELECT cn.*, ti.invoice_number as original_invoice_number
    INTO v_credit_note
    FROM credit_notes cn
    LEFT JOIN tax_invoices ti ON cn.original_invoice_id = ti.id
    WHERE cn.id = p_credit_note_id;
    
    -- Validation 1: Original Invoice Reference
    RETURN QUERY SELECT 
        'ORIGINAL_INVOICE_REF'::VARCHAR(50),
        (v_credit_note.original_invoice_id IS NOT NULL),
        CASE WHEN v_credit_note.original_invoice_id IS NULL THEN 'Original invoice reference is mandatory' ELSE NULL END;
    
    -- Validation 2: Credit Note Reason
    RETURN QUERY SELECT 
        'CREDIT_NOTE_REASON'::VARCHAR(50),
        (v_credit_note.reason IS NOT NULL AND LENGTH(v_credit_note.reason) > 0),
        CASE WHEN v_credit_note.reason IS NULL THEN 'Credit note reason is mandatory' ELSE NULL END;
    
    -- Validation 3: HSN/SAC Consistency
    RETURN QUERY SELECT 
        'HSN_SAC_CONSISTENCY'::VARCHAR(50),
        validate_credit_note_hsn_consistency(p_credit_note_id),
        CASE WHEN NOT validate_credit_note_hsn_consistency(p_credit_note_id) 
            THEN 'HSN/SAC codes must match original invoice' ELSE NULL END;
END;
$$ LANGUAGE plpgsql;
```

## 6. GSTR-1 Compilation Validations

### Data Completeness
- [ ] **All Invoices Included**
  - No missing invoice numbers in sequence
  - All amendments captured
  - Cancelled invoices properly marked

- [ ] **HSN Summary Accuracy**
  - HSN-wise quantity and value totals
  - Tax rate-wise breakup
  - UOM consistency

```sql
-- GSTR-1 Data Validation
CREATE OR REPLACE FUNCTION validate_gstr1_data(
    p_company_id UUID,
    p_period VARCHAR(7) -- MM-YYYY
) RETURNS TABLE (
    validation_type VARCHAR(50),
    record_count INTEGER,
    error_count INTEGER,
    error_details JSONB
) AS $$
BEGIN
    -- B2B Invoice Validation
    RETURN QUERY
    WITH b2b_issues AS (
        SELECT ti.id, ti.invoice_number,
            CASE 
                WHEN c.gstin IS NULL THEN 'Missing customer GSTIN'
                WHEN NOT validate_gstin(c.gstin) THEN 'Invalid customer GSTIN'
                WHEN ti.place_of_supply_state_id IS NULL THEN 'Missing place of supply'
                ELSE NULL
            END as issue
        FROM tax_invoices ti
        JOIN customers c ON ti.customer_id = c.id
        WHERE ti.company_id = p_company_id
        AND TO_CHAR(ti.invoice_date, 'MM-YYYY') = p_period
        AND ti.status NOT IN ('DRAFT', 'CANCELLED')
        AND ti.total_amount > 0
    )
    SELECT 
        'B2B_INVOICES'::VARCHAR(50),
        (SELECT COUNT(*) FROM b2b_issues)::INTEGER,
        (SELECT COUNT(*) FROM b2b_issues WHERE issue IS NOT NULL)::INTEGER,
        (SELECT jsonb_agg(jsonb_build_object('invoice', invoice_number, 'issue', issue)) 
         FROM b2b_issues WHERE issue IS NOT NULL);
    
    -- HSN Summary Validation
    RETURN QUERY
    WITH hsn_summary AS (
        SELECT 
            its.hsn_sac_code,
            COUNT(DISTINCT ti.id) as invoice_count,
            SUM(tii.quantity) as total_quantity,
            SUM(tii.taxable_amount) as total_value,
            its.unit_of_measure,
            COUNT(DISTINCT its.unit_of_measure) as uom_variants
        FROM tax_invoice_items tii
        JOIN tax_invoices ti ON tii.invoice_id = ti.id
        JOIN items_services its ON tii.item_service_id = its.id
        WHERE ti.company_id = p_company_id
        AND TO_CHAR(ti.invoice_date, 'MM-YYYY') = p_period
        AND ti.status NOT IN ('DRAFT', 'CANCELLED')
        GROUP BY its.hsn_sac_code, its.unit_of_measure
        HAVING COUNT(DISTINCT its.unit_of_measure) > 1 -- Multiple UOMs for same HSN
    )
    SELECT 
        'HSN_SUMMARY'::VARCHAR(50),
        (SELECT COUNT(DISTINCT hsn_sac_code) FROM hsn_summary)::INTEGER,
        (SELECT COUNT(*) FROM hsn_summary WHERE uom_variants > 1)::INTEGER,
        (SELECT jsonb_agg(jsonb_build_object('hsn', hsn_sac_code, 'uom_variants', uom_variants)) 
         FROM hsn_summary WHERE uom_variants > 1);
END;
$$ LANGUAGE plpgsql;
```

## 7. Real-time Validation Triggers

```sql
-- Trigger to validate invoice on save
CREATE OR REPLACE FUNCTION trigger_validate_invoice() RETURNS TRIGGER AS $$
DECLARE
    v_validation RECORD;
    v_errors TEXT[] := '{}';
BEGIN
    -- Run validations
    FOR v_validation IN SELECT * FROM validate_tax_invoice(NEW.id) WHERE NOT is_valid
    LOOP
        v_errors := array_append(v_errors, v_validation.error_message);
    END LOOP;
    
    -- Prevent save if critical errors found
    IF array_length(v_errors, 1) > 0 AND NEW.status != 'DRAFT' THEN
        RAISE EXCEPTION 'Invoice validation failed: %', array_to_string(v_errors, ', ');
    END IF;
    
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_invoice_validation 
    BEFORE INSERT OR UPDATE ON tax_invoices 
    FOR EACH ROW 
    EXECUTE FUNCTION trigger_validate_invoice();
```

## 8. Validation Summary Dashboard

```sql
-- Create validation summary view
CREATE VIEW gst_compliance_summary AS
SELECT 
    c.legal_name as company_name,
    DATE_TRUNC('month', ti.invoice_date) as period,
    COUNT(*) as total_invoices,
    COUNT(*) FILTER (WHERE validate_gstin(cust.gstin) OR cust.gstin IS NULL) as valid_gstin_count,
    COUNT(*) FILTER (WHERE ti.irn IS NOT NULL AND ti.total_amount >= 500000) as einvoice_generated,
    COUNT(*) FILTER (WHERE ti.total_amount >= 500000 AND ti.irn IS NULL) as einvoice_pending,
    SUM(ti.total_amount) as total_invoice_value,
    COUNT(*) FILTER (WHERE ti.status = 'DRAFT') as draft_invoices
FROM tax_invoices ti
JOIN companies c ON ti.company_id = c.id
JOIN customers cust ON ti.customer_id = cust.id
WHERE ti.created_at >= CURRENT_DATE - INTERVAL '12 months'
GROUP BY c.id, c.legal_name, DATE_TRUNC('month', ti.invoice_date)
ORDER BY period DESC, company_name;
```

This comprehensive validation framework ensures that all GST compliance requirements are met at each stage of the sales workflow, preventing issues during GST returns filing and audits. 