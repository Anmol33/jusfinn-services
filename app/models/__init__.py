# Import all models directly in this __init__.py file to avoid circular imports

from datetime import datetime
from typing import Optional, List, Dict, Any
from decimal import Decimal
from pydantic import BaseModel, Field, validator
from enum import Enum
import enum

# SQLAlchemy imports for PostgreSQL models
from sqlalchemy import Column, String, Integer, DateTime, Boolean, Text, Numeric, Date, ForeignKey, Enum as SQLEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
import uuid

# Shared database base
from app.database import Base

# Import separated model groups
from .auth_models import *
from .client_models import *
from .vendor_models import *

# =====================================================
# EXPENSE MODELS  
# =====================================================

class ExpenseCreateRequest(BaseModel):
    """Request model for creating expense."""
    category_id: int
    vendor_id: Optional[str] = None
    expense_date: datetime
    description: str
    amount: float
    cgst_amount: float = 0.0
    sgst_amount: float = 0.0
    igst_amount: float = 0.0
    tds_amount: float = 0.0
    receipt_number: Optional[str] = None
    receipt_date: Optional[datetime] = None
    notes: Optional[str] = None

class ExpenseResponse(BaseModel):
    """Response model for expense."""
    id: str
    category_id: int
    vendor_id: Optional[str] = None
    expense_date: datetime
    description: str
    amount: float
    cgst_amount: float
    sgst_amount: float
    igst_amount: float
    tds_amount: float
    receipt_number: Optional[str] = None
    receipt_date: Optional[datetime] = None
    notes: Optional[str] = None
    created_at: datetime
    updated_at: datetime

# =====================================================
# BANK & PAYMENT MODELS
# =====================================================

class BankAccountCreateRequest(BaseModel):
    """Request model for creating bank account."""
    account_name: str
    account_number: str
    bank_name: str
    branch_name: Optional[str] = None
    ifsc_code: str
    account_type: str = 'CURRENT'

class BankAccountResponse(BaseModel):
    """Response model for bank account."""
    id: str
    account_name: str
    account_number: str
    bank_name: str
    branch_name: Optional[str] = None
    ifsc_code: str
    account_type: str
    is_active: bool
    created_at: datetime
    updated_at: datetime

class PaymentCreateRequest(BaseModel):
    """Request model for creating payment."""
    vendor_id: str
    amount: float
    payment_method: str
    payment_date: datetime
    bank_account_id: str
    reference_number: Optional[str] = None
    notes: Optional[str] = None

class PaymentResponse(BaseModel):
    """Response model for payment."""
    id: str
    vendor_id: str
    amount: float
    payment_method: str
    payment_date: datetime
    bank_account_id: str
    reference_number: Optional[str] = None
    notes: Optional[str] = None
    status: str
    created_at: datetime
    updated_at: datetime

class BankTransactionImportRequest(BaseModel):
    """Request model for importing bank transactions."""
    bank_account_id: str
    transactions: List[Dict[str, Any]]

class BankTransactionResponse(BaseModel):
    """Response model for bank transaction."""
    id: str
    bank_account_id: str
    transaction_date: datetime
    description: str
    amount: float
    transaction_type: str
    balance: float
    reference_number: Optional[str] = None
    created_at: datetime

# =====================================================
# DATABASE ENUMS
# =====================================================

class GSTRegistrationType(enum.Enum):
    REGULAR = "REGULAR"
    COMPOSITION = "COMPOSITION"
    INPUT_SERVICE_DISTRIBUTOR = "INPUT_SERVICE_DISTRIBUTOR"
    TDS = "TDS"
    TCS = "TCS"
    NON_RESIDENT = "NON_RESIDENT"
    OIDAR = "OIDAR"
    EMBASSIES = "EMBASSIES"
    UN_BODY = "UN_BODY"
    CASUAL_TAXABLE_PERSON = "CASUAL_TAXABLE_PERSON"

class PaymentTermsEnum(enum.Enum):
    IMMEDIATE = "IMMEDIATE"
    NET_15 = "NET_15"
    NET_30 = "NET_30"
    NET_45 = "NET_45"
    NET_60 = "NET_60"
    NET_90 = "NET_90"

class TDSSectionEnum(enum.Enum):
    SECTION_194A = "194A"
    SECTION_194B = "194B"
    SECTION_194C = "194C"
    SECTION_194J = "194J"
    SECTION_194O = "194O"

class ITCStatusEnum(enum.Enum):
    ELIGIBLE = "ELIGIBLE"
    CLAIMED = "CLAIMED"
    REVERSED = "REVERSED"
    BLOCKED = "BLOCKED"
    LAPSED = "LAPSED"

