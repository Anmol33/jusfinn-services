# GSTR-1 Generation & Validation System

## Overview
This system generates GSTR-1 data in the exact JSON format required by GSTN APIs, with comprehensive validation and reconciliation features.

## 1. GSTR-1 JSON Structure

### Complete GSTR-1 Schema
```json
{
  "gstin": "07AAACT2727Q1ZZ",
  "ret_period": "032024",
  "b2b": [
    {
      "ctin": "01AAAAP1208Q1ZS",
      "inv": [
        {
          "inum": "INV-2024-25-A-0001",
          "idt": "01-03-2024",
          "val": 100000.00,
          "pos": "07",
          "rchrg": "N",
          "etin": "01AAAAP1208Q1ZS",
          "itms": [
            {
              "num": 1,
              "itm_det": {
                "hsn_sc": "1001",
                "txval": 100000.00,
                "irt": 18.00,
                "iamt": 18000.00,
                "csamt": 0
              }
            }
          ]
        }
      ]
    }
  ],
  "b2cl": [],
  "b2cs": [],
  "cdnr": [],
  "cdnur": [],
  "exp": [],
  "at": [],
  "atadj": [],
  "exemp": [],
  "hsn": []
}
```

## 2. Database Functions for GSTR-1 Generation

### Main GSTR-1 Generation Function
```sql
-- Generate complete GSTR-1 JSON
CREATE OR REPLACE FUNCTION generate_gstr1_json(
    p_company_id UUID,
    p_period VARCHAR(7), -- MM-YYYY format
    p_include_amendments BOOLEAN DEFAULT FALSE
) RETURNS JSONB AS $$
DECLARE
    v_company RECORD;
    v_gstr1_json JSONB;
    v_ret_period VARCHAR(6);
BEGIN
    -- Get company details
    SELECT * INTO v_company FROM companies WHERE id = p_company_id;
    
    -- Convert period format MM-YYYY to MMYYYY
    v_ret_period := REPLACE(p_period, '-', '');
    
    -- Build main GSTR-1 structure
    v_gstr1_json := jsonb_build_object(
        'gstin', v_company.gstin,
        'ret_period', v_ret_period,
        'b2b', generate_b2b_data(p_company_id, p_period),
        'b2cl', generate_b2cl_data(p_company_id, p_period),
        'b2cs', generate_b2cs_data(p_company_id, p_period),
        'cdnr', generate_cdnr_data(p_company_id, p_period),
        'cdnur', generate_cdnur_data(p_company_id, p_period),
        'exp', generate_export_data(p_company_id, p_period),
        'at', generate_advance_tax_data(p_company_id, p_period),
        'atadj', generate_advance_adjustment_data(p_company_id, p_period),
        'exemp', generate_exempt_data(p_company_id, p_period),
        'hsn', generate_hsn_summary_data(p_company_id, p_period)
    );
    
    RETURN v_gstr1_json;
END;
$$ LANGUAGE plpgsql;
```

### B2B Data Generation
```sql
-- Generate B2B section (Business to Business invoices)
CREATE OR REPLACE FUNCTION generate_b2b_data(
    p_company_id UUID,
    p_period VARCHAR(7)
) RETURNS JSONB AS $$
DECLARE
    v_b2b_data JSONB := '[]'::jsonb;
    v_customer RECORD;
    v_customer_invoices JSONB;
BEGIN
    -- Group by customer GSTIN
    FOR v_customer IN 
        SELECT DISTINCT c.gstin as ctin
        FROM tax_invoices ti
        JOIN customers c ON ti.customer_id = c.id
        WHERE ti.company_id = p_company_id
        AND TO_CHAR(ti.invoice_date, 'MM-YYYY') = p_period
        AND ti.status NOT IN ('DRAFT', 'CANCELLED')
        AND c.gstin IS NOT NULL
        AND c.customer_category = 'REGULAR'
        AND ti.total_amount > 0
        ORDER BY c.gstin
    LOOP
        -- Get all invoices for this customer
        SELECT jsonb_agg(
            jsonb_build_object(
                'inum', ti.invoice_number,
                'idt', TO_CHAR(ti.invoice_date, 'DD-MM-YYYY'),
                'val', ROUND(ti.total_amount, 2),
                'pos', LPAD(s.code::TEXT, 2, '0'),
                'rchrg', CASE WHEN ti.reverse_charge_applicable THEN 'Y' ELSE 'N' END,
                'etin', c.gstin,
                'itms', generate_invoice_items_b2b(ti.id)
            ) ORDER BY ti.invoice_date, ti.invoice_number
        ) INTO v_customer_invoices
        FROM tax_invoices ti
        JOIN customers c ON ti.customer_id = c.id
        JOIN states s ON ti.place_of_supply_state_id = s.id
        WHERE ti.company_id = p_company_id
        AND TO_CHAR(ti.invoice_date, 'MM-YYYY') = p_period
        AND ti.status NOT IN ('DRAFT', 'CANCELLED')
        AND c.gstin = v_customer.ctin;
        
        -- Add customer data to B2B array
        v_b2b_data := v_b2b_data || jsonb_build_array(
            jsonb_build_object(
                'ctin', v_customer.ctin,
                'inv', v_customer_invoices
            )
        );
    END LOOP;
    
    RETURN v_b2b_data;
END;
$$ LANGUAGE plpgsql;
```

