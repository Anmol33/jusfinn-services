# Inventory Synchronization Best Practices

## Overview
This guide outlines best practices for maintaining real-time inventory accuracy throughout the sales workflow, ensuring stock consistency and preventing overselling.

## 1. Inventory Architecture

### Multi-Warehouse Support
```sql
-- Warehouse-based inventory tracking
CREATE TABLE warehouse_stock_levels (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    warehouse_id UUID NOT NULL REFERENCES warehouses(id),
    item_service_id UUID NOT NULL REFERENCES items_services(id),
    
    -- Stock Levels
    physical_stock DECIMAL(15,3) NOT NULL DEFAULT 0,
    available_stock DECIMAL(15,3) NOT NULL DEFAULT 0, -- Physical - Reserved
    reserved_stock DECIMAL(15,3) NOT NULL DEFAULT 0,
    in_transit_stock DECIMAL(15,3) NOT NULL DEFAULT 0,
    
    -- Valuation
    average_cost DECIMAL(15,2) NOT NULL DEFAULT 0,
    total_value DECIMAL(15,2) NOT NULL DEFAULT 0,
    
    -- Reorder Management
    reorder_level DECIMAL(15,3) DEFAULT 0,
    reorder_quantity DECIMAL(15,3) DEFAULT 0,
    max_stock_level DECIMAL(15,3),
    
    -- Tracking
    last_updated TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    last_movement_id UUID REFERENCES stock_movements(id),
    
    UNIQUE(warehouse_id, item_service_id)
);
```

### Stock Reservation System
```sql
-- Stock reservations for sales orders
CREATE TABLE stock_reservations (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    warehouse_id UUID NOT NULL REFERENCES warehouses(id),
    item_service_id UUID NOT NULL REFERENCES items_services(id),
    
    -- Reservation Details
    reference_type VARCHAR(20) NOT NULL CHECK (reference_type IN ('SALES_ORDER', 'QUOTATION', 'MANUAL')),
    reference_id UUID NOT NULL,
    reference_number VARCHAR(50),
    
    -- Quantities
    reserved_quantity DECIMAL(15,3) NOT NULL,
    fulfilled_quantity DECIMAL(15,3) DEFAULT 0,
    remaining_quantity DECIMAL(15,3) GENERATED ALWAYS AS (reserved_quantity - fulfilled_quantity) STORED,
    
    -- Status
    status VARCHAR(20) DEFAULT 'ACTIVE' CHECK (status IN ('ACTIVE', 'FULFILLED', 'CANCELLED', 'EXPIRED')),
    
    -- Timing
    reserved_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    expires_at TIMESTAMP WITH TIME ZONE,
    fulfilled_at TIMESTAMP WITH TIME ZONE,
    
    -- Audit
    created_by UUID REFERENCES users(id),
    
    INDEX(warehouse_id, item_service_id, status),
    INDEX(reference_type, reference_id)
);
```

## 2. Real-time Synchronization Points

### Sales Workflow Integration Points

| Stage | Inventory Action | Stock Impact | Validation Required |
|-------|------------------|-------------|-------------------|
| **Quotation Creation** | Stock availability check | None | Available quantity check |
| **Quotation Approval** | Optional soft reservation | Reserve stock (optional) | Stock availability |
| **Sales Order Creation** | Hard stock reservation | Reduce available stock | Available >= required |
| **Sales Order Approval** | Confirm reservation | Maintain reservation | Credit limit + stock |
| **Delivery Challan** | Allocate specific stock | Transfer to allocated | Reserved >= allocated |
| **Goods Dispatch** | Reduce physical stock | Reduce physical inventory | Allocated quantity check |
| **Invoice Generation** | Update cost of goods sold | Calculate COGS | Delivery confirmation |
| **Sales Return** | Return to inventory | Increase physical stock | Quality check required |

### Implementation Functions

