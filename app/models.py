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

# =====================================================
# EXISTING PYDANTIC MODELS (MongoDB - Auth & Clients)
# =====================================================

class GoogleOAuth2Response(BaseModel):
    """Model for Google OAuth2 response data."""
    access_token: str
    token_type: str
    expires_in: int
    refresh_token: Optional[str] = None
    scope: str

class GoogleUserInfo(BaseModel):
    """Model for Google user information."""
    id: str
    email: str
    verified_email: bool
    name: str
    given_name: str
    family_name: str
    picture: str

class User(BaseModel):
    """Model for user data stored in MongoDB."""
    id: Optional[str] = Field(None, alias="_id")
    google_id: str
    email: str
    name: str
    given_name: str
    family_name: str
    picture: str
    access_token: Optional[str] = None
    refresh_token: Optional[str] = None
    token_expires_at: Optional[datetime] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        populate_by_name = True
        json_schema_extra = {
            "example": {
                "google_id": "123456789",
                "email": "user@example.com",
                "name": "John Doe",
                "given_name": "John",
                "family_name": "Doe",
                "picture": "https://example.com/picture.jpg",
                "access_token": "ya29.a0AfH6SMB...",
                "refresh_token": "1//04dX...",
                "token_expires_at": "2024-01-01T12:00:00Z",
                "created_at": "2024-01-01T10:00:00Z",
                "updated_at": "2024-01-01T10:00:00Z"
            }
        }

class UserResponse(BaseModel):
    """Model for user response (without sensitive data)."""
    id: str
    email: str
    name: str
    given_name: str
    family_name: str
    picture: str
    created_at: datetime
    updated_at: datetime

class ClientType(str, Enum):
    """Enum for client types."""
    INDIVIDUAL = "individual"
    BUSINESS = "business"
    PARTNERSHIP = "partnership"
    COMPANY = "company"

class ClientStatus(str, Enum):
    """Enum for client status."""
    ACTIVE = "active"
    INACTIVE = "inactive"
    PENDING = "pending"

class ClientAddress(BaseModel):
    """Model for client address information."""
    street: str
    city: str
    state: str
    postal_code: str
    country: str = "India"

class Client(BaseModel):
    """Model for client data stored in MongoDB."""
    id: Optional[str] = Field(None, alias="_id")
    user_google_id: str  # Maps client to the CA user

    # Basic Information
    name: str
    email: str
    phone: str

    # Business Information
    company_name: Optional[str] = None
    client_type: ClientType = ClientType.INDIVIDUAL

    # Tax Information
    pan_number: str  # Made mandatory
    gst_number: Optional[str] = None
    aadhar_number: Optional[str] = None

    # Address Information
    address: ClientAddress

    # Status and Metadata
    status: ClientStatus = ClientStatus.ACTIVE
    notes: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    @validator('pan_number')
    def validate_pan_number(cls, v):
        if not v:
            raise ValueError('PAN number is required')
        # PAN format: 5 letters + 4 digits + 1 letter
        import re
        if not re.match(r'^[A-Z]{5}[0-9]{4}[A-Z]{1}$', v.upper()):
            raise ValueError('PAN number must be in format: ABCPD1234E')
        return v.upper()

    class Config:
        populate_by_name = True

class ClientResponse(BaseModel):
    """Model for client response."""
    id: str
    user_google_id: str
    name: str
    email: str
    phone: str
    company_name: Optional[str] = None
    client_type: ClientType
    pan_number: str  # Made mandatory
    gst_number: Optional[str] = None
    aadhar_number: Optional[str] = None
    address: ClientAddress
    status: ClientStatus
    notes: Optional[str] = None
    created_at: datetime
    updated_at: datetime

class ClientCreateRequest(BaseModel):
    """Model for creating a new client."""
    name: str
    email: str
    phone: str
    company_name: Optional[str] = None
    client_type: ClientType = ClientType.INDIVIDUAL
    pan_number: str  # Made mandatory
    gst_number: Optional[str] = None
    aadhar_number: Optional[str] = None
    address: ClientAddress
    notes: Optional[str] = None

    @validator('pan_number')
    def validate_pan_number(cls, v):
        if not v:
            raise ValueError('PAN number is required')
        # PAN format: 5 letters + 4 digits + 1 letter
        import re
        if not re.match(r'^[A-Z]{5}[0-9]{4}[A-Z]{1}$', v.upper()):
            raise ValueError('PAN number must be in format: ABCPD1234E')
        return v.upper()

class ClientUpdateRequest(BaseModel):
    """Model for updating an existing client."""
    name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    company_name: Optional[str] = None
    client_type: Optional[ClientType] = None
    pan_number: Optional[str] = None  # Optional for updates to allow partial updates
    gst_number: Optional[str] = None
    aadhar_number: Optional[str] = None
    address: Optional[ClientAddress] = None
    status: Optional[ClientStatus] = None
    notes: Optional[str] = None

    @validator('pan_number')
    def validate_pan_number(cls, v):
        if v is not None and v.strip():
            # PAN format: 5 letters + 4 digits + 1 letter
            import re
            if not re.match(r'^[A-Z]{5}[0-9]{4}[A-Z]{1}$', v.upper()):
                raise ValueError('PAN number must be in format: ABCPD1234E')
            return v.upper()
        return v 

# =====================================================
# SQLALCHEMY MODELS (PostgreSQL - Purchase & Expense)
# =====================================================

Base = declarative_base()

# Enums matching the PostgreSQL schema
import enum

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

class OrderStatusEnum(enum.Enum):
    DRAFT = "DRAFT"
    PENDING_APPROVAL = "PENDING_APPROVAL"
    APPROVED = "APPROVED"
    IN_PROGRESS = "IN_PROGRESS"
    PARTIALLY_DELIVERED = "PARTIALLY_DELIVERED"
    DELIVERED = "DELIVERED"
    INVOICED = "INVOICED"
    CANCELLED = "CANCELLED"

class TDSSectionEnum(enum.Enum):
    SECTION_194A = "194A"
    SECTION_194B = "194B"
    SECTION_194BB = "194BB"
    SECTION_194C = "194C"
    SECTION_194D = "194D"
    SECTION_194DA = "194DA"
    SECTION_194E = "194E"
    SECTION_194EE = "194EE"
    SECTION_194F = "194F"
    SECTION_194G = "194G"
    SECTION_194H = "194H"
    SECTION_194I = "194I"
    SECTION_194IA = "194IA"
    SECTION_194IB = "194IB"
    SECTION_194IC = "194IC"
    SECTION_194J = "194J"
    SECTION_194K = "194K"
    SECTION_194LA = "194LA"
    SECTION_194LB = "194LB"
    SECTION_194LBA = "194LBA"
    SECTION_194LBB = "194LBB"
    SECTION_194LBC = "194LBC"
    SECTION_194LC = "194LC"
    SECTION_194M = "194M"
    SECTION_194N = "194N"
    SECTION_194O = "194O"
    SECTION_194P = "194P"
    SECTION_194Q = "194Q"
    SECTION_194R = "194R"
    SECTION_194S = "194S"

