-- GRN Tables Migration Script
-- This script creates the necessary tables for the Goods Receipt Note (GRN) system

-- Create GRNs table
CREATE TABLE IF NOT EXISTS grns (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id VARCHAR(255) NOT NULL,
    grn_number VARCHAR(50) NOT NULL UNIQUE,
    po_id UUID NOT NULL REFERENCES purchase_orders(id),
    vendor_id UUID NOT NULL REFERENCES vendors(id),
    
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
    po_item_id UUID NOT NULL REFERENCES purchase_order_items(id),
    
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

-- Add GRN tracking fields to purchase_order_items table
ALTER TABLE purchase_order_items 
ADD COLUMN IF NOT EXISTS received_quantity DECIMAL(15, 3) DEFAULT 0,
ADD COLUMN IF NOT EXISTS pending_quantity DECIMAL(15, 3) DEFAULT 0;

-- Update the purchase_orders status constraint to include new GRN-related statuses
ALTER TABLE purchase_orders DROP CONSTRAINT IF EXISTS valid_status_check;
ALTER TABLE purchase_orders ADD CONSTRAINT valid_status_check 
CHECK (status IN (
    'draft', 'pending_approval', 'approved', 'acknowledged', 'in_progress', 
    'partially_delivered', 'delivered', 'completed', 'cancelled', 'rejected',
    'partially_received', 'fully_received'
));

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

-- Create a trigger to automatically update the updated_at timestamp
CREATE OR REPLACE FUNCTION update_grn_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_grns_updated_at
    BEFORE UPDATE ON grns
    FOR EACH ROW
    EXECUTE FUNCTION update_grn_updated_at();

-- Create a trigger to log status changes
CREATE OR REPLACE FUNCTION log_grn_status_change()
RETURNS TRIGGER AS $$
BEGIN
    IF OLD.status IS DISTINCT FROM NEW.status THEN
        INSERT INTO grn_status_history (grn_id, previous_status, new_status, changed_by, notes)
        VALUES (NEW.id, OLD.status, NEW.status, NEW.updated_by, 'Status changed via system');
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_grn_status_change
    AFTER UPDATE ON grns
    FOR EACH ROW
    EXECUTE FUNCTION log_grn_status_change();

-- Create a function to update PO item received quantities
CREATE OR REPLACE FUNCTION update_po_item_received_quantities()
RETURNS TRIGGER AS $$
BEGIN
    -- Update the received quantity in purchase_order_items
    UPDATE purchase_order_items 
    SET received_quantity = (
        SELECT COALESCE(SUM(gi.accepted_quantity), 0)
        FROM grn_items gi
        JOIN grns g ON gi.grn_id = g.id
        WHERE gi.po_item_id = NEW.po_item_id
        AND g.status IN ('approved', 'completed')
    ),
    pending_quantity = quantity - (
        SELECT COALESCE(SUM(gi.accepted_quantity), 0)
        FROM grn_items gi
        JOIN grns g ON gi.grn_id = g.id
        WHERE gi.po_item_id = NEW.po_item_id
        AND g.status IN ('approved', 'completed')
    )
    WHERE id = NEW.po_item_id;
    
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_update_po_received_quantities
    AFTER INSERT OR UPDATE OR DELETE ON grn_items
    FOR EACH ROW
    EXECUTE FUNCTION update_po_item_received_quantities();

-- Insert sample data for testing (optional - remove in production)
-- This is commented out but can be used for testing
/*
-- Sample GRN
INSERT INTO grns (
    user_id, grn_number, po_id, vendor_id, grn_date, received_date, 
    received_by, status, total_ordered_amount, total_received_amount, 
    total_accepted_amount, notes
) VALUES (
    'test-user-id', 'GRN-2025-0001', 
    (SELECT id FROM purchase_orders LIMIT 1),
    (SELECT id FROM vendors LIMIT 1),
    CURRENT_DATE, CURRENT_DATE, 'John Doe', 'draft',
    10000.00, 9500.00, 9500.00, 'Sample GRN for testing'
);
*/

-- Grant necessary permissions (adjust as needed for your setup)
-- GRANT SELECT, INSERT, UPDATE, DELETE ON grns TO your_app_user;
-- GRANT SELECT, INSERT, UPDATE, DELETE ON grn_items TO your_app_user;
-- GRANT SELECT, INSERT, UPDATE, DELETE ON grn_status_history TO your_app_user;