```sql
-- Comprehensive stock update function
CREATE OR REPLACE FUNCTION update_inventory_transaction(
    p_company_id UUID,
    p_warehouse_id UUID,
    p_item_id UUID,
    p_transaction_type stock_movement_type,
    p_quantity DECIMAL(15,3),
    p_unit_cost DECIMAL(15,2) DEFAULT NULL,
    p_reference_type VARCHAR(20) DEFAULT NULL,
    p_reference_id UUID DEFAULT NULL,
    p_reference_number VARCHAR(50) DEFAULT NULL,
    p_user_id UUID DEFAULT NULL
) RETURNS JSONB AS $$
DECLARE
    v_current_stock RECORD;
    v_new_physical_stock DECIMAL(15,3);
    v_new_available_stock DECIMAL(15,3);
    v_movement_direction INTEGER;
    v_movement_id UUID;
    v_result JSONB;
BEGIN
    -- Acquire row-level lock to prevent concurrent modifications
    SELECT * INTO v_current_stock
    FROM warehouse_stock_levels
    WHERE warehouse_id = p_warehouse_id 
    AND item_service_id = p_item_id
    FOR UPDATE;
    
    -- Initialize if record doesn't exist
    IF NOT FOUND THEN
        INSERT INTO warehouse_stock_levels (
            warehouse_id, item_service_id, physical_stock, 
            available_stock, reserved_stock, average_cost, total_value
        ) VALUES (
            p_warehouse_id, p_item_id, 0, 0, 0, 
            COALESCE(p_unit_cost, 0), 0
        ) RETURNING * INTO v_current_stock;
    END IF;
    
    -- Determine movement direction (positive = inward, negative = outward)
    v_movement_direction := CASE 
        WHEN p_transaction_type IN ('PURCHASE', 'SALES_RETURN', 'STOCK_ADJUSTMENT_IN', 'OPENING_STOCK') THEN 1
        WHEN p_transaction_type IN ('SALES', 'PURCHASE_RETURN', 'STOCK_ADJUSTMENT_OUT', 'CONSUMPTION') THEN -1
        ELSE 0
    END;
    
    -- Calculate new stock levels
    v_new_physical_stock := v_current_stock.physical_stock + (p_quantity * v_movement_direction);
    
    -- Validate negative stock prevention
    IF v_new_physical_stock < 0 AND p_transaction_type NOT IN ('STOCK_ADJUSTMENT_OUT') THEN
        RAISE EXCEPTION 'Insufficient stock. Available: %, Required: %', 
            v_current_stock.physical_stock, p_quantity;
    END IF;
    
    -- Insert stock movement record
    INSERT INTO stock_movements (
        company_id, warehouse_id, item_service_id, movement_type,
        movement_date, quantity, rate, total_value,
        reference_type, reference_id, reference_number,
        stock_before, stock_after, created_by
    ) VALUES (
        p_company_id, p_warehouse_id, p_item_id, p_transaction_type,
        CURRENT_DATE, p_quantity * v_movement_direction, 
        COALESCE(p_unit_cost, v_current_stock.average_cost),
        (p_quantity * v_movement_direction) * COALESCE(p_unit_cost, v_current_stock.average_cost),
        p_reference_type, p_reference_id, p_reference_number,
        v_current_stock.physical_stock, v_new_physical_stock, p_user_id
    ) RETURNING id INTO v_movement_id;
    
    -- Update warehouse stock levels
    UPDATE warehouse_stock_levels SET
        physical_stock = v_new_physical_stock,
        available_stock = v_new_physical_stock - reserved_stock,
        average_cost = CASE 
            WHEN v_new_physical_stock > 0 AND v_movement_direction > 0 AND p_unit_cost IS NOT NULL THEN
                ((physical_stock * average_cost) + (p_quantity * p_unit_cost)) / v_new_physical_stock
            ELSE average_cost
        END,
        total_value = v_new_physical_stock * CASE 
            WHEN v_new_physical_stock > 0 AND v_movement_direction > 0 AND p_unit_cost IS NOT NULL THEN
                ((physical_stock * average_cost) + (p_quantity * p_unit_cost)) / v_new_physical_stock
            ELSE average_cost
        END,
        last_updated = NOW(),
        last_movement_id = v_movement_id
    WHERE warehouse_id = p_warehouse_id 
    AND item_service_id = p_item_id;
    
    -- Build result
    SELECT jsonb_build_object(
        'success', true,
        'movement_id', v_movement_id,
        'previous_stock', v_current_stock.physical_stock,
        'new_stock', v_new_physical_stock,
        'movement_quantity', p_quantity * v_movement_direction,
        'updated_at', NOW()
    ) INTO v_result;
    
    RETURN v_result;
    
EXCEPTION
    WHEN OTHERS THEN
        RETURN jsonb_build_object(
            'success', false,
            'error', SQLERRM,
            'error_code', SQLSTATE
        );
END;
$$ LANGUAGE plpgsql;
```

