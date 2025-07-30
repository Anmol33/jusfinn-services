
from enum import Enum
import uuid
from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel
from sqlalchemy import Column, String, Text, Integer, Numeric, Boolean, DateTime, Date, ForeignKey, Enum as SQLEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.database import Base
from app.models.vendor_models import Vendor
from app.models.purchase_order_models import PurchaseOrder

class PurchaseBillStatus(str, Enum):
    DRAFT = "draft"
    SUBMITTED = "submitted"
    PAID = "paid"
    CANCELLED = "cancelled"

class PurchaseBillItem(BaseModel):
    po_item_id: str
    item_description: str
    quantity: float
    unit_price: float
    hsn_code: str  # Made mandatory for GST compliance
    cgst_rate: float = 0.0  # Central GST rate percentage
    sgst_rate: float = 0.0  # State GST rate percentage  
    igst_rate: float = 0.0  # Integrated GST rate percentage
    taxable_amount: float   # Item-level taxable amount (quantity * unit_price)
    cgst_amount: float = 0.0  # Calculated CGST amount
    sgst_amount: float = 0.0  # Calculated SGST amount
    igst_amount: float = 0.0  # Calculated IGST amount
    total_price: float      # Final amount including taxes
    notes: Optional[str] = None

    class Config:
        orm_mode = True

class PurchaseBillCreateRequest(BaseModel):
    po_id: str
    bill_number: str
    bill_date: datetime
    due_date: datetime
    items: List[PurchaseBillItem]
    notes: Optional[str] = None
    attachments: Optional[List[str]] = None
    status: PurchaseBillStatus = PurchaseBillStatus.DRAFT

class PurchaseBillResponse(BaseModel):
    id: str
    bill_number: str
    po_id: str
    po_number: str
    vendor_name: str
    bill_date: datetime
    due_date: datetime
    taxable_amount: float    # Total taxable amount before taxes
    total_cgst: float = 0.0  # Total CGST for entire bill
    total_sgst: float = 0.0  # Total SGST for entire bill  
    total_igst: float = 0.0  # Total IGST for entire bill
    total_amount: float      # Subtotal (taxable_amount + all taxes)
    grand_total: float       # Final bill amount (includes any additional charges/discounts)
    status: PurchaseBillStatus
    items: List[PurchaseBillItem]
    notes: Optional[str] = None
    attachments: Optional[List[str]] = None
    created_at: datetime
    updated_at: datetime
    created_by: str

    class Config:
        orm_mode = True

class PurchaseBill(Base):
    __tablename__ = "purchase_bills"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_google_id = Column(String(255), nullable=False)
    bill_number = Column(String(50), nullable=False, unique=True)
    vendor_bill_number = Column(String(50), nullable=False)
    vendor_id = Column(UUID(as_uuid=True), ForeignKey('vendors.id'), nullable=False)
    po_id = Column(UUID(as_uuid=True), ForeignKey('purchase_orders.id'), nullable=True)
    grn_id = Column(UUID(as_uuid=True), nullable=True)
    bill_date = Column(Date, nullable=False)
    due_date = Column(Date, nullable=False)
    
    # Tax totals at bill level
    taxable_amount = Column(Numeric(15, 2), nullable=False, default=0)  # Total before taxes
    total_cgst = Column(Numeric(15, 2), default=0)      # Total CGST amount
    total_sgst = Column(Numeric(15, 2), default=0)      # Total SGST amount
    total_igst = Column(Numeric(15, 2), default=0)      # Total IGST amount
    total_amount = Column(Numeric(15, 2), nullable=False, default=0)  # Subtotal with taxes
    grand_total = Column(Numeric(15, 2), nullable=False)  # Final amount
    
    # Additional fields that exist in database
    subtotal = Column(Numeric(15, 2), nullable=False, default=0)
    discount_amount = Column(Numeric(15, 2), default=0)
    cgst_amount = Column(Numeric(15, 2), default=0)
    sgst_amount = Column(Numeric(15, 2), default=0)
    igst_amount = Column(Numeric(15, 2), default=0)
    cess_amount = Column(Numeric(15, 2), default=0)
    tds_amount = Column(Numeric(15, 2), default=0)
    paid_amount = Column(Numeric(15, 2), default=0)
    
    status = Column(String(20), default='DRAFT')
    notes = Column(Text)
    attachments = Column(Text)  # Store as comma-separated URLs or JSON
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow)
    created_by = Column(String(255), nullable=False)
    updated_by = Column(String(255), nullable=False)

    # Fix the relationship by specifying foreign keys explicitly
    vendor = relationship("Vendor", foreign_keys=[vendor_id])
    items = relationship("PurchaseBillItemDB", back_populates="purchase_bill", 
                        foreign_keys="[PurchaseBillItemDB.purchase_bill_id]",
                        cascade="all, delete-orphan")

class PurchaseBillItemDB(Base):
    __tablename__ = "purchase_bill_items"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    purchase_bill_id = Column(UUID(as_uuid=True), ForeignKey('purchase_bills.id'), nullable=False)
    po_item_id = Column(UUID(as_uuid=True), ForeignKey('purchase_order_items.id'), nullable=False)
    item_description = Column(String(500), nullable=False)
    quantity = Column(Numeric(15, 3), nullable=False)
    unit_price = Column(Numeric(15, 2), nullable=False)
    
    # Tax fields at item level
    hsn_code = Column(String(10), nullable=False)         # HSN/SAC code (mandatory)
    cgst_rate = Column(Numeric(5, 2), default=0)          # CGST rate percentage
    sgst_rate = Column(Numeric(5, 2), default=0)          # SGST rate percentage  
    igst_rate = Column(Numeric(5, 2), default=0)          # IGST rate percentage
    taxable_amount = Column(Numeric(15, 2), nullable=False)  # Quantity * unit_price
    cgst_amount = Column(Numeric(15, 2), default=0)       # Calculated CGST amount f
    sgst_amount = Column(Numeric(15, 2), default=0)       # Calculated SGST amount
    igst_amount = Column(Numeric(15, 2), default=0)       # Calculated IGST amount
    
    total_price = Column(Numeric(15, 2), nullable=False)  # Final item amount with taxes
    notes = Column(Text)

    # Fix the back reference with explicit foreign key
    purchase_bill = relationship("PurchaseBill", back_populates="items",
                                foreign_keys=[purchase_bill_id])