### Invoice Items Generation for B2B
```sql
-- Generate items array for B2B invoices
CREATE OR REPLACE FUNCTION generate_invoice_items_b2b(p_invoice_id UUID) 
RETURNS JSONB AS $$
DECLARE
    v_items JSONB;
BEGIN
    SELECT jsonb_agg(
        jsonb_build_object(
            'num', row_number() OVER (ORDER BY tii.id),
            'itm_det', jsonb_build_object(
                'hsn_sc', its.hsn_sac_code,
                'txval', ROUND(tii.taxable_amount, 2),
                'irt', CASE 
                    WHEN ti.place_of_supply_state_id = comp_state.id THEN tii.cgst_rate + tii.sgst_rate
                    ELSE tii.igst_rate 
                END,
                'iamt', ROUND(tii.igst_amount, 2),
                'camt', ROUND(tii.cgst_amount, 2),
                'samt', ROUND(tii.sgst_amount, 2),
                'csamt', ROUND(tii.cess_amount, 2)
            )
        ) ORDER BY tii.id
    ) INTO v_items
    FROM tax_invoice_items tii
    JOIN tax_invoices ti ON tii.invoice_id = ti.id
    JOIN items_services its ON tii.item_service_id = its.id
    JOIN companies comp ON ti.company_id = comp.id
    JOIN states comp_state ON comp.state_id = comp_state.id
    WHERE tii.invoice_id = p_invoice_id;
    
    RETURN COALESCE(v_items, '[]'::jsonb);
END;
$$ LANGUAGE plpgsql;
```

### B2CL Data Generation (B2C Large - >₹2.5 lakhs)
```sql
-- Generate B2CL section
CREATE OR REPLACE FUNCTION generate_b2cl_data(
    p_company_id UUID,
    p_period VARCHAR(7)
) RETURNS JSONB AS $$
DECLARE
    v_b2cl_data JSONB := '[]'::jsonb;
    v_pos_record RECORD;
    v_pos_invoices JSONB;
BEGIN
    -- Group by place of supply for B2C Large invoices (>2.5 lakhs)
    FOR v_pos_record IN 
        SELECT DISTINCT s.code as pos
        FROM tax_invoices ti
        JOIN customers c ON ti.customer_id = c.id
        JOIN states s ON ti.place_of_supply_state_id = s.id
        WHERE ti.company_id = p_company_id
        AND TO_CHAR(ti.invoice_date, 'MM-YYYY') = p_period
        AND ti.status NOT IN ('DRAFT', 'CANCELLED')
        AND (c.gstin IS NULL OR c.customer_category = 'UNREGISTERED')
        AND ti.total_amount >= 250000 -- ₹2.5 lakhs threshold
        ORDER BY s.code
    LOOP
        -- Get all B2CL invoices for this place of supply
        SELECT jsonb_agg(
            jsonb_build_object(
                'inum', ti.invoice_number,
                'idt', TO_CHAR(ti.invoice_date, 'DD-MM-YYYY'),
                'val', ROUND(ti.total_amount, 2),
                'etin', c.gstin,
                'itms', generate_invoice_items_b2cl(ti.id)
            ) ORDER BY ti.invoice_date, ti.invoice_number
        ) INTO v_pos_invoices
        FROM tax_invoices ti
        JOIN customers c ON ti.customer_id = c.id
        JOIN states s ON ti.place_of_supply_state_id = s.id
        WHERE ti.company_id = p_company_id
        AND TO_CHAR(ti.invoice_date, 'MM-YYYY') = p_period
        AND ti.status NOT IN ('DRAFT', 'CANCELLED')
        AND (c.gstin IS NULL OR c.customer_category = 'UNREGISTERED')
        AND ti.total_amount >= 250000
        AND s.code = v_pos_record.pos;
        
        -- Add to B2CL array
        v_b2cl_data := v_b2cl_data || jsonb_build_array(
            jsonb_build_object(
                'pos', LPAD(v_pos_record.pos::TEXT, 2, '0'),
                'inv', v_pos_invoices
            )
        );
    END LOOP;
    
    RETURN v_b2cl_data;
END;
$$ LANGUAGE plpgsql;
```