class ITCStatusEnum(enum.Enum):
    ELIGIBLE = "ELIGIBLE"
    CLAIMED = "CLAIMED"
    REVERSED = "REVERSED"
    BLOCKED = "BLOCKED"
    LAPSED = "LAPSED"

class MSMERegistrationEnum(enum.Enum):
    MICRO = "MICRO"
    SMALL = "SMALL"
    MEDIUM = "MEDIUM"
    NOT_APPLICABLE = "NOT_APPLICABLE"

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

# Purchase Order Approval Workflow Enums
class POApprovalStatusEnum(str, enum.Enum):
    DRAFT = "draft"
    PENDING_APPROVAL = "pending_approval" 
    LEVEL_1_APPROVED = "level_1_approved"
    LEVEL_2_APPROVED = "level_2_approved"
    FINAL_APPROVED = "final_approved"
    REJECTED = "rejected"
    CANCELLED = "cancelled"

class ApprovalActionEnum(str, enum.Enum):
    SUBMIT = "submit"
    APPROVE = "approve"
    REJECT = "reject"
    REQUEST_CHANGES = "request_changes"
    CANCEL = "cancel"

class ApprovalLevelEnum(str, enum.Enum):
    LEVEL_1 = "level_1"  # Department/Team Lead
    LEVEL_2 = "level_2"  # Manager
    LEVEL_3 = "level_3"  # Director/Finance
    FINANCE = "finance"  # Finance Team
    ADMIN = "admin"     # Admin Override

# States table
class State(Base):
    __tablename__ = "states"
    
    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False, unique=True)
    code = Column(String(2), nullable=False, unique=True)
    gst_state_code = Column(String(2), nullable=False, unique=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow)

# HSN/SAC Codes table
class HSNSACCode(Base):
    __tablename__ = "hsn_sac_codes"
    
    id = Column(Integer, primary_key=True)
    code = Column(String(10), nullable=False, unique=True)
    description = Column(Text, nullable=False)
    type = Column(String(10), nullable=False)  # HSN or SAC
    gst_rate = Column(Numeric(5, 2), default=0)
    cess_rate = Column(Numeric(5, 2), default=0)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow)

# Vendors table
class Vendor(Base):
    __tablename__ = "vendors"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(String(255), nullable=False)  # Links to MongoDB user
    vendor_code = Column(String(20), nullable=False, unique=True)
    business_name = Column(String(255), nullable=False)
    legal_name = Column(String(255))
    gstin = Column(String(15), unique=True)
    pan = Column(String(10))
    
    # --- Critical Compliance Fields ---
    is_msme = Column(Boolean, default=False)  # Simplified MSME status
    udyam_registration_number = Column(String(20))
    
    # Contact Information
    contact_person = Column(String(100))
    phone = Column(String(15))
    email = Column(String(100))
    website = Column(String(255))
    
    # --- Payment & Terms ---
    credit_limit = Column(Numeric(15, 2), default=0)
    credit_days = Column(Integer, default=30)
    payment_terms = Column(String(20), default='NET_30')  # Simplified to string
    
    # --- Critical Banking Fields ---
    bank_account_number = Column(String(50))
    bank_ifsc_code = Column(String(11))
    bank_account_holder_name = Column(String(255))
    
    # Address
    address_line1 = Column(String(255))
    address_line2 = Column(String(255))
    city = Column(String(100))
    state_id = Column(Integer, ForeignKey('states.id'))
    pincode = Column(String(10))
    country = Column(String(50), default='India')
    
    # --- Critical Tax & Accounting Fields ---
    tds_applicable = Column(Boolean, default=True)
    default_tds_section = Column(String(10))  # e.g., "194J"
    default_expense_ledger_id = Column(UUID(as_uuid=True))  # FK to accounting ledger
    
    # Business Metrics
    vendor_rating = Column(Integer)
    total_purchases = Column(Numeric(15, 2), default=0)
    outstanding_amount = Column(Numeric(15, 2), default=0)
    last_transaction_date = Column(Date)
    
    # Status and Audit
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow)
    created_by = Column(UUID(as_uuid=True))
    updated_by = Column(UUID(as_uuid=True))
    
    # Relationships
    state = relationship("State")

# Items/Services table
class ItemService(Base):
    __tablename__ = "items_services"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    item_code = Column(String(50), nullable=False, unique=True)
    name = Column(String(255), nullable=False)
    description = Column(Text)
    type = Column(String(10), nullable=False)  # PRODUCT or SERVICE
    
    # Tax Information
    hsn_sac_code_id = Column(Integer, ForeignKey('hsn_sac_codes.id'))
    gst_rate = Column(Numeric(5, 2), default=0)
    cess_rate = Column(Numeric(5, 2), default=0)
    
    # Pricing
    base_price = Column(Numeric(15, 2), nullable=False)
    selling_price = Column(Numeric(15, 2), nullable=False)
    discount_percentage = Column(Numeric(5, 2), default=0)
    
    # Inventory (for products)
    unit_of_measure = Column(String(20))
    opening_stock = Column(Numeric(15, 3), default=0)
    current_stock = Column(Numeric(15, 3), default=0)
    reorder_level = Column(Numeric(15, 3), default=0)
    
    # Vendor Information
    primary_vendor_id = Column(UUID(as_uuid=True), ForeignKey('vendors.id'))
    vendor_item_code = Column(String(50))
    
    # Business Metrics
    total_sales_quantity = Column(Numeric(15, 3), default=0)
    total_sales_value = Column(Numeric(15, 2), default=0)
    last_sale_date = Column(Date)
    
    # Status and Audit
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow)
    created_by = Column(UUID(as_uuid=True))
    updated_by = Column(UUID(as_uuid=True))
    
    # Relationships
    hsn_sac_code = relationship("HSNSACCode")
    primary_vendor = relationship("Vendor")

