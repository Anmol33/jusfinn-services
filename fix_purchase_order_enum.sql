-- Create the missing purchaseorderstatus ENUM type
-- Run this script on your PostgreSQL database to fix the schema issue

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
    WHEN duplicate_object THEN null;
END $$;

-- Verify the ENUM was created
SELECT 
    t.typname as enum_name,
    e.enumlabel as enum_value
FROM pg_type t 
JOIN pg_enum e ON t.oid = e.enumtypid  
WHERE t.typname = 'purchaseorderstatus'
ORDER BY e.enumsortorder;