### B2CS Data Generation (B2C Small - consolidated)
```sql
-- Generate B2CS section (B2C Small - consolidated by state, rate, type)
CREATE OR REPLACE FUNCTION generate_b2cs_data(
    p_company_id UUID,
    p_period VARCHAR(7)
) RETURNS JSONB AS $$
DECLARE
    v_b2cs_data JSONB;
BEGIN
    SELECT jsonb_agg(
        jsonb_build_object(
            'sply_ty', supply_type,
            'pos', LPAD(pos::TEXT, 2, '0'),
            'typ', transaction_type,
            'txval', ROUND(total_taxable_value, 2),
            'rt', tax_rate,
            'iamt', ROUND(total_igst, 2),
            'camt', ROUND(total_cgst, 2),
            'samt', ROUND(total_sgst, 2),
            'csamt', ROUND(total_cess, 2)
        ) ORDER BY pos, tax_rate
    ) INTO v_b2cs_data
    FROM (
        SELECT 
            'INTER' as supply_type, -- Simplified for now
            s.code as pos,
            'OE' as transaction_type, -- OE = Others, E = Ecommerce
            SUM(tii.taxable_amount) as total_taxable_value,
            CASE 
                WHEN s.code = comp_state.code THEN tii.cgst_rate + tii.sgst_rate
                ELSE tii.igst_rate 
            END as tax_rate,
            SUM(tii.igst_amount) as total_igst,
            SUM(tii.cgst_amount) as total_cgst,
            SUM(tii.sgst_amount) as total_sgst,
            SUM(tii.cess_amount) as total_cess
        FROM tax_invoice_items tii
        JOIN tax_invoices ti ON tii.invoice_id = ti.id
        JOIN customers c ON ti.customer_id = c.id
        JOIN states s ON ti.place_of_supply_state_id = s.id
        JOIN companies comp ON ti.company_id = comp.id
        JOIN states comp_state ON comp.state_id = comp_state.id
        WHERE ti.company_id = p_company_id
        AND TO_CHAR(ti.invoice_date, 'MM-YYYY') = p_period
        AND ti.status NOT IN ('DRAFT', 'CANCELLED')
        AND (c.gstin IS NULL OR c.customer_category = 'UNREGISTERED')
        AND ti.total_amount < 250000 -- Below ₹2.5 lakhs
        GROUP BY s.code, comp_state.code, 
            CASE 
                WHEN s.code = comp_state.code THEN tii.cgst_rate + tii.sgst_rate
                ELSE tii.igst_rate 
            END,
            tii.cgst_rate, tii.sgst_rate, tii.igst_rate
        HAVING SUM(tii.taxable_amount) > 0
    ) consolidated;
    
    RETURN COALESCE(v_b2cs_data, '[]'::jsonb);
END;
$$ LANGUAGE plpgsql;
```

