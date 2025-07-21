# GST-Compliant Invoice Numbering Strategy

## Overview

GST law mandates that invoice numbers must be:
1. **Sequential** - No gaps in the sequence
2. **Unique** - Within each financial year
3. **Chronological** - Reflect date order (with some flexibility)
4. **Persistent** - Cannot be changed once issued
5. **Series-based** - Can have multiple series per document type

## Numbering Scheme Design

### 1. Multi-Series Support

```
Format: {PREFIX}-{FINANCIAL_YEAR}-{SERIES_CODE}-{SEQUENCE}
Example: INV-2024-25-A-0001
```

| Component | Description | Example | Rules |
|-----------|-------------|---------|-------|
| PREFIX | Document type identifier | INV, QUO, SO, DC, CN | 2-4 characters |
| FINANCIAL_YEAR | FY in short format | 24-25, 25-26 | YY-YY format |
| SERIES_CODE | Optional series identifier | A, B, MUM, DEL | 1-3 characters |
| SEQUENCE | Sequential number | 0001, 0002 | Zero-padded, configurable length |

### 2. Document Type Prefixes

| Document Type | Prefix | Series Examples |
|---------------|--------|-----------------|
| Tax Invoice | INV | INV-24-25-A-0001 |
| Sales Quotation | QUO | QUO-24-25-A-0001 |
| Sales Order | SO | SO-24-25-A-0001 |
| Delivery Challan | DC | DC-24-25-A-0001 |
| Credit Note | CN | CN-24-25-A-0001 |
| Debit Note | DN | DN-24-25-A-0001 |
| Purchase Order | PO | PO-24-25-A-0001 |
| Receipt | RCP | RCP-24-25-A-0001 |

### 3. Series Configuration

```sql
-- Enhanced invoice_series table structure
CREATE TABLE invoice_series (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    company_id UUID NOT NULL REFERENCES companies(id),
    
    -- Series Identification
    series_name VARCHAR(50) NOT NULL, -- TAX_INVOICE, QUOTATION, etc.
    series_code VARCHAR(10) NOT NULL, -- A, B, MUM, DEL, etc.
    prefix VARCHAR(10) NOT NULL, -- INV, QUO, SO, etc.
    suffix VARCHAR(10) DEFAULT '',
    
    -- Numbering Configuration
    current_number INTEGER NOT NULL DEFAULT 1,
    min_number INTEGER DEFAULT 1,
    max_number INTEGER DEFAULT 999999,
    number_length INTEGER DEFAULT 4, -- Zero-padding length
    
    -- Format Template
    number_format VARCHAR(100) NOT NULL, -- Template for generation
    sample_number VARCHAR(50), -- Generated sample for preview
    
    -- Scope & Validity
    financial_year VARCHAR(9) NOT NULL, -- 2024-2025
    location_code VARCHAR(10), -- Branch/location specific
    
    -- Configuration
    is_default BOOLEAN DEFAULT FALSE,
    is_active BOOLEAN DEFAULT TRUE,
    auto_increment BOOLEAN DEFAULT TRUE,
    allow_manual_override BOOLEAN DEFAULT FALSE,
    
    -- Date-based numbering
    reset_frequency VARCHAR(10) DEFAULT 'YEARLY' 
        CHECK (reset_frequency IN ('NEVER', 'YEARLY', 'MONTHLY', 'DAILY')),
    last_reset_date DATE,
    
    -- Compliance
    gst_compliant BOOLEAN DEFAULT TRUE,
    sequence_validation BOOLEAN DEFAULT TRUE,
    
    -- Audit
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    created_by UUID REFERENCES users(id),
    
    UNIQUE(company_id, series_name, series_code, financial_year)
);
```

### 4. Advanced Number Generation Function

