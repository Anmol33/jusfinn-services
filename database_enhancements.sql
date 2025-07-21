-- ============================================================================
-- JUSFINN - Database Enhancements for Sales Flow & Multi-tenancy
-- Additional tables and modifications for comprehensive accounting system
-- ============================================================================

-- ============================================================================
-- MULTI-TENANCY AND USER MANAGEMENT ENHANCEMENTS
-- ============================================================================

-- Companies/Businesses (Multi-tenant support)
CREATE TABLE companies (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    company_code VARCHAR(20) NOT NULL UNIQUE,
    legal_name VARCHAR(255) NOT NULL,
    trade_name VARCHAR(255),
    
    -- GST Registration
    gstin VARCHAR(15) UNIQUE,
    pan VARCHAR(10) NOT NULL,
    cin VARCHAR(21), -- Corporate Identification Number
    gst_registration_type gst_registration_type DEFAULT 'REGULAR',
    
    -- Contact Information
    email VARCHAR(255) NOT NULL,
    phone VARCHAR(15),
    website VARCHAR(255),
    
    -- Address
    address_line1 VARCHAR(255) NOT NULL,
    address_line2 VARCHAR(255),
    city VARCHAR(100) NOT NULL,
    state_id INTEGER REFERENCES states(id) NOT NULL,
    pincode VARCHAR(10) NOT NULL,
    country VARCHAR(50) DEFAULT 'India',
    
    -- Banking Details
    bank_name VARCHAR(255),
    bank_account_number VARCHAR(50),
    bank_ifsc VARCHAR(15),
    bank_branch VARCHAR(255),
    
    -- Subscription & Status
    subscription_plan VARCHAR(20) DEFAULT 'BASIC' CHECK (subscription_plan IN ('BASIC', 'PROFESSIONAL', 'ENTERPRISE')),
    subscription_expires_at DATE,
    is_active BOOLEAN DEFAULT TRUE,
    
    -- Financial Year
    financial_year_start DATE DEFAULT '2024-04-01',
    financial_year_end DATE DEFAULT '2025-03-31',
    
    -- Audit
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    created_by UUID
);

-- User Roles
CREATE TYPE user_role AS ENUM (
    'BUSINESS_OWNER', 'ACCOUNTANT', 'SALES_MANAGER', 'INVENTORY_MANAGER', 
    'ACCOUNTS_PAYABLE', 'ACCOUNTS_RECEIVABLE', 'VIEWER'
);

-- Enhanced Users Table
ALTER TABLE users ADD COLUMN company_id UUID REFERENCES companies(id);
ALTER TABLE users ADD COLUMN user_role user_role DEFAULT 'VIEWER';
ALTER TABLE users ADD COLUMN permissions JSONB DEFAULT '{}';
ALTER TABLE users ADD COLUMN last_login_at TIMESTAMP WITH TIME ZONE;
ALTER TABLE users ADD COLUMN is_email_verified BOOLEAN DEFAULT FALSE;

-- User Company Access (for accountants managing multiple companies)
CREATE TABLE user_company_access (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    company_id UUID NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    role user_role NOT NULL,
    permissions JSONB DEFAULT '{}',
    granted_by UUID REFERENCES users(id),
    granted_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    is_active BOOLEAN DEFAULT TRUE,
    UNIQUE(user_id, company_id)
);

-- ============================================================================
-- INVOICE NUMBERING SERIES MANAGEMENT
-- ============================================================================

CREATE TABLE invoice_series (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    company_id UUID NOT NULL REFERENCES companies(id),
    series_name VARCHAR(50) NOT NULL,
    prefix VARCHAR(10) NOT NULL,
    suffix VARCHAR(10) DEFAULT '',
    current_number INTEGER NOT NULL DEFAULT 1,
    number_format VARCHAR(50) NOT NULL, -- e.g., "INV-{YYYY}-{MM}-{NNNN}"
    is_default BOOLEAN DEFAULT FALSE,
    is_active BOOLEAN DEFAULT TRUE,
    financial_year VARCHAR(9) NOT NULL, -- e.g., "2024-2025"
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(company_id, series_name, financial_year)
);

-- Insert default series for each document type
INSERT INTO invoice_series (company_id, series_name, prefix, number_format, is_default, financial_year) 
SELECT 
    c.id,
    series_type,
    prefix,
    format,
    true,
    '2024-2025'