### Credit/Debit Notes (CDNR) Generation
```sql
-- Generate CDNR section (Credit/Debit Notes - Registered customers)
CREATE OR REPLACE FUNCTION generate_cdnr_data(
    p_company_id UUID,
    p_period VARCHAR(7)
) RETURNS JSONB AS $$
DECLARE
    v_cdnr_data JSONB := '[]'::jsonb;
    v_customer RECORD;
    v_customer_notes JSONB;
BEGIN
    FOR v_customer IN 
        SELECT DISTINCT c.gstin as ctin
        FROM credit_notes cn
        JOIN customers c ON cn.customer_id = c.id
        WHERE cn.company_id = p_company_id
        AND TO_CHAR(cn.note_date, 'MM-YYYY') = p_period
        AND cn.status NOT IN ('DRAFT', 'CANCELLED')
        AND c.gstin IS NOT NULL
        ORDER BY c.gstin
    LOOP
        SELECT jsonb_agg(
            jsonb_build_object(
                'ntty', 'C', -- C = Credit Note, D = Debit Note
                'nt_num', cn.note_number,
                'nt_dt', TO_CHAR(cn.note_date, 'DD-MM-YYYY'),
                'rsn', LEFT(cn.reason, 30), -- Reason (max 30 chars)
                'p_gst', 'Y', -- Pre-GST or not
                'itms', generate_credit_note_items(cn.id)
            ) ORDER BY cn.note_date, cn.note_number
        ) INTO v_customer_notes
        FROM credit_notes cn
        JOIN customers c ON cn.customer_id = c.id
        WHERE cn.company_id = p_company_id
        AND TO_CHAR(cn.note_date, 'MM-YYYY') = p_period
        AND cn.status NOT IN ('DRAFT', 'CANCELLED')
        AND c.gstin = v_customer.ctin;
        
        v_cdnr_data := v_cdnr_data || jsonb_build_array(
            jsonb_build_object(
                'ctin', v_customer.ctin,
                'nt', v_customer_notes
            )
        );
    END LOOP;
    
    RETURN v_cdnr_data;
END;
$$ LANGUAGE plpgsql;
```

### HSN Summary Generation
```sql
-- Generate HSN Summary
CREATE OR REPLACE FUNCTION generate_hsn_summary_data(
    p_company_id UUID,
    p_period VARCHAR(7)
) RETURNS JSONB AS $$
DECLARE
    v_hsn_data JSONB;
BEGIN
    SELECT jsonb_agg(
        jsonb_build_object(
            'num', row_number() OVER (ORDER BY hsn_sac_code),
            'hsn_sc', hsn_sac_code,
            'desc', LEFT(description, 30),
            'uqc', unit_code,
            'qty', ROUND(total_quantity, 3),
            'val', ROUND(total_value, 2),
            'txval', ROUND(total_taxable_value, 2),
            'iamt', ROUND(total_igst, 2),
            'camt', ROUND(total_cgst, 2),
            'samt', ROUND(total_sgst, 2),
            'csamt', ROUND(total_cess, 2)
        ) ORDER BY hsn_sac_code
    ) INTO v_hsn_data
    FROM (
        SELECT 
            its.hsn_sac_code,
            its.description,
            its.unit_of_measure as unit_code,
            SUM(tii.quantity) as total_quantity,
            SUM(tii.total_amount) as total_value,
            SUM(tii.taxable_amount) as total_taxable_value,
            SUM(tii.igst_amount) as total_igst,
            SUM(tii.cgst_amount) as total_cgst,
            SUM(tii.sgst_amount) as total_sgst,
            SUM(tii.cess_amount) as total_cess
        FROM tax_invoice_items tii
        JOIN tax_invoices ti ON tii.invoice_id = ti.id
        JOIN items_services its ON tii.item_service_id = its.id
        WHERE ti.company_id = p_company_id
        AND TO_CHAR(ti.invoice_date, 'MM-YYYY') = p_period
        AND ti.status NOT IN ('DRAFT', 'CANCELLED')
        AND its.type = 'PRODUCT'
        GROUP BY its.hsn_sac_code, its.description, its.unit_of_measure
        HAVING SUM(tii.taxable_value) > 0
    ) hsn_summary;
    
    RETURN COALESCE(v_hsn_data, '[]'::jsonb);
END;
$$ LANGUAGE plpgsql;
```

## 3. GSTR-1 Validation System