# Purchase Orders table
class PurchaseOrder(Base):
    __tablename__ = "purchase_orders"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(String(255), nullable=False)  # User who created the PO
    po_number = Column(String(50), nullable=False, unique=True)
    vendor_id = Column(UUID(as_uuid=True), ForeignKey('vendors.id'), nullable=False)
    po_date = Column(Date, nullable=False, default=datetime.utcnow)
    expected_delivery_date = Column(Date)
    
    # Amounts
    subtotal = Column(Numeric(15, 2), nullable=False, default=0)
    discount_amount = Column(Numeric(15, 2), default=0)
    total_amount = Column(Numeric(15, 2), nullable=False, default=0)
    
    # Status
    status = Column(SQLEnum(OrderStatusEnum), default=OrderStatusEnum.DRAFT)
    
    # Approval Workflow
    approval_status = Column(String(20), default='PENDING')
    approved_by = Column(String(24))
    approved_at = Column(DateTime)
    
    # Additional Information
    delivery_address = Column(Text)
    terms_and_conditions = Column(Text)
    notes = Column(Text)
    
    # Audit
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow)
    created_by = Column(UUID(as_uuid=True))
    updated_by = Column(UUID(as_uuid=True))
    
    # Relationships
    vendor = relationship("Vendor")
    items = relationship("PurchaseOrderItem", back_populates="purchase_order")
    approval_history = relationship("POApprovalHistory", back_populates="purchase_order")
    approval_workflow = relationship("POApprovalWorkflow", back_populates="purchase_order", uselist=False)

# Purchase Order Items table
class PurchaseOrderItem(Base):
    __tablename__ = "purchase_order_items"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    po_id = Column(UUID(as_uuid=True), ForeignKey('purchase_orders.id'), nullable=False)
    
    # Essential item information only
    item_description = Column(String(500), nullable=False)
    hsn_code = Column(String(20), default='')
    unit = Column(String(20), default='Nos')
    quantity = Column(Numeric(15, 3), nullable=False)
    unit_price = Column(Numeric(15, 2), nullable=False)
    total_amount = Column(Numeric(15, 2), nullable=False)
    
    # Relationships
    purchase_order = relationship("PurchaseOrder", back_populates="items")

# Goods Receipt Notes table
class GoodsReceiptNote(Base):
    __tablename__ = "goods_receipt_notes"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_google_id = Column(String(255), nullable=False)  # Links to MongoDB user
    grn_number = Column(String(50), nullable=False, unique=True)
    po_id = Column(UUID(as_uuid=True), ForeignKey('purchase_orders.id'), nullable=False)
    vendor_id = Column(UUID(as_uuid=True), ForeignKey('vendors.id'), nullable=False)
    grn_date = Column(Date, nullable=False, default=datetime.utcnow)
    
    # Delivery Details
    vendor_challan_number = Column(String(50))
    vendor_challan_date = Column(Date)
    vehicle_number = Column(String(20))
    transporter_name = Column(String(255))
    
    # Status
    status = Column(String(20), default='DRAFT')
    
    # Quality Check
    quality_checked = Column(Boolean, default=False)
    quality_checked_by = Column(UUID(as_uuid=True))
    quality_checked_at = Column(DateTime)
    quality_remarks = Column(Text)
    
    # Additional Information
    remarks = Column(Text)
    
    # Audit
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow)
    created_by = Column(UUID(as_uuid=True))
    updated_by = Column(UUID(as_uuid=True))
    
    # Relationships
    purchase_order = relationship("PurchaseOrder")
    vendor = relationship("Vendor")

# GRN Items table
class GRNItem(Base):
    __tablename__ = "grn_items"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    grn_id = Column(UUID(as_uuid=True), ForeignKey('goods_receipt_notes.id'), nullable=False)
    po_item_id = Column(UUID(as_uuid=True), ForeignKey('purchase_order_items.id'), nullable=False)
    item_service_id = Column(UUID(as_uuid=True), ForeignKey('items_services.id'), nullable=False)
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
    
    # Relationships
    grn = relationship("GoodsReceiptNote")
    po_item = relationship("PurchaseOrderItem")
    item_service = relationship("ItemService")

# Purchase Bills table
class PurchaseBill(Base):
    __tablename__ = "purchase_bills"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_google_id = Column(String(255), nullable=False)  # Links to MongoDB user
    bill_number = Column(String(50), nullable=False)
    vendor_bill_number = Column(String(50), nullable=False)
    vendor_id = Column(UUID(as_uuid=True), ForeignKey('vendors.id'), nullable=False)
    po_id = Column(UUID(as_uuid=True), ForeignKey('purchase_orders.id'))
    grn_id = Column(UUID(as_uuid=True), ForeignKey('goods_receipt_notes.id'))
    bill_date = Column(Date, nullable=False)
    due_date = Column(Date, nullable=False)
    
    # OCR Processing
    is_ocr_processed = Column(Boolean, default=False)
    ocr_confidence_score = Column(Numeric(5, 2))
    ocr_extracted_data = Column(Text)  # JSON stored as text
    
    # Three-way Matching
    po_matching_status = Column(String(20), default='PENDING')
    grn_matching_status = Column(String(20), default='PENDING')
    price_variance_percentage = Column(Numeric(5, 2), default=0)
    quantity_variance_percentage = Column(Numeric(5, 2), default=0)
    
    # Amounts
    subtotal = Column(Numeric(15, 2), nullable=False, default=0)
    discount_amount = Column(Numeric(15, 2), default=0)
    cgst_amount = Column(Numeric(15, 2), default=0)
    sgst_amount = Column(Numeric(15, 2), default=0)
    igst_amount = Column(Numeric(15, 2), default=0)
    cess_amount = Column(Numeric(15, 2), default=0)
    tds_amount = Column(Numeric(15, 2), default=0)
    total_amount = Column(Numeric(15, 2), nullable=False, default=0)
    paid_amount = Column(Numeric(15, 2), default=0)
    
    # ITC Information
    itc_eligible_amount = Column(Numeric(15, 2), default=0)
    itc_claimed_amount = Column(Numeric(15, 2), default=0)
    itc_status = Column(SQLEnum(ITCStatusEnum), default=ITCStatusEnum.ELIGIBLE)
    
    # Status
    status = Column(SQLEnum(InvoiceStatusEnum), default=InvoiceStatusEnum.DRAFT)
    
    # GSTR-2B Reconciliation
    gstr2b_period = Column(String(7))  # MM-YYYY format
    gstr2b_reconciled = Column(Boolean, default=False)
    gstr2b_reconciled_date = Column(Date)
    
    # Additional Information
    place_of_supply = Column(Integer, ForeignKey('states.id'))
    reverse_charge_applicable = Column(Boolean, default=False)
    notes = Column(Text)
    
    # Audit
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow)
    created_by = Column(UUID(as_uuid=True))
    updated_by = Column(UUID(as_uuid=True))
    
    # Relationships
    vendor = relationship("Vendor")
    purchase_order = relationship("PurchaseOrder")
    grn = relationship("GoodsReceiptNote")
    place_of_supply_state = relationship("State")

