-- ============================================================================
-- GST-ENHANCED SCHEMA ADDITIONS FOR SALES WORKFLOW
-- Building upon database_enhancements.sql
-- ============================================================================

-- ============================================================================
-- ENHANCED GST COMPLIANCE FIELDS
-- ============================================================================

-- GST Registration Types (more comprehensive)
DROP TYPE IF EXISTS gst_registration_type CASCADE;
CREATE TYPE gst_registration_type AS ENUM (
    'REGULAR', 'COMPOSITION', 'CASUAL_TAXABLE', 'NON_RESIDENT', 
    'INPUT_SERVICE_DISTRIBUTOR', 'OIDAR', 'UNREGISTERED', 'SEZ_UNIT', 'SEZ_DEVELOPER'
);

-- Transaction Types for E-Invoice
CREATE TYPE einvoice_transaction_type AS ENUM (
    'B2B', 'B2C', 'SEZWP', 'SEZWOP', 'EXPWP', 'EXPWOP', 'DEXP'
);

-- Sales Document Status with proper state management
CREATE TYPE sales_document_status AS ENUM (
    'DRAFT', 'PENDING_APPROVAL', 'APPROVED', 'SENT', 'ACCEPTED', 
    'REJECTED', 'CONVERTED', 'PARTIALLY_CONVERTED', 'CANCELLED', 
    'EXPIRED', 'ON_HOLD'
);

-- Invoice Status with GST compliance states
CREATE TYPE invoice_status AS ENUM (
    'DRAFT', 'PENDING_APPROVAL', 'APPROVED', 'EINVOICE_PENDING', 
    'EINVOICE_GENERATED', 'EINVOICE_CANCELLED', 'SENT', 'PARTIALLY_PAID', 
    'PAID', 'OVERDUE', 'CANCELLED', 'CREDIT_NOTE_ISSUED'
);

-- ============================================================================
-- ENHANCED ITEMS/SERVICES TABLE
-- ============================================================================

-- Add GST-specific fields to items_services
ALTER TABLE items_services ADD COLUMN IF NOT EXISTS hsn_sac_code VARCHAR(10);
ALTER TABLE items_services ADD COLUMN IF NOT EXISTS gst_rate DECIMAL(5,2) DEFAULT 0;
ALTER TABLE items_services ADD COLUMN IF NOT EXISTS cess_rate DECIMAL(5,2) DEFAULT 0;
ALTER TABLE items_services ADD COLUMN IF NOT EXISTS exemption_reason VARCHAR(100);
ALTER TABLE items_services ADD COLUMN IF NOT EXISTS nil_rated BOOLEAN DEFAULT FALSE;
ALTER TABLE items_services ADD COLUMN IF NOT EXISTS reverse_charge_applicable BOOLEAN DEFAULT FALSE;

-- Validate GST rates
ALTER TABLE items_services ADD CONSTRAINT check_gst_rate 
    CHECK (gst_rate IN (0, 0.25, 3, 5, 12, 18, 28));

-- ============================================================================
-- ENHANCED SALES QUOTATIONS WITH STATE MANAGEMENT
-- ============================================================================

-- Add workflow fields to sales_quotations
ALTER TABLE sales_quotations ADD COLUMN IF NOT EXISTS status sales_document_status DEFAULT 'DRAFT';
ALTER TABLE sales_quotations ADD COLUMN IF NOT EXISTS version INTEGER DEFAULT 1;
ALTER TABLE sales_quotations ADD COLUMN IF NOT EXISTS parent_quotation_id UUID REFERENCES sales_quotations(id);
ALTER TABLE sales_quotations ADD COLUMN IF NOT EXISTS approved_by UUID REFERENCES users(id);
ALTER TABLE sales_quotations ADD COLUMN IF NOT EXISTS approved_at TIMESTAMP WITH TIME ZONE;
ALTER TABLE sales_quotations ADD COLUMN IF NOT EXISTS sent_at TIMESTAMP WITH TIME ZONE;
ALTER TABLE sales_quotations ADD COLUMN IF NOT EXISTS customer_response_date DATE;
ALTER TABLE sales_quotations ADD COLUMN IF NOT EXISTS follow_up_date DATE;

-- Quotation Terms & Conditions
CREATE TABLE IF NOT EXISTS quotation_terms (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    quotation_id UUID NOT NULL REFERENCES sales_quotations(id) ON DELETE CASCADE,
    term_type VARCHAR(20) NOT NULL CHECK (term_type IN ('PAYMENT', 'DELIVERY', 'WARRANTY', 'VALIDITY', 'OTHER')),
    description TEXT NOT NULL,
    sort_order INTEGER DEFAULT 1
);