### Comprehensive Validation Function
```sql
-- Validate complete GSTR-1 data
CREATE OR REPLACE FUNCTION validate_gstr1_json(
    p_gstr1_json JSONB,
    p_company_id UUID,
    p_period VARCHAR(7)
) RETURNS TABLE (
    section VARCHAR(10),
    validation_type VARCHAR(50),
    is_valid BOOLEAN,
    error_count INTEGER,
    error_details JSONB
) AS $$
BEGIN
    -- Validate B2B Section
    RETURN QUERY SELECT 
        'B2B'::VARCHAR(10),
        'GSTIN_FORMAT'::VARCHAR(50),
        validate_b2b_gstins(p_gstr1_json->'b2b'),
        get_b2b_gstin_errors(p_gstr1_json->'b2b'),
        get_b2b_gstin_error_details(p_gstr1_json->'b2b');
    
    -- Validate Invoice Numbers
    RETURN QUERY SELECT 
        'B2B'::VARCHAR(10),
        'INVOICE_SEQUENCE'::VARCHAR(50),
        validate_invoice_sequence(p_company_id, p_period),
        get_sequence_gap_count(p_company_id, p_period),
        get_sequence_gap_details(p_company_id, p_period);
    
    -- Validate HSN Codes
    RETURN QUERY SELECT 
        'HSN'::VARCHAR(10),
        'HSN_FORMAT'::VARCHAR(50),
        validate_hsn_codes(p_gstr1_json->'hsn'),
        get_hsn_error_count(p_gstr1_json->'hsn'),
        get_hsn_error_details(p_gstr1_json->'hsn');
    
    -- Validate Tax Calculations
    RETURN QUERY SELECT 
        'ALL'::VARCHAR(10),
        'TAX_CALCULATION'::VARCHAR(50),
        validate_tax_calculations(p_gstr1_json),
        get_tax_calc_errors(p_gstr1_json),
        get_tax_calc_error_details(p_gstr1_json);
END;
$$ LANGUAGE plpgsql;

-- Validate B2B GSTIN formats
CREATE OR REPLACE FUNCTION validate_b2b_gstins(p_b2b_data JSONB) 
RETURNS BOOLEAN AS $$
DECLARE
    v_entry JSONB;
    v_invalid_count INTEGER := 0;
BEGIN
    FOR v_entry IN SELECT value FROM jsonb_array_elements(p_b2b_data)
    LOOP
        IF NOT validate_gstin(v_entry->>'ctin') THEN
            v_invalid_count := v_invalid_count + 1;
        END IF;
    END LOOP;
    
    RETURN v_invalid_count = 0;
END;
$$ LANGUAGE plpgsql;
```

## 4. GSTR-1 API Integration

### API Submission Function
```sql
-- Create GSTR-1 submission record
CREATE TABLE gstr1_submissions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    company_id UUID NOT NULL REFERENCES companies(id),
    return_period VARCHAR(7) NOT NULL,
    
    -- Submission Details
    submission_type VARCHAR(20) DEFAULT 'ORIGINAL' CHECK (submission_type IN ('ORIGINAL', 'AMENDMENT')),
    gstr1_json JSONB NOT NULL,
    
    -- API Details
    api_request_payload JSONB,
    api_response JSONB,
    reference_id VARCHAR(50),
    token VARCHAR(100),
    
    -- Status
    status VARCHAR(20) DEFAULT 'DRAFT' CHECK (status IN ('DRAFT', 'SUBMITTED', 'ACCEPTED', 'REJECTED', 'FILED')),
    submission_date TIMESTAMP WITH TIME ZONE,
    acknowledgment_number VARCHAR(50),
    filed_date TIMESTAMP WITH TIME ZONE,
    
    -- Validation
    validation_errors JSONB DEFAULT '[]',
    is_valid BOOLEAN DEFAULT FALSE,
    
    -- Audit
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    created_by UUID REFERENCES users(id),
    
    UNIQUE(company_id, return_period, submission_type)
);

-- Submit GSTR-1 Function
CREATE OR REPLACE FUNCTION submit_gstr1(
    p_company_id UUID,
    p_period VARCHAR(7),
    p_user_id UUID
) RETURNS JSONB AS $$
DECLARE
    v_gstr1_json JSONB;
    v_validation_result JSONB;
    v_submission_id UUID;
    v_result JSONB;
BEGIN
    -- Generate GSTR-1 JSON
    v_gstr1_json := generate_gstr1_json(p_company_id, p_period);
    
    -- Validate GSTR-1 data
    SELECT jsonb_agg(
        jsonb_build_object(
            'section', section,
            'validation_type', validation_type,
            'is_valid', is_valid,
            'error_count', error_count,
            'error_details', error_details
        )
    ) INTO v_validation_result
    FROM validate_gstr1_json(v_gstr1_json, p_company_id, p_period)
    WHERE NOT is_valid;
    
    -- Create submission record
    INSERT INTO gstr1_submissions (
        company_id, return_period, gstr1_json, validation_errors,
        is_valid, created_by
    ) VALUES (
        p_company_id, p_period, v_gstr1_json, 
        COALESCE(v_validation_result, '[]'::jsonb),
        (v_validation_result IS NULL OR jsonb_array_length(v_validation_result) = 0),
        p_user_id
    ) RETURNING id INTO v_submission_id;
    
    -- Return result
    SELECT jsonb_build_object(
        'submission_id', v_submission_id,
        'is_valid', (v_validation_result IS NULL OR jsonb_array_length(v_validation_result) = 0),
        'validation_errors', COALESCE(v_validation_result, '[]'::jsonb),
        'gstr1_json', v_gstr1_json
    ) INTO v_result;
    
    RETURN v_result;
END;
$$ LANGUAGE plpgsql;
```