```sql
CREATE OR REPLACE FUNCTION generate_document_number(
    p_company_id UUID,
    p_series_name VARCHAR(50),
    p_series_code VARCHAR(10) DEFAULT 'A',
    p_document_date DATE DEFAULT CURRENT_DATE,
    p_manual_number INTEGER DEFAULT NULL
) RETURNS VARCHAR(100) AS $$
DECLARE
    v_series_record RECORD;
    v_next_number INTEGER;
    v_formatted_number VARCHAR(100);
    v_financial_year VARCHAR(9);
    v_date_part VARCHAR(20);
    v_lock_acquired BOOLEAN := FALSE;
BEGIN
    -- Determine financial year
    SELECT get_financial_year(p_document_date) INTO v_financial_year;
    
    -- Acquire advisory lock for this series to prevent concurrent issues
    SELECT pg_try_advisory_lock(
        hashtext(p_company_id::TEXT || p_series_name || p_series_code || v_financial_year)
    ) INTO v_lock_acquired;
    
    IF NOT v_lock_acquired THEN
        RAISE EXCEPTION 'Could not acquire lock for number generation. Please retry.';
    END IF;
    
    BEGIN
        -- Get series configuration
        SELECT * INTO v_series_record
        FROM invoice_series 
        WHERE company_id = p_company_id 
        AND series_name = p_series_name 
        AND series_code = p_series_code
        AND financial_year = v_financial_year
        AND is_active = TRUE;
        
        IF NOT FOUND THEN
            RAISE EXCEPTION 'Active invoice series not found: % - % - %', 
                p_series_name, p_series_code, v_financial_year;
        END IF;
        
        -- Handle reset frequency
        IF v_series_record.reset_frequency != 'NEVER' THEN
            PERFORM handle_series_reset(v_series_record.id, p_document_date);
            -- Refresh record after potential reset
            SELECT * INTO v_series_record FROM invoice_series WHERE id = v_series_record.id;
        END IF;
        
        -- Determine next number
        IF p_manual_number IS NOT NULL AND v_series_record.allow_manual_override THEN
            -- Validate manual number
            IF p_manual_number < v_series_record.min_number OR 
               p_manual_number > v_series_record.max_number THEN
                RAISE EXCEPTION 'Manual number % is outside allowed range % - %',
                    p_manual_number, v_series_record.min_number, v_series_record.max_number;
            END IF;
            
            -- Check if number already used
            IF EXISTS (
                SELECT 1 FROM document_numbers 
                WHERE series_id = v_series_record.id 
                AND sequence_number = p_manual_number
            ) THEN
                RAISE EXCEPTION 'Manual number % already exists in series', p_manual_number;
            END IF;
            
            v_next_number := p_manual_number;
            
            -- Update current_number if manual number is higher
            IF p_manual_number >= v_series_record.current_number THEN
                UPDATE invoice_series 
                SET current_number = p_manual_number + 1
                WHERE id = v_series_record.id;
            END IF;
        ELSE
            -- Auto-increment
            v_next_number := v_series_record.current_number;
            
            -- Validate against max number
            IF v_next_number > v_series_record.max_number THEN
                RAISE EXCEPTION 'Sequence exhausted. Maximum number % reached for series %',
                    v_series_record.max_number, v_series_record.series_name;
            END IF;
            
            -- Update current number
            UPDATE invoice_series 
            SET current_number = current_number + 1,
                updated_at = NOW()
            WHERE id = v_series_record.id;
        END IF;
        
        -- Generate formatted number
        v_formatted_number := v_series_record.number_format;
        
        -- Replace placeholders
        v_formatted_number := REPLACE(v_formatted_number, '{PREFIX}', v_series_record.prefix);
        v_formatted_number := REPLACE(v_formatted_number, '{FY}', v_financial_year);
        v_formatted_number := REPLACE(v_formatted_number, '{SERIES}', v_series_record.series_code);
        
        -- Date-based replacements
        v_formatted_number := REPLACE(v_formatted_number, '{YYYY}', EXTRACT(YEAR FROM p_document_date)::TEXT);
        v_formatted_number := REPLACE(v_formatted_number, '{MM}', LPAD(EXTRACT(MONTH FROM p_document_date)::TEXT, 2, '0'));
        v_formatted_number := REPLACE(v_formatted_number, '{DD}', LPAD(EXTRACT(DAY FROM p_document_date)::TEXT, 2, '0'));
        
        -- Number formatting
        v_formatted_number := REPLACE(v_formatted_number, '{NNNNNN}', 
            LPAD(v_next_number::TEXT, v_series_record.number_length, '0'));
        v_formatted_number := REPLACE(v_formatted_number, '{NNNNN}', 
            LPAD(v_next_number::TEXT, LEAST(5, v_series_record.number_length), '0'));
        v_formatted_number := REPLACE(v_formatted_number, '{NNNN}', 
            LPAD(v_next_number::TEXT, LEAST(4, v_series_record.number_length), '0'));
        v_formatted_number := REPLACE(v_formatted_number, '{NNN}', 
            LPAD(v_next_number::TEXT, LEAST(3, v_series_record.number_length), '0'));
        
        -- Add suffix
        v_formatted_number := v_formatted_number || v_series_record.suffix;
        
        -- Record the generated number
        INSERT INTO document_numbers (
            series_id, sequence_number, formatted_number, 
            document_date, generated_at, is_manual
        ) VALUES (
            v_series_record.id, v_next_number, v_formatted_number,
            p_document_date, NOW(), (p_manual_number IS NOT NULL)
        );
        
        -- Release lock
        PERFORM pg_advisory_unlock(
            hashtext(p_company_id::TEXT || p_series_name || p_series_code || v_financial_year)
        );
        
        RETURN v_formatted_number;
        
    EXCEPTION
        WHEN OTHERS THEN
            -- Ensure lock is released on error
            PERFORM pg_advisory_unlock(
                hashtext(p_company_id::TEXT || p_series_name || p_series_code || v_financial_year)
            );
            RAISE;
    END;
END;
$$ LANGUAGE plpgsql;
```

