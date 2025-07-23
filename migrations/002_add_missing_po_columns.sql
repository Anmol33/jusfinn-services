-- Quick fix: Add missing columns to purchase_order_items table
-- This script adds the GRN tracking fields that are missing

-- Add GRN tracking fields to purchase_order_items table if they don't exist
DO $$ 
BEGIN
    -- Add received_quantity column if it doesn't exist
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                   WHERE table_name = 'purchase_order_items' 
                   AND column_name = 'received_quantity') THEN
        ALTER TABLE purchase_order_items 
        ADD COLUMN received_quantity DECIMAL(15, 3) DEFAULT 0;
        RAISE NOTICE 'Added received_quantity column to purchase_order_items';
    ELSE
        RAISE NOTICE 'received_quantity column already exists in purchase_order_items';
    END IF;

    -- Add pending_quantity column if it doesn't exist
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                   WHERE table_name = 'purchase_order_items' 
                   AND column_name = 'pending_quantity') THEN
        ALTER TABLE purchase_order_items 
        ADD COLUMN pending_quantity DECIMAL(15, 3) DEFAULT 0;
        RAISE NOTICE 'Added pending_quantity column to purchase_order_items';
    ELSE
        RAISE NOTICE 'pending_quantity column already exists in purchase_order_items';
    END IF;

    -- Update pending_quantity to equal quantity for existing records
    UPDATE purchase_order_items 
    SET pending_quantity = quantity 
    WHERE pending_quantity = 0 AND quantity > 0;
    
    RAISE NOTICE 'Updated pending quantities for existing purchase order items';
END $$;