FROM companies c
CROSS JOIN (
    VALUES 
    ('TAX_INVOICE', 'INV', 'INV-{FY}-{NNNN}'),
    ('SALES_ORDER', 'SO', 'SO-{FY}-{NNNN}'),
    ('QUOTATION', 'QUO', 'QUO-{FY}-{NNNN}'),
    ('CREDIT_NOTE', 'CN', 'CN-{FY}-{NNNN}'),
    ('DELIVERY_CHALLAN', 'DC', 'DC-{FY}-{NNNN}')
) AS series(series_type, prefix, format);

-- Function to generate next number
CREATE OR REPLACE FUNCTION get_next_invoice_number(
    p_company_id UUID,
    p_series_name VARCHAR(50),
    p_financial_year VARCHAR(9) DEFAULT NULL
) RETURNS VARCHAR(50) AS $$
DECLARE
    v_series_record RECORD;
    v_next_number INTEGER;
    v_formatted_number VARCHAR(50);
    v_fy VARCHAR(9);
BEGIN
    -- Default to current financial year if not provided
    IF p_financial_year IS NULL THEN
        SELECT CASE 
            WHEN EXTRACT(MONTH FROM CURRENT_DATE) >= 4 THEN 
                EXTRACT(YEAR FROM CURRENT_DATE)::VARCHAR || '-' || (EXTRACT(YEAR FROM CURRENT_DATE) + 1)::VARCHAR
            ELSE 
                (EXTRACT(YEAR FROM CURRENT_DATE) - 1)::VARCHAR || '-' || EXTRACT(YEAR FROM CURRENT_DATE)::VARCHAR
        END INTO v_fy;
    ELSE
        v_fy := p_financial_year;
    END IF;
    
    -- Get or create series record
    SELECT * INTO v_series_record 
    FROM invoice_series 
    WHERE company_id = p_company_id 
    AND series_name = p_series_name 
    AND financial_year = v_fy;
    
    IF NOT FOUND THEN
        RAISE EXCEPTION 'Invoice series not found for company % and series %', p_company_id, p_series_name;
    END IF;
    
    -- Get next number and update
    UPDATE invoice_series 
    SET current_number = current_number + 1 
    WHERE id = v_series_record.id
    RETURNING current_number INTO v_next_number;
    
    -- Format the number
    v_formatted_number := v_series_record.number_format;
    v_formatted_number := REPLACE(v_formatted_number, '{FY}', v_fy);
    v_formatted_number := REPLACE(v_formatted_number, '{YYYY}', EXTRACT(YEAR FROM CURRENT_DATE)::VARCHAR);
    v_formatted_number := REPLACE(v_formatted_number, '{MM}', LPAD(EXTRACT(MONTH FROM CURRENT_DATE)::VARCHAR, 2, '0'));
    v_formatted_number := REPLACE(v_formatted_number, '{NNNN}', LPAD(v_next_number::VARCHAR, 4, '0'));
    
    RETURN v_series_record.prefix || v_formatted_number || v_series_record.suffix;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- ENHANCED INVENTORY MANAGEMENT
-- ============================================================================

-- Warehouses/Locations
CREATE TABLE warehouses (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    company_id UUID NOT NULL REFERENCES companies(id),
    warehouse_code VARCHAR(20) NOT NULL,
    name VARCHAR(255) NOT NULL,
    address_line1 VARCHAR(255),
    address_line2 VARCHAR(255),
    city VARCHAR(100),
    state_id INTEGER REFERENCES states(id),
    pincode VARCHAR(10),
    is_default BOOLEAN DEFAULT FALSE,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(company_id, warehouse_code)
);

-- Stock Movements
CREATE TYPE stock_movement_type AS ENUM (
    'OPENING_STOCK', 'PURCHASE', 'SALES', 'SALES_RETURN', 'PURCHASE_RETURN',
    'STOCK_ADJUSTMENT', 'STOCK_TRANSFER', 'MANUFACTURING', 'CONSUMPTION'
);

