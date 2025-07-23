from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
import uuid
from sqlalchemy import select, insert, update, delete, func, and_, or_, desc
from sqlalchemy.orm import joinedload
from sqlalchemy.exc import IntegrityError
from app.database import get_postgres_session_direct
from app.services.purchase_order_service import purchase_order_service
from app.models.grn_models import GRNItem
from app.models import (
    # Import expense related models only
    ExpenseCreateRequest, ExpenseResponse,
    # Goods Receipt Note
    GoodsReceiptNote,
    # Purchase Bills
    PurchaseBill, PurchaseBillItem, InvoiceStatusEnum,
    # Expenses
    Expense, ExpenseCategory,
    # TDS
    TDSTransaction, TDSSectionEnum,
    # ITC
    ITCRecord, ITCStatusEnum,
    # Landed Cost
    Shipment, LandedCost,
    # Vendors and Items
    Vendor, ItemService,
    # Purchase Order models - for delegation (moved to dedicated import below)
    PurchaseOrderCreateRequest, PurchaseOrderUpdateRequest, 
    PurchaseOrderResponse
)
# Import PurchaseOrderStatus from the dedicated models file
from app.models.purchase_order_models import PurchaseOrderStatus


class PurchaseExpenseService:
    """Comprehensive service for all Purchase & Expense operations using PostgreSQL."""
    
    def __init__(self):
        pass
    
    # =====================================================
    # PURCHASE ORDERS - DELEGATE TO DEDICATED SERVICE
    # =====================================================
    
    async def create_purchase_order(self, po_data, user_id):
        """Delegate to purchase order service."""
        return await purchase_order_service.create_purchase_order(po_data, user_id)
    
    async def update_purchase_order(self, po_id, po_data, user_id):
        """Delegate to purchase order service."""
        return await purchase_order_service.update_purchase_order(po_id, po_data, user_id)
    
    async def get_purchase_orders(self, user_id, skip=0, limit=100, operational_status=None, approval_status=None, vendor_id=None, search=None):
        """Delegate to purchase order service."""
        return await purchase_order_service.get_purchase_orders(
            user_id=user_id, skip=skip, limit=limit,
            operational_status=operational_status, approval_status=approval_status,
            vendor_id=vendor_id, search=search
        )
    
    async def get_purchase_order_by_id(self, po_id, user_id):
        """Delegate to purchase order service."""
        return await purchase_order_service.get_purchase_order_by_id(po_id, user_id)
    
    async def submit_po_for_approval(self, po_id, user_id):
        """Delegate to purchase order service."""
        return await purchase_order_service.submit_for_approval(po_id, user_id)
    
    async def process_po_approval(self, po_id, action, comments, user_id):
        """Delegate to purchase order service."""
        return await purchase_order_service.process_approval(po_id, action, comments, user_id)
    
    async def get_po_approval_history(self, po_id, user_id):
        """Delegate to purchase order service."""
        return await purchase_order_service.get_approval_history(po_id, user_id)
    
    async def get_pending_approvals(self, user_id):
        """Delegate to purchase order service."""
        return await purchase_order_service.get_pending_approvals(user_id)
    
    async def update_po_operational_status(self, po_id, status, user_id):
        """Delegate to purchase order service."""
        return await purchase_order_service.update_operational_status(po_id, status, user_id)

    # =====================================================
    # GOODS RECEIPT NOTE
    # =====================================================
    
    async def create_grn(self, grn_data: Dict[str, Any], user_id: str) -> Dict[str, Any]:
        """Create a new goods receipt note."""
        
        async with get_postgres_session_direct() as session:
            try:
                grn = GoodsReceiptNote(
                    user_id=user_id,
                    po_id=grn_data.get('po_id'),
                    grn_number=grn_data.get('grn_number'),
                    received_date=datetime.fromisoformat(grn_data.get('received_date')),
                    vendor_id=grn_data.get('vendor_id'),
                    total_received_amount=grn_data.get('total_received_amount', 0),
                    status='RECEIVED',
                    received_by=user_id,
                    notes=grn_data.get('notes')
                )
                
                session.add(grn)
                await session.commit()
                await session.refresh(grn)
                
                # Add GRN items if provided
                if grn_data.get('items'):
                    for item_data in grn_data['items']:
                        grn_item = GRNItem(
                            grn_id=grn.id,
                            item_description=item_data.get('item_description'),
                            ordered_quantity=item_data.get('ordered_quantity'),
                            received_quantity=item_data.get('received_quantity'),
                            unit_price=item_data.get('unit_price'),
                            total_amount=item_data.get('total_amount')
                        )
                        session.add(grn_item)
                
                await session.commit()
                
                return {
                    "id": str(grn.id),
                    "grn_number": grn.grn_number,
                    "status": grn.status,
                    "message": "GRN created successfully"
                }
                
            except Exception as e:
                await session.rollback()
                raise Exception(f"Failed to create GRN: {str(e)}")

    # =====================================================
    # PURCHASE BILLS
    # =====================================================
    
    async def create_purchase_bill(self, bill_data: Dict[str, Any], user_id: str) -> Dict[str, Any]:
        """Create a new purchase bill."""
        
        async with get_postgres_session_direct() as session:
            try:
                bill = PurchaseBill(
                    user_id=user_id,
                    po_id=bill_data.get('po_id'),
                    vendor_id=bill_data.get('vendor_id'),
                    bill_number=bill_data.get('bill_number'),
                    bill_date=datetime.fromisoformat(bill_data.get('bill_date')),
                    due_date=datetime.fromisoformat(bill_data.get('due_date')) if bill_data.get('due_date') else None,
                    subtotal=bill_data.get('subtotal', 0),
                    tax_amount=bill_data.get('tax_amount', 0),
                    total_amount=bill_data.get('total_amount', 0),
                    status=InvoiceStatusEnum.PENDING,
                    payment_terms=bill_data.get('payment_terms'),
                    notes=bill_data.get('notes')
                )
                
                session.add(bill)
                await session.commit()
                await session.refresh(bill)
                
                # Add bill items if provided
                if bill_data.get('items'):
                    for item_data in bill_data['items']:
                        bill_item = PurchaseBillItem(
                            bill_id=bill.id,
                            item_description=item_data.get('item_description'),
                            quantity=item_data.get('quantity'),
                            unit_price=item_data.get('unit_price'),
                            total_amount=item_data.get('total_amount')
                        )
                        session.add(bill_item)
                
                await session.commit()
                
                return {
                    "id": str(bill.id),
                    "bill_number": bill.bill_number,
                    "status": bill.status.value,
                    "message": "Purchase bill created successfully"
                }
                
            except Exception as e:
                await session.rollback()
                raise Exception(f"Failed to create purchase bill: {str(e)}")

    # =====================================================
    # EXPENSES
    # =====================================================
    
    async def create_expense(self, expense_data: ExpenseCreateRequest, user_id: str) -> ExpenseResponse:
        """Create a new expense record."""
        
        async with get_postgres_session_direct() as session:
            try:
                expense = Expense(
                    user_id=user_id,
                    expense_date=expense_data.expense_date,
                    amount=expense_data.amount,
                    description=expense_data.description,
                    category=expense_data.category,
                    vendor_id=expense_data.vendor_id,
                    receipt_number=expense_data.receipt_number,
                    payment_method=expense_data.payment_method,
                    is_reimbursable=expense_data.is_reimbursable,
                    status='PENDING',
                    notes=expense_data.notes,
                    created_at=datetime.utcnow(),
                    updated_at=datetime.utcnow()
                )
                
                session.add(expense)
                await session.commit()
                await session.refresh(expense)
                
                return ExpenseResponse(
                    id=str(expense.id),
                    expense_date=expense.expense_date,
                    amount=float(expense.amount),
                    description=expense.description,
                    category=expense.category,
                    vendor_id=str(expense.vendor_id) if expense.vendor_id else None,
                    receipt_number=expense.receipt_number,
                    payment_method=expense.payment_method,
                    is_reimbursable=expense.is_reimbursable,
                    status=expense.status,
                    notes=expense.notes,
                    created_at=expense.created_at,
                    updated_at=expense.updated_at
                )
                
            except Exception as e:
                await session.rollback()
                raise Exception(f"Failed to create expense: {str(e)}")


# Create instance
purchase_expense_service = PurchaseExpenseService()