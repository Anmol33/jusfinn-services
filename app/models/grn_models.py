from enum import Enum

import uuid
from datetime import datetime
from typing import List, Optional


from pydantic import BaseModel
from sqlalchemy import Column, String, Text, Integer, Numeric, Boolean, DateTime, Date, ForeignKey, Enum as SQLEnum, CheckConstraint, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.database import Base

class GRNStatus(str, Enum):
    DRAFT = "draft"
    COMPLETED = "completed"
    BILLED = "billed"
    CANCELLED = "cancelled"

class GRNItem(BaseModel):
    po_item_id: str
    item_description: str
    ordered_quantity: float
    received_quantity: float
    rejected_quantity: float = 0
    rejection_reason: Optional[str] = None
    unit_price: float
    unit: str = "Nos"
    notes: Optional[str] = None

    class Config:
        orm_mode = True

class GRNCreateRequest(BaseModel):
    po_id: str
    grn_number: Optional[str] = None
    received_date: datetime
    received_by: str
    warehouse_location: str
    items: List[GRNItem]
    delivery_note_number: Optional[str] = None
    vehicle_number: Optional[str] = None
    driver_name: Optional[str] = None
    general_notes: Optional[str] = None
    status: GRNStatus = GRNStatus.DRAFT  # Allow choosing status during creation

class GRNResponse(BaseModel):
    id: str
    grn_number: str
    po_id: str
    po_number: str
    vendor_name: str
    received_date: datetime
    received_by: str
    warehouse_location: str
    status: GRNStatus
    total_ordered_quantity: float
    total_received_quantity: float
    total_rejected_quantity: float
    items: List[GRNItem]
    delivery_note_number: Optional[str] = None
    vehicle_number: Optional[str] = None
    driver_name: Optional[str] = None
    general_notes: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    created_by: str

    class Config:
        orm_mode = True


# Database Models
class GoodsReceiptNoteV2(Base):
    __tablename__ = "goods_receipt_notes"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_google_id = Column(String(255), nullable=False)
    grn_number = Column(String(50), nullable=False, unique=True)
    po_id = Column(UUID(as_uuid=True), ForeignKey('purchase_orders.id'), nullable=False)
    vendor_id = Column(UUID(as_uuid=True), ForeignKey('vendors.id'), nullable=False)
    grn_date = Column(Date, nullable=False, default=datetime.utcnow)

    # Receipt Details (ADDED MISSING FIELDS)
    received_by = Column(String(255))  # Added: who received the goods
    warehouse_location = Column(String(255))  # Added: where goods were received

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

    # Items
    items = relationship("GoodsReceiptNoteOrderItem", back_populates="grn", cascade="all, delete-orphan",  lazy="selectin")

    # Additional Information
    remarks = Column(Text)

    # Audit
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow)
    created_by = Column(String(255), nullable=False)
    updated_by = Column(String(255), nullable=False)

    # Relationships
    purchase_order = relationship("PurchaseOrder")
    vendor = relationship("Vendor")


class GoodsReceiptNoteOrderItem(Base):
    __tablename__ = "goods_receipt_notes_items"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    grn_id = Column(UUID(as_uuid=True), ForeignKey('goods_receipt_notes.id'), nullable=False)
    po_item_id = Column(UUID(as_uuid=True), ForeignKey('purchase_order_items.id'), nullable=False)

    item_description = Column(String(500), nullable=False)
    unit = Column(String(20), default='Nos')

    ordered_quantity = Column(Numeric(15, 3), nullable=False)  # From PO item at creation
    received_quantity = Column(Numeric(15, 3), nullable=False)
    rejected_quantity = Column(Numeric(15, 3), default=0)
    rejection_reason = Column(Text, nullable=True)
    unit_price = Column(Numeric(15, 2), nullable=False)

    item_remarks = Column(Text, default='')

    grn = relationship("GoodsReceiptNoteV2", back_populates="items")