CREATE TABLE stock_movements (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    company_id UUID NOT NULL REFERENCES companies(id),
    item_service_id UUID NOT NULL REFERENCES items_services(id),
    warehouse_id UUID NOT NULL REFERENCES warehouses(id),
    
    -- Movement Details
    movement_type stock_movement_type NOT NULL,
    movement_date DATE NOT NULL DEFAULT CURRENT_DATE,
    quantity DECIMAL(15,3) NOT NULL,
    rate DECIMAL(15,2) DEFAULT 0,
    total_value DECIMAL(15,2) DEFAULT 0,
    
    -- Reference Documents
    reference_type VARCHAR(20), -- INVOICE, ORDER, CHALLAN, ADJUSTMENT, etc.
    reference_id UUID,
    reference_number VARCHAR(50),
    
    -- Stock Levels After Movement
    stock_before DECIMAL(15,3) NOT NULL,
    stock_after DECIMAL(15,3) NOT NULL,
    
    -- Additional Information
    batch_number VARCHAR(50),
    expiry_date DATE,
    notes TEXT,
    
    -- Audit
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    created_by UUID REFERENCES users(id)
);

-- Current Stock Levels (Materialized View Alternative)
CREATE TABLE current_stock (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    company_id UUID NOT NULL REFERENCES companies(id),
    item_service_id UUID NOT NULL REFERENCES items_services(id),
    warehouse_id UUID NOT NULL REFERENCES warehouses(id),
    current_quantity DECIMAL(15,3) NOT NULL DEFAULT 0,
    average_rate DECIMAL(15,2) NOT NULL DEFAULT 0,
    total_value DECIMAL(15,2) NOT NULL DEFAULT 0,
    last_updated TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(company_id, item_service_id, warehouse_id)
);

-- Function to update stock
CREATE OR REPLACE FUNCTION update_stock(
    p_company_id UUID,
    p_item_id UUID,
    p_warehouse_id UUID,
    p_quantity DECIMAL(15,3),
    p_rate DECIMAL(15,2),
    p_movement_type stock_movement_type,
    p_reference_type VARCHAR(20) DEFAULT NULL,
    p_reference_id UUID DEFAULT NULL,
    p_reference_number VARCHAR(50) DEFAULT NULL
) RETURNS VOID AS $$
DECLARE
    v_current_stock DECIMAL(15,3) := 0;
    v_new_stock DECIMAL(15,3);
    v_movement_quantity DECIMAL(15,3);
BEGIN
    -- Get current stock
    SELECT COALESCE(current_quantity, 0) INTO v_current_stock
    FROM current_stock 
    WHERE company_id = p_company_id 
    AND item_service_id = p_item_id 
    AND warehouse_id = p_warehouse_id;
    
    -- Determine movement direction
    CASE p_movement_type
        WHEN 'SALES', 'CONSUMPTION', 'STOCK_ADJUSTMENT'::stock_movement_type THEN
            v_movement_quantity := -ABS(p_quantity);
        ELSE
            v_movement_quantity := ABS(p_quantity);
    END CASE;
    
    v_new_stock := v_current_stock + v_movement_quantity;
    
    -- Insert stock movement
    INSERT INTO stock_movements (
        company_id, item_service_id, warehouse_id, movement_type, 
        quantity, rate, total_value, reference_type, reference_id, 
        reference_number, stock_before, stock_after
    ) VALUES (
        p_company_id, p_item_id, p_warehouse_id, p_movement_type,
        v_movement_quantity, p_rate, v_movement_quantity * p_rate,
        p_reference_type, p_reference_id, p_reference_number,
        v_current_stock, v_new_stock
    );
    
    -- Update current stock
    INSERT INTO current_stock (company_id, item_service_id, warehouse_id, current_quantity, average_rate, total_value)
    VALUES (p_company_id, p_item_id, p_warehouse_id, v_new_stock, p_rate, v_new_stock * p_rate)
    ON CONFLICT (company_id, item_service_id, warehouse_id)
    DO UPDATE SET 
        current_quantity = v_new_stock,
        average_rate = CASE 
            WHEN EXCLUDED.current_quantity > 0 THEN 
                (current_stock.total_value + EXCLUDED.total_value) / EXCLUDED.current_quantity
            ELSE EXCLUDED.average_rate
        END,
        total_value = current_stock.current_quantity * current_stock.average_rate,
        last_updated = NOW();
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- GST INTEGRATION ENHANCEMENTS
-- ============================================================================

