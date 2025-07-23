-- Simplified GRN Tables Creation Script
-- Creates the essential GRN tables without complex triggers

-- Create GRNs table
CREATE TABLE IF NOT EXISTS grns (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id VARCHAR(255) NOT NULL,
    grn_number VARCHAR(50) NOT NULL UNIQUE,
    po_id UUID NOT NULL,
    vendor_id UUID NOT NULL,
    
    -- Dates
    grn_date DATE NOT NULL DEFAULT CURRENT_DATE,
    received_date DATE NOT NULL,
    expected_delivery_date DATE,
    
    -- Delivery Information
    delivery_note_number VARCHAR(100),
    vehicle_number VARCHAR(20),
    received_by VARCHAR(255) NOT NULL,
    
    -- Status and Workflow
    status VARCHAR(50) NOT NULL DEFAULT 'draft',
    
    -- Quality and Inspection
    quality_check_required BOOLEAN DEFAULT FALSE,
    quality_approved BOOLEAN DEFAULT TRUE,
    quality_checked_by VARCHAR(255),
    quality_check_date DATE,
    quality_notes TEXT,
    
    -- Financial
    total_ordered_amount DECIMAL(15, 2) DEFAULT 0,
    total_received_amount DECIMAL(15, 2) DEFAULT 0,
    total_accepted_amount DECIMAL(15, 2) DEFAULT 0,
    total_rejected_amount DECIMAL(15, 2) DEFAULT 0,
    
    -- Additional Information
    delivery_address TEXT,
    notes TEXT,
    rejection_reason TEXT,
    
    -- Audit
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_by UUID,
    updated_by UUID,
    
    -- Constraints
    CONSTRAINT valid_grn_status CHECK (status IN ('draft', 'pending_approval', 'approved', 'rejected', 'completed', 'cancelled'))
);

-- Create GRN Items table
CREATE TABLE IF NOT EXISTS grn_items (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    grn_id UUID NOT NULL REFERENCES grns(id) ON DELETE CASCADE,
    po_item_id UUID NOT NULL,
    
    -- Item Information
    item_description VARCHAR(500) NOT NULL,
    hsn_code VARCHAR(20) DEFAULT '',
    unit VARCHAR(20) DEFAULT 'Nos',
    
    -- Quantities
    ordered_quantity DECIMAL(15, 3) NOT NULL,
    received_quantity DECIMAL(15, 3) NOT NULL,
    accepted_quantity DECIMAL(15, 3) NOT NULL,
    rejected_quantity DECIMAL(15, 3) DEFAULT 0,
    
    -- Pricing
    unit_price DECIMAL(15, 2) NOT NULL,
    total_ordered_amount DECIMAL(15, 2) NOT NULL,
    total_received_amount DECIMAL(15, 2) NOT NULL,
    total_accepted_amount DECIMAL(15, 2) NOT NULL,
    
    -- Quality Information
    quality_status VARCHAR(20) DEFAULT 'approved',
    rejection_reason TEXT,
    batch_number VARCHAR(50),
    expiry_date DATE,
    
    -- Additional Information
    notes TEXT,
    
    -- Constraints
    CONSTRAINT valid_quality_status CHECK (quality_status IN ('approved', 'rejected', 'pending')),
    CONSTRAINT valid_quantities CHECK (
        received_quantity >= 0 AND 
        accepted_quantity >= 0 AND 
        rejected_quantity >= 0 AND
        accepted_quantity + rejected_quantity = received_quantity
    )
);

-- Create GRN Status History table
CREATE TABLE IF NOT EXISTS grn_status_history (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    grn_id UUID NOT NULL REFERENCES grns(id) ON DELETE CASCADE,
    
    previous_status VARCHAR(50),
    new_status VARCHAR(50) NOT NULL,
    changed_by VARCHAR(255) NOT NULL,
    changed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    notes TEXT,
    
    -- Constraints
    CONSTRAINT valid_previous_status CHECK (previous_status IN ('draft', 'pending_approval', 'approved', 'rejected', 'completed', 'cancelled')),
    CONSTRAINT valid_new_status CHECK (new_status IN ('draft', 'pending_approval', 'approved', 'rejected', 'completed', 'cancelled'))
);

-- Create indexes for better performance
CREATE INDEX IF NOT EXISTS idx_grns_user_id ON grns(user_id);
CREATE INDEX IF NOT EXISTS idx_grns_po_id ON grns(po_id);
CREATE INDEX IF NOT EXISTS idx_grns_vendor_id ON grns(vendor_id);
CREATE INDEX IF NOT EXISTS idx_grns_status ON grns(status);
CREATE INDEX IF NOT EXISTS idx_grns_grn_date ON grns(grn_date);
CREATE INDEX IF NOT EXISTS idx_grns_received_date ON grns(received_date);

CREATE INDEX IF NOT EXISTS idx_grn_items_grn_id ON grn_items(grn_id);
CREATE INDEX IF NOT EXISTS idx_grn_items_po_item_id ON grn_items(po_item_id);

CREATE INDEX IF NOT EXISTS idx_grn_status_history_grn_id ON grn_status_history(grn_id);
CREATE INDEX IF NOT EXISTS idx_grn_status_history_changed_at ON grn_status_history(changed_at);