class InvoiceStatusEnum(enum.Enum):
    DRAFT = "DRAFT"
    PENDING_APPROVAL = "PENDING_APPROVAL"
    APPROVED = "APPROVED"
    SENT = "SENT"
    PARTIALLY_PAID = "PARTIALLY_PAID"
    PAID = "PAID"
    OVERDUE = "OVERDUE"
    CANCELLED = "CANCELLED"
    CREDITED = "CREDITED"

# Purchase Order Status is now defined in app.models.purchase_order_models
# Removed duplicate definition to avoid import conflicts

class ApprovalActionEnum(str, enum.Enum):
    APPROVE = "approve"
    REJECT = "reject"
    REQUEST_CHANGES = "request_changes"
    ESCALATE = "escalate"
    CANCEL = "cancel"

class ApprovalLevelEnum(str, enum.Enum):
    LEVEL_1 = "level_1"
    LEVEL_2 = "level_2"
    LEVEL_3 = "level_3"
    FINANCE = "finance"
    ADMIN = "admin"

# =====================================================
# SQLALCHEMY DATABASE MODELS
# =====================================================

class State(Base):
    __tablename__ = "states"
    
    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False, unique=True)
    code = Column(String(2), nullable=False, unique=True)
    gst_state_code = Column(String(2), nullable=False, unique=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow)

class HSNSACCode(Base):
    __tablename__ = "hsn_sac_codes"
    
    id = Column(Integer, primary_key=True)
    code = Column(String(10), nullable=False, unique=True)
    description = Column(Text, nullable=False)
    type = Column(String(10), nullable=False)
    gst_rate = Column(Numeric(5, 2), default=0)
    cess_rate = Column(Numeric(5, 2), default=0)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow)



class ItemService(Base):
    __tablename__ = "items_services"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    item_code = Column(String(50), nullable=False, unique=True)
    name = Column(String(255), nullable=False)
    description = Column(Text)
    type = Column(String(10), nullable=False)
    hsn_sac_code_id = Column(Integer, nullable=True)
    gst_rate = Column(Numeric(5, 2), default=0)
    cess_rate = Column(Numeric(5, 2), default=0)
    base_price = Column(Numeric(15, 2), nullable=False)
    selling_price = Column(Numeric(15, 2), nullable=False)
    discount_percentage = Column(Numeric(5, 2), default=0)
    unit_of_measure = Column(String(20))
    opening_stock = Column(Numeric(15, 3), default=0)
    current_stock = Column(Numeric(15, 3), default=0)
    reorder_level = Column(Numeric(15, 3), default=0)
    primary_vendor_id = Column(UUID(as_uuid=True), ForeignKey('vendors.id'))
    vendor_item_code = Column(String(50))
    total_sales_quantity = Column(Numeric(15, 3), default=0)
    total_sales_value = Column(Numeric(15, 2), default=0)
    last_sale_date = Column(Date)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow)
    created_by = Column(UUID(as_uuid=True))
    updated_by = Column(UUID(as_uuid=True))

class BankAccount(Base):
    __tablename__ = "bank_accounts"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_google_id = Column(String(255), nullable=False)
    account_name = Column(String(255), nullable=False)
    account_number = Column(String(50), nullable=False)
    bank_name = Column(String(255), nullable=False)
    branch_name = Column(String(255))
    ifsc_code = Column(String(11), nullable=False)
    account_type = Column(String(20), default='CURRENT')
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow)

class Payment(Base):
    __tablename__ = "payments"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_google_id = Column(String(255), nullable=False)
    vendor_id = Column(UUID(as_uuid=True), ForeignKey('vendors.id'), nullable=False)
    amount = Column(Numeric(15, 2), nullable=False)
    payment_method = Column(String(20), nullable=False)
    payment_date = Column(Date, nullable=False)
    bank_account_id = Column(UUID(as_uuid=True), ForeignKey('bank_accounts.id'), nullable=False)
    reference_number = Column(String(50))
    notes = Column(Text)
    status = Column(String(20), default='PENDING')
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow)

class BankTransaction(Base):
    __tablename__ = "bank_transactions"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    bank_account_id = Column(UUID(as_uuid=True), ForeignKey('bank_accounts.id'), nullable=False)
    transaction_date = Column(Date, nullable=False)
    description = Column(String(500), nullable=False)
    amount = Column(Numeric(15, 2), nullable=False)
    transaction_type = Column(String(10), nullable=False)
    balance = Column(Numeric(15, 2), nullable=False)
    reference_number = Column(String(50))
    created_at = Column(DateTime, default=datetime.utcnow)