# Purchase Bill Items table
class PurchaseBillItem(Base):
    __tablename__ = "purchase_bill_items"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    bill_id = Column(UUID(as_uuid=True), ForeignKey('purchase_bills.id'), nullable=False)
    item_service_id = Column(UUID(as_uuid=True), ForeignKey('items_services.id'), nullable=False)
    po_item_id = Column(UUID(as_uuid=True), ForeignKey('purchase_order_items.id'))
    grn_item_id = Column(UUID(as_uuid=True), ForeignKey('grn_items.id'))
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
    
    # ITC Information
    itc_eligible = Column(Boolean, default=True)
    itc_amount = Column(Numeric(15, 2), default=0)
    itc_reversal_reason = Column(String(100))
    
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    bill = relationship("PurchaseBill")
    item_service = relationship("ItemService")
    po_item = relationship("PurchaseOrderItem")
    grn_item = relationship("GRNItem")

# TDS Transactions table
class TDSTransaction(Base):
    __tablename__ = "tds_transactions"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_google_id = Column(String(255), nullable=False)  # Links to MongoDB user
    bill_id = Column(UUID(as_uuid=True), ForeignKey('purchase_bills.id'))
    vendor_id = Column(UUID(as_uuid=True), ForeignKey('vendors.id'), nullable=False)
    transaction_date = Column(Date, nullable=False)
    
    # TDS Details
    tds_section = Column(SQLEnum(TDSSectionEnum), nullable=False)
    tds_rate = Column(Numeric(5, 2), nullable=False)
    payment_amount = Column(Numeric(15, 2), nullable=False)
    tds_amount = Column(Numeric(15, 2), nullable=False)
    net_payment_amount = Column(Numeric(15, 2), nullable=False)
    
    # Deductee Information
    deductee_pan = Column(String(10), nullable=False)
    deductee_name = Column(String(255), nullable=False)
    deductee_address = Column(Text)
    
    # Challan Information
    challan_number = Column(String(20))
    challan_date = Column(Date)
    bsr_code = Column(String(10))
    challan_amount = Column(Numeric(15, 2))
    
    # Certificate Details
    certificate_number = Column(String(20))
    certificate_generated = Column(Boolean, default=False)
    certificate_generated_date = Column(Date)
    
    # Filing Information
    return_type = Column(String(10))  # 24Q, 26Q, 27Q, 27EQ
    filing_period = Column(String(10))  # Q1-YYYY format
    filed = Column(Boolean, default=False)
    filed_date = Column(Date)
    acknowledgment_number = Column(String(20))
    
    # Audit
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow)
    created_by = Column(UUID(as_uuid=True))
    updated_by = Column(UUID(as_uuid=True))
    
    # Relationships
    bill = relationship("PurchaseBill")
    vendor = relationship("Vendor")

# ITC Records table
class ITCRecord(Base):
    __tablename__ = "itc_records"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_google_id = Column(String(255), nullable=False)  # Links to MongoDB user
    bill_id = Column(UUID(as_uuid=True), ForeignKey('purchase_bills.id'), nullable=False)
    vendor_id = Column(UUID(as_uuid=True), ForeignKey('vendors.id'), nullable=False)
    
    # Period Information
    tax_period = Column(String(7), nullable=False)  # MM-YYYY format
    return_period = Column(String(7), nullable=False)  # MM-YYYY format
    
    # ITC Details
    cgst_itc = Column(Numeric(15, 2), default=0)
    sgst_itc = Column(Numeric(15, 2), default=0)
    igst_itc = Column(Numeric(15, 2), default=0)
    cess_itc = Column(Numeric(15, 2), default=0)
    total_itc = Column(Numeric(15, 2), nullable=False)
    
    # Status and Eligibility
    itc_status = Column(SQLEnum(ITCStatusEnum), default=ITCStatusEnum.ELIGIBLE)
    eligibility_reason = Column(Text)
    
    # Reversal Information
    reversal_rule = Column(String(50))  # Rule 42, Rule 43, Section 17(5), etc.
    reversal_percentage = Column(Numeric(5, 2), default=0)
    reversal_amount = Column(Numeric(15, 2), default=0)
    
    # GSTR-2B Reconciliation
    gstr2b_reported = Column(Boolean, default=False)
    gstr2b_amount = Column(Numeric(15, 2), default=0)
    variance_amount = Column(Numeric(15, 2), default=0)
    reconciled = Column(Boolean, default=False)
    
    # Claim Information
    claimed_in_gstr3b = Column(Boolean, default=False)
    claim_period = Column(String(7))
    claim_amount = Column(Numeric(15, 2), default=0)
    
    # Additional Information
    purchase_type = Column(String(20))  # CAPITAL_GOODS, INPUT_SERVICES, INPUTS, OTHER
    notes = Column(Text)
    
    # Audit
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    bill = relationship("PurchaseBill")
    vendor = relationship("Vendor")

# Expense Categories table
class ExpenseCategory(Base):
    __tablename__ = "expense_categories"
    
    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False, unique=True)
    description = Column(Text)
    hsn_sac_code_id = Column(Integer, ForeignKey('hsn_sac_codes.id'))
    default_tds_section = Column(SQLEnum(TDSSectionEnum))
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    hsn_sac_code = relationship("HSNSACCode")

# Expenses table
class Expense(Base):
    __tablename__ = "expenses"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_google_id = Column(String(255), nullable=False)  # Links to MongoDB user
    expense_number = Column(String(50), nullable=False, unique=True)
    category_id = Column(Integer, ForeignKey('expense_categories.id'), nullable=False)
    vendor_id = Column(UUID(as_uuid=True), ForeignKey('vendors.id'))
    expense_date = Column(Date, nullable=False, default=datetime.utcnow)
    
    # Expense Details
    description = Column(Text, nullable=False)
    amount = Column(Numeric(15, 2), nullable=False)
    
    # Tax Information
    cgst_amount = Column(Numeric(15, 2), default=0)
    sgst_amount = Column(Numeric(15, 2), default=0)
    igst_amount = Column(Numeric(15, 2), default=0)
    tds_amount = Column(Numeric(15, 2), default=0)
    total_amount = Column(Numeric(15, 2), nullable=False)
    
    # Receipt Information
    receipt_number = Column(String(50))
    receipt_date = Column(Date)
    receipt_image_url = Column(String(500))
    
    # Approval
    approval_status = Column(String(20), default='PENDING')
    approved_by = Column(String(24))
    approved_at = Column(DateTime)
    
    # Reimbursement
    reimbursement_status = Column(String(20), default='PENDING')
    reimbursed_amount = Column(Numeric(15, 2), default=0)
    
    # Additional Information
    project_id = Column(UUID(as_uuid=True))
    employee_id = Column(UUID(as_uuid=True))
    notes = Column(Text)
    
    # Audit
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow)
    created_by = Column(UUID(as_uuid=True))
    updated_by = Column(UUID(as_uuid=True))
    
    # Relationships
    category = relationship("ExpenseCategory")
    vendor = relationship("Vendor")

