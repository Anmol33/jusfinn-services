from datetime import datetime
from typing import Optional
from decimal import Decimal
from pydantic import BaseModel
from enum import Enum
import uuid

# SQLAlchemy imports
from sqlalchemy import Column, String, Integer, DateTime, Boolean, Text, Numeric, Date, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

# Shared database base
from app.database import Base

# =====================================================
# VENDOR PYDANTIC MODELS
# =====================================================

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
    is_msme: bool = False
    udyam_registration_number: Optional[str] = None
    contact_person: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    website: Optional[str] = None
    credit_limit: float = 0.0
    credit_days: int = 30
    payment_terms: VendorPaymentTerms = VendorPaymentTerms.NET_30
    bank_account_number: Optional[str] = None
    bank_ifsc_code: Optional[str] = None
    bank_account_holder_name: Optional[str] = None
    address: VendorAddress
    tds_applicable: bool = True
    default_tds_section: Optional[str] = None
    default_expense_ledger_id: Optional[str] = None

class VendorUpdateRequest(BaseModel):
    """Request model for updating vendor."""
    business_name: Optional[str] = None
    legal_name: Optional[str] = None
    gstin: Optional[str] = None
    pan: Optional[str] = None
    is_msme: Optional[bool] = None
    udyam_registration_number: Optional[str] = None
    contact_person: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    website: Optional[str] = None
    credit_limit: Optional[float] = None
    credit_days: Optional[int] = None
    payment_terms: Optional[VendorPaymentTerms] = None
    bank_account_number: Optional[str] = None
    bank_ifsc_code: Optional[str] = None
    bank_account_holder_name: Optional[str] = None
    address: Optional[VendorAddress] = None
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
    is_msme: bool
    udyam_registration_number: Optional[str] = None
    contact_person: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    website: Optional[str] = None
    credit_limit: float
    credit_days: int
    payment_terms: str
    bank_account_number: Optional[str] = None
    bank_ifsc_code: Optional[str] = None
    bank_account_holder_name: Optional[str] = None
    address_line1: Optional[str] = None
    address_line2: Optional[str] = None
    city: Optional[str] = None
    state_id: Optional[int] = None
    pincode: Optional[str] = None
    country: Optional[str] = None
    tds_applicable: bool
    default_tds_section: Optional[str] = None
    default_expense_ledger_id: Optional[str] = None
    vendor_rating: Optional[int] = None
    total_purchases: float = 0
    outstanding_amount: float = 0
    last_transaction_date: Optional[str] = None
    is_active: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

# =====================================================
# VENDOR SQLALCHEMY MODELS
# =====================================================

class Vendor(Base):
    __tablename__ = "vendors"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(String(255), nullable=False)
    vendor_code = Column(String(20), nullable=False, unique=True)
    business_name = Column(String(255), nullable=False)
    legal_name = Column(String(255))
    gstin = Column(String(15), unique=True)
    pan = Column(String(10))
    is_msme = Column(Boolean, default=False)
    udyam_registration_number = Column(String(20))
    contact_person = Column(String(100))
    phone = Column(String(15))
    email = Column(String(100))
    website = Column(String(255))
    credit_limit = Column(Numeric(15, 2), default=0)
    credit_days = Column(Integer, default=30)
    payment_terms = Column(String(20), default='NET_30')
    bank_account_number = Column(String(50))
    bank_ifsc_code = Column(String(11))
    bank_account_holder_name = Column(String(255))
    address_line1 = Column(String(255))
    address_line2 = Column(String(255))
    city = Column(String(100))
    state_id = Column(Integer, ForeignKey('states.id'))
    pincode = Column(String(10))
    country = Column(String(50), default='India')
    tds_applicable = Column(Boolean, default=True)
    default_tds_section = Column(String(10))
    default_expense_ledger_id = Column(UUID(as_uuid=True))
    vendor_rating = Column(Integer)
    total_purchases = Column(Numeric(15, 2), default=0)
    outstanding_amount = Column(Numeric(15, 2), default=0)
    last_transaction_date = Column(Date)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow)
    created_by = Column(String(255))  # Changed from UUID to String to accept MongoDB ObjectIds
    updated_by = Column(String(255))  # Changed from UUID to String to accept MongoDB ObjectIds
    state = relationship("State")