## 5. Python Integration for API Calls

### Python Service for GSTN API Integration
```python
import json
import requests
from datetime import datetime
from typing import Dict, Any, Optional

class GSTR1APIService:
    def __init__(self, gstin: str, username: str, client_id: str, client_secret: str):
        self.gstin = gstin
        self.username = username
        self.client_id = client_id
        self.client_secret = client_secret
        self.base_url = "https://api.mastergst.com/gstapi/v1.1"  # Example API
        self.auth_token = None
    
    def authenticate(self) -> bool:
        """Authenticate with GSTN API"""
        auth_data = {
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "username": self.username,
            "gstin": self.gstin
        }
        
        response = requests.post(f"{self.base_url}/auth", json=auth_data)
        if response.status_code == 200:
            self.auth_token = response.json().get("auth_token")
            return True
        return False
    
    def submit_gstr1(self, gstr1_data: Dict[Any, Any], return_period: str) -> Dict[str, Any]:
        """Submit GSTR-1 data to GSTN"""
        if not self.auth_token:
            if not self.authenticate():
                return {"error": "Authentication failed"}
        
        headers = {
            "Authorization": f"Bearer {self.auth_token}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "gstin": self.gstin,
            "ret_period": return_period,
            "data": gstr1_data
        }
        
        try:
            response = requests.post(
                f"{self.base_url}/gstr1/save",
                headers=headers,
                json=payload,
                timeout=30
            )
            
            return {
                "status_code": response.status_code,
                "response": response.json(),
                "success": response.status_code == 200
            }
        except Exception as e:
            return {"error": str(e), "success": False}
    
    def file_gstr1(self, return_period: str) -> Dict[str, Any]:
        """File GSTR-1 return"""
        headers = {
            "Authorization": f"Bearer {self.auth_token}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "gstin": self.gstin,
            "ret_period": return_period
        }
        
        response = requests.post(
            f"{self.base_url}/gstr1/file",
            headers=headers,
            json=payload
        )
        
        return {
            "status_code": response.status_code,
            "response": response.json(),
            "success": response.status_code == 200
        }
    
    def get_filing_status(self, return_period: str) -> Dict[str, Any]:
        """Check GSTR-1 filing status"""
        headers = {"Authorization": f"Bearer {self.auth_token}"}
        
        response = requests.get(
            f"{self.base_url}/gstr1/status/{self.gstin}/{return_period}",
            headers=headers
        )
        
        return response.json() if response.status_code == 200 else {}
```

## 6. Usage Examples

### Generate and Submit GSTR-1
```sql
-- Example: Generate GSTR-1 for March 2024
SELECT submit_gstr1(
    '550e8400-e29b-41d4-a716-446655440000'::UUID, -- company_id
    '03-2024', -- period
    '550e8400-e29b-41d4-a716-446655440001'::UUID  -- user_id
);

-- Check validation results
SELECT 
    section,
    validation_type,
    is_valid,
    error_count,
    error_details
FROM validate_gstr1_json(
    generate_gstr1_json(
        '550e8400-e29b-41d4-a716-446655440000'::UUID,
        '03-2024'
    ),
    '550e8400-e29b-41d4-a716-446655440000'::UUID,
    '03-2024'
);
```

### API Integration Example
```python
# Example usage
api_service = GSTR1APIService(
    gstin="07AAACT2727Q1ZZ",
    username="test_user",
    client_id="your_client_id",
    client_secret="your_client_secret"
)

# Get GSTR-1 data from database
gstr1_data = get_gstr1_from_db(company_id, "03-2024")

# Submit to GSTN
result = api_service.submit_gstr1(gstr1_data, "032024")

if result["success"]:
    print("GSTR-1 submitted successfully")
    # File the return
    file_result = api_service.file_gstr1("032024")
    if file_result["success"]:
        print("GSTR-1 filed successfully")
else:
    print(f"Submission failed: {result.get('error')}")
```

This comprehensive GSTR-1 system ensures accurate data generation, thorough validation, and seamless API integration with GSTN portals. 