### 5. Document Number Tracking

```sql
-- Track all generated numbers for audit and validation
CREATE TABLE document_numbers (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    series_id UUID NOT NULL REFERENCES invoice_series(id),
    sequence_number INTEGER NOT NULL,
    formatted_number VARCHAR(100) NOT NULL,
    
    -- Document Details
    document_type VARCHAR(20) NOT NULL,
    document_id UUID, -- Reference to actual document
    document_date DATE NOT NULL,
    
    -- Generation Details
    generated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    generated_by UUID REFERENCES users(id),
    is_manual BOOLEAN DEFAULT FALSE,
    
    -- Status
    is_cancelled BOOLEAN DEFAULT FALSE,
    cancelled_at TIMESTAMP WITH TIME ZONE,
    cancelled_by UUID REFERENCES users(id),
    cancel_reason TEXT,
    
    UNIQUE(series_id, sequence_number),
    UNIQUE(series_id, formatted_number)
);
```

### 6. Financial Year Management

```sql
-- Function to determine financial year
CREATE OR REPLACE FUNCTION get_financial_year(p_date DATE DEFAULT CURRENT_DATE) 
RETURNS VARCHAR(9) AS $$
DECLARE
    v_year INTEGER;
    v_fy_start_month INTEGER := 4; -- April
BEGIN
    v_year := EXTRACT(YEAR FROM p_date);
    
    IF EXTRACT(MONTH FROM p_date) >= v_fy_start_month THEN
        -- Apr-Mar: Current year to next year
        RETURN v_year || '-' || (v_year + 1);
    ELSE
        -- Jan-Mar: Previous year to current year
        RETURN (v_year - 1) || '-' || v_year;
    END IF;
END;
$$ LANGUAGE plpgsql;

-- Auto-create series for new financial year
CREATE OR REPLACE FUNCTION create_new_fy_series() RETURNS TRIGGER AS $$
DECLARE
    v_new_fy VARCHAR(9);
    v_series RECORD;
BEGIN
    v_new_fy := get_financial_year();
    
    -- Check if we need to create series for new FY
    IF NOT EXISTS (
        SELECT 1 FROM invoice_series 
        WHERE company_id = NEW.company_id 
        AND financial_year = v_new_fy
    ) THEN
        -- Copy current FY series to new FY
        FOR v_series IN 
            SELECT * FROM invoice_series 
            WHERE company_id = NEW.company_id 
            AND financial_year != v_new_fy
            AND is_active = TRUE
        LOOP
            INSERT INTO invoice_series (
                company_id, series_name, series_code, prefix, suffix,
                current_number, min_number, max_number, number_length,
                number_format, financial_year, location_code,
                is_default, is_active, auto_increment, allow_manual_override,
                reset_frequency, gst_compliant, sequence_validation,
                created_by
            ) VALUES (
                v_series.company_id, v_series.series_name, v_series.series_code,
                v_series.prefix, v_series.suffix, 1, -- Reset to 1
                v_series.min_number, v_series.max_number, v_series.number_length,
                v_series.number_format, v_new_fy, v_series.location_code,
                v_series.is_default, v_series.is_active, v_series.auto_increment,
                v_series.allow_manual_override, v_series.reset_frequency,
                v_series.gst_compliant, v_series.sequence_validation,
                NEW.created_by
            );
        END LOOP;
    END IF;
    
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;
```

### 7. Validation & Compliance Checks

