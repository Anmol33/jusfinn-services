-- Fix approval_status check constraint to support complete workflow
-- Current constraint only allows: 'PENDING', 'APPROVED', 'REJECTED'
-- We need to add: 'PENDING_APPROVAL', 'CHANGES_REQUESTED'

-- Drop the existing check constraint
ALTER TABLE purchase_orders DROP CONSTRAINT IF EXISTS purchase_orders_approval_status_check;

-- Add the new check constraint with all required values
ALTER TABLE purchase_orders ADD CONSTRAINT purchase_orders_approval_status_check 
CHECK (approval_status IN ('PENDING', 'PENDING_APPROVAL', 'APPROVED', 'REJECTED', 'CHANGES_REQUESTED'));

-- Verify the constraint was added
SELECT conname, consrc 
FROM pg_constraint 
WHERE conrelid = 'purchase_orders'::regclass 
AND conname = 'purchase_orders_approval_status_check';