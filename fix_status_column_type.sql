-- Fix Purchase Order Status Column Type Mismatch
-- This script fixes the column type from order_status to purchaseorderstatus

-- Step 1: Create the purchaseorderstatus ENUM if it doesn't exist
DO $$ BEGIN
    CREATE TYPE purchaseorderstatus AS ENUM (
        'draft',
        'pending_approval', 
        'approved',
        'acknowledged',
        'in_progress',
        'partially_delivered',
        'delivered',
        'completed',
        'cancelled',
        'rejected'
    );
EXCEPTION
    WHEN duplicate_object THEN 
        RAISE NOTICE 'purchaseorderstatus ENUM already exists, skipping creation';
END $$;

-- Step 2: Check current column type (for verification)
SELECT 
    column_name, 
    data_type, 
    udt_name
FROM information_schema.columns 
WHERE table_name = 'purchase_orders' 
AND column_name = 'status';

-- Step 3: Alter the column type from order_status to purchaseorderstatus
-- This maps the existing values to the new ENUM
ALTER TABLE purchase_orders 
ALTER COLUMN status TYPE purchaseorderstatus 
USING CASE 
    WHEN status::text = 'DRAFT' THEN 'draft'
    WHEN status::text = 'PENDING_APPROVAL' THEN 'pending_approval'
    WHEN status::text = 'APPROVED' THEN 'approved'
    WHEN status::text = 'IN_PROGRESS' THEN 'in_progress'
    WHEN status::text = 'PARTIALLY_DELIVERED' THEN 'partially_delivered'
    WHEN status::text = 'DELIVERED' THEN 'delivered'
    WHEN status::text = 'INVOICED' THEN 'completed'
    WHEN status::text = 'CANCELLED' THEN 'cancelled'
    ELSE 'draft'
END::purchaseorderstatus;

-- Step 4: Set the default value for new records
ALTER TABLE purchase_orders 
ALTER COLUMN status SET DEFAULT 'draft';

-- Step 5: Verify the change was successful
SELECT 
    column_name, 
    data_type, 
    udt_name,
    column_default
FROM information_schema.columns 
WHERE table_name = 'purchase_orders' 
AND column_name = 'status';

-- Step 6: Check if there are any existing records and their status values
SELECT status, COUNT(*) as count
FROM purchase_orders 
GROUP BY status
ORDER BY status;