# Shipments table
class Shipment(Base):
    __tablename__ = "shipments"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_google_id = Column(String(255), nullable=False)  # Links to MongoDB user
    shipment_number = Column(String(50), nullable=False, unique=True)
    po_id = Column(UUID(as_uuid=True), ForeignKey('purchase_orders.id'))
    
    # Shipment Details
    origin_port = Column(String(100))
    destination_port = Column(String(100))
    vessel_name = Column(String(100))
    container_number = Column(String(20))
    
    # Dates
    shipped_date = Column(Date)
    eta = Column(Date)
    arrived_date = Column(Date)
    cleared_date = Column(Date)
    
    # Status
    status = Column(String(20), default='IN_TRANSIT')
    
    # Currency and Exchange
    shipment_currency = Column(String(3), default='INR')
    exchange_rate = Column(Numeric(10, 4), default=1)
    
    # Audit
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow)
    created_by = Column(UUID(as_uuid=True))
    updated_by = Column(UUID(as_uuid=True))
    
    # Relationships
    purchase_order = relationship("PurchaseOrder")

# Landed Costs table
class LandedCost(Base):
    __tablename__ = "landed_costs"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_google_id = Column(String(255), nullable=False)  # Links to MongoDB user
    shipment_id = Column(UUID(as_uuid=True), ForeignKey('shipments.id'), nullable=False)
    
    # Cost Details
    cost_type = Column(String(30), nullable=False)
    cost_description = Column(String(255), nullable=False)
    amount = Column(Numeric(15, 2), nullable=False)
    currency = Column(String(3), default='INR')
    
    # Allocation Method
    allocation_method = Column(String(20), default='VALUE')
    allocation_percentage = Column(Numeric(5, 2))
    
    # Vendor Information
    service_provider = Column(String(255))
    bill_number = Column(String(50))
    bill_date = Column(Date)
    
    # Audit
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    shipment = relationship("Shipment")

# Vendor Payments table
class VendorPayment(Base):
    __tablename__ = "vendor_payments"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_google_id = Column(String(255), nullable=False)  # Links to MongoDB user
    payment_number = Column(String(50), nullable=False, unique=True)
    vendor_id = Column(UUID(as_uuid=True), ForeignKey('vendors.id'), nullable=False)
    payment_date = Column(Date, nullable=False, default=datetime.utcnow)
    
    # Payment Details
    payment_method = Column(String(20), nullable=False)
    amount = Column(Numeric(15, 2), nullable=False)
    
    # Bank Details
    bank_name = Column(String(255))
    cheque_number = Column(String(50))
    cheque_date = Column(Date)
    utr_number = Column(String(50))
    
    # TDS Deduction
    tds_amount = Column(Numeric(15, 2), default=0)
    net_payment_amount = Column(Numeric(15, 2), nullable=False)
    
    # Status
    status = Column(String(20), default='PAID')
    clearance_date = Column(Date)
    
    # Additional Information
    notes = Column(Text)
    
    # Audit
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow)
    created_by = Column(UUID(as_uuid=True))
    updated_by = Column(UUID(as_uuid=True))
    
    # Relationships
    vendor = relationship("Vendor")