-- ============================================================================
-- ENHANCED SALES ORDERS WITH FULFILLMENT TRACKING
-- ============================================================================

-- Add fulfillment tracking to sales_orders
ALTER TABLE sales_orders ADD COLUMN IF NOT EXISTS status sales_document_status DEFAULT 'DRAFT';
ALTER TABLE sales_orders ADD COLUMN IF NOT EXISTS fulfillment_status VARCHAR(20) DEFAULT 'PENDING' 
    CHECK (fulfillment_status IN ('PENDING', 'PARTIAL', 'COMPLETED', 'CANCELLED'));
ALTER TABLE sales_orders ADD COLUMN IF NOT EXISTS priority VARCHAR(10) DEFAULT 'MEDIUM' 
    CHECK (priority IN ('LOW', 'MEDIUM', 'HIGH', 'URGENT'));
ALTER TABLE sales_orders ADD COLUMN IF NOT EXISTS expected_delivery_date DATE;
ALTER TABLE sales_orders ADD COLUMN IF NOT EXISTS advance_amount DECIMAL(15,2) DEFAULT 0;
ALTER TABLE sales_orders ADD COLUMN IF NOT EXISTS advance_received DECIMAL(15,2) DEFAULT 0;

-- Order Item Fulfillment
CREATE TABLE IF NOT EXISTS sales_order_item_fulfillment (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    order_item_id UUID NOT NULL REFERENCES sales_order_items(id) ON DELETE CASCADE,
    quantity_fulfilled DECIMAL(15,3) NOT NULL DEFAULT 0,
    delivery_challan_id UUID, -- References delivery_challans(id)
    invoice_id UUID REFERENCES tax_invoices(id),
    fulfilled_date DATE DEFAULT CURRENT_DATE,
    notes TEXT
);

-- ============================================================================
-- GST-COMPLIANT TAX INVOICES
-- ============================================================================

-- Enhance tax_invoices for full GST compliance
ALTER TABLE tax_invoices ADD COLUMN IF NOT EXISTS status invoice_status DEFAULT 'DRAFT';
ALTER TABLE tax_invoices ADD COLUMN IF NOT EXISTS invoice_category VARCHAR(20) DEFAULT 'REGULAR' 
    CHECK (invoice_category IN ('REGULAR', 'SEZ', 'EXPORT', 'DEEMED_EXPORT', 'ADVANCE_RECEIPT'));
ALTER TABLE tax_invoices ADD COLUMN IF NOT EXISTS place_of_supply_state_id INTEGER REFERENCES states(id);
ALTER TABLE tax_invoices ADD COLUMN IF NOT EXISTS supply_type VARCHAR(10) DEFAULT 'GOODS' 
    CHECK (supply_type IN ('GOODS', 'SERVICES', 'BOTH'));
ALTER TABLE tax_invoices ADD COLUMN IF NOT EXISTS reverse_charge_applicable BOOLEAN DEFAULT FALSE;
ALTER TABLE tax_invoices ADD COLUMN IF NOT EXISTS ecommerce_gstin VARCHAR(15);

-- E-Invoice specific fields
ALTER TABLE tax_invoices ADD COLUMN IF NOT EXISTS einvoice_applicable BOOLEAN DEFAULT FALSE;
ALTER TABLE tax_invoices ADD COLUMN IF NOT EXISTS irn VARCHAR(64);
ALTER TABLE tax_invoices ADD COLUMN IF NOT EXISTS ack_number VARCHAR(20);
ALTER TABLE tax_invoices ADD COLUMN IF NOT EXISTS ack_date TIMESTAMP WITH TIME ZONE;
ALTER TABLE tax_invoices ADD COLUMN IF NOT EXISTS qr_code_data TEXT;
ALTER TABLE tax_invoices ADD COLUMN IF NOT EXISTS einvoice_status VARCHAR(20) 
    CHECK (einvoice_status IN ('NOT_APPLICABLE', 'PENDING', 'GENERATED', 'CANCELLED'));

-- Additional GST fields
ALTER TABLE tax_invoices ADD COLUMN IF NOT EXISTS tcs_rate DECIMAL(5,2) DEFAULT 0;
ALTER TABLE tax_invoices ADD COLUMN IF NOT EXISTS tcs_amount DECIMAL(15,2) DEFAULT 0;
ALTER TABLE tax_invoices ADD COLUMN IF NOT EXISTS round_off_amount DECIMAL(15,2) DEFAULT 0;

-- ============================================================================
-- DELIVERY CHALLANS
-- ============================================================================