-- GST API Integration Log
CREATE TABLE gst_api_requests (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    company_id UUID NOT NULL REFERENCES companies(id),
    api_type VARCHAR(20) NOT NULL CHECK (api_type IN ('EINVOICE', 'GSTR1', 'GSTR2B', 'GSTR3B')),
    request_type VARCHAR(20) NOT NULL CHECK (request_type IN ('GENERATE', 'CANCEL', 'GET', 'FILE')),
    
    -- Request Details
    reference_id UUID, -- Invoice ID, Return ID, etc.
    reference_number VARCHAR(50),
    request_payload JSONB,
    
    -- Response Details
    response_payload JSONB,
    status VARCHAR(20) DEFAULT 'PENDING' CHECK (status IN ('PENDING', 'SUCCESS', 'FAILED', 'RETRY')),
    error_message TEXT,
    
    -- API Specific Fields
    irn VARCHAR(64),
    ack_number VARCHAR(20),
    ack_date TIMESTAMP WITH TIME ZONE,
    qr_code TEXT,
    
    -- Timing
    request_time TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    response_time TIMESTAMP WITH TIME ZONE,
    retry_count INTEGER DEFAULT 0,
    
    -- Audit
    created_by UUID REFERENCES users(id)
);

-- GSTR-1 Data Compilation
CREATE TABLE gstr1_data (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    company_id UUID NOT NULL REFERENCES companies(id),
    return_period VARCHAR(7) NOT NULL, -- MM-YYYY format
    
    -- Invoice Summary
    b2b_invoices JSONB DEFAULT '[]',
    b2c_large_invoices JSONB DEFAULT '[]',
    b2c_small_invoices JSONB DEFAULT '[]',
    credit_debit_notes JSONB DEFAULT '[]',
    exports JSONB DEFAULT '[]',
    advances JSONB DEFAULT '[]',
    
    -- Status
    compilation_status VARCHAR(20) DEFAULT 'DRAFT' CHECK (compilation_status IN ('DRAFT', 'READY', 'FILED')),
    total_taxable_value DECIMAL(15,2) DEFAULT 0,
    total_tax_amount DECIMAL(15,2) DEFAULT 0,
    
    -- Filing Information
    filed_date DATE,
    acknowledgment_number VARCHAR(20),
    reference_id VARCHAR(50),
    
    -- Audit
    compiled_at TIMESTAMP WITH TIME ZONE,
    compiled_by UUID REFERENCES users(id),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- ============================================================================
-- DOCUMENT TEMPLATES AND GENERATION
-- ============================================================================

CREATE TABLE document_templates (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    company_id UUID NOT NULL REFERENCES companies(id),
    template_name VARCHAR(100) NOT NULL,
    document_type VARCHAR(20) NOT NULL CHECK (document_type IN ('INVOICE', 'QUOTATION', 'ORDER', 'CHALLAN', 'CREDIT_NOTE')),
    
    -- Template Content
    template_content JSONB NOT NULL, -- HTML/JSON template
    css_styles TEXT,
    header_image_url VARCHAR(500),
    footer_text TEXT,
    
    -- Settings
    is_default BOOLEAN DEFAULT FALSE,
    paper_size VARCHAR(10) DEFAULT 'A4' CHECK (paper_size IN ('A4', 'A5', 'LETTER')),
    show_company_logo BOOLEAN DEFAULT TRUE,
    show_signature BOOLEAN DEFAULT TRUE,
    
    -- Status
    is_active BOOLEAN DEFAULT TRUE,
    version INTEGER DEFAULT 1,
    
    -- Audit
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    created_by UUID REFERENCES users(id)
);

-- Document Generation Queue
CREATE TABLE document_queue (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    company_id UUID NOT NULL REFERENCES companies(id),
    document_type VARCHAR(20) NOT NULL,
    reference_id UUID NOT NULL,
    reference_number VARCHAR(50),
    
    -- Generation Details
    template_id UUID REFERENCES document_templates(id),
    output_format VARCHAR(10) DEFAULT 'PDF' CHECK (output_format IN ('PDF', 'HTML', 'EMAIL')),
    recipient_email VARCHAR(255),
    
    -- Status
    status VARCHAR(20) DEFAULT 'QUEUED' CHECK (status IN ('QUEUED', 'PROCESSING', 'COMPLETED', 'FAILED')),
    file_path VARCHAR(500),
    error_message TEXT,
    
    -- Timing
    queued_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    started_at TIMESTAMP WITH TIME ZONE,
    completed_at TIMESTAMP WITH TIME ZONE,
    
    -- Audit
    requested_by UUID REFERENCES users(id)
);

-- ============================================================================
-- ENHANCED CONSTRAINTS AND RELATIONSHIPS
-- ============================================================================

-- Add company_id to existing tables
ALTER TABLE customers ADD COLUMN company_id UUID REFERENCES companies(id);
ALTER TABLE vendors ADD COLUMN company_id UUID REFERENCES companies(id);
ALTER TABLE items_services ADD COLUMN company_id UUID REFERENCES companies(id);
ALTER TABLE sales_quotations ADD COLUMN company_id UUID REFERENCES companies(id);
ALTER TABLE sales_orders ADD COLUMN company_id UUID REFERENCES companies(id);
ALTER TABLE tax_invoices ADD COLUMN company_id UUID REFERENCES companies(id);
ALTER TABLE credit_notes ADD COLUMN company_id UUID REFERENCES companies(id);
ALTER TABLE purchase_orders ADD COLUMN company_id UUID REFERENCES companies(id);
ALTER TABLE purchase_bills ADD COLUMN company_id UUID REFERENCES companies(id);

-- Add indexes for performance
CREATE INDEX idx_companies_gstin ON companies(gstin);
CREATE INDEX idx_companies_pan ON companies(pan);
CREATE INDEX idx_stock_movements_company_item ON stock_movements(company_id, item_service_id);
CREATE INDEX idx_current_stock_company_item ON current_stock(company_id, item_service_id);
CREATE INDEX idx_gst_api_requests_company_type ON gst_api_requests(company_id, api_type);
CREATE INDEX idx_invoice_series_company_name ON invoice_series(company_id, series_name);

-- ============================================================================
-- SALES FLOW SPECIFIC ENHANCEMENTS
-- ============================================================================

-- Sales Return (separate from credit notes for better tracking)
CREATE TABLE sales_returns (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    return_number VARCHAR(50) NOT NULL,
    company_id UUID NOT NULL REFERENCES companies(id),
    customer_id UUID NOT NULL REFERENCES customers(id),
    invoice_id UUID NOT NULL REFERENCES tax_invoices(id),
    return_date DATE NOT NULL DEFAULT CURRENT_DATE,
    
    -- Return Details
    return_type VARCHAR(20) NOT NULL CHECK (return_type IN ('DEFECTIVE', 'CUSTOMER_REQUEST', 'WRONG_ITEM', 'DAMAGED', 'OTHER')),
    return_reason TEXT NOT NULL,
    
    -- Amounts
    subtotal DECIMAL(15,2) NOT NULL DEFAULT 0,
    cgst_amount DECIMAL(15,2) DEFAULT 0,
    sgst_amount DECIMAL(15,2) DEFAULT 0,
    igst_amount DECIMAL(15,2) DEFAULT 0,
    cess_amount DECIMAL(15,2) DEFAULT 0,
    total_amount DECIMAL(15,2) NOT NULL DEFAULT 0,
    
    -- Processing Status
    status VARCHAR(20) DEFAULT 'DRAFT' CHECK (status IN ('DRAFT', 'APPROVED', 'CREDIT_NOTE_ISSUED', 'REFUNDED', 'CANCELLED')),
    credit_note_id UUID REFERENCES credit_notes(id),
    
    -- Quality Check
    quality_checked BOOLEAN DEFAULT FALSE,
    quality_status VARCHAR(20) CHECK (quality_status IN ('ACCEPTABLE', 'DAMAGED', 'DEFECTIVE')),
    
    -- Audit
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    created_by UUID REFERENCES users(id),
    approved_by UUID REFERENCES users(id),
    
    UNIQUE(company_id, return_number)
);

-- Sales Return Items
CREATE TABLE sales_return_items (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    return_id UUID NOT NULL REFERENCES sales_returns(id) ON DELETE CASCADE,
    invoice_item_id UUID NOT NULL REFERENCES tax_invoice_items(id),
    item_service_id UUID NOT NULL REFERENCES items_services(id),
    
    -- Return Quantities
    invoiced_quantity DECIMAL(15,3) NOT NULL,
    return_quantity DECIMAL(15,3) NOT NULL,
    accepted_quantity DECIMAL(15,3) DEFAULT 0,
    rejected_quantity DECIMAL(15,3) DEFAULT 0,
    
    -- Pricing
    unit_price DECIMAL(15,2) NOT NULL,
    taxable_amount DECIMAL(15,2) NOT NULL,
    cgst_rate DECIMAL(5,2) DEFAULT 0,
    sgst_rate DECIMAL(5,2) DEFAULT 0,
    igst_rate DECIMAL(5,2) DEFAULT 0,
    cess_rate DECIMAL(5,2) DEFAULT 0,
    cgst_amount DECIMAL(15,2) DEFAULT 0,
    sgst_amount DECIMAL(15,2) DEFAULT 0,
    igst_amount DECIMAL(15,2) DEFAULT 0,
    cess_amount DECIMAL(15,2) DEFAULT 0,
    total_amount DECIMAL(15,2) NOT NULL,
    
    -- Quality Assessment
    condition_notes TEXT,
    
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- ============================================================================
-- BUSINESS RULES AND TRIGGERS
-- ============================================================================

-- Function to validate GST rates match HSN codes
CREATE OR REPLACE FUNCTION validate_gst_rates() RETURNS TRIGGER AS $$
BEGIN
    -- Add validation logic for GST rates
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Trigger to auto-generate invoice numbers
CREATE OR REPLACE FUNCTION auto_generate_invoice_number() RETURNS TRIGGER AS $$
BEGIN
    IF NEW.invoice_number IS NULL OR NEW.invoice_number = '' THEN
        NEW.invoice_number := get_next_invoice_number(NEW.company_id, 'TAX_INVOICE');
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_auto_invoice_number 
    BEFORE INSERT ON tax_invoices 
    FOR EACH ROW 
    EXECUTE FUNCTION auto_generate_invoice_number();

-- Trigger to update stock on invoice confirmation
CREATE OR REPLACE FUNCTION update_stock_on_invoice() RETURNS TRIGGER AS $$
DECLARE
    item RECORD;
BEGIN
    IF NEW.status = 'APPROVED' AND (OLD.status IS NULL OR OLD.status != 'APPROVED') THEN
        -- Reduce stock for each item
        FOR item IN SELECT tii.*, ii.type as item_type 
                    FROM tax_invoice_items tii 
                    JOIN items_services ii ON tii.item_service_id = ii.id
                    WHERE tii.invoice_id = NEW.id AND ii.type = 'PRODUCT'
        LOOP
            PERFORM update_stock(
                NEW.company_id,
                item.item_service_id,
                (SELECT id FROM warehouses WHERE company_id = NEW.company_id AND is_default = TRUE LIMIT 1),
                item.quantity,
                item.unit_price,
                'SALES'::stock_movement_type,
                'INVOICE',
                NEW.id,
                NEW.invoice_number
            );
        END LOOP;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_update_stock_invoice 
    AFTER INSERT OR UPDATE ON tax_invoices 
    FOR EACH ROW 
    EXECUTE FUNCTION update_stock_on_invoice();

-- ============================================================================
-- VIEWS FOR BUSINESS INTELLIGENCE
-- ============================================================================

-- Monthly Sales Summary by Company
CREATE VIEW monthly_sales_summary AS
SELECT 
    c.id as company_id,
    c.legal_name as company_name,
    DATE_TRUNC('month', ti.invoice_date) as month,
    COUNT(ti.id) as invoice_count,
    SUM(ti.subtotal) as gross_sales,
    SUM(ti.cgst_amount + ti.sgst_amount + ti.igst_amount) as total_gst,
    SUM(ti.total_amount) as net_sales,
    SUM(ti.outstanding_amount) as total_outstanding
FROM companies c
LEFT JOIN tax_invoices ti ON c.id = ti.company_id 
    AND ti.status NOT IN ('DRAFT', 'CANCELLED')
GROUP BY c.id, c.legal_name, DATE_TRUNC('month', ti.invoice_date)
ORDER BY month DESC, company_name;

-- Stock Alert View
CREATE VIEW stock_alerts AS
SELECT 
    c.legal_name as company_name,
    w.name as warehouse_name,
    ii.name as item_name,
    ii.item_code,
    cs.current_quantity,
    ii.reorder_level,
    (ii.reorder_level - cs.current_quantity) as shortage_quantity,
    ii.unit_of_measure
FROM current_stock cs
JOIN companies c ON cs.company_id = c.id
JOIN warehouses w ON cs.warehouse_id = w.id
JOIN items_services ii ON cs.item_service_id = ii.id
WHERE cs.current_quantity <= ii.reorder_level
    AND ii.type = 'PRODUCT'
    AND ii.is_active = TRUE
ORDER BY shortage_quantity DESC;

-- Top Customers by Sales
CREATE VIEW top_customers_by_sales AS
SELECT 
    c.id as company_id,
    cust.id as customer_id,
    cust.business_name,
    COUNT(ti.id) as total_invoices,
    SUM(ti.total_amount) as total_sales,
    SUM(ti.outstanding_amount) as total_outstanding,
    AVG(ti.total_amount) as average_invoice_value,
    MAX(ti.invoice_date) as last_invoice_date
FROM companies c
JOIN customers cust ON c.id = cust.company_id
JOIN tax_invoices ti ON cust.id = ti.customer_id
WHERE ti.status NOT IN ('DRAFT', 'CANCELLED')
GROUP BY c.id, cust.id, cust.business_name
ORDER BY total_sales DESC;

-- ============================================================================
-- SAMPLE DATA FOR TESTING
-- ============================================================================

-- Insert a sample company
INSERT INTO companies (
    company_code, legal_name, trade_name, gstin, pan, email, phone,
    address_line1, city, state_id, pincode, subscription_plan
) VALUES (
    'COMP001', 'Sample Trading Company Ltd', 'Sample Trading', 
    '07AAACT2727Q1ZZ', 'AAACT2727Q', 'admin@sample.com', '+919876543210',
    '123 Business Street', 'New Delhi', 
    (SELECT id FROM states WHERE code = 'DL'), '110001', 'PROFESSIONAL'
);

-- Insert default warehouse
INSERT INTO warehouses (company_id, warehouse_code, name, city, state_id, is_default)
SELECT 
    c.id, 'WH001', 'Main Warehouse', 'New Delhi', 
    (SELECT id FROM states WHERE code = 'DL'), TRUE
FROM companies c WHERE company_code = 'COMP001';

-- Create default document templates
INSERT INTO document_templates (
    company_id, template_name, document_type, template_content, is_default
) 
SELECT 
    c.id, 
    dt.template_name,
    dt.document_type,
    '{"template": "default"}' as template_content,
    TRUE
FROM companies c
CROSS JOIN (
    VALUES 
    ('Standard Invoice', 'INVOICE'),
    ('Standard Quotation', 'QUOTATION'),
    ('Standard Sales Order', 'ORDER'),
    ('Standard Delivery Challan', 'CHALLAN'),
    ('Standard Credit Note', 'CREDIT_NOTE')
) AS dt(template_name, document_type)
WHERE c.company_code = 'COMP001';

-- ============================================================================
-- PERMISSIONS AND SECURITY
-- ============================================================================

-- Row Level Security Policies (Enable RLS on tables)
ALTER TABLE companies ENABLE ROW LEVEL SECURITY;
ALTER TABLE customers ENABLE ROW LEVEL SECURITY;
ALTER TABLE vendors ENABLE ROW LEVEL SECURITY;
ALTER TABLE tax_invoices ENABLE ROW LEVEL SECURITY;
ALTER TABLE purchase_bills ENABLE ROW LEVEL SECURITY;

-- Create policies for multi-tenant access
CREATE POLICY company_isolation_policy ON companies
    FOR ALL
    USING (id IN (
        SELECT company_id 
        FROM user_company_access 
        WHERE user_id = current_setting('app.current_user_id')::uuid
        AND is_active = TRUE
    ));

-- Apply similar policies to other tables...

-- ============================================================================
-- FINAL COMMENTS
-- ============================================================================

COMMENT ON TABLE companies IS 'Multi-tenant companies with GST registration details';
COMMENT ON TABLE invoice_series IS 'Configurable invoice numbering series per company';
COMMENT ON TABLE stock_movements IS 'All inventory movements with reference tracking';
COMMENT ON TABLE current_stock IS 'Real-time stock levels per item per warehouse';
COMMENT ON TABLE gst_api_requests IS 'Log of all GST API interactions for compliance';
COMMENT ON TABLE sales_returns IS 'Comprehensive sales return management';
COMMENT ON FUNCTION get_next_invoice_number IS 'Generates sequential invoice numbers per series';
COMMENT ON FUNCTION update_stock IS 'Updates inventory levels with full audit trail'; 