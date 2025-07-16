-- ============================================================================
-- JUSFINN - Complete Database Schema for Invoicing & Sales + Purchases & Expenses
-- PostgreSQL Database Schema with Indian GST Compliance
-- ============================================================================

-- Enable necessary extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";

-- ============================================================================
-- COMMON ENUMS AND TYPES
-- ============================================================================

-- GST Registration Types
CREATE TYPE gst_registration_type AS ENUM (
    'REGULAR', 'COMPOSITION', 'INPUT_SERVICE_DISTRIBUTOR', 
    'TDS', 'TCS', 'NON_RESIDENT', 'OIDAR', 'EMBASSIES', 
    'UN_BODY', 'CASUAL_TAXABLE_PERSON'
);

-- Payment Terms
CREATE TYPE payment_terms AS ENUM (
    'IMMEDIATE', 'NET_15', 'NET_30', 'NET_45', 'NET_60', 'NET_90'
);

-- Invoice Status
CREATE TYPE invoice_status AS ENUM (
    'DRAFT', 'PENDING_APPROVAL', 'APPROVED', 'SENT', 'PARTIALLY_PAID', 
    'PAID', 'OVERDUE', 'CANCELLED', 'CREDITED'
);

-- Order Status
CREATE TYPE order_status AS ENUM (
    'DRAFT', 'PENDING_APPROVAL', 'APPROVED', 'IN_PROGRESS', 
    'PARTIALLY_DELIVERED', 'DELIVERED', 'INVOICED', 'CANCELLED'
);

-- TDS Sections
CREATE TYPE tds_section AS ENUM (
    '194A', '194B', '194BB', '194C', '194D', '194DA', '194E', '194EE', 
    '194F', '194G', '194H', '194I', '194IA', '194IB', '194IC', '194J', 
    '194K', '194LA', '194LB', '194LBA', '194LBB', '194LBC', '194LC', 
    '194M', '194N', '194O', '194P', '194Q', '194R', '194S'
);

-- ITC Status
CREATE TYPE itc_status AS ENUM (
    'ELIGIBLE', 'CLAIMED', 'REVERSED', 'BLOCKED', 'LAPSED'
);

-- MSME Registration
CREATE TYPE msme_registration AS ENUM (
    'MICRO', 'SMALL', 'MEDIUM', 'NOT_APPLICABLE'
);

-- ============================================================================
-- CORE MASTER DATA TABLES
-- ============================================================================