```sql
-- Validate number sequence compliance
CREATE OR REPLACE FUNCTION validate_number_sequence(
    p_series_id UUID,
    p_from_date DATE DEFAULT NULL,
    p_to_date DATE DEFAULT NULL
) RETURNS TABLE (
    sequence_number INTEGER,
    formatted_number VARCHAR(100),
    document_date DATE,
    is_missing BOOLEAN,
    is_out_of_order BOOLEAN,
    date_gap_days INTEGER
) AS $$
BEGIN
    RETURN QUERY
    WITH number_sequence AS (
        SELECT 
            dn.sequence_number,
            dn.formatted_number,
            dn.document_date,
            LAG(dn.document_date) OVER (ORDER BY dn.sequence_number) as prev_date,
            LAG(dn.sequence_number) OVER (ORDER BY dn.sequence_number) as prev_number
        FROM document_numbers dn
        WHERE dn.series_id = p_series_id
        AND dn.is_cancelled = FALSE
        AND (p_from_date IS NULL OR dn.document_date >= p_from_date)
        AND (p_to_date IS NULL OR dn.document_date <= p_to_date)
        ORDER BY dn.sequence_number
    ),
    gaps AS (
        SELECT 
            generate_series(
                COALESCE(ns.prev_number, 0) + 1, 
                ns.sequence_number - 1
            ) as missing_number,
            ns.sequence_number as next_number
        FROM number_sequence ns
        WHERE ns.sequence_number - COALESCE(ns.prev_number, 0) > 1
    )
    
    -- Return actual numbers with flags
    SELECT 
        ns.sequence_number,
        ns.formatted_number,
        ns.document_date,
        FALSE as is_missing,
        (ns.document_date < ns.prev_date) as is_out_of_order,
        COALESCE(ns.document_date - ns.prev_date, 0) as date_gap_days
    FROM number_sequence ns
    
    UNION ALL
    
    -- Return missing numbers
    SELECT 
        g.missing_number,
        '** MISSING **' as formatted_number,
        NULL as document_date,
        TRUE as is_missing,
        FALSE as is_out_of_order,
        NULL as date_gap_days
    FROM gaps g
    
    ORDER BY sequence_number;
END;
$$ LANGUAGE plpgsql;
```

### 8. Implementation Examples

#### Creating Default Series for a Company

```sql
-- Setup default series for a new company
INSERT INTO invoice_series (
    company_id, series_name, series_code, prefix, number_format, 
    financial_year, is_default, gst_compliant
) VALUES 
    -- Tax Invoices
    ('{company_id}', 'TAX_INVOICE', 'A', 'INV', '{PREFIX}-{FY}-{SERIES}-{NNNN}', '2024-2025', TRUE, TRUE),
    ('{company_id}', 'TAX_INVOICE', 'B', 'INV', '{PREFIX}-{FY}-{SERIES}-{NNNN}', '2024-2025', FALSE, TRUE),
    
    -- Export Invoices  
    ('{company_id}', 'TAX_INVOICE', 'EXP', 'EXP', '{PREFIX}-{FY}-{SERIES}-{NNNN}', '2024-2025', FALSE, TRUE),
    
    -- Quotations
    ('{company_id}', 'QUOTATION', 'A', 'QUO', '{PREFIX}-{FY}-{SERIES}-{NNNN}', '2024-2025', TRUE, FALSE),
    
    -- Sales Orders
    ('{company_id}', 'SALES_ORDER', 'A', 'SO', '{PREFIX}-{FY}-{SERIES}-{NNNN}', '2024-2025', TRUE, FALSE),
    
    -- Delivery Challans
    ('{company_id}', 'DELIVERY_CHALLAN', 'A', 'DC', '{PREFIX}-{FY}-{SERIES}-{NNNN}', '2024-2025', TRUE, TRUE),
    
    -- Credit Notes
    ('{company_id}', 'CREDIT_NOTE', 'A', 'CN', '{PREFIX}-{FY}-{SERIES}-{NNNN}', '2024-2025', TRUE, TRUE);
```

#### Usage in Application

```python
# Generate invoice number
def create_invoice(company_id, customer_id, items, invoice_date=None):
    invoice_date = invoice_date or datetime.now().date()
    
    # Generate invoice number
    cursor.execute("""
        SELECT generate_document_number(%s, 'TAX_INVOICE', 'A', %s)
    """, (company_id, invoice_date))
    
    invoice_number = cursor.fetchone()[0]
    
    # Create invoice with generated number
    # ... rest of invoice creation logic
```

### 9. GST Compliance Features

#### Sequential Validation
- No gaps allowed in sequence
- Automatic gap detection and reporting
- Manual number allocation with validation

#### Date-based Validation
- Allow reasonable date variations (±7 days)
- Flag significant date inconsistencies
- Support for backdated entries with approval

#### Multi-location Support
- Location-specific series (MUM, DEL, BLR)
- Branch-wise number sequences
- Centralized reporting and consolidation

#### Audit Trail
- Complete history of number generation
- Cancellation tracking with reasons
- User activity logging

### 10. Performance Considerations

- **Advisory Locks**: Prevent concurrent number generation conflicts
- **Indexing**: Optimized queries for sequence validation
- **Caching**: Cache active series configuration
- **Archival**: Archive old financial year data

This numbering strategy ensures full GST compliance while providing flexibility for different business needs and operational requirements. 