CREATE TABLE IF NOT EXISTS delivery_challans (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    challan_number VARCHAR(50) NOT NULL,
    company_id UUID NOT NULL REFERENCES companies(id),
    customer_id UUID NOT NULL REFERENCES customers(id),
    sales_order_id UUID REFERENCES sales_orders(id),
    
    -- Challan Details
    challan_date DATE NOT NULL DEFAULT CURRENT_DATE,
    supply_type VARCHAR(10) NOT NULL CHECK (supply_type IN ('GOODS', 'SERVICES', 'BOTH')),
    
    -- Transportation Details
    transporter_name VARCHAR(255),
    transporter_id VARCHAR(15), -- GST number of transporter
    lr_number VARCHAR(50),
    vehicle_number VARCHAR(20),
    transportation_mode VARCHAR(20) DEFAULT 'ROAD' 
        CHECK (transportation_mode IN ('ROAD', 'RAIL', 'AIR', 'SHIP')),
    transportation_distance INTEGER, -- in KM
    
    -- Delivery Details
    dispatch_from_address TEXT NOT NULL,
    delivery_to_address TEXT NOT NULL,
    delivery_date DATE,
    delivered_by VARCHAR(255),
    received_by VARCHAR(255),
    
    -- E-Way Bill
    eway_bill_number VARCHAR(20),
    eway_bill_date DATE,
    eway_bill_validity DATE,
    
    -- Status
    status VARCHAR(20) DEFAULT 'DRAFT' CHECK (status IN ('DRAFT', 'DISPATCHED', 'IN_TRANSIT', 'DELIVERED', 'CANCELLED')),
    
    -- Amounts (for E-Way Bill calculation)
    total_invoice_value DECIMAL(15,2) DEFAULT 0,
    
    -- Audit
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    created_by UUID REFERENCES users(id),
    
    UNIQUE(company_id, challan_number)
);