## 3. Stock Reservation Management

### Automatic Reservation on Sales Order
```sql
-- Reserve stock for sales order
CREATE OR REPLACE FUNCTION reserve_stock_for_order(
    p_order_id UUID,
    p_user_id UUID
) RETURNS JSONB AS $$
DECLARE
    v_order RECORD;
    v_item RECORD;
    v_warehouse_id UUID;
    v_reservation_id UUID;
    v_total_reserved INTEGER := 0;
    v_errors JSONB := '[]';
    v_result JSONB;
BEGIN
    -- Get order details
    SELECT * INTO v_order FROM sales_orders WHERE id = p_order_id;
    
    -- Get default warehouse
    SELECT id INTO v_warehouse_id 
    FROM warehouses 
    WHERE company_id = v_order.company_id 
    AND is_default = TRUE;
    
    -- Process each order item
    FOR v_item IN 
        SELECT * FROM sales_order_items 
        WHERE order_id = p_order_id
    LOOP
        BEGIN
            -- Check available stock
            IF NOT check_stock_availability_single(
                v_warehouse_id, v_item.item_service_id, v_item.quantity
            ) THEN
                v_errors := v_errors || jsonb_build_object(
                    'item_id', v_item.item_service_id,
                    'error', 'Insufficient stock available'
                );
                CONTINUE;
            END IF;
            
            -- Create reservation
            INSERT INTO stock_reservations (
                warehouse_id, item_service_id, reference_type, reference_id,
                reference_number, reserved_quantity, created_by
            ) VALUES (
                v_warehouse_id, v_item.item_service_id, 'SALES_ORDER', p_order_id,
                v_order.order_number, v_item.quantity, p_user_id
            ) RETURNING id INTO v_reservation_id;
            
            -- Update warehouse stock levels (reduce available)
            UPDATE warehouse_stock_levels SET
                reserved_stock = reserved_stock + v_item.quantity,
                available_stock = physical_stock - (reserved_stock + v_item.quantity),
                last_updated = NOW()
            WHERE warehouse_id = v_warehouse_id 
            AND item_service_id = v_item.item_service_id;
            
            v_total_reserved := v_total_reserved + 1;
            
        EXCEPTION
            WHEN OTHERS THEN
                v_errors := v_errors || jsonb_build_object(
                    'item_id', v_item.item_service_id,
                    'error', SQLERRM
                );
        END;
    END LOOP;
    
    -- Update order status if all items reserved
    IF jsonb_array_length(v_errors) = 0 THEN
        UPDATE sales_orders SET 
            status = 'APPROVED',
            updated_at = NOW()
        WHERE id = p_order_id;
    END IF;
    
    SELECT jsonb_build_object(
        'success', jsonb_array_length(v_errors) = 0,
        'items_reserved', v_total_reserved,
        'errors', v_errors
    ) INTO v_result;
    
    RETURN v_result;
END;
$$ LANGUAGE plpgsql;

-- Release stock reservation
CREATE OR REPLACE FUNCTION release_stock_reservation(
    p_reservation_id UUID,
    p_reason VARCHAR(100) DEFAULT 'Order cancelled'
) RETURNS BOOLEAN AS $$
DECLARE
    v_reservation RECORD;
BEGIN
    -- Get reservation details
    SELECT * INTO v_reservation 
    FROM stock_reservations 
    WHERE id = p_reservation_id AND status = 'ACTIVE';
    
    IF NOT FOUND THEN
        RETURN FALSE;
    END IF;
    
    -- Update warehouse stock levels
    UPDATE warehouse_stock_levels SET
        reserved_stock = reserved_stock - v_reservation.remaining_quantity,
        available_stock = physical_stock - (reserved_stock - v_reservation.remaining_quantity),
        last_updated = NOW()
    WHERE warehouse_id = v_reservation.warehouse_id 
    AND item_service_id = v_reservation.item_service_id;
    
    -- Mark reservation as cancelled
    UPDATE stock_reservations SET
        status = 'CANCELLED',
        fulfilled_at = NOW()
    WHERE id = p_reservation_id;
    
    RETURN TRUE;
END;
$$ LANGUAGE plpgsql;
```

