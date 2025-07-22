-- PostgreSQL Enum Creation Script
-- This script creates all the enum types required by the application

-- Create PurchaseOrderStatus ENUM for purchase order lifecycle
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

-- Create OrderStatusEnum for purchase orders
DO $$ BEGIN
    CREATE TYPE orderstatusenum AS ENUM (
        'DRAFT',
        'PENDING_APPROVAL', 
        'APPROVED',
        'IN_PROGRESS',
        'PARTIALLY_DELIVERED',
        'DELIVERED',
        'INVOICED',
        'CANCELLED'
    );
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

-- Create POApprovalStatusEnum for purchase order approvals
DO $$ BEGIN
    CREATE TYPE poapprovalstatusenum AS ENUM (
        'draft',
        'pending_approval',
        'level_1_approved',
        'level_2_approved', 
        'final_approved',
        'rejected',
        'cancelled'
    );
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

-- Create ApprovalActionEnum for approval actions
DO $$ BEGIN
    CREATE TYPE approvalactionenum AS ENUM (
        'submit',
        'approve',
        'reject',
        'request_changes',
        'cancel'
    );
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

-- Create ApprovalLevelEnum for approval levels
DO $$ BEGIN
    CREATE TYPE approvallevelenum AS ENUM (
        'level_1',
        'level_2', 
        'level_3',
        'finance',
        'admin'
    );
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

-- Create PaymentTermsEnum
DO $$ BEGIN
    CREATE TYPE paymenttermsenum AS ENUM (
        'IMMEDIATE',
        'NET_15',
        'NET_30',
        'NET_45',
        'NET_60',
        'NET_90'
    );
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

-- Create GSTRegistrationType
DO $$ BEGIN
    CREATE TYPE gstregistrationtype AS ENUM (
        'REGULAR',
        'COMPOSITION',
        'INPUT_SERVICE_DISTRIBUTOR',
        'TDS',
        'TCS',
        'NON_RESIDENT',
        'OIDAR',
        'EMBASSIES',
        'UN_BODY',
        'CASUAL_TAXABLE_PERSON'
    );
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

-- Create TDSSectionEnum
DO $$ BEGIN
    CREATE TYPE tdssectionenum AS ENUM (
        '194A', '194B', '194BB', '194C', '194D', '194DA', '194E', '194EE',
        '194F', '194G', '194H', '194I', '194IA', '194IB', '194IC', '194J',
        '194K', '194LA', '194LB', '194LBA', '194LBB', '194LBC', '194LC',
        '194M', '194N', '194O', '194P', '194Q', '194R', '194S'
    );
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

-- Create ITCStatusEnum
DO $$ BEGIN
    CREATE TYPE itcstatusenum AS ENUM (
        'ELIGIBLE',
        'CLAIMED',
        'REVERSED',
        'BLOCKED',
        'LAPSED'
    );
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

-- Create MSMERegistrationEnum
DO $$ BEGIN
    CREATE TYPE msmeregistrationenum AS ENUM (
        'MICRO',
        'SMALL',
        'MEDIUM',
        'NOT_APPLICABLE'
    );
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

-- Create InvoiceStatusEnum
DO $$ BEGIN
    CREATE TYPE invoicestatusenum AS ENUM (
        'DRAFT',
        'PENDING_APPROVAL',
        'APPROVED',
        'SENT',
        'PARTIALLY_PAID',
        'PAID',
        'OVERDUE',
        'CANCELLED',
        'CREDITED'
    );
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

-- Create AccountTypeEnum for bank accounts
DO $$ BEGIN
    CREATE TYPE accounttypeenum AS ENUM (
        'savings',
        'current',
        'overdraft',
        'fixed_deposit',
        'cash_credit'
    );
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

-- Create TransactionTypeEnum
DO $$ BEGIN
    CREATE TYPE transactiontypeenum AS ENUM (
        'debit',
        'credit'
    );
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

-- Create PaymentTypeEnum
DO $$ BEGIN
    CREATE TYPE paymenttypeenum AS ENUM (
        'vendor_payment',
        'employee_reimbursement',
        'salary_payment',
        'tax_payment',
        'advance_payment',
        'refund'
    );
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

-- Create PaymentMethodEnum
DO $$ BEGIN
    CREATE TYPE paymentmethodenum AS ENUM (
        'rtgs',
        'neft',
        'imps',
        'cheque',
        'cash',
        'upi',
        'demand_draft'
    );
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

-- Create PaymentReferenceTypeEnum
DO $$ BEGIN
    CREATE TYPE paymentreferencetypeenum AS ENUM (
        'purchase_bill',
        'expense',
        'advance',
        'salary'
    );
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

-- Create PaymentStatusEnum
DO $$ BEGIN
    CREATE TYPE paymentstatusenum AS ENUM (
        'draft',
        'pending_approval',
        'approved',
        'processed',
        'failed',
        'cancelled'
    );
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

-- Create ApprovalStatusEnum
DO $$ BEGIN
    CREATE TYPE approvalstatusenum AS ENUM (
        'pending',
        'approved',
        'rejected'
    );
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

-- Create ReconciliationStatusEnum
DO $$ BEGIN
    CREATE TYPE reconciliationstatusenum AS ENUM (
        'unreconciled',
        'reconciled',
        'in_progress',
        'partially_reconciled'
    );
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

-- Create ModuleTypeEnum
DO $$ BEGIN
    CREATE TYPE moduletypeenum AS ENUM (
        'purchase',
        'expense',
        'payroll',
        'general'
    );
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

-- Verify enum creation
SELECT 
    t.typname as enum_name,
    e.enumlabel as enum_value
FROM pg_type t 
JOIN pg_enum e ON t.oid = e.enumtypid  
WHERE t.typname LIKE '%enum'
ORDER BY t.typname, e.enumsortorder;