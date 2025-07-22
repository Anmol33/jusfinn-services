-- Fix enum type mismatch by renaming existing enum to match SQLAlchemy expectations

-- First, let's rename the existing order_status enum to orderstatusenum
-- This avoids data loss and maintains existing enum values

-- Drop the duplicate orderstatusenum we created (if it exists)
DROP TYPE IF EXISTS orderstatusenum;

-- Rename the existing order_status to orderstatusenum
ALTER TYPE order_status RENAME TO orderstatusenum;

-- Verify the change
SELECT 
    t.typname as enum_name,
    e.enumlabel as enum_value
FROM pg_type t 
JOIN pg_enum e ON t.oid = e.enumtypid  
WHERE t.typname = 'orderstatusenum'
ORDER BY e.enumsortorder;