## 4. Batch and Serial Number Tracking

### Advanced Inventory with Batch Management
```sql
-- Batch/Serial tracking
CREATE TABLE inventory_batches (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    warehouse_id UUID NOT NULL REFERENCES warehouses(id),
    item_service_id UUID NOT NULL REFERENCES items_services(id),
    
    -- Batch Details
    batch_number VARCHAR(50) NOT NULL,
    serial_numbers TEXT[], -- Array of serial numbers
    
    -- Quantities
    total_quantity DECIMAL(15,3) NOT NULL,
    available_quantity DECIMAL(15,3) NOT NULL,
    reserved_quantity DECIMAL(15,3) DEFAULT 0,
    
    -- Dates
    manufacturing_date DATE,
    expiry_date DATE,
    received_date DATE DEFAULT CURRENT_DATE,
    
    -- Costing
    unit_cost DECIMAL(15,2) NOT NULL,
    total_value DECIMAL(15,2) GENERATED ALWAYS AS (available_quantity * unit_cost) STORED,
    
    -- Status
    status VARCHAR(20) DEFAULT 'ACTIVE' CHECK (status IN ('ACTIVE', 'EXPIRED', 'DAMAGED', 'BLOCKED')),
    
    -- Audit
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    UNIQUE(warehouse_id, item_service_id, batch_number)
);

-- FIFO/LIFO inventory allocation
CREATE OR REPLACE FUNCTION allocate_inventory_fifo(
    p_warehouse_id UUID,
    p_item_id UUID,
    p_required_quantity DECIMAL(15,3)
) RETURNS TABLE (
    batch_id UUID,
    batch_number VARCHAR(50),
    allocated_quantity DECIMAL(15,3),
    unit_cost DECIMAL(15,2),
    expiry_date DATE
) AS $$
DECLARE
    v_batch RECORD;
    v_remaining_qty DECIMAL(15,3) := p_required_quantity;
    v_allocated_qty DECIMAL(15,3);
BEGIN
    -- FIFO allocation (oldest batches first)
    FOR v_batch IN 
        SELECT * FROM inventory_batches
        WHERE warehouse_id = p_warehouse_id 
        AND item_service_id = p_item_id
        AND status = 'ACTIVE'
        AND available_quantity > 0
        ORDER BY received_date ASC, batch_number ASC
    LOOP
        EXIT WHEN v_remaining_qty <= 0;
        
        v_allocated_qty := LEAST(v_batch.available_quantity, v_remaining_qty);
        
        RETURN QUERY SELECT 
            v_batch.id,
            v_batch.batch_number,
            v_allocated_qty,
            v_batch.unit_cost,
            v_batch.expiry_date;
        
        v_remaining_qty := v_remaining_qty - v_allocated_qty;
    END LOOP;
    
    -- Check if full quantity could be allocated
    IF v_remaining_qty > 0 THEN
        RAISE EXCEPTION 'Insufficient stock in batches. Short by: %', v_remaining_qty;
    END IF;
END;
$$ LANGUAGE plpgsql;
```

## 5. Inventory Synchronization Triggers