class BankReconciliation(Base):
    __tablename__ = "bank_reconciliations"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    bank_account_id = Column(UUID(as_uuid=True), ForeignKey('bank_accounts.id'), nullable=False)
    reconciliation_date = Column(Date, nullable=False)
    opening_balance = Column(Numeric(15, 2), nullable=False)
    closing_balance = Column(Numeric(15, 2), nullable=False)
    total_credits = Column(Numeric(15, 2), default=0)
    total_debits = Column(Numeric(15, 2), default=0)
    unreconciled_items = Column(Integer, default=0)
    status = Column(String(20), default='PENDING')
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow)

class GoodsReceiptNote(Base):
    __tablename__ = "goods_receipt_notes"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_google_id = Column(String(255), nullable=False)
    grn_number = Column(String(50), nullable=False, unique=True)
    po_id = Column(UUID(as_uuid=True), nullable=False)
    vendor_id = Column(UUID(as_uuid=True), ForeignKey('vendors.id'), nullable=False)
    grn_date = Column(Date, nullable=False, default=datetime.utcnow)
    vendor_challan_number = Column(String(50))
    vendor_challan_date = Column(Date)
    vehicle_number = Column(String(20))
    transporter_name = Column(String(255))
    status = Column(String(20), default='DRAFT')
    quality_checked = Column(Boolean, default=False)
    quality_checked_by = Column(UUID(as_uuid=True))
    quality_checked_at = Column(DateTime)
    quality_remarks = Column(Text)
    remarks = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow)
    created_by = Column(UUID(as_uuid=True))
    updated_by = Column(UUID(as_uuid=True))

class GRNItem(Base):
    __tablename__ = "grn_items"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    grn_id = Column(UUID(as_uuid=True), ForeignKey('goods_receipt_notes.id'), nullable=False)
    po_item_id = Column(UUID(as_uuid=True), nullable=False)
    item_service_id = Column(UUID(as_uuid=True), nullable=False)
    ordered_quantity = Column(Numeric(15, 3), nullable=False)
    received_quantity = Column(Numeric(15, 3), nullable=False)
    accepted_quantity = Column(Numeric(15, 3), nullable=False)
    rejected_quantity = Column(Numeric(15, 3), default=0)
    unit_price = Column(Numeric(15, 2), nullable=False)
    total_amount = Column(Numeric(15, 2), nullable=False)
    batch_number = Column(String(50))
    expiry_date = Column(Date)
    remarks = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)

class PurchaseBill(Base):
    __tablename__ = "purchase_bills"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_google_id = Column(String(255), nullable=False)
    bill_number = Column(String(50), nullable=False)
    vendor_bill_number = Column(String(50), nullable=False)
    vendor_id = Column(UUID(as_uuid=True), ForeignKey('vendors.id'), nullable=False)
    po_id = Column(UUID(as_uuid=True), nullable=True)
    grn_id = Column(UUID(as_uuid=True), nullable=True)
    bill_date = Column(Date, nullable=False)
    due_date = Column(Date, nullable=False)
    subtotal = Column(Numeric(15, 2), nullable=False, default=0)
    discount_amount = Column(Numeric(15, 2), default=0)
    cgst_amount = Column(Numeric(15, 2), default=0)
    sgst_amount = Column(Numeric(15, 2), default=0)
    igst_amount = Column(Numeric(15, 2), default=0)
    cess_amount = Column(Numeric(15, 2), default=0)
    tds_amount = Column(Numeric(15, 2), default=0)
    total_amount = Column(Numeric(15, 2), nullable=False, default=0)
    paid_amount = Column(Numeric(15, 2), default=0)
    status = Column(SQLEnum(InvoiceStatusEnum), default=InvoiceStatusEnum.DRAFT)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow)
    created_by = Column(UUID(as_uuid=True))
    updated_by = Column(UUID(as_uuid=True))