# Vendor Payment Allocations table
class VendorPaymentAllocation(Base):
    __tablename__ = "vendor_payment_allocations"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    payment_id = Column(UUID(as_uuid=True), ForeignKey('vendor_payments.id'), nullable=False)
    bill_id = Column(UUID(as_uuid=True), ForeignKey('purchase_bills.id'), nullable=False)
    allocated_amount = Column(Numeric(15, 2), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    payment = relationship("VendorPayment")
    bill = relationship("PurchaseBill")

# =====================================================
# PYDANTIC MODELS FOR API REQUESTS/RESPONSES
# =====================================================

# Vendor API models
class VendorPaymentTerms(str, Enum):
    """Enum for vendor payment terms."""
    IMMEDIATE = "IMMEDIATE"
    NET_15 = "NET_15"
    NET_30 = "NET_30" 
    NET_45 = "NET_45"
    NET_60 = "NET_60"
    NET_90 = "NET_90"

class VendorAddress(BaseModel):
    """Model for vendor address."""
    address_line1: str
    address_line2: Optional[str] = None
    city: str
    state_id: int
    pincode: str
    country: str = "India"

class VendorCreateRequest(BaseModel):
    """Request model for creating vendor."""
    vendor_code: str
    business_name: str
    legal_name: Optional[str] = None
    gstin: Optional[str] = None
    pan: Optional[str] = None
    
    # --- Critical Compliance Fields ---
    is_msme: bool = False
    udyam_registration_number: Optional[str] = None
    
    # Contact Information
    contact_person: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    website: Optional[str] = None
    
    # --- Payment & Terms ---
    credit_limit: float = 0.0
    credit_days: int = 30
    payment_terms: VendorPaymentTerms = VendorPaymentTerms.NET_30
    
    # --- Critical Banking Fields ---
    bank_account_number: Optional[str] = None
    bank_ifsc_code: Optional[str] = None
    bank_account_holder_name: Optional[str] = None
    
    # Address
    address: VendorAddress
    
    # --- Critical Tax & Accounting Fields ---
    tds_applicable: bool = True
    default_tds_section: Optional[str] = None  # e.g., "194J"
    default_expense_ledger_id: Optional[str] = None

class VendorUpdateRequest(BaseModel):
    """Request model for updating vendor."""
    business_name: Optional[str] = None
    legal_name: Optional[str] = None
    gstin: Optional[str] = None
    pan: Optional[str] = None
    
    # --- Critical Compliance Fields ---
    is_msme: Optional[bool] = None
    udyam_registration_number: Optional[str] = None
    
    # Contact Information
    contact_person: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    website: Optional[str] = None
    
    # --- Payment & Terms ---
    credit_limit: Optional[float] = None
    credit_days: Optional[int] = None
    payment_terms: Optional[VendorPaymentTerms] = None
    
    # --- Critical Banking Fields ---
    bank_account_number: Optional[str] = None
    bank_ifsc_code: Optional[str] = None
    bank_account_holder_name: Optional[str] = None
    
    # Address
    address: Optional[VendorAddress] = None
    
    # --- Critical Tax & Accounting Fields ---
    tds_applicable: Optional[bool] = None
    default_tds_section: Optional[str] = None
    default_expense_ledger_id: Optional[str] = None
    is_active: Optional[bool] = None

class VendorResponse(BaseModel):
    """Response model for vendor."""
    id: str
    vendor_code: str
    business_name: str
    legal_name: Optional[str] = None
    gstin: Optional[str] = None
    pan: Optional[str] = None
    
    # --- Critical Compliance Fields ---
    is_msme: bool
    udyam_registration_number: Optional[str] = None
    
    # Contact Information
    contact_person: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    website: Optional[str] = None
    
    # --- Payment & Terms ---
    credit_limit: float
    credit_days: int
    payment_terms: str
    
    # --- Critical Banking Fields ---
    bank_account_number: Optional[str] = None
    bank_ifsc_code: Optional[str] = None
    bank_account_holder_name: Optional[str] = None
    
    # Address
    address_line1: Optional[str] = None
    address_line2: Optional[str] = None
    city: Optional[str] = None
    state_id: Optional[int] = None
    pincode: Optional[str] = None
    country: Optional[str] = None
    
    # --- Critical Tax & Accounting Fields ---
    tds_applicable: bool
    default_tds_section: Optional[str] = None
    default_expense_ledger_id: Optional[str] = None
    
    # Business Metrics
    vendor_rating: Optional[int] = None
    total_purchases: float = 0
    outstanding_amount: float = 0
    last_transaction_date: Optional[str] = None
    
    # Status and Audit
    is_active: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
# Remove all the Pydantic approval models that are causing build failures - move to separate file later

# Purchase Order API models
class POLineItem(BaseModel):
    """Model for purchase order line item."""
    item_description: str  # Item description
    unit: str = "Nos"  # Unit of measurement
    quantity: float
    unit_price: float
    discount_percentage: float = 0.0
    total_amount: float  # Simplified - no GST calculation at PO level

class PurchaseOrderCreateRequest(BaseModel):
    """Request model for creating purchase order."""
    po_number: str
    vendor_id: str
    po_date: datetime
    expected_delivery_date: Optional[datetime] = None
    line_items: List[POLineItem]
    delivery_address: Optional[str] = None
    terms_and_conditions: Optional[str] = None
    notes: Optional[str] = None
class PurchaseOrderUpdateRequest(BaseModel):
    """Request model for updating purchase order."""
    po_number: Optional[str] = None
    vendor_id: Optional[str] = None
    po_date: Optional[str] = None  # Accept as string to avoid datetime parsing issues
    expected_delivery_date: Optional[str] = None  # Accept as string to avoid datetime parsing issues
    line_items: Optional[List[POLineItem]] = None
    delivery_address: Optional[str] = None
    terms_and_conditions: Optional[str] = None
    notes: Optional[str] = None
    status: Optional[str] = None

class POLineItemResponse(BaseModel):
    """Response model for purchase order line item."""
    id: str
    item_description: str
    unit: str
    quantity: float
    unit_price: float
    total_amount: float

class PurchaseOrderResponse(BaseModel):
    """Response model for purchase order with clear dual status system."""
    id: str
    po_number: str
    vendor_id: str
    po_date: datetime
    expected_delivery_date: Optional[datetime] = None
    subtotal: float
    total_amount: float
    
    # Dual Status System - Clearly labeled
    operational_status: str = Field(alias="status", description="Order fulfillment status: DRAFT, APPROVED, IN_PROGRESS, DELIVERED, etc.")
    approval_status: str = Field(default="PENDING", description="Approval workflow status: PENDING, PENDING_APPROVAL, APPROVED, REJECTED")
    
    # Approval Details
    approved_by: Optional[str] = None
    approved_at: Optional[datetime] = None
    
    # Additional Information
    delivery_address: Optional[str] = None
    terms_and_conditions: Optional[str] = None
    notes: Optional[str] = None
    items: List[POLineItemResponse] = []
    
    # Audit Information
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
        populate_by_name = True

# Expense API models
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
    expense_number: str
    category_id: int
    expense_date: datetime
    description: str
    amount: float
    total_amount: float
    approval_status: str
    reimbursement_status: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True 

# =====================================================
# BANK MODULE MODELS (PostgreSQL)
# =====================================================


class AccountTypeEnum(str, Enum):
    SAVINGS = "savings"
    CURRENT = "current"
    OVERDRAFT = "overdraft"
    FIXED_DEPOSIT = "fixed_deposit"
    CASH_CREDIT = "cash_credit"

class TransactionTypeEnum(str, Enum):
    DEBIT = "debit"
    CREDIT = "credit"

class PaymentTypeEnum(str, Enum):
    VENDOR_PAYMENT = "vendor_payment"
    EMPLOYEE_REIMBURSEMENT = "employee_reimbursement"
    SALARY_PAYMENT = "salary_payment"
    TAX_PAYMENT = "tax_payment"
    ADVANCE_PAYMENT = "advance_payment"
    REFUND = "refund"

class PaymentMethodEnum(str, Enum):
    RTGS = "rtgs"
    NEFT = "neft"
    IMPS = "imps"
    CHEQUE = "cheque"
    CASH = "cash"
    UPI = "upi"
    DEMAND_DRAFT = "demand_draft"

class PaymentReferenceTypeEnum(str, Enum):
    PURCHASE_BILL = "purchase_bill"
    EXPENSE = "expense"
    ADVANCE = "advance"
    SALARY = "salary"

class PaymentStatusEnum(str, Enum):
    DRAFT = "draft"
    PENDING_APPROVAL = "pending_approval"
    APPROVED = "approved"
    PROCESSED = "processed"
    FAILED = "failed"
    CANCELLED = "cancelled"

class ApprovalStatusEnum(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"

class ReconciliationStatusEnum(str, Enum):
    UNRECONCILED = "unreconciled"
    RECONCILED = "reconciled"
    IN_PROGRESS = "in_progress"
    PARTIALLY_RECONCILED = "partially_reconciled"

class ModuleTypeEnum(str, Enum):
    PURCHASE = "purchase"
    EXPENSE = "expense"
    PAYROLL = "payroll"
    GENERAL = "general"

# Purchase Order Approval Workflow Models
class POApprovalRule(Base):
    """Defines approval rules based on amount thresholds and user roles"""
    __tablename__ = "po_approval_rules"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(String(255), nullable=False)  # Organization/Company
    
    # Rule Configuration
    rule_name = Column(String(100), nullable=False)
    min_amount = Column(Numeric(15, 2), default=0)
    max_amount = Column(Numeric(15, 2))  # NULL for unlimited
    
    # Approval Levels Required
    level_1_required = Column(Boolean, default=True)
    level_2_required = Column(Boolean, default=False)
    level_3_required = Column(Boolean, default=False)
    finance_approval_required = Column(Boolean, default=False)
    
    # Approver Configuration
    level_1_approvers = Column(Text)  # JSON array of user IDs
    level_2_approvers = Column(Text)  # JSON array of user IDs  
    level_3_approvers = Column(Text)  # JSON array of user IDs
    finance_approvers = Column(Text)  # JSON array of user IDs
    
    # Auto-approval settings
    auto_approve_below = Column(Numeric(15, 2), default=0)
    
    # Status and Audit
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow)
    created_by = Column(String(255))
    updated_by = Column(String(255))

class POApprovalHistory(Base):
    """Tracks the complete approval history for each purchase order"""
    __tablename__ = "po_approval_history"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    po_id = Column(UUID(as_uuid=True), ForeignKey('purchase_orders.id'), nullable=False)
    
    # Approval Details
    approval_level = Column(SQLEnum(ApprovalLevelEnum), nullable=False)
    action = Column(SQLEnum(ApprovalActionEnum), nullable=False)
    approver_id = Column(String(255), nullable=False)
    approver_name = Column(String(255))
    approver_email = Column(String(255))
    
    # Action Details
    action_date = Column(DateTime, default=datetime.utcnow)
    comments = Column(Text)
    previous_status = Column(SQLEnum(POApprovalStatusEnum))
    new_status = Column(SQLEnum(POApprovalStatusEnum))
    
    # Additional Context
    po_amount_at_time = Column(Numeric(15, 2))
    ip_address = Column(String(45))
    user_agent = Column(String(500))
    
    # Relationships
    purchase_order = relationship("PurchaseOrder", back_populates="approval_history")

class POApprovalWorkflow(Base):
    """Tracks current workflow state for each purchase order"""
    __tablename__ = "po_approval_workflows"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    po_id = Column(UUID(as_uuid=True), ForeignKey('purchase_orders.id'), nullable=False, unique=True)
    
    # Current Workflow State
    current_level = Column(SQLEnum(ApprovalLevelEnum))
    approval_status = Column(SQLEnum(POApprovalStatusEnum), default=POApprovalStatusEnum.DRAFT)
    
    # Rule Application
    applied_rule_id = Column(UUID(as_uuid=True), ForeignKey('po_approval_rules.id'))
    
    # Level Completion Status
    level_1_status = Column(SQLEnum(ApprovalStatusEnum), default=ApprovalStatusEnum.PENDING)
    level_1_approver = Column(String(255))
    level_1_approved_at = Column(DateTime)
    
    level_2_status = Column(SQLEnum(ApprovalStatusEnum), default=ApprovalStatusEnum.PENDING)
    level_2_approver = Column(String(255))
    level_2_approved_at = Column(DateTime)
    
    level_3_status = Column(SQLEnum(ApprovalStatusEnum), default=ApprovalStatusEnum.PENDING)
    level_3_approver = Column(String(255))
    level_3_approved_at = Column(DateTime)
    
    finance_status = Column(SQLEnum(ApprovalStatusEnum), default=ApprovalStatusEnum.PENDING)
    finance_approver = Column(String(255))
    finance_approved_at = Column(DateTime)
    
    # Workflow Metadata
    submitted_at = Column(DateTime)
    submitted_by = Column(String(255))
    final_approved_at = Column(DateTime)
    final_approved_by = Column(String(255))
    
    # SLA Tracking
    expected_approval_date = Column(DateTime)
    is_overdue = Column(Boolean, default=False)
    escalation_count = Column(Integer, default=0)
    last_escalation_date = Column(DateTime)
    
    # Audit
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    purchase_order = relationship("PurchaseOrder", back_populates="approval_workflow")
    applied_rule = relationship("POApprovalRule")

# Bank Account Models
class BankAccount(Base):
    """Bank account information."""
    __tablename__ = "bank_accounts"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    account_name = Column(String(255), nullable=False)
    account_number = Column(String(50), nullable=False, unique=True)
    ifsc_code = Column(String(20), nullable=False)
    bank_name = Column(String(255), nullable=False)
    branch_name = Column(String(255), nullable=False)
    account_type = Column(SQLEnum(AccountTypeEnum), nullable=False)
    currency = Column(String(10), default="INR")
    opening_balance = Column(Numeric(15, 2), default=0.0)
    current_balance = Column(Numeric(15, 2), default=0.0)
    overdraft_limit = Column(Numeric(15, 2), default=0.0)
    is_active = Column(Boolean, default=True)
    is_primary = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    transactions = relationship("BankTransaction", back_populates="bank_account")
    payments = relationship("Payment", back_populates="bank_account")

class BankTransaction(Base):
    """Bank transaction records."""
    __tablename__ = "bank_transactions"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    bank_account_id = Column(UUID(as_uuid=True), ForeignKey("bank_accounts.id"), nullable=False)
    transaction_date = Column(Date, nullable=False)
    value_date = Column(Date, nullable=False)
    description = Column(Text, nullable=False)
    reference_number = Column(String(100), nullable=False)
    debit_amount = Column(Numeric(15, 2), default=0.0)
    credit_amount = Column(Numeric(15, 2), default=0.0)
    balance = Column(Numeric(15, 2), nullable=False)
    transaction_type = Column(SQLEnum(TransactionTypeEnum), nullable=False)
    reconciliation_status = Column(SQLEnum(ReconciliationStatusEnum), default=ReconciliationStatusEnum.UNRECONCILED)
    reconciled_with = Column(UUID(as_uuid=True), nullable=True)  # Payment ID or Journal Entry ID
    reconciled_date = Column(DateTime, nullable=True)
    reconciled_by = Column(String(255), nullable=True)
    imported_at = Column(DateTime, default=datetime.utcnow)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    bank_account = relationship("BankAccount", back_populates="transactions")

# Payment Models
class Payment(Base):
    """Payment records for Purchase and Expense modules."""
    __tablename__ = "payments"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    payment_number = Column(String(50), nullable=False, unique=True)
    payment_type = Column(SQLEnum(PaymentTypeEnum), nullable=False)
    reference_id = Column(UUID(as_uuid=True), nullable=False)  # Purchase Bill ID or Expense ID
    reference_type = Column(SQLEnum(PaymentReferenceTypeEnum), nullable=False)
    vendor_id = Column(UUID(as_uuid=True), nullable=True)
    employee_id = Column(UUID(as_uuid=True), nullable=True)
    
    # Payment Details
    payment_date = Column(Date, nullable=False)
    payment_method = Column(SQLEnum(PaymentMethodEnum), nullable=False)
    bank_account_id = Column(UUID(as_uuid=True), ForeignKey("bank_accounts.id"), nullable=True)
    
    # Amounts
    gross_amount = Column(Numeric(15, 2), nullable=False)
    tds_amount = Column(Numeric(15, 2), default=0.0)
    other_deductions = Column(Numeric(15, 2), default=0.0)
    net_amount = Column(Numeric(15, 2), nullable=False)
    
    # Payment Instrument Details
    cheque_number = Column(String(50), nullable=True)
    cheque_date = Column(Date, nullable=True)
    utr_number = Column(String(50), nullable=True)  # For RTGS/NEFT
    transaction_reference = Column(String(100), nullable=True)
    
    # Status and Approval
    payment_status = Column(SQLEnum(PaymentStatusEnum), default=PaymentStatusEnum.DRAFT)
    approval_status = Column(SQLEnum(ApprovalStatusEnum), default=ApprovalStatusEnum.PENDING)
    approved_by = Column(String(255), nullable=True)
    approved_at = Column(DateTime, nullable=True)
    
    # Reconciliation
    reconciled = Column(Boolean, default=False)
    reconciled_with_transaction = Column(UUID(as_uuid=True), nullable=True)
    reconciled_date = Column(DateTime, nullable=True)
    
    notes = Column(Text, nullable=True)
    created_by = Column(String(255), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    bank_account = relationship("BankAccount", back_populates="payments")
    approval_workflow = relationship("PaymentApproval", back_populates="payment")

# Approval Workflow Models
class PaymentApproval(Base):
    """Payment approval workflow."""
    __tablename__ = "payment_approvals"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    payment_id = Column(UUID(as_uuid=True), ForeignKey("payments.id"), nullable=False)
    approval_level = Column(Integer, nullable=False)
    approver_role = Column(String(100), nullable=False)
    approver_email = Column(String(255), nullable=False)
    approval_status = Column(SQLEnum(ApprovalStatusEnum), default=ApprovalStatusEnum.PENDING)
    approved_at = Column(DateTime, nullable=True)
    rejection_reason = Column(Text, nullable=True)
    comments = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    payment = relationship("Payment", back_populates="approval_workflow")

class ApprovalMatrix(Base):
    """Configurable approval matrix."""
    __tablename__ = "approval_matrix"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    module_type = Column(SQLEnum(ModuleTypeEnum), nullable=False)
    transaction_type = Column(String(100), nullable=False)
    min_amount = Column(Numeric(15, 2), default=0.0)
    max_amount = Column(Numeric(15, 2), nullable=True)
    approval_level = Column(Integer, nullable=False)
    approver_role = Column(String(100), nullable=False)
    is_mandatory = Column(Boolean, default=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

# Bank Reconciliation Models
class BankReconciliation(Base):
    """Bank reconciliation records."""
    __tablename__ = "bank_reconciliations"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    bank_account_id = Column(UUID(as_uuid=True), ForeignKey("bank_accounts.id"), nullable=False)
    reconciliation_date = Column(Date, nullable=False)
    opening_balance = Column(Numeric(15, 2), nullable=False)
    closing_balance = Column(Numeric(15, 2), nullable=False)
    statement_balance = Column(Numeric(15, 2), nullable=False)
    difference_amount = Column(Numeric(15, 2), default=0.0)
    reconciled_transactions = Column(Integer, default=0)
    unreconciled_transactions = Column(Integer, default=0)
    reconciliation_status = Column(SQLEnum(ReconciliationStatusEnum), default=ReconciliationStatusEnum.IN_PROGRESS)
    reconciled_by = Column(String(255), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)

# Additional Enums for Bank Module

# =====================================================
# BANK MODULE PYDANTIC MODELS (API Requests/Responses)
# =====================================================

# Bank Account API Models
class BankAccountCreateRequest(BaseModel):
    """Request model for creating bank account."""
    account_name: str
    account_number: str
    ifsc_code: str
    bank_name: str
    branch_name: str
    account_type: AccountTypeEnum
    currency: str = "INR"
    opening_balance: float = 0.0
    overdraft_limit: float = 0.0
    is_primary: bool = False

class BankAccountResponse(BaseModel):
    """Response model for bank account."""
    id: str
    account_name: str
    account_number: str
    ifsc_code: str
    bank_name: str
    branch_name: str
    account_type: str
    currency: str
    current_balance: float
    overdraft_limit: float
    is_active: bool
    is_primary: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

# Payment API Models
class PaymentCreateRequest(BaseModel):
    """Request model for creating payment."""
    payment_type: PaymentTypeEnum
    reference_id: str
    reference_type: PaymentReferenceTypeEnum
    vendor_id: Optional[str] = None
    employee_id: Optional[str] = None
    payment_date: datetime
    payment_method: PaymentMethodEnum
    bank_account_id: Optional[str] = None
    gross_amount: float
    tds_amount: float = 0.0
    other_deductions: float = 0.0
    cheque_number: Optional[str] = None
    cheque_date: Optional[datetime] = None
    utr_number: Optional[str] = None
    transaction_reference: Optional[str] = None
    notes: Optional[str] = None

class PaymentResponse(BaseModel):
    """Response model for payment."""
    id: str
    payment_number: str
    payment_type: str
    payment_date: datetime
    payment_method: str
    gross_amount: float
    tds_amount: float
    net_amount: float
    payment_status: str
    approval_status: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

# Bank Transaction API Models
class BankTransactionImportRequest(BaseModel):
    """Request model for importing bank transactions."""
    bank_account_id: str
    transactions: List[Dict[str, Any]]

class BankTransactionResponse(BaseModel):
    """Response model for bank transaction."""
    id: str
    transaction_date: datetime
    description: str
    reference_number: str
    debit_amount: float
    credit_amount: float
    balance: float
    transaction_type: str
    reconciliation_status: str
    created_at: datetime

    class Config:
        from_attributes = True

# Approval API Models
class ApprovalActionRequest(BaseModel):
    """Request model for approval actions."""
    action: str  # approve/reject
    comments: Optional[str] = None
    rejection_reason: Optional[str] = None

class ApprovalResponse(BaseModel):
    """Response model for approval."""
    id: str
    approval_level: int
    approver_role: str
    approval_status: str
    approved_at: Optional[datetime] = None
    comments: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True 