### Automatic Updates on Document State Changes
```sql
-- Trigger for sales order stock reservation
CREATE OR REPLACE FUNCTION trigger_order_stock_reservation() RETURNS TRIGGER AS $$
BEGIN
    -- Reserve stock when order is approved
    IF NEW.status = 'APPROVED' AND (OLD.status IS NULL OR OLD.status != 'APPROVED') THEN
        PERFORM reserve_stock_for_order(NEW.id, NEW.updated_by);
    END IF;
    
    -- Release reservation when order is cancelled
    IF NEW.status = 'CANCELLED' AND OLD.status != 'CANCELLED' THEN
        UPDATE stock_reservations SET
            status = 'CANCELLED',
            fulfilled_at = NOW()
        WHERE reference_type = 'SALES_ORDER' 
        AND reference_id = NEW.id 
        AND status = 'ACTIVE';
        
        -- Update warehouse stock levels
        UPDATE warehouse_stock_levels SET
            reserved_stock = reserved_stock - sr.remaining_quantity,
            available_stock = physical_stock - (reserved_stock - sr.remaining_quantity),
            last_updated = NOW()
        FROM stock_reservations sr
        WHERE sr.warehouse_id = warehouse_stock_levels.warehouse_id
        AND sr.item_service_id = warehouse_stock_levels.item_service_id
        AND sr.reference_type = 'SALES_ORDER'
        AND sr.reference_id = NEW.id;
    END IF;
    
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_sales_order_stock_sync
    AFTER UPDATE ON sales_orders
    FOR EACH ROW
    EXECUTE FUNCTION trigger_order_stock_reservation();

-- Trigger for delivery challan stock allocation
CREATE OR REPLACE FUNCTION trigger_delivery_stock_update() RETURNS TRIGGER AS $$
BEGIN
    -- Allocate stock when delivery challan is dispatched
    IF NEW.status = 'DISPATCHED' AND (OLD.status IS NULL OR OLD.status != 'DISPATCHED') THEN
        -- Move from reserved to allocated
        PERFORM allocate_delivery_stock(NEW.id);
    END IF;
    
    -- Update physical stock when goods are delivered
    IF NEW.status = 'DELIVERED' AND OLD.status != 'DELIVERED' THEN
        PERFORM update_delivery_stock_movement(NEW.id);
    END IF;
    
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_delivery_challan_stock_sync
    AFTER UPDATE ON delivery_challans
    FOR EACH ROW
    EXECUTE FUNCTION trigger_delivery_stock_update();
```

## 6. Real-time Stock Monitoring

### Stock Alert System
```sql
-- Create stock alerts view
CREATE VIEW stock_alerts AS
SELECT 
    w.name as warehouse_name,
    its.name as item_name,
    its.item_code,
    wsl.physical_stock,
    wsl.available_stock,
    wsl.reserved_stock,
    its.reorder_level,
    its.max_stock_level,
    CASE 
        WHEN wsl.available_stock <= 0 THEN 'OUT_OF_STOCK'
        WHEN wsl.available_stock <= its.reorder_level THEN 'LOW_STOCK'
        WHEN wsl.physical_stock >= its.max_stock_level THEN 'OVERSTOCK'
        ELSE 'NORMAL'
    END as alert_type,
    (its.reorder_level - wsl.available_stock) as shortage_quantity,
    wsl.last_updated
FROM warehouse_stock_levels wsl
JOIN warehouses w ON wsl.warehouse_id = w.id
JOIN items_services its ON wsl.item_service_id = its.id
WHERE its.type = 'PRODUCT' 
AND its.is_active = TRUE
AND (
    wsl.available_stock <= its.reorder_level OR
    wsl.physical_stock >= its.max_stock_level OR
    wsl.available_stock <= 0
)
ORDER BY 
    CASE 
        WHEN wsl.available_stock <= 0 THEN 1
        WHEN wsl.available_stock <= its.reorder_level THEN 2
        WHEN wsl.physical_stock >= its.max_stock_level THEN 3
        ELSE 4
    END,
    wsl.available_stock ASC;

-- Stock movement audit trail
CREATE VIEW stock_movement_trail AS
SELECT 
    sm.id,
    c.legal_name as company_name,
    w.name as warehouse_name,
    its.name as item_name,
    its.item_code,
    sm.movement_type,
    sm.movement_date,
    sm.quantity,
    sm.rate,
    sm.total_value,
    sm.reference_type,
    sm.reference_number,
    sm.stock_before,
    sm.stock_after,
    u.full_name as created_by_user,
    sm.created_at
FROM stock_movements sm
JOIN companies c ON sm.company_id = c.id
JOIN warehouses w ON sm.warehouse_id = w.id
JOIN items_services its ON sm.item_service_id = its.id
LEFT JOIN users u ON sm.created_by = u.id
ORDER BY sm.created_at DESC;
```

## 7. Performance Optimization

### Indexing Strategy
```sql
-- Critical indexes for inventory queries
CREATE INDEX CONCURRENTLY idx_warehouse_stock_levels_item_warehouse 
    ON warehouse_stock_levels(item_service_id, warehouse_id);

CREATE INDEX CONCURRENTLY idx_stock_movements_date_type 
    ON stock_movements(movement_date DESC, movement_type);

CREATE INDEX CONCURRENTLY idx_stock_reservations_reference 
    ON stock_reservations(reference_type, reference_id, status);

CREATE INDEX CONCURRENTLY idx_inventory_batches_expiry 
    ON inventory_batches(expiry_date) WHERE status = 'ACTIVE';

-- Partial index for active stock levels
CREATE INDEX CONCURRENTLY idx_active_stock_levels 
    ON warehouse_stock_levels(warehouse_id, item_service_id) 
    WHERE physical_stock > 0;
```

