import enum
import uuid
from datetime import datetime, date
from typing import List, Optional
from decimal import Decimal
from pydantic import BaseModel, Field
from sqlalchemy import Column, String, Text, Integer, Numeric, Boolean, DateTime, Date, ForeignKey, Enum as SQLEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.database import Base


class GRNStatus(str, enum.Enum):
    DRAFT = "draft"
    PENDING_APPROVAL = "pending_approval"
    APPROVED = "approved"
    REJECTED = "rejected"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


# =====================================================
# GRN SQLALCHEMY MODELS
# =====================================================

class GRN(Base):
    __tablename__ = "grns"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(String(255), nullable=False)
    grn_number = Column(String(50), nullable=False, unique=True)
    po_id = Column(UUID(as_uuid=True), ForeignKey('purchase_orders.id'), nullable=False)
    vendor_id = Column(UUID(as_uuid=True), ForeignKey('vendors.id'), nullable=False)
    
    # Dates
    grn_date = Column(Date, nullable=False, default=datetime.utcnow)
    received_date = Column(Date, nullable=False)
    expected_delivery_date = Column(Date)
    
    # Delivery Information
    delivery_note_number = Column(String(100))
    vehicle_number = Column(String(20))
    received_by = Column(String(255), nullable=False)
    
    # Status and Workflow
    status = Column(String(50), nullable=False, default='draft')
    
    # Quality and Inspection
    quality_check_required = Column(Boolean, default=False)
    quality_approved = Column(Boolean, default=True)
    quality_checked_by = Column(String(255))
    quality_check_date = Column(Date)
    quality_notes = Column(Text)
    
    # Financial
    total_ordered_amount = Column(Numeric(15, 2), default=0)
    total_received_amount = Column(Numeric(15, 2), default=0)
    total_accepted_amount = Column(Numeric(15, 2), default=0)
    total_rejected_amount = Column(Numeric(15, 2), default=0)
    
    # Additional Information
    delivery_address = Column(Text)
    notes = Column(Text)
    rejection_reason = Column(Text)
    
    # Audit
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow)
    created_by = Column(UUID(as_uuid=True))
    updated_by = Column(UUID(as_uuid=True))
    
    # Relationships
    # purchase_order = relationship("PurchaseOrder", back_populates="grns")  # Temporarily commented out
    vendor = relationship("Vendor")
    items = relationship("GRNItem", back_populates="grn")


class GRNItem(Base):
    __tablename__ = "grn_items"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    grn_id = Column(UUID(as_uuid=True), ForeignKey('grns.id'), nullable=False)
    po_item_id = Column(UUID(as_uuid=True), ForeignKey('purchase_order_items.id'), nullable=False)
    
    # Item Information
    item_description = Column(String(500), nullable=False)
    hsn_code = Column(String(20), default='')
    unit = Column(String(20), default='Nos')
    
    # Quantities
    ordered_quantity = Column(Numeric(15, 3), nullable=False)
    received_quantity = Column(Numeric(15, 3), nullable=False)
    accepted_quantity = Column(Numeric(15, 3), nullable=False)
    rejected_quantity = Column(Numeric(15, 3), default=0)
    
    # Pricing
    unit_price = Column(Numeric(15, 2), nullable=False)
    total_ordered_amount = Column(Numeric(15, 2), nullable=False)
    total_received_amount = Column(Numeric(15, 2), nullable=False)
    total_accepted_amount = Column(Numeric(15, 2), nullable=False)
    
    # Quality Information
    quality_status = Column(String(20), default='approved')  # approved, rejected, pending
    rejection_reason = Column(Text)
    batch_number = Column(String(50))
    expiry_date = Column(Date)
    
    # Additional Information
    notes = Column(Text)
    
    # Relationships
    grn = relationship("GRN", back_populates="items")
    po_item = relationship("PurchaseOrderItem")


class GRNStatusHistory(Base):
    __tablename__ = "grn_status_history"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    grn_id = Column(UUID(as_uuid=True), ForeignKey('grns.id'), nullable=False)
    
    previous_status = Column(SQLEnum(GRNStatus))
    new_status = Column(SQLEnum(GRNStatus), nullable=False)
    changed_by = Column(String(255), nullable=False)
    changed_at = Column(DateTime, default=datetime.utcnow)
    notes = Column(Text)
    
    # Relationships
    grn = relationship("GRN")


# =====================================================
# GRN PYDANTIC MODELS
# =====================================================

class GRNItemRequest(BaseModel):
    po_item_id: str
    received_quantity: float
    accepted_quantity: float
    rejected_quantity: float = 0
    rejection_reason: Optional[str] = None
    batch_number: Optional[str] = None
    expiry_date: Optional[date] = None
    notes: Optional[str] = None


class GRNCreateRequest(BaseModel):
    po_id: str
    grn_date: date
    received_date: date
    delivery_note_number: Optional[str] = None
    vehicle_number: Optional[str] = None
    received_by: str
    quality_check_required: bool = False
    items: List[GRNItemRequest]
    notes: Optional[str] = None


class GRNUpdateRequest(BaseModel):
    grn_date: Optional[date] = None
    received_date: Optional[date] = None
    delivery_note_number: Optional[str] = None
    vehicle_number: Optional[str] = None
    received_by: Optional[str] = None
    quality_check_required: Optional[bool] = None
    quality_approved: Optional[bool] = None
    quality_notes: Optional[str] = None
    items: Optional[List[GRNItemRequest]] = None
    notes: Optional[str] = None
    status: Optional[GRNStatus] = None


class GRNItemResponse(BaseModel):
    id: str
    po_item_id: str
    item_description: str
    unit: str
    ordered_quantity: float
    received_quantity: float
    accepted_quantity: float
    rejected_quantity: float
    unit_price: float
    total_received_amount: float
    quality_status: str
    rejection_reason: Optional[str] = None
    batch_number: Optional[str] = None
    expiry_date: Optional[date] = None
    notes: Optional[str] = None

    class Config:
        from_attributes = True


class GRNResponse(BaseModel):
    id: str
    grn_number: str
    po_id: str
    po_number: str
    vendor_id: str
    vendor_name: str
    grn_date: date
    received_date: date
    delivery_note_number: Optional[str] = None
    vehicle_number: Optional[str] = None
    received_by: str
    status: GRNStatus
    quality_check_required: bool
    quality_approved: bool
    total_ordered_amount: float
    total_received_amount: float
    total_accepted_amount: float
    total_rejected_amount: float
    items: List[GRNItemResponse]
    notes: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class StatusChangeRequest(BaseModel):
    """Request for changing GRN status"""
    status: GRNStatus
    notes: Optional[str] = None


class StatusChangeResponse(BaseModel):
    """Response model for status change operations"""
    success: bool
    message: str
    new_status: GRNStatus