class PurchaseBillItem(Base):
    __tablename__ = "purchase_bill_items"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    bill_id = Column(UUID(as_uuid=True), ForeignKey('purchase_bills.id'), nullable=False)
    item_service_id = Column(UUID(as_uuid=True), nullable=False)
    po_item_id = Column(UUID(as_uuid=True), nullable=True)
    grn_item_id = Column(UUID(as_uuid=True), nullable=True)
    quantity = Column(Numeric(15, 3), nullable=False)
    unit_price = Column(Numeric(15, 2), nullable=False)
    discount_percentage = Column(Numeric(5, 2), default=0)
    discount_amount = Column(Numeric(15, 2), default=0)
    taxable_amount = Column(Numeric(15, 2), nullable=False)
    cgst_rate = Column(Numeric(5, 2), default=0)
    sgst_rate = Column(Numeric(5, 2), default=0)
    igst_rate = Column(Numeric(5, 2), default=0)
    cess_rate = Column(Numeric(5, 2), default=0)
    cgst_amount = Column(Numeric(15, 2), default=0)
    sgst_amount = Column(Numeric(15, 2), default=0)
    igst_amount = Column(Numeric(15, 2), default=0)
    cess_amount = Column(Numeric(15, 2), default=0)
    total_amount = Column(Numeric(15, 2), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

class Expense(Base):
    __tablename__ = "expenses"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_google_id = Column(String(255), nullable=False)
    expense_number = Column(String(50), nullable=False, unique=True)
    category_id = Column(Integer, nullable=False)
    vendor_id = Column(UUID(as_uuid=True), ForeignKey('vendors.id'))
    expense_date = Column(Date, nullable=False, default=datetime.utcnow)
    description = Column(Text, nullable=False)
    amount = Column(Numeric(15, 2), nullable=False)
    cgst_amount = Column(Numeric(15, 2), default=0)
    sgst_amount = Column(Numeric(15, 2), default=0)
    igst_amount = Column(Numeric(15, 2), default=0)
    tds_amount = Column(Numeric(15, 2), default=0)
    total_amount = Column(Numeric(15, 2), nullable=False)
    receipt_number = Column(String(50))
    receipt_date = Column(Date)
    receipt_image_url = Column(String(500))
    approval_status = Column(String(20), default='PENDING')
    approved_by = Column(String(24))
    approved_at = Column(DateTime)
    notes = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow)
    created_by = Column(UUID(as_uuid=True))
    updated_by = Column(UUID(as_uuid=True))

class ExpenseCategory(Base):
    __tablename__ = "expense_categories"
    
    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False, unique=True)
    description = Column(Text)
    default_tds_section = Column(SQLEnum(TDSSectionEnum))
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

class TDSTransaction(Base):
    __tablename__ = "tds_transactions"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_google_id = Column(String(255), nullable=False)
    bill_id = Column(UUID(as_uuid=True), nullable=True)
    vendor_id = Column(UUID(as_uuid=True), ForeignKey('vendors.id'), nullable=False)
    transaction_date = Column(Date, nullable=False)
    tds_section = Column(SQLEnum(TDSSectionEnum), nullable=False)
    tds_rate = Column(Numeric(5, 2), nullable=False)
    payment_amount = Column(Numeric(15, 2), nullable=False)
    tds_amount = Column(Numeric(15, 2), nullable=False)
    net_payment_amount = Column(Numeric(15, 2), nullable=False)
    deductee_pan = Column(String(10), nullable=False)
    deductee_name = Column(String(255), nullable=False)
    deductee_address = Column(Text)
    certificate_number = Column(String(20))
    certificate_generated = Column(Boolean, default=False)
    certificate_generated_date = Column(Date)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow)
    created_by = Column(UUID(as_uuid=True))
    updated_by = Column(UUID(as_uuid=True))

class ITCRecord(Base):
    __tablename__ = "itc_records"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_google_id = Column(String(255), nullable=False)
    bill_id = Column(UUID(as_uuid=True), nullable=False)
    vendor_id = Column(UUID(as_uuid=True), ForeignKey('vendors.id'), nullable=False)
    tax_period = Column(String(7), nullable=False)
    return_period = Column(String(7), nullable=False)
    cgst_itc = Column(Numeric(15, 2), default=0)
    sgst_itc = Column(Numeric(15, 2), default=0)
    igst_itc = Column(Numeric(15, 2), default=0)
    cess_itc = Column(Numeric(15, 2), default=0)
    total_itc = Column(Numeric(15, 2), nullable=False)
    itc_status = Column(SQLEnum(ITCStatusEnum), default=ITCStatusEnum.ELIGIBLE)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow)

class Shipment(Base):
    __tablename__ = "shipments"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_google_id = Column(String(255), nullable=False)
    shipment_number = Column(String(50), nullable=False, unique=True)
    po_id = Column(UUID(as_uuid=True), nullable=True)
    origin_port = Column(String(100))
    destination_port = Column(String(100))
    vessel_name = Column(String(100))
    container_number = Column(String(20))
    shipped_date = Column(Date)
    eta = Column(Date)
    arrived_date = Column(Date)
    cleared_date = Column(Date)
    status = Column(String(20), default='IN_TRANSIT')
    shipment_currency = Column(String(3), default='INR')
    exchange_rate = Column(Numeric(10, 4), default=1)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow)
    created_by = Column(UUID(as_uuid=True))
    updated_by = Column(UUID(as_uuid=True))