-- Delivery Challan Items
CREATE TABLE IF NOT EXISTS delivery_challan_items (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    challan_id UUID NOT NULL REFERENCES delivery_challans(id) ON DELETE CASCADE,
    item_service_id UUID NOT NULL REFERENCES items_services(id),
    sales_order_item_id UUID REFERENCES sales_order_items(id),
    
    -- Quantities
    quantity DECIMAL(15,3) NOT NULL,
    unit_price DECIMAL(15,2) NOT NULL,
    total_value DECIMAL(15,2) NOT NULL,
    
    -- Additional Details
    hsn_sac_code VARCHAR(10),
    batch_number VARCHAR(50),
    serial_numbers TEXT[],
    expiry_date DATE,
    
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- ============================================================================
-- ENHANCED CUSTOMER TABLE FOR GST COMPLIANCE
-- ============================================================================

-- Add GST-specific customer fields
ALTER TABLE customers ADD COLUMN IF NOT EXISTS customer_category VARCHAR(20) DEFAULT 'REGULAR' 
    CHECK (customer_category IN ('REGULAR', 'SEZ', 'EXPORT', 'DEEMED_EXPORT', 'UNREGISTERED'));
ALTER TABLE customers ADD COLUMN IF NOT EXISTS place_of_supply_state_id INTEGER REFERENCES states(id);
ALTER TABLE customers ADD COLUMN IF NOT EXISTS ecommerce_operator BOOLEAN DEFAULT FALSE;
ALTER TABLE customers ADD COLUMN IF NOT EXISTS tcs_applicable BOOLEAN DEFAULT FALSE;

-- ============================================================================
-- GSTR-1 DATA COMPILATION ENHANCEMENT
-- ============================================================================

-- Enhanced GSTR-1 with detailed breakdown
ALTER TABLE gstr1_data ADD COLUMN IF NOT EXISTS hsn_summary JSONB DEFAULT '[]';
ALTER TABLE gstr1_data ADD COLUMN IF NOT EXISTS document_summary JSONB DEFAULT '{}';
ALTER TABLE gstr1_data ADD COLUMN IF NOT EXISTS amendment_data JSONB DEFAULT '[]';

-- GSTR-1 Invoice mapping for reconciliation
CREATE TABLE IF NOT EXISTS gstr1_invoice_mapping (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    gstr1_id UUID NOT NULL REFERENCES gstr1_data(id) ON DELETE CASCADE,
    invoice_id UUID NOT NULL REFERENCES tax_invoices(id),
    invoice_type VARCHAR(10) NOT NULL CHECK (invoice_type IN ('B2B', 'B2CL', 'B2CS', 'CDNR', 'CDNUR', 'EXP', 'AT', 'ATADJ', 'EXEMP', 'HSN')),
    included_in_gstr1 BOOLEAN DEFAULT TRUE,
    amendment_type VARCHAR(10) CHECK (amendment_type IN ('NEW', 'AMENDED', 'CANCELLED')),
    original_period VARCHAR(7), -- For amendments
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- ============================================================================
-- DOCUMENT SEQUENCE MANAGEMENT
-- ============================================================================

-- Function to check E-Invoice applicability
CREATE OR REPLACE FUNCTION is_einvoice_applicable(
    p_total_amount DECIMAL(15,2),
    p_customer_gstin VARCHAR(15),
    p_company_turnover DECIMAL(20,2) DEFAULT NULL
) RETURNS BOOLEAN AS $$
BEGIN
    -- E-Invoice applicable if:
    -- 1. B2B invoice amount >= 5 lakhs OR
    -- 2. Company turnover > 100 crores (all invoices) OR
    -- 3. Export invoices (regardless of amount)
    
    RETURN (
        p_total_amount >= 500000 OR 
        (p_company_turnover IS NOT NULL AND p_company_turnover > 10000000000) OR
        p_customer_gstin IS NULL -- Export assumption
    );
END;
$$ LANGUAGE plpgsql;

-- Function to validate HSN/SAC codes
CREATE OR REPLACE FUNCTION validate_hsn_sac(p_code VARCHAR(10), p_type VARCHAR(10)) RETURNS BOOLEAN AS $$
BEGIN
    -- HSN codes: 4-8 digits for goods
    -- SAC codes: 6 digits for services
    IF p_type = 'GOODS' THEN
        RETURN p_code ~ '^[0-9]{4,8}$';
    ELSIF p_type = 'SERVICES' THEN
        RETURN p_code ~ '^[0-9]{6}$';
    END IF;
    RETURN FALSE;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- INDEXING FOR PERFORMANCE
-- ============================================================================

-- Additional indexes for GST compliance queries
CREATE INDEX IF NOT EXISTS idx_tax_invoices_einvoice_status ON tax_invoices(einvoice_status);
CREATE INDEX IF NOT EXISTS idx_tax_invoices_place_of_supply ON tax_invoices(place_of_supply_state_id);
CREATE INDEX IF NOT EXISTS idx_delivery_challans_eway_bill ON delivery_challans(eway_bill_number);
CREATE INDEX IF NOT EXISTS idx_gstr1_mapping_period ON gstr1_invoice_mapping(gstr1_id, invoice_type);
CREATE INDEX IF NOT EXISTS idx_customers_category ON customers(customer_category);

-- ============================================================================
-- BUSINESS LOGIC TRIGGERS
-- ============================================================================

-- Auto-generate delivery challan number
CREATE OR REPLACE FUNCTION auto_generate_challan_number() RETURNS TRIGGER AS $$
BEGIN
    IF NEW.challan_number IS NULL OR NEW.challan_number = '' THEN
        NEW.challan_number := get_next_invoice_number(NEW.company_id, 'DELIVERY_CHALLAN');
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_auto_challan_number 
    BEFORE INSERT ON delivery_challans 
    FOR EACH ROW 
    EXECUTE FUNCTION auto_generate_challan_number();

-- E-Invoice applicability check
CREATE OR REPLACE FUNCTION check_einvoice_applicability() RETURNS TRIGGER AS $$
BEGIN
    NEW.einvoice_applicable := is_einvoice_applicable(
        NEW.total_amount, 
        (SELECT gstin FROM customers WHERE id = NEW.customer_id),
        (SELECT annual_turnover FROM companies WHERE id = NEW.company_id)
    );
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_einvoice_check 
    BEFORE INSERT OR UPDATE ON tax_invoices 
    FOR EACH ROW 
    EXECUTE FUNCTION check_einvoice_applicability();

-- ============================================================================
-- SAMPLE DATA ENHANCEMENTS
-- ============================================================================

-- Add annual turnover to companies for E-Invoice calculation
ALTER TABLE companies ADD COLUMN IF NOT EXISTS annual_turnover DECIMAL(20,2) DEFAULT 0;

-- Insert default delivery challan series
INSERT INTO invoice_series (company_id, series_name, prefix, number_format, is_default, financial_year) 
SELECT 
    c.id,
    'DELIVERY_CHALLAN',
    'DC',
    'DC-{FY}-{NNNN}',
    true,
    '2024-2025'
FROM companies c
WHERE NOT EXISTS (
    SELECT 1 FROM invoice_series 
    WHERE company_id = c.id AND series_name = 'DELIVERY_CHALLAN'
);

COMMENT ON TABLE delivery_challans IS 'Delivery challans with E-Way Bill integration';
COMMENT ON TABLE delivery_challan_items IS 'Items in delivery challans with batch tracking';
COMMENT ON FUNCTION is_einvoice_applicable IS 'Determines if E-Invoice is mandatory for a transaction';
COMMENT ON FUNCTION validate_hsn_sac IS 'Validates HSN/SAC code format based on goods/services type'; 