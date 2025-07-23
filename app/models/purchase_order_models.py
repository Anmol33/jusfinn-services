import enum
import uuid
from datetime import datetime, date
from typing import List, Optional
from decimal import Decimal

from pydantic import BaseModel, Field
from sqlalchemy import Column, String, Text, Integer, Numeric, Boolean, DateTime, Date, ForeignKey, Enum as SQLEnum, CheckConstraint, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.database import Base


# Simplified Single Status Enum for Purchase Orders
class PurchaseOrderStatus(str, enum.Enum):
    """Simplified single status for purchase order lifecycle"""
    DRAFT = "draft"                    # Being created/edited
    PENDING_APPROVAL = "pending_approval"  # Submitted for approval
    APPROVED = "approved"              # Approved and sent to vendor
    ACKNOWLEDGED = "acknowledged"       # Vendor confirmed receipt
    IN_PROGRESS = "in_progress"        # Vendor working on order
    PARTIALLY_DELIVERED = "partially_delivered"  # Some items delivered
    DELIVERED = "delivered"            # All items delivered
    COMPLETED = "completed"            # Invoiced and paid
    CANCELLED = "cancelled"            # Order cancelled
    REJECTED = "rejected"              # Approval rejected
    PARTIALLY_RECEIVED = "partially_received"  # Some items received via GRN
    FULLY_RECEIVED = "fully_received"  # All items received via GRN


# Keep some supporting enums for specific actions/workflows
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


# Database Models
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
    
    # Single simplified status (use string to avoid enum issues)
    status = Column(String(50), nullable=False, default='draft')
    
    __table_args__ = (
        CheckConstraint(
            "status IN ('draft', 'pending_approval', 'approved', 'acknowledged', 'in_progress', 'partially_delivered', 'delivered', 'completed', 'cancelled', 'rejected', 'partially_received', 'fully_received')",
            name='valid_status_check'
        ),
    )
    
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
    # grns = relationship("GRN", back_populates="purchase_order")  # Temporarily commented out
    # Simplified - remove complex approval relationships for now


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
    
    # GRN tracking fields
    received_quantity = Column(Numeric(15, 3), default=0)
    pending_quantity = Column(Numeric(15, 3), default=0)  # Computed field
    
    # Relationships
    purchase_order = relationship("PurchaseOrder", back_populates="items")


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


# Simple status history for audit trail (optional)
class POStatusHistory(Base):
    """Simple status change history for purchase orders"""
    __tablename__ = "po_status_history"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    po_id = Column(UUID(as_uuid=True), ForeignKey('purchase_orders.id'), nullable=False)
    
    # Status change details
    previous_status = Column(SQLEnum(PurchaseOrderStatus))
    new_status = Column(SQLEnum(PurchaseOrderStatus), nullable=False)
    changed_by = Column(String(255), nullable=False)
    changed_at = Column(DateTime, default=datetime.utcnow)
    notes = Column(Text)


# Pydantic Models (API Request/Response)
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
    status: Optional[PurchaseOrderStatus] = None  # Use simplified status


class POLineItemResponse(BaseModel):
    """Response model for purchase order line item."""
    id: str
    item_description: str
    unit: str
    quantity: float
    unit_price: float
    total_amount: float


class PurchaseOrderResponse(BaseModel):
    """Response model for purchase order with simplified single status."""
    id: str
    po_number: str
    vendor_id: str
    vendor_name: Optional[str] = None  # Add vendor business name
    vendor_code: Optional[str] = None  # Add vendor code for reference
    po_date: datetime
    expected_delivery_date: Optional[datetime] = None
    subtotal: float
    total_amount: float
    
    # Single simplified status
    status: PurchaseOrderStatus = Field(description="Purchase order status covering entire lifecycle")
    
    # Backward compatibility fields for frontend
    operational_status: Optional[str] = Field(default=None, description="For frontend compatibility - maps to status")
    approval_status: Optional[str] = Field(default=None, description="For frontend compatibility - maps to status")
    
    # Additional Information
    delivery_address: Optional[str] = None
    terms_and_conditions: Optional[str] = None
    notes: Optional[str] = None
    line_items: List[POLineItemResponse] = []
    
    # Audit fields
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# Simple action request for status changes
class StatusChangeRequest(BaseModel):
    """Simplified request for changing purchase order status"""
    status: PurchaseOrderStatus
    notes: Optional[str] = None


class StatusChangeResponse(BaseModel):
    """Response model for status change operations"""
    success: bool
    message: str
    new_status: PurchaseOrderStatus