class LandedCost(Base):
    __tablename__ = "landed_costs"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_google_id = Column(String(255), nullable=False)
    shipment_id = Column(UUID(as_uuid=True), ForeignKey('shipments.id'), nullable=False)
    cost_type = Column(String(30), nullable=False)
    cost_description = Column(String(255), nullable=False)
    amount = Column(Numeric(15, 2), nullable=False)
    currency = Column(String(3), default='INR')
    allocation_method = Column(String(20), default='VALUE')
    allocation_percentage = Column(Numeric(5, 2))
    service_provider = Column(String(255))
    bill_number = Column(String(50))
    bill_date = Column(Date)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow)

class VendorPayment(Base):
    __tablename__ = "vendor_payments"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_google_id = Column(String(255), nullable=False)
    payment_number = Column(String(50), nullable=False, unique=True)
    vendor_id = Column(UUID(as_uuid=True), ForeignKey('vendors.id'), nullable=False)
    payment_date = Column(Date, nullable=False, default=datetime.utcnow)
    payment_method = Column(String(20), nullable=False)
    amount = Column(Numeric(15, 2), nullable=False)
    bank_name = Column(String(255))
    cheque_number = Column(String(50))
    cheque_date = Column(Date)
    utr_number = Column(String(50))
    tds_amount = Column(Numeric(15, 2), default=0)
    net_payment_amount = Column(Numeric(15, 2), nullable=False)
    status = Column(String(20), default='PAID')
    clearance_date = Column(Date)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow)
    created_by = Column(UUID(as_uuid=True))
    updated_by = Column(UUID(as_uuid=True))

class VendorPaymentAllocation(Base):
    __tablename__ = "vendor_payment_allocations"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    payment_id = Column(UUID(as_uuid=True), ForeignKey('vendor_payments.id'), nullable=False)
    bill_id = Column(UUID(as_uuid=True), ForeignKey('purchase_bills.id'), nullable=False)
    allocated_amount = Column(Numeric(15, 2), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

class PaymentTypeEnum(enum.Enum):
    VENDOR_PAYMENT = "VENDOR_PAYMENT"
    ADVANCE_PAYMENT = "ADVANCE_PAYMENT"
    EXPENSE_PAYMENT = "EXPENSE_PAYMENT"
    REFUND = "REFUND"
    SALARY = "SALARY"

class PaymentMethodEnum(enum.Enum):
    CASH = "CASH"
    CHEQUE = "CHEQUE"
    NEFT = "NEFT"
    RTGS = "RTGS"
    UPI = "UPI"
    BANK_TRANSFER = "BANK_TRANSFER"

class PaymentStatusEnum(enum.Enum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    PAID = "PAID"
    REJECTED = "REJECTED"
    CANCELLED = "CANCELLED"

class ApprovalStatusEnum(enum.Enum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    ESCALATED = "ESCALATED"

class ReconciliationStatusEnum(enum.Enum):
    PENDING = "PENDING"
    RECONCILED = "RECONCILED"
    DISCREPANCY = "DISCREPANCY"

class ModuleTypeEnum(enum.Enum):
    PURCHASE_ORDER = "PURCHASE_ORDER"
    VENDOR_PAYMENT = "VENDOR_PAYMENT"
    EXPENSE = "EXPENSE"
    BANK_TRANSACTION = "BANK_TRANSACTION"

class PaymentApproval(Base):
    __tablename__ = "payment_approvals"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    payment_id = Column(UUID(as_uuid=True), ForeignKey('payments.id'), nullable=False)
    approver_level = Column(Integer, nullable=False)
    approver_email = Column(String(255), nullable=False)
    approval_status = Column(SQLEnum(ApprovalStatusEnum), default=ApprovalStatusEnum.PENDING)
    approved_at = Column(DateTime)
    rejection_reason = Column(Text)
    comments = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow)

class ApprovalMatrix(Base):
    __tablename__ = "approval_matrix"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_google_id = Column(String(255), nullable=False)
    module_type = Column(SQLEnum(ModuleTypeEnum), nullable=False)
    approval_level = Column(Integer, nullable=False)
    min_amount = Column(Numeric(15, 2), default=0)
    max_amount = Column(Numeric(15, 2))
    approver_email = Column(String(255), nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow)

# Now import PO models from the separated file 
from .purchase_order_models import *