### Caching Strategy
```sql
-- Materialized view for frequently accessed stock data
CREATE MATERIALIZED VIEW current_stock_summary AS
SELECT 
    its.id as item_id,
    its.name as item_name,
    its.item_code,
    its.type as item_type,
    SUM(wsl.physical_stock) as total_physical_stock,
    SUM(wsl.available_stock) as total_available_stock,
    SUM(wsl.reserved_stock) as total_reserved_stock,
    AVG(wsl.average_cost) as weighted_average_cost,
    SUM(wsl.total_value) as total_inventory_value,
    COUNT(w.id) as warehouse_count,
    MAX(wsl.last_updated) as last_updated
FROM items_services its
LEFT JOIN warehouse_stock_levels wsl ON its.id = wsl.item_service_id
LEFT JOIN warehouses w ON wsl.warehouse_id = w.id
WHERE its.type = 'PRODUCT' AND its.is_active = TRUE
GROUP BY its.id, its.name, its.item_code, its.type;

-- Refresh materialized view periodically
CREATE OR REPLACE FUNCTION refresh_stock_summary() RETURNS VOID AS $$
BEGIN
    REFRESH MATERIALIZED VIEW CONCURRENTLY current_stock_summary;
END;
$$ LANGUAGE plpgsql;

-- Schedule refresh every 5 minutes (using pg_cron or external scheduler)
```

## 8. Error Handling and Recovery

### Inventory Reconciliation
```sql
-- Inventory reconciliation function
CREATE OR REPLACE FUNCTION reconcile_inventory(
    p_warehouse_id UUID,
    p_item_id UUID DEFAULT NULL,
    p_reconciliation_date DATE DEFAULT CURRENT_DATE
) RETURNS TABLE (
    item_id UUID,
    item_name VARCHAR(255),
    calculated_stock DECIMAL(15,3),
    recorded_stock DECIMAL(15,3),
    variance DECIMAL(15,3),
    variance_value DECIMAL(15,2)
) AS $$
BEGIN
    RETURN QUERY
    WITH calculated_stock AS (
        SELECT 
            sm.item_service_id,
            COALESCE(SUM(
                CASE 
                    WHEN sm.movement_type IN ('PURCHASE', 'SALES_RETURN', 'STOCK_ADJUSTMENT', 'OPENING_STOCK') 
                    THEN sm.quantity
                    ELSE -sm.quantity
                END
            ), 0) as calc_stock
        FROM stock_movements sm
        WHERE sm.warehouse_id = p_warehouse_id
        AND (p_item_id IS NULL OR sm.item_service_id = p_item_id)
        AND sm.movement_date <= p_reconciliation_date
        GROUP BY sm.item_service_id
    )
    SELECT 
        its.id,
        its.name,
        COALESCE(cs.calc_stock, 0),
        COALESCE(wsl.physical_stock, 0),
        COALESCE(cs.calc_stock, 0) - COALESCE(wsl.physical_stock, 0),
        (COALESCE(cs.calc_stock, 0) - COALESCE(wsl.physical_stock, 0)) * COALESCE(wsl.average_cost, 0)
    FROM items_services its
    LEFT JOIN calculated_stock cs ON its.id = cs.item_service_id
    LEFT JOIN warehouse_stock_levels wsl ON its.id = wsl.item_service_id 
        AND wsl.warehouse_id = p_warehouse_id
    WHERE its.type = 'PRODUCT'
    AND (p_item_id IS NULL OR its.id = p_item_id)
    AND (cs.calc_stock IS NOT NULL OR wsl.physical_stock IS NOT NULL)
    AND ABS(COALESCE(cs.calc_stock, 0) - COALESCE(wsl.physical_stock, 0)) > 0.001;
END;
$$ LANGUAGE plpgsql;
```

This comprehensive inventory synchronization system ensures real-time accuracy, prevents overselling, and maintains complete audit trails throughout the sales workflow. 