-- States Master for Indian States
CREATE TABLE states (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL UNIQUE,
    code VARCHAR(2) NOT NULL UNIQUE,
    gst_state_code VARCHAR(2) NOT NULL UNIQUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Insert Indian States
INSERT INTO states (name, code, gst_state_code) VALUES
('Andhra Pradesh', 'AP', '37'),
('Arunachal Pradesh', 'AR', '12'),
('Assam', 'AS', '18'),
('Bihar', 'BR', '10'),
('Chhattisgarh', 'CG', '22'),
('Goa', 'GA', '30'),
('Gujarat', 'GJ', '24'),
('Haryana', 'HR', '06'),
('Himachal Pradesh', 'HP', '02'),
('Jharkhand', 'JH', '20'),
('Karnataka', 'KA', '29'),
('Kerala', 'KL', '32'),
('Madhya Pradesh', 'MP', '23'),
('Maharashtra', 'MH', '27'),
('Manipur', 'MN', '14'),
('Meghalaya', 'ML', '17'),
('Mizoram', 'MZ', '15'),
('Nagaland', 'NL', '13'),
('Odisha', 'OR', '21'),
('Punjab', 'PB', '03'),
('Rajasthan', 'RJ', '08'),
('Sikkim', 'SK', '11'),
('Tamil Nadu', 'TN', '33'),
('Telangana', 'TS', '36'),
('Tripura', 'TR', '16'),
('Uttar Pradesh', 'UP', '09'),
('Uttarakhand', 'UK', '05'),
('West Bengal', 'WB', '19'),
('Andaman and Nicobar Islands', 'AN', '35'),
('Chandigarh', 'CH', '04'),
('Dadra and Nagar Haveli and Daman and Diu', 'DH', '26'),
('Delhi', 'DL', '07'),
('Jammu and Kashmir', 'JK', '01'),
('Ladakh', 'LA', '38'),
('Lakshadweep', 'LD', '31'),
('Puducherry', 'PY', '34'),
('Other Territory', 'OT', '97');

-- HSN/SAC Codes Master
CREATE TABLE hsn_sac_codes (
    id SERIAL PRIMARY KEY,
    code VARCHAR(10) NOT NULL UNIQUE,
    description TEXT NOT NULL,
    type VARCHAR(10) NOT NULL CHECK (type IN ('HSN', 'SAC')),
    gst_rate DECIMAL(5,2) DEFAULT 0,
    cess_rate DECIMAL(5,2) DEFAULT 0,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- ============================================================================
-- CUSTOMER MANAGEMENT (INVOICING & SALES)
-- ============================================================================

-- Customer Master
CREATE TABLE customers (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    customer_code VARCHAR(20) NOT NULL UNIQUE,
    business_name VARCHAR(255) NOT NULL,
    legal_name VARCHAR(255),
    gstin VARCHAR(15) UNIQUE,
    pan VARCHAR(10),
    customer_type VARCHAR(20) DEFAULT 'BUSINESS' CHECK (customer_type IN ('BUSINESS', 'INDIVIDUAL')),
    gst_registration_type gst_registration_type,
    
    -- Primary Contact
    contact_person VARCHAR(100),
    phone VARCHAR(15),
    email VARCHAR(100),
    website VARCHAR(255),
    
    -- Credit Management
    credit_limit DECIMAL(15,2) DEFAULT 0,
    credit_days INTEGER DEFAULT 30,
    payment_terms payment_terms DEFAULT 'NET_30',
    
    -- Billing Address
    billing_address_line1 VARCHAR(255),
    billing_address_line2 VARCHAR(255),
    billing_city VARCHAR(100),
    billing_state_id INTEGER REFERENCES states(id),
    billing_pincode VARCHAR(10),
    billing_country VARCHAR(50) DEFAULT 'India',
    
    -- Shipping Address
    shipping_address_line1 VARCHAR(255),
    shipping_address_line2 VARCHAR(255),
    shipping_city VARCHAR(100),
    shipping_state_id INTEGER REFERENCES states(id),
    shipping_pincode VARCHAR(10),
    shipping_country VARCHAR(50) DEFAULT 'India',
    
    -- Business Metrics
    customer_rating INTEGER CHECK (customer_rating BETWEEN 1 AND 5),
    total_sales DECIMAL(15,2) DEFAULT 0,
    outstanding_amount DECIMAL(15,2) DEFAULT 0,
    last_transaction_date DATE,
    
    -- Status and Audit
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    created_by UUID,
    updated_by UUID
);

-- Items/Services Master
CREATE TABLE items_services (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    item_code VARCHAR(50) NOT NULL UNIQUE,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    type VARCHAR(10) NOT NULL CHECK (type IN ('PRODUCT', 'SERVICE')),
    
    -- Tax Information
    hsn_sac_code_id INTEGER REFERENCES hsn_sac_codes(id),
    gst_rate DECIMAL(5,2) DEFAULT 0,
    cess_rate DECIMAL(5,2) DEFAULT 0,
    
    -- Pricing
    base_price DECIMAL(15,2) NOT NULL,
    selling_price DECIMAL(15,2) NOT NULL,
    discount_percentage DECIMAL(5,2) DEFAULT 0,
    
    -- Inventory (for products)
    unit_of_measure VARCHAR(20),
    opening_stock DECIMAL(15,3) DEFAULT 0,
    current_stock DECIMAL(15,3) DEFAULT 0,
    reorder_level DECIMAL(15,3) DEFAULT 0,
    
    -- Vendor Information
    primary_vendor_id UUID,
    vendor_item_code VARCHAR(50),
    
    -- Business Metrics
    total_sales_quantity DECIMAL(15,3) DEFAULT 0,
    total_sales_value DECIMAL(15,2) DEFAULT 0,
    last_sale_date DATE,
    
    -- Status and Audit
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    created_by UUID,
    updated_by UUID
);

-- Sales Quotations
CREATE TABLE sales_quotations (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    quotation_number VARCHAR(50) NOT NULL UNIQUE,
    customer_id UUID NOT NULL REFERENCES customers(id),
    quotation_date DATE NOT NULL DEFAULT CURRENT_DATE,
    validity_date DATE NOT NULL,
    
    -- Amounts
    subtotal DECIMAL(15,2) NOT NULL DEFAULT 0,
    discount_amount DECIMAL(15,2) DEFAULT 0,
    cgst_amount DECIMAL(15,2) DEFAULT 0,
    sgst_amount DECIMAL(15,2) DEFAULT 0,
    igst_amount DECIMAL(15,2) DEFAULT 0,
    cess_amount DECIMAL(15,2) DEFAULT 0,
    total_amount DECIMAL(15,2) NOT NULL DEFAULT 0,
    
    -- Status and Conversion
    status VARCHAR(20) DEFAULT 'DRAFT' CHECK (status IN ('DRAFT', 'SENT', 'APPROVED', 'REJECTED', 'EXPIRED', 'CONVERTED')),
    is_converted_to_order BOOLEAN DEFAULT FALSE,
    converted_order_id UUID,
    
    -- Additional Information
    terms_and_conditions TEXT,
    notes TEXT,
    follow_up_date DATE,
    
    -- Audit
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    created_by UUID,
    updated_by UUID
);

-- Sales Quotation Items
CREATE TABLE sales_quotation_items (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    quotation_id UUID NOT NULL REFERENCES sales_quotations(id) ON DELETE CASCADE,
    item_service_id UUID NOT NULL REFERENCES items_services(id),
    quantity DECIMAL(15,3) NOT NULL,
    unit_price DECIMAL(15,2) NOT NULL,
    discount_percentage DECIMAL(5,2) DEFAULT 0,
    discount_amount DECIMAL(15,2) DEFAULT 0,
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
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Sales Orders
CREATE TABLE sales_orders (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    order_number VARCHAR(50) NOT NULL UNIQUE,
    customer_id UUID NOT NULL REFERENCES customers(id),
    quotation_id UUID REFERENCES sales_quotations(id),
    order_date DATE NOT NULL DEFAULT CURRENT_DATE,
    expected_delivery_date DATE,
    
    -- Amounts (same structure as quotations)
    subtotal DECIMAL(15,2) NOT NULL DEFAULT 0,
    discount_amount DECIMAL(15,2) DEFAULT 0,
    cgst_amount DECIMAL(15,2) DEFAULT 0,
    sgst_amount DECIMAL(15,2) DEFAULT 0,
    igst_amount DECIMAL(15,2) DEFAULT 0,
    cess_amount DECIMAL(15,2) DEFAULT 0,
    total_amount DECIMAL(15,2) NOT NULL DEFAULT 0,
    
    -- Status and Progress
    status order_status DEFAULT 'DRAFT',
    progress_percentage INTEGER DEFAULT 0 CHECK (progress_percentage BETWEEN 0 AND 100),
    
    -- Approval Workflow
    approval_status VARCHAR(20) DEFAULT 'PENDING' CHECK (approval_status IN ('PENDING', 'APPROVED', 'REJECTED')),
    approved_by UUID,
    approved_at TIMESTAMP WITH TIME ZONE,
    
    -- Additional Information
    customer_po_number VARCHAR(50),
    customer_po_date DATE,
    terms_and_conditions TEXT,
    notes TEXT,
    
    -- Audit
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    created_by UUID,
    updated_by UUID
);

-- Sales Order Items
CREATE TABLE sales_order_items (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    order_id UUID NOT NULL REFERENCES sales_orders(id) ON DELETE CASCADE,
    item_service_id UUID NOT NULL REFERENCES items_services(id),
    quantity DECIMAL(15,3) NOT NULL,
    delivered_quantity DECIMAL(15,3) DEFAULT 0,
    pending_quantity DECIMAL(15,3) GENERATED ALWAYS AS (quantity - delivered_quantity) STORED,
    unit_price DECIMAL(15,2) NOT NULL,
    discount_percentage DECIMAL(5,2) DEFAULT 0,
    discount_amount DECIMAL(15,2) DEFAULT 0,
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
    expected_delivery_date DATE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Delivery Challans
CREATE TABLE delivery_challans (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    challan_number VARCHAR(50) NOT NULL UNIQUE,
    order_id UUID NOT NULL REFERENCES sales_orders(id),
    customer_id UUID NOT NULL REFERENCES customers(id),
    challan_date DATE NOT NULL DEFAULT CURRENT_DATE,
    
    -- Transport Details
    transporter_name VARCHAR(255),
    transporter_id VARCHAR(15),
    vehicle_number VARCHAR(20),
    driver_name VARCHAR(100),
    driver_license VARCHAR(50),
    driver_phone VARCHAR(15),
    
    -- E-Way Bill
    eway_bill_number VARCHAR(15) UNIQUE,
    eway_bill_date DATE,
    eway_bill_valid_until DATE,
    
    -- Delivery Details
    from_address TEXT,
    to_address TEXT,
    distance_km DECIMAL(8,2),
    
    -- Status
    status VARCHAR(20) DEFAULT 'DRAFT' CHECK (status IN ('DRAFT', 'IN_TRANSIT', 'DELIVERED', 'CANCELLED')),
    delivered_at TIMESTAMP WITH TIME ZONE,
    received_by VARCHAR(100),
    
    -- Additional Information
    remarks TEXT,
    
    -- Audit
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    created_by UUID,
    updated_by UUID
);

-- Delivery Challan Items
CREATE TABLE delivery_challan_items (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    challan_id UUID NOT NULL REFERENCES delivery_challans(id) ON DELETE CASCADE,
    order_item_id UUID NOT NULL REFERENCES sales_order_items(id),
    item_service_id UUID NOT NULL REFERENCES items_services(id),
    quantity DECIMAL(15,3) NOT NULL,
    unit_price DECIMAL(15,2) NOT NULL,
    total_amount DECIMAL(15,2) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Tax Invoices
CREATE TABLE tax_invoices (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    invoice_number VARCHAR(50) NOT NULL UNIQUE,
    customer_id UUID NOT NULL REFERENCES customers(id),
    order_id UUID REFERENCES sales_orders(id),
    challan_id UUID REFERENCES delivery_challans(id),
    invoice_date DATE NOT NULL DEFAULT CURRENT_DATE,
    due_date DATE NOT NULL,
    
    -- E-Invoice Details
    irn VARCHAR(64) UNIQUE,
    ack_number VARCHAR(20),
    ack_date TIMESTAMP WITH TIME ZONE,
    qr_code TEXT,
    signed_qr_code TEXT,
    
    -- Amounts
    subtotal DECIMAL(15,2) NOT NULL DEFAULT 0,
    discount_amount DECIMAL(15,2) DEFAULT 0,
    cgst_amount DECIMAL(15,2) DEFAULT 0,
    sgst_amount DECIMAL(15,2) DEFAULT 0,
    igst_amount DECIMAL(15,2) DEFAULT 0,
    cess_amount DECIMAL(15,2) DEFAULT 0,
    tcs_rate DECIMAL(5,2) DEFAULT 0,
    tcs_amount DECIMAL(15,2) DEFAULT 0,
    total_amount DECIMAL(15,2) NOT NULL DEFAULT 0,
    
    -- Payment Information
    paid_amount DECIMAL(15,2) DEFAULT 0,
    outstanding_amount DECIMAL(15,2) GENERATED ALWAYS AS (total_amount - paid_amount) STORED,
    
    -- Status
    status invoice_status DEFAULT 'DRAFT',
    
    -- Bank Details for Payment
    bank_name VARCHAR(255),
    bank_account_number VARCHAR(50),
    bank_ifsc VARCHAR(15),
    bank_branch VARCHAR(255),
    
    -- Additional Information
    place_of_supply INTEGER REFERENCES states(id),
    reverse_charge_applicable BOOLEAN DEFAULT FALSE,
    terms_and_conditions TEXT,
    notes TEXT,
    
    -- GSTR-1 Filing
    gstr1_filing_period VARCHAR(7), -- MM-YYYY format
    gstr1_filed BOOLEAN DEFAULT FALSE,
    gstr1_filed_date DATE,
    
    -- Audit
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    created_by UUID,
    updated_by UUID
);

-- Tax Invoice Items
CREATE TABLE tax_invoice_items (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    invoice_id UUID NOT NULL REFERENCES tax_invoices(id) ON DELETE CASCADE,
    item_service_id UUID NOT NULL REFERENCES items_services(id),
    order_item_id UUID REFERENCES sales_order_items(id),
    quantity DECIMAL(15,3) NOT NULL,
    unit_price DECIMAL(15,2) NOT NULL,
    discount_percentage DECIMAL(5,2) DEFAULT 0,
    discount_amount DECIMAL(15,2) DEFAULT 0,
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
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Credit Notes
CREATE TABLE credit_notes (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    credit_note_number VARCHAR(50) NOT NULL UNIQUE,
    invoice_id UUID NOT NULL REFERENCES tax_invoices(id),
    customer_id UUID NOT NULL REFERENCES customers(id),
    credit_note_date DATE NOT NULL DEFAULT CURRENT_DATE,
    
    -- Reason and Type
    reason_code VARCHAR(10) NOT NULL CHECK (reason_code IN ('01', '02', '03', '04', '05', '06', '07', '08', '09', '10')),
    reason_description TEXT NOT NULL,
    credit_type VARCHAR(20) NOT NULL CHECK (credit_type IN ('RETURN', 'DISCOUNT', 'DEFICIENCY', 'OTHER')),
    
    -- E-Invoice Details
    irn VARCHAR(64) UNIQUE,
    ack_number VARCHAR(20),
    ack_date TIMESTAMP WITH TIME ZONE,
    qr_code TEXT,
    
    -- Amounts
    subtotal DECIMAL(15,2) NOT NULL DEFAULT 0,
    cgst_amount DECIMAL(15,2) DEFAULT 0,
    sgst_amount DECIMAL(15,2) DEFAULT 0,
    igst_amount DECIMAL(15,2) DEFAULT 0,
    cess_amount DECIMAL(15,2) DEFAULT 0,
    total_amount DECIMAL(15,2) NOT NULL DEFAULT 0,
    
    -- Approval
    approval_status VARCHAR(20) DEFAULT 'PENDING' CHECK (approval_status IN ('PENDING', 'APPROVED', 'REJECTED')),
    approved_by UUID,
    approved_at TIMESTAMP WITH TIME ZONE,
    
    -- Status
    status VARCHAR(20) DEFAULT 'DRAFT' CHECK (status IN ('DRAFT', 'APPROVED', 'CANCELLED')),
    
    -- Additional Information
    notes TEXT,
    
    -- Audit
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    created_by UUID,
    updated_by UUID
);

-- Credit Note Items
CREATE TABLE credit_note_items (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    credit_note_id UUID NOT NULL REFERENCES credit_notes(id) ON DELETE CASCADE,
    invoice_item_id UUID NOT NULL REFERENCES tax_invoice_items(id),
    item_service_id UUID NOT NULL REFERENCES items_services(id),
    quantity DECIMAL(15,3) NOT NULL,
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
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Payment Collections
CREATE TABLE payment_collections (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    payment_number VARCHAR(50) NOT NULL UNIQUE,
    customer_id UUID NOT NULL REFERENCES customers(id),
    payment_date DATE NOT NULL DEFAULT CURRENT_DATE,
    
    -- Payment Details
    payment_method VARCHAR(20) NOT NULL CHECK (payment_method IN ('CASH', 'CHEQUE', 'BANK_TRANSFER', 'UPI', 'CARD', 'OTHER')),
    amount DECIMAL(15,2) NOT NULL,
    
    -- Bank Details (for non-cash payments)
    bank_name VARCHAR(255),
    cheque_number VARCHAR(50),
    cheque_date DATE,
    utr_number VARCHAR(50),
    
    -- TCS Calculation
    tcs_applicable BOOLEAN DEFAULT FALSE,
    tcs_rate DECIMAL(5,2) DEFAULT 0,
    tcs_amount DECIMAL(15,2) DEFAULT 0,
    
    -- Status
    status VARCHAR(20) DEFAULT 'RECEIVED' CHECK (status IN ('RECEIVED', 'CLEARED', 'BOUNCED', 'CANCELLED')),
    clearance_date DATE,
    
    -- Reconciliation
    is_reconciled BOOLEAN DEFAULT FALSE,
    reconciled_date DATE,
    bank_statement_reference VARCHAR(100),
    
    -- Additional Information
    notes TEXT,
    
    -- Audit
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    created_by UUID,
    updated_by UUID
);

-- Payment Allocations (to invoices)
CREATE TABLE payment_allocations (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    payment_id UUID NOT NULL REFERENCES payment_collections(id) ON DELETE CASCADE,
    invoice_id UUID NOT NULL REFERENCES tax_invoices(id),
    allocated_amount DECIMAL(15,2) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- ============================================================================
-- VENDOR MANAGEMENT (PURCHASES & EXPENSES)
-- ============================================================================

-- Vendor Master
CREATE TABLE vendors (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    vendor_code VARCHAR(20) NOT NULL UNIQUE,
    business_name VARCHAR(255) NOT NULL,
    legal_name VARCHAR(255),
    gstin VARCHAR(15) UNIQUE,
    pan VARCHAR(10),
    vendor_type VARCHAR(20) DEFAULT 'SUPPLIER' CHECK (vendor_type IN ('SUPPLIER', 'SERVICE_PROVIDER', 'CONTRACTOR')),
    gst_registration_type gst_registration_type,
    
    -- MSME Information
    msme_registration msme_registration DEFAULT 'NOT_APPLICABLE',
    msme_number VARCHAR(20),
    udyam_registration_number VARCHAR(20),
    
    -- Primary Contact
    contact_person VARCHAR(100),
    phone VARCHAR(15),
    email VARCHAR(100),
    website VARCHAR(255),
    
    -- Credit Management
    credit_limit DECIMAL(15,2) DEFAULT 0,
    credit_days INTEGER DEFAULT 30,
    payment_terms payment_terms DEFAULT 'NET_30',
    
    -- Address
    address_line1 VARCHAR(255),
    address_line2 VARCHAR(255),
    city VARCHAR(100),
    state_id INTEGER REFERENCES states(id),
    pincode VARCHAR(10),
    country VARCHAR(50) DEFAULT 'India',
    
    -- TDS Information
    tds_section tds_section,
    tds_rate DECIMAL(5,2) DEFAULT 0,
    tds_applicable BOOLEAN DEFAULT TRUE,
    
    -- Business Metrics
    vendor_rating INTEGER CHECK (vendor_rating BETWEEN 1 AND 5),
    total_purchases DECIMAL(15,2) DEFAULT 0,
    outstanding_amount DECIMAL(15,2) DEFAULT 0,
    last_transaction_date DATE,
    
    -- Status and Audit
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    created_by UUID,
    updated_by UUID
);

-- Purchase Orders
CREATE TABLE purchase_orders (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    po_number VARCHAR(50) NOT NULL UNIQUE,
    vendor_id UUID NOT NULL REFERENCES vendors(id),
    po_date DATE NOT NULL DEFAULT CURRENT_DATE,
    expected_delivery_date DATE,
    
    -- Amounts
    subtotal DECIMAL(15,2) NOT NULL DEFAULT 0,
    discount_amount DECIMAL(15,2) DEFAULT 0,
    cgst_amount DECIMAL(15,2) DEFAULT 0,
    sgst_amount DECIMAL(15,2) DEFAULT 0,
    igst_amount DECIMAL(15,2) DEFAULT 0,
    cess_amount DECIMAL(15,2) DEFAULT 0,
    total_amount DECIMAL(15,2) NOT NULL DEFAULT 0,
    
    -- Status
    status order_status DEFAULT 'DRAFT',
    
    -- Approval Workflow
    approval_status VARCHAR(20) DEFAULT 'PENDING' CHECK (approval_status IN ('PENDING', 'APPROVED', 'REJECTED')),
    approved_by UUID,
    approved_at TIMESTAMP WITH TIME ZONE,
    
    -- Additional Information
    delivery_address TEXT,
    terms_and_conditions TEXT,
    notes TEXT,
    
    -- Audit
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    created_by UUID,
    updated_by UUID
);

-- Purchase Order Items
CREATE TABLE purchase_order_items (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    po_id UUID NOT NULL REFERENCES purchase_orders(id) ON DELETE CASCADE,
    item_service_id UUID NOT NULL REFERENCES items_services(id),
    quantity DECIMAL(15,3) NOT NULL,
    received_quantity DECIMAL(15,3) DEFAULT 0,
    pending_quantity DECIMAL(15,3) GENERATED ALWAYS AS (quantity - received_quantity) STORED,
    unit_price DECIMAL(15,2) NOT NULL,
    discount_percentage DECIMAL(5,2) DEFAULT 0,
    discount_amount DECIMAL(15,2) DEFAULT 0,
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
    expected_delivery_date DATE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Goods Receipt Notes
CREATE TABLE goods_receipt_notes (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    grn_number VARCHAR(50) NOT NULL UNIQUE,
    po_id UUID NOT NULL REFERENCES purchase_orders(id),
    vendor_id UUID NOT NULL REFERENCES vendors(id),
    grn_date DATE NOT NULL DEFAULT CURRENT_DATE,
    
    -- Delivery Details
    vendor_challan_number VARCHAR(50),
    vendor_challan_date DATE,
    vehicle_number VARCHAR(20),
    transporter_name VARCHAR(255),
    
    -- Status
    status VARCHAR(20) DEFAULT 'DRAFT' CHECK (status IN ('DRAFT', 'RECEIVED', 'INSPECTED', 'ACCEPTED', 'REJECTED')),
    
    -- Quality Check
    quality_checked BOOLEAN DEFAULT FALSE,
    quality_checked_by UUID,
    quality_checked_at TIMESTAMP WITH TIME ZONE,
    quality_remarks TEXT,
    
    -- Additional Information
    remarks TEXT,
    
    -- Audit
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    created_by UUID,
    updated_by UUID
);

-- Goods Receipt Note Items
CREATE TABLE grn_items (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    grn_id UUID NOT NULL REFERENCES goods_receipt_notes(id) ON DELETE CASCADE,
    po_item_id UUID NOT NULL REFERENCES purchase_order_items(id),
    item_service_id UUID NOT NULL REFERENCES items_services(id),
    ordered_quantity DECIMAL(15,3) NOT NULL,
    received_quantity DECIMAL(15,3) NOT NULL,
    accepted_quantity DECIMAL(15,3) NOT NULL,
    rejected_quantity DECIMAL(15,3) DEFAULT 0,
    unit_price DECIMAL(15,2) NOT NULL,
    total_amount DECIMAL(15,2) NOT NULL,
    batch_number VARCHAR(50),
    expiry_date DATE,
    remarks TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Purchase Bills/Invoices
CREATE TABLE purchase_bills (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    bill_number VARCHAR(50) NOT NULL,
    vendor_bill_number VARCHAR(50) NOT NULL,
    vendor_id UUID NOT NULL REFERENCES vendors(id),
    po_id UUID REFERENCES purchase_orders(id),
    grn_id UUID REFERENCES goods_receipt_notes(id),
    bill_date DATE NOT NULL,
    due_date DATE NOT NULL,
    
    -- OCR Processing
    is_ocr_processed BOOLEAN DEFAULT FALSE,
    ocr_confidence_score DECIMAL(5,2),
    ocr_extracted_data JSONB,
    
    -- Three-way Matching
    po_matching_status VARCHAR(20) DEFAULT 'PENDING' CHECK (po_matching_status IN ('PENDING', 'MATCHED', 'VARIANCE', 'NO_PO')),
    grn_matching_status VARCHAR(20) DEFAULT 'PENDING' CHECK (grn_matching_status IN ('PENDING', 'MATCHED', 'VARIANCE', 'NO_GRN')),
    price_variance_percentage DECIMAL(5,2) DEFAULT 0,
    quantity_variance_percentage DECIMAL(5,2) DEFAULT 0,
    
    -- Amounts
    subtotal DECIMAL(15,2) NOT NULL DEFAULT 0,
    discount_amount DECIMAL(15,2) DEFAULT 0,
    cgst_amount DECIMAL(15,2) DEFAULT 0,
    sgst_amount DECIMAL(15,2) DEFAULT 0,
    igst_amount DECIMAL(15,2) DEFAULT 0,
    cess_amount DECIMAL(15,2) DEFAULT 0,
    tds_amount DECIMAL(15,2) DEFAULT 0,
    total_amount DECIMAL(15,2) NOT NULL DEFAULT 0,
    paid_amount DECIMAL(15,2) DEFAULT 0,
    outstanding_amount DECIMAL(15,2) GENERATED ALWAYS AS (total_amount - paid_amount) STORED,
    
    -- ITC Information
    itc_eligible_amount DECIMAL(15,2) DEFAULT 0,
    itc_claimed_amount DECIMAL(15,2) DEFAULT 0,
    itc_status itc_status DEFAULT 'ELIGIBLE',
    
    -- Status
    status invoice_status DEFAULT 'DRAFT',
    
    -- GSTR-2B Reconciliation
    gstr2b_period VARCHAR(7), -- MM-YYYY format
    gstr2b_reconciled BOOLEAN DEFAULT FALSE,
    gstr2b_reconciled_date DATE,
    
    -- Additional Information
    place_of_supply INTEGER REFERENCES states(id),
    reverse_charge_applicable BOOLEAN DEFAULT FALSE,
    notes TEXT,
    
    -- Audit
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    created_by UUID,
    updated_by UUID,
    
    UNIQUE(vendor_id, vendor_bill_number)
);

-- Purchase Bill Items
CREATE TABLE purchase_bill_items (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    bill_id UUID NOT NULL REFERENCES purchase_bills(id) ON DELETE CASCADE,
    item_service_id UUID NOT NULL REFERENCES items_services(id),
    po_item_id UUID REFERENCES purchase_order_items(id),
    grn_item_id UUID REFERENCES grn_items(id),
    quantity DECIMAL(15,3) NOT NULL,
    unit_price DECIMAL(15,2) NOT NULL,
    discount_percentage DECIMAL(5,2) DEFAULT 0,
    discount_amount DECIMAL(15,2) DEFAULT 0,
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
    
    -- ITC Information
    itc_eligible BOOLEAN DEFAULT TRUE,
    itc_amount DECIMAL(15,2) DEFAULT 0,
    itc_reversal_reason VARCHAR(100),
    
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- TDS Compliance
CREATE TABLE tds_transactions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    bill_id UUID REFERENCES purchase_bills(id),
    vendor_id UUID NOT NULL REFERENCES vendors(id),
    transaction_date DATE NOT NULL,
    
    -- TDS Details
    tds_section tds_section NOT NULL,
    tds_rate DECIMAL(5,2) NOT NULL,
    payment_amount DECIMAL(15,2) NOT NULL,
    tds_amount DECIMAL(15,2) NOT NULL,
    net_payment_amount DECIMAL(15,2) NOT NULL,
    
    -- Deductee Information
    deductee_pan VARCHAR(10) NOT NULL,
    deductee_name VARCHAR(255) NOT NULL,
    deductee_address TEXT,
    
    -- Challan Information
    challan_number VARCHAR(20),
    challan_date DATE,
    bsr_code VARCHAR(10),
    challan_amount DECIMAL(15,2),
    
    -- Certificate Details
    certificate_number VARCHAR(20),
    certificate_generated BOOLEAN DEFAULT FALSE,
    certificate_generated_date DATE,
    
    -- Filing Information
    return_type VARCHAR(10) CHECK (return_type IN ('24Q', '26Q', '27Q', '27EQ')),
    filing_period VARCHAR(10), -- Q1-YYYY format
    filed BOOLEAN DEFAULT FALSE,
    filed_date DATE,
    acknowledgment_number VARCHAR(20),
    
    -- Audit
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    created_by UUID,
    updated_by UUID
);

-- ITC Management
CREATE TABLE itc_records (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    bill_id UUID NOT NULL REFERENCES purchase_bills(id),
    vendor_id UUID NOT NULL REFERENCES vendors(id),
    
    -- Period Information
    tax_period VARCHAR(7) NOT NULL, -- MM-YYYY format
    return_period VARCHAR(7) NOT NULL, -- MM-YYYY format
    
    -- ITC Details
    cgst_itc DECIMAL(15,2) DEFAULT 0,
    sgst_itc DECIMAL(15,2) DEFAULT 0,
    igst_itc DECIMAL(15,2) DEFAULT 0,
    cess_itc DECIMAL(15,2) DEFAULT 0,
    total_itc DECIMAL(15,2) NOT NULL,
    
    -- Status and Eligibility
    itc_status itc_status DEFAULT 'ELIGIBLE',
    eligibility_reason TEXT,
    
    -- Reversal Information
    reversal_rule VARCHAR(50), -- Rule 42, Rule 43, Section 17(5), etc.
    reversal_percentage DECIMAL(5,2) DEFAULT 0,
    reversal_amount DECIMAL(15,2) DEFAULT 0,
    
    -- GSTR-2B Reconciliation
    gstr2b_reported BOOLEAN DEFAULT FALSE,
    gstr2b_amount DECIMAL(15,2) DEFAULT 0,
    variance_amount DECIMAL(15,2) DEFAULT 0,
    reconciled BOOLEAN DEFAULT FALSE,
    
    -- Claim Information
    claimed_in_gstr3b BOOLEAN DEFAULT FALSE,
    claim_period VARCHAR(7),
    claim_amount DECIMAL(15,2) DEFAULT 0,
    
    -- Additional Information
    purchase_type VARCHAR(20) CHECK (purchase_type IN ('CAPITAL_GOODS', 'INPUT_SERVICES', 'INPUTS', 'OTHER')),
    notes TEXT,
    
    -- Audit
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Expense Management
CREATE TABLE expense_categories (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL UNIQUE,
    description TEXT,
    hsn_sac_code_id INTEGER REFERENCES hsn_sac_codes(id),
    default_tds_section tds_section,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE TABLE expenses (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    expense_number VARCHAR(50) NOT NULL UNIQUE,
    category_id INTEGER NOT NULL REFERENCES expense_categories(id),
    vendor_id UUID REFERENCES vendors(id),
    expense_date DATE NOT NULL DEFAULT CURRENT_DATE,
    
    -- Expense Details
    description TEXT NOT NULL,
    amount DECIMAL(15,2) NOT NULL,
    
    -- Tax Information
    cgst_amount DECIMAL(15,2) DEFAULT 0,
    sgst_amount DECIMAL(15,2) DEFAULT 0,
    igst_amount DECIMAL(15,2) DEFAULT 0,
    tds_amount DECIMAL(15,2) DEFAULT 0,
    total_amount DECIMAL(15,2) NOT NULL,
    
    -- Receipt Information
    receipt_number VARCHAR(50),
    receipt_date DATE,
    receipt_image_url VARCHAR(500),
    
    -- Approval
    approval_status VARCHAR(20) DEFAULT 'PENDING' CHECK (approval_status IN ('PENDING', 'APPROVED', 'REJECTED')),
    approved_by UUID,
    approved_at TIMESTAMP WITH TIME ZONE,
    
    -- Reimbursement
    reimbursement_status VARCHAR(20) DEFAULT 'PENDING' CHECK (reimbursement_status IN ('PENDING', 'APPROVED', 'PAID', 'REJECTED')),
    reimbursed_amount DECIMAL(15,2) DEFAULT 0,
    
    -- Additional Information
    project_id UUID,
    employee_id UUID,
    notes TEXT,
    
    -- Audit
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    created_by UUID,
    updated_by UUID
);

-- Landed Cost Accounting
CREATE TABLE shipments (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    shipment_number VARCHAR(50) NOT NULL UNIQUE,
    po_id UUID REFERENCES purchase_orders(id),
    
    -- Shipment Details
    origin_port VARCHAR(100),
    destination_port VARCHAR(100),
    vessel_name VARCHAR(100),
    container_number VARCHAR(20),
    
    -- Dates
    shipped_date DATE,
    eta DATE,
    arrived_date DATE,
    cleared_date DATE,
    
    -- Status
    status VARCHAR(20) DEFAULT 'IN_TRANSIT' CHECK (status IN ('PLANNED', 'IN_TRANSIT', 'ARRIVED', 'CLEARED', 'DELIVERED')),
    
    -- Currency and Exchange
    shipment_currency VARCHAR(3) DEFAULT 'INR',
    exchange_rate DECIMAL(10,4) DEFAULT 1,
    
    -- Audit
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    created_by UUID,
    updated_by UUID
);

CREATE TABLE landed_costs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    shipment_id UUID NOT NULL REFERENCES shipments(id),
    
    -- Cost Details
    cost_type VARCHAR(30) NOT NULL CHECK (cost_type IN ('FREIGHT', 'INSURANCE', 'CUSTOMS_DUTY', 'CLEARING_CHARGES', 'TRANSPORT', 'HANDLING', 'STORAGE', 'OTHER')),
    cost_description VARCHAR(255) NOT NULL,
    amount DECIMAL(15,2) NOT NULL,
    currency VARCHAR(3) DEFAULT 'INR',
    
    -- Allocation Method
    allocation_method VARCHAR(20) DEFAULT 'VALUE' CHECK (allocation_method IN ('VALUE', 'WEIGHT', 'QUANTITY', 'MANUAL')),
    allocation_percentage DECIMAL(5,2),
    
    -- Vendor Information
    service_provider VARCHAR(255),
    bill_number VARCHAR(50),
    bill_date DATE,
    
    -- Audit
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- ============================================================================
-- PAYMENT TRACKING TABLES
-- ============================================================================

-- Vendor Payments
CREATE TABLE vendor_payments (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    payment_number VARCHAR(50) NOT NULL UNIQUE,
    vendor_id UUID NOT NULL REFERENCES vendors(id),
    payment_date DATE NOT NULL DEFAULT CURRENT_DATE,
    
    -- Payment Details
    payment_method VARCHAR(20) NOT NULL CHECK (payment_method IN ('CASH', 'CHEQUE', 'BANK_TRANSFER', 'UPI', 'CARD', 'OTHER')),
    amount DECIMAL(15,2) NOT NULL,
    
    -- Bank Details
    bank_name VARCHAR(255),
    cheque_number VARCHAR(50),
    cheque_date DATE,
    utr_number VARCHAR(50),
    
    -- TDS Deduction
    tds_amount DECIMAL(15,2) DEFAULT 0,
    net_payment_amount DECIMAL(15,2) NOT NULL,
    
    -- Status
    status VARCHAR(20) DEFAULT 'PAID' CHECK (status IN ('PAID', 'CLEARED', 'BOUNCED', 'CANCELLED')),
    clearance_date DATE,
    
    -- Additional Information
    notes TEXT,
    
    -- Audit
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    created_by UUID,
    updated_by UUID
);

-- Vendor Payment Allocations
CREATE TABLE vendor_payment_allocations (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    payment_id UUID NOT NULL REFERENCES vendor_payments(id) ON DELETE CASCADE,
    bill_id UUID NOT NULL REFERENCES purchase_bills(id),
    allocated_amount DECIMAL(15,2) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- ============================================================================
-- AUDIT AND SYSTEM TABLES
-- ============================================================================

-- Users Table (referenced in audit fields)
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    email VARCHAR(255) NOT NULL UNIQUE,
    full_name VARCHAR(255) NOT NULL,
    role VARCHAR(50) NOT NULL,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Audit Log
CREATE TABLE audit_logs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    table_name VARCHAR(100) NOT NULL,
    record_id UUID NOT NULL,
    action VARCHAR(10) NOT NULL CHECK (action IN ('INSERT', 'UPDATE', 'DELETE')),
    old_values JSONB,
    new_values JSONB,
    changed_by UUID REFERENCES users(id),
    changed_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Document Attachments
CREATE TABLE document_attachments (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    entity_type VARCHAR(50) NOT NULL,
    entity_id UUID NOT NULL,
    file_name VARCHAR(255) NOT NULL,
    file_path VARCHAR(500) NOT NULL,
    file_size INTEGER,
    mime_type VARCHAR(100),
    uploaded_by UUID REFERENCES users(id),
    uploaded_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- ============================================================================
-- INDEXES FOR PERFORMANCE
-- ============================================================================

-- Customer indexes
CREATE INDEX idx_customers_gstin ON customers(gstin);
CREATE INDEX idx_customers_pan ON customers(pan);
CREATE INDEX idx_customers_customer_code ON customers(customer_code);
CREATE INDEX idx_customers_business_name ON customers USING gin(business_name gin_trgm_ops);

-- Vendor indexes
CREATE INDEX idx_vendors_gstin ON vendors(gstin);
CREATE INDEX idx_vendors_pan ON vendors(pan);
CREATE INDEX idx_vendors_vendor_code ON vendors(vendor_code);
CREATE INDEX idx_vendors_business_name ON vendors USING gin(business_name gin_trgm_ops);

-- Invoice indexes
CREATE INDEX idx_tax_invoices_customer_id ON tax_invoices(customer_id);
CREATE INDEX idx_tax_invoices_invoice_date ON tax_invoices(invoice_date);
CREATE INDEX idx_tax_invoices_due_date ON tax_invoices(due_date);
CREATE INDEX idx_tax_invoices_status ON tax_invoices(status);
CREATE INDEX idx_tax_invoices_irn ON tax_invoices(irn);

-- Purchase Bill indexes
CREATE INDEX idx_purchase_bills_vendor_id ON purchase_bills(vendor_id);
CREATE INDEX idx_purchase_bills_bill_date ON purchase_bills(bill_date);
CREATE INDEX idx_purchase_bills_due_date ON purchase_bills(due_date);
CREATE INDEX idx_purchase_bills_status ON purchase_bills(status);

-- Order indexes
CREATE INDEX idx_sales_orders_customer_id ON sales_orders(customer_id);
CREATE INDEX idx_sales_orders_order_date ON sales_orders(order_date);
CREATE INDEX idx_sales_orders_status ON sales_orders(status);

CREATE INDEX idx_purchase_orders_vendor_id ON purchase_orders(vendor_id);
CREATE INDEX idx_purchase_orders_po_date ON purchase_orders(po_date);
CREATE INDEX idx_purchase_orders_status ON purchase_orders(status);

-- TDS indexes
CREATE INDEX idx_tds_transactions_vendor_id ON tds_transactions(vendor_id);
CREATE INDEX idx_tds_transactions_transaction_date ON tds_transactions(transaction_date);
CREATE INDEX idx_tds_transactions_tds_section ON tds_transactions(tds_section);
CREATE INDEX idx_tds_transactions_filing_period ON tds_transactions(filing_period);

-- ITC indexes
CREATE INDEX idx_itc_records_bill_id ON itc_records(bill_id);
CREATE INDEX idx_itc_records_tax_period ON itc_records(tax_period);
CREATE INDEX idx_itc_records_itc_status ON itc_records(itc_status);

-- Payment indexes
CREATE INDEX idx_payment_collections_customer_id ON payment_collections(customer_id);
CREATE INDEX idx_payment_collections_payment_date ON payment_collections(payment_date);

CREATE INDEX idx_vendor_payments_vendor_id ON vendor_payments(vendor_id);
CREATE INDEX idx_vendor_payments_payment_date ON vendor_payments(payment_date);

-- ============================================================================
-- TRIGGERS FOR AUDIT TRAILS
-- ============================================================================

-- Function to update timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Apply updated_at triggers to all main tables
CREATE TRIGGER update_customers_updated_at BEFORE UPDATE ON customers FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_vendors_updated_at BEFORE UPDATE ON vendors FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_items_services_updated_at BEFORE UPDATE ON items_services FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_sales_quotations_updated_at BEFORE UPDATE ON sales_quotations FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_sales_orders_updated_at BEFORE UPDATE ON sales_orders FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_tax_invoices_updated_at BEFORE UPDATE ON tax_invoices FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_purchase_orders_updated_at BEFORE UPDATE ON purchase_orders FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_purchase_bills_updated_at BEFORE UPDATE ON purchase_bills FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Audit log trigger function
CREATE OR REPLACE FUNCTION audit_trigger_function()
RETURNS TRIGGER AS $$
BEGIN
    IF TG_OP = 'DELETE' THEN
        INSERT INTO audit_logs (table_name, record_id, action, old_values, changed_at)
        VALUES (TG_TABLE_NAME, OLD.id, 'DELETE', row_to_json(OLD), NOW());
        RETURN OLD;
    ELSIF TG_OP = 'UPDATE' THEN
        INSERT INTO audit_logs (table_name, record_id, action, old_values, new_values, changed_at)
        VALUES (TG_TABLE_NAME, NEW.id, 'UPDATE', row_to_json(OLD), row_to_json(NEW), NOW());
        RETURN NEW;
    ELSIF TG_OP = 'INSERT' THEN
        INSERT INTO audit_logs (table_name, record_id, action, new_values, changed_at)
        VALUES (TG_TABLE_NAME, NEW.id, 'INSERT', row_to_json(NEW), NOW());
        RETURN NEW;
    END IF;
    RETURN NULL;
END;
$$ LANGUAGE plpgsql;

-- Apply audit triggers to main tables
CREATE TRIGGER audit_customers AFTER INSERT OR UPDATE OR DELETE ON customers FOR EACH ROW EXECUTE FUNCTION audit_trigger_function();
CREATE TRIGGER audit_vendors AFTER INSERT OR UPDATE OR DELETE ON vendors FOR EACH ROW EXECUTE FUNCTION audit_trigger_function();
CREATE TRIGGER audit_tax_invoices AFTER INSERT OR UPDATE OR DELETE ON tax_invoices FOR EACH ROW EXECUTE FUNCTION audit_trigger_function();
CREATE TRIGGER audit_purchase_bills AFTER INSERT OR UPDATE OR DELETE ON purchase_bills FOR EACH ROW EXECUTE FUNCTION audit_trigger_function();

-- ============================================================================
-- VIEWS FOR COMMON QUERIES
-- ============================================================================

-- Customer Outstanding View
CREATE VIEW customer_outstanding_summary AS
SELECT 
    c.id,
    c.customer_code,
    c.business_name,
    c.credit_limit,
    COALESCE(SUM(ti.outstanding_amount), 0) as total_outstanding,
    c.credit_limit - COALESCE(SUM(ti.outstanding_amount), 0) as available_credit,
    COUNT(ti.id) as total_invoices,
    COUNT(CASE WHEN ti.status = 'OVERDUE' THEN 1 END) as overdue_invoices
FROM customers c
LEFT JOIN tax_invoices ti ON c.id = ti.customer_id AND ti.status IN ('SENT', 'PARTIALLY_PAID', 'OVERDUE')
WHERE c.is_active = TRUE
GROUP BY c.id, c.customer_code, c.business_name, c.credit_limit;

-- Vendor Outstanding View
CREATE VIEW vendor_outstanding_summary AS
SELECT 
    v.id,
    v.vendor_code,
    v.business_name,
    v.msme_registration,
    COALESCE(SUM(pb.outstanding_amount), 0) as total_outstanding,
    COUNT(pb.id) as total_bills,
    COUNT(CASE WHEN pb.status = 'OVERDUE' THEN 1 END) as overdue_bills,
    -- MSME compliance (45 days)
    COUNT(CASE WHEN v.msme_registration != 'NOT_APPLICABLE' AND pb.due_date < CURRENT_DATE - INTERVAL '45 days' AND pb.outstanding_amount > 0 THEN 1 END) as msme_violations
FROM vendors v
LEFT JOIN purchase_bills pb ON v.id = pb.vendor_id AND pb.status IN ('APPROVED', 'PARTIALLY_PAID', 'OVERDUE')
WHERE v.is_active = TRUE
GROUP BY v.id, v.vendor_code, v.business_name, v.msme_registration;

-- Sales Performance View
CREATE VIEW sales_performance_summary AS
SELECT 
    DATE_TRUNC('month', ti.invoice_date) as month,
    COUNT(ti.id) as total_invoices,
    SUM(ti.subtotal) as gross_sales,
    SUM(ti.total_amount) as net_sales,
    SUM(ti.cgst_amount + ti.sgst_amount + ti.igst_amount) as total_gst,
    AVG(ti.total_amount) as average_invoice_value
FROM tax_invoices ti
WHERE ti.status NOT IN ('DRAFT', 'CANCELLED')
GROUP BY DATE_TRUNC('month', ti.invoice_date)
ORDER BY month DESC;

-- Purchase Performance View
CREATE VIEW purchase_performance_summary AS
SELECT 
    DATE_TRUNC('month', pb.bill_date) as month,
    COUNT(pb.id) as total_bills,
    SUM(pb.subtotal) as gross_purchases,
    SUM(pb.total_amount) as net_purchases,
    SUM(pb.cgst_amount + pb.sgst_amount + pb.igst_amount) as total_gst,
    SUM(pb.itc_eligible_amount) as total_itc_eligible,
    AVG(pb.total_amount) as average_bill_value
FROM purchase_bills pb
WHERE pb.status NOT IN ('DRAFT', 'CANCELLED')
GROUP BY DATE_TRUNC('month', pb.bill_date)
ORDER BY month DESC;

-- TDS Summary View
CREATE VIEW tds_summary AS
SELECT 
    tds_section,
    DATE_TRUNC('quarter', transaction_date) as quarter,
    COUNT(*) as total_transactions,
    SUM(payment_amount) as total_payments,
    SUM(tds_amount) as total_tds_deducted,
    AVG(tds_rate) as average_tds_rate,
    COUNT(CASE WHEN filed = TRUE THEN 1 END) as filed_returns,
    COUNT(CASE WHEN certificate_generated = TRUE THEN 1 END) as certificates_generated
FROM tds_transactions
GROUP BY tds_section, DATE_TRUNC('quarter', transaction_date)
ORDER BY quarter DESC, tds_section;

-- ============================================================================
-- SAMPLE DATA INSERTION (Optional - for testing)
-- ============================================================================

-- Insert sample HSN codes
INSERT INTO hsn_sac_codes (code, description, type, gst_rate) VALUES
('1001', 'Wheat and meslin', 'HSN', 0.00),
('8471', 'Automatic data processing machines', 'HSN', 18.00),
('998314', 'Information technology consulting services', 'SAC', 18.00),
('998313', 'Software development services', 'SAC', 18.00);

-- Insert sample expense categories
INSERT INTO expense_categories (name, description, default_tds_section) VALUES
('Professional Services', 'Consulting, legal, audit services', '194J'),
('Rent', 'Office rent and facilities', '194I'),
('Travel', 'Business travel and accommodation', NULL),
('Office Supplies', 'Stationery, equipment, etc.', NULL),
('Utilities', 'Electricity, internet, phone', NULL);

-- Add foreign key constraints that reference items_services in vendors table
ALTER TABLE vendors ADD CONSTRAINT fk_vendors_items_services 
    FOREIGN KEY (id) REFERENCES vendors(id) DEFERRABLE INITIALLY DEFERRED;

-- Update items_services to reference vendors properly
ALTER TABLE items_services ADD CONSTRAINT fk_items_services_primary_vendor 
    FOREIGN KEY (primary_vendor_id) REFERENCES vendors(id) DEFERRABLE INITIALLY DEFERRED;

-- ============================================================================
-- GRANT PERMISSIONS (Adjust as needed for your application)
-- ============================================================================

-- Create application role
-- CREATE ROLE jusfinn_app;
-- GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO jusfinn_app;
-- GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO jusfinn_app;

-- ============================================================================
-- ADDITIONAL CONSTRAINTS AND VALIDATIONS
-- ============================================================================

-- Ensure outstanding amounts are non-negative
ALTER TABLE tax_invoices ADD CONSTRAINT chk_outstanding_non_negative 
    CHECK (outstanding_amount >= 0);

ALTER TABLE purchase_bills ADD CONSTRAINT chk_outstanding_non_negative 
    CHECK (outstanding_amount >= 0);

-- Ensure credit limits are non-negative
ALTER TABLE customers ADD CONSTRAINT chk_credit_limit_non_negative 
    CHECK (credit_limit >= 0);

ALTER TABLE vendors ADD CONSTRAINT chk_credit_limit_non_negative 
    CHECK (credit_limit >= 0);

-- Ensure GST rates are valid (0-28% + some special rates)
ALTER TABLE hsn_sac_codes ADD CONSTRAINT chk_gst_rate_valid 
    CHECK (gst_rate >= 0 AND gst_rate <= 28);

-- Ensure TDS rates are valid (0-30%)
ALTER TABLE tds_transactions ADD CONSTRAINT chk_tds_rate_valid 
    CHECK (tds_rate >= 0 AND tds_rate <= 30);

-- Ensure quantities are positive
ALTER TABLE sales_order_items ADD CONSTRAINT chk_quantity_positive 
    CHECK (quantity > 0);

ALTER TABLE purchase_order_items ADD CONSTRAINT chk_quantity_positive 
    CHECK (quantity > 0);

-- ============================================================================
-- COMMENTS FOR DOCUMENTATION
-- ============================================================================

COMMENT ON TABLE customers IS 'Master data for all customers with GST compliance fields';
COMMENT ON TABLE vendors IS 'Master data for all vendors with MSME and TDS information';
COMMENT ON TABLE tax_invoices IS 'Sales invoices with E-Invoice IRN and GST compliance';
COMMENT ON TABLE purchase_bills IS 'Purchase invoices with three-way matching and ITC tracking';
COMMENT ON TABLE tds_transactions IS 'TDS deductions with quarterly return filing tracking';
COMMENT ON TABLE itc_records IS 'Input Tax Credit management with GSTR-2B reconciliation';
COMMENT ON TABLE audit_logs IS 'Complete audit trail for all data changes';

COMMENT ON COLUMN customers.gstin IS 'GST Identification Number (15 characters)';
COMMENT ON COLUMN customers.pan IS 'Permanent Account Number (10 characters)';
COMMENT ON COLUMN vendors.msme_registration IS 'MSME category for 45-day payment compliance';
COMMENT ON COLUMN tax_invoices.irn IS 'Invoice Reference Number for E-Invoice';
COMMENT ON COLUMN purchase_bills.ocr_extracted_data IS 'JSON data extracted from bill image via OCR';
COMMENT ON COLUMN tds_transactions.bsr_code IS 'Basic Statistical Return code for TDS challan';

-- End of schema 