from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
import uuid
from sqlalchemy import select, insert, update, delete, func, and_, or_, desc
from sqlalchemy.orm import joinedload
from sqlalchemy.exc import IntegrityError

from app.database import get_postgres_session_direct
from app.models.vendor_models import Vendor
from app.models.purchase_order_models import (
    PurchaseOrder, PurchaseOrderItem, 
    PurchaseOrderCreateRequest, PurchaseOrderUpdateRequest, PurchaseOrderResponse, 
    POLineItemResponse, PurchaseOrderStatus, 
    StatusChangeRequest, StatusChangeResponse, POStatusHistory
)


class PurchaseOrderService:
    """Service for managing purchase orders."""
    
    async def create_purchase_order(
        self, 
        po_data: PurchaseOrderCreateRequest, 
        user_id: str
    ) -> PurchaseOrderResponse:
        """Create a new purchase order."""
        
        # DEBUG: Log incoming data
        print(f"🔍 DEBUG [SERVICE]: Starting PO creation for user_id: {user_id}")
        print(f"🔍 DEBUG [SERVICE]: PO data received: {po_data}")
        print(f"🔍 DEBUG [SERVICE]: PO number: {po_data.po_number}")
        print(f"🔍 DEBUG [SERVICE]: Vendor ID: {po_data.vendor_id}")
        print(f"🔍 DEBUG [SERVICE]: PO date: {po_data.po_date} (type: {type(po_data.po_date)})")
        print(f"🔍 DEBUG [SERVICE]: Expected delivery date: {po_data.expected_delivery_date}")
        print(f"🔍 DEBUG [SERVICE]: Line items count: {len(po_data.line_items)}")
        
        async with get_postgres_session_direct() as session:
            try:
                print(f"🔍 DEBUG [SERVICE]: Database session created successfully")
                
                # Check if PO number already exists
                print(f"🔍 DEBUG [SERVICE]: Checking for existing PO number: {po_data.po_number}")
                existing_po = await session.execute(
                    select(PurchaseOrder).where(
                        and_(
                            PurchaseOrder.user_id == user_id,
                            PurchaseOrder.po_number == po_data.po_number
                        )
                    )
                )
                existing_po = existing_po.scalar_one_or_none()
                
                if existing_po:
                    print(f"🔍 DEBUG [SERVICE]: ERROR - PO number already exists: {po_data.po_number}")
                    raise ValueError(f"PO number '{po_data.po_number}' already exists")
                
                print(f"🔍 DEBUG [SERVICE]: PO number is unique, proceeding...")
                
                # Calculate totals from line items
                print(f"🔍 DEBUG [SERVICE]: Calculating totals from line items...")
                subtotal = 0
                for i, item in enumerate(po_data.line_items):
                    print(f"🔍 DEBUG [SERVICE]: Line item {i}: {item}")
                    print(f"🔍 DEBUG [SERVICE]: Item total_amount: {item.total_amount} (type: {type(item.total_amount)})")
                    subtotal += item.total_amount
                
                print(f"🔍 DEBUG [SERVICE]: Calculated subtotal: {subtotal}")
                total_amount = subtotal
                print(f"🔍 DEBUG [SERVICE]: Total amount: {total_amount}")
                
                # Validate and convert date fields
                try:
                    # Handle string dates from frontend
                    if po_data.po_date:
                        if isinstance(po_data.po_date, str):
                            # Parse ISO string (e.g., "2024-01-01T00:00:00.000Z")
                            po_date_converted = datetime.fromisoformat(po_data.po_date.replace('Z', '+00:00')).date()
                        else:
                            po_date_converted = po_data.po_date.date() if hasattr(po_data.po_date, 'date') else po_data.po_date
                    else:
                        po_date_converted = None
                        
                    if po_data.expected_delivery_date:
                        if isinstance(po_data.expected_delivery_date, str):
                            # Parse ISO string
                            expected_delivery_date_converted = datetime.fromisoformat(po_data.expected_delivery_date.replace('Z', '+00:00')).date()
                        else:
                            expected_delivery_date_converted = po_data.expected_delivery_date.date() if hasattr(po_data.expected_delivery_date, 'date') else po_data.expected_delivery_date
                    else:
                        expected_delivery_date_converted = None
                        
                    print(f"🔍 DEBUG [SERVICE]: Date conversion successful")
                    print(f"🔍 DEBUG [SERVICE]: PO date converted: {po_date_converted}")
                    print(f"🔍 DEBUG [SERVICE]: Expected delivery date converted: {expected_delivery_date_converted}")
                except Exception as date_error:
                    print(f"🔍 DEBUG [SERVICE]: ERROR in date conversion: {date_error}")
                    raise ValueError(f"Date conversion error: {date_error}")
                
                # Create PO object
                print(f"🔍 DEBUG [SERVICE]: Creating PurchaseOrder object...")
                try:
                    new_po = PurchaseOrder(
                        user_id=user_id,
                        po_number=po_data.po_number,
                        vendor_id=po_data.vendor_id,
                        po_date=po_date_converted,
                        expected_delivery_date=expected_delivery_date_converted,
                        subtotal=subtotal,
                        total_amount=total_amount,
                        status=PurchaseOrderStatus.DRAFT.value,  # Use .value to ensure string is passed
                        delivery_address=po_data.delivery_address,
                        terms_and_conditions=po_data.terms_and_conditions,
                        notes=po_data.notes,
                        created_at=datetime.utcnow(),
                        updated_at=datetime.utcnow()
                    )
                    print(f"🔍 DEBUG [SERVICE]: PurchaseOrder object created successfully")
                except Exception as po_error:
                    print(f"🔍 DEBUG [SERVICE]: ERROR creating PurchaseOrder object: {po_error}")
                    print(f"🔍 DEBUG [SERVICE]: Error type: {type(po_error)}")
                    raise ValueError(f"Failed to create PO object: {po_error}")
                
                # Add and commit PO
                try:
                    print(f"🔍 DEBUG [SERVICE]: Status value being used: '{new_po.status}' (type: {type(new_po.status)})")
                    print(f"🔍 DEBUG [SERVICE]: PurchaseOrderStatus.DRAFT value: '{PurchaseOrderStatus.DRAFT}'")
                    print(f"🔍 DEBUG [SERVICE]: Adding PO to session...")
                    session.add(new_po)
                    print(f"🔍 DEBUG [SERVICE]: Committing PO...")
                    await session.commit()
                    print(f"🔍 DEBUG [SERVICE]: Refreshing PO...")
                    await session.refresh(new_po)
                    print(f"🔍 DEBUG [SERVICE]: PO committed successfully with ID: {new_po.id}")
                except Exception as e:
                    print(f"🔍 DEBUG [SERVICE]: ERROR in PO commit: {e}")
                    print(f"🔍 DEBUG [SERVICE]: Error type: {type(e)}")
                    await session.rollback()
                    raise ValueError(f"Failed to save PO: {e}")

                
                # Insert PO line items
                print(f"🔍 DEBUG [SERVICE]: Creating line items...")
                for i, item in enumerate(po_data.line_items):
                    try:
                        print(f"🔍 DEBUG [SERVICE]: Creating line item {i}: {item}")
                        new_item = PurchaseOrderItem(
                            po_id=new_po.id,
                            item_description=item.item_description,
                            unit=item.unit,
                            quantity=item.quantity,
                            unit_price=item.unit_price,
                            total_amount=item.total_amount
                        )
                        session.add(new_item)
                        print(f"🔍 DEBUG [SERVICE]: Line item {i} added to session")
                    except Exception as item_error:
                        print(f"🔍 DEBUG [SERVICE]: ERROR creating line item {i}: {item_error}")
                        raise ValueError(f"Failed to create line item {i}: {item_error}")
                
                print(f"🔍 DEBUG [SERVICE]: Committing line items...")
                await session.commit()
                print(f"🔍 DEBUG [SERVICE]: All line items committed successfully")
                
                print(f"🔍 DEBUG [SERVICE]: Creating response object...")
                
                # Load vendor information
                vendor_result = await session.execute(
                    select(Vendor).where(Vendor.id == new_po.vendor_id)
                )
                vendor = vendor_result.scalar_one_or_none()
                
                # DEBUG: Check each field individually to identify the NoneType issue
                print(f"🔍 DEBUG [SERVICE]: new_po.id: {new_po.id}")
                print(f"🔍 DEBUG [SERVICE]: new_po.po_number: {new_po.po_number}")
                print(f"🔍 DEBUG [SERVICE]: new_po.vendor_id: {new_po.vendor_id} (type: {type(new_po.vendor_id)})")
                print(f"🔍 DEBUG [SERVICE]: vendor: {vendor.business_name if vendor else 'Not found'}")
                print(f"🔍 DEBUG [SERVICE]: new_po.status: {new_po.status} (type: {type(new_po.status)})")
                
                response = PurchaseOrderResponse(
                    id=str(new_po.id),
                    po_number=new_po.po_number,
                    vendor_id=str(new_po.vendor_id),
                    vendor_name=vendor.business_name if vendor else "Unknown Vendor",
                    vendor_code=vendor.vendor_code if vendor else None,
                    po_date=new_po.po_date,
                    expected_delivery_date=new_po.expected_delivery_date,
                    subtotal=float(new_po.subtotal),
                    total_amount=float(new_po.total_amount),
                    status=new_po.status,
                    operational_status=new_po.status.value if hasattr(new_po.status, 'value') else str(new_po.status),
                    approval_status=new_po.status.value if hasattr(new_po.status, 'value') else str(new_po.status),
                    delivery_address=new_po.delivery_address,
                    terms_and_conditions=new_po.terms_and_conditions,
                    notes=new_po.notes,
                    line_items=[],
                    created_at=new_po.created_at,
                    updated_at=new_po.updated_at
                )
                
                print(f"🔍 DEBUG [SERVICE]: Response object created successfully")
                return response
                
            except IntegrityError as e:
                await session.rollback()
                raise ValueError(f"Database constraint violation: {str(e)}")
            except Exception as e:
                await session.rollback()
                raise Exception(f"Failed to create purchase order: {str(e)}")

    async def update_purchase_order(
        self, 
        po_id: str,
        po_data: PurchaseOrderUpdateRequest, 
        user_id: str
    ) -> PurchaseOrderResponse:
        """Update an existing purchase order."""
        
        # DEBUG: Log incoming data
        print(f"🔍 DEBUG [SERVICE]: Starting PO update for po_id: {po_id}, user_id: {user_id}")
        print(f"🔍 DEBUG [SERVICE]: Update data: {po_data}")
        
        async with get_postgres_session_direct() as session:
            try:
                # Find the existing PO
                print(f"🔍 DEBUG [SERVICE]: Looking for PO with id: {po_id}")
                existing_po_result = await session.execute(
                    select(PurchaseOrder).where(
                        and_(
                            PurchaseOrder.id == po_id,
                            PurchaseOrder.user_id == user_id
                        )
                    )
                )
                existing_po = existing_po_result.scalar_one_or_none()
                
                if not existing_po:
                    print(f"🔍 DEBUG [SERVICE]: PO not found with id: {po_id}")
                    raise ValueError(f"Purchase order not found with id: {po_id}")
                
                print(f"🔍 DEBUG [SERVICE]: Found existing PO: {existing_po.po_number}")
                
                # Update PO fields if provided
                if po_data.po_number:
                    existing_po.po_number = po_data.po_number
                if po_data.vendor_id:
                    existing_po.vendor_id = po_data.vendor_id
                    
                # Handle date fields with proper conversion
                if po_data.po_date:
                    print(f"🔍 DEBUG [SERVICE]: Original po_date: {po_data.po_date} (type: {type(po_data.po_date)})")
                    if isinstance(po_data.po_date, str):
                        # Parse ISO string and extract date part
                        # Handle malformed dates with duplicate time components
                        date_str = po_data.po_date
                        print(f"🔍 DEBUG [SERVICE]: Processing date string: {date_str}")
                        # Clean up malformed date strings like "2025-07-21T00:00:00T00:00:00.000Z"
                        if date_str.count('T') > 1:
                            # Take only the first part before the second T
                            date_str = date_str.split('T')[0] + 'T00:00:00.000Z'
                            print(f"🔍 DEBUG [SERVICE]: Cleaned date string: {date_str}")
                        existing_po.po_date = datetime.fromisoformat(date_str.replace('Z', '+00:00')).date()
                        print(f"🔍 DEBUG [SERVICE]: Converted po_date: {existing_po.po_date}")
                    else:
                        existing_po.po_date = po_data.po_date.date() if hasattr(po_data.po_date, 'date') else po_data.po_date
                        
                if po_data.expected_delivery_date:
                    print(f"🔍 DEBUG [SERVICE]: Original expected_delivery_date: {po_data.expected_delivery_date} (type: {type(po_data.expected_delivery_date)})")
                    if isinstance(po_data.expected_delivery_date, str):
                        # Parse ISO string and extract date part
                        # Handle malformed dates with duplicate time components
                        date_str = po_data.expected_delivery_date
                        print(f"🔍 DEBUG [SERVICE]: Processing expected delivery date string: {date_str}")
                        # Clean up malformed date strings
                        if date_str.count('T') > 1:
                            # Take only the first part before the second T
                            date_str = date_str.split('T')[0] + 'T00:00:00.000Z'
                            print(f"🔍 DEBUG [SERVICE]: Cleaned expected delivery date string: {date_str}")
                        existing_po.expected_delivery_date = datetime.fromisoformat(date_str.replace('Z', '+00:00')).date()
                        print(f"🔍 DEBUG [SERVICE]: Converted expected_delivery_date: {existing_po.expected_delivery_date}")
                    else:
                        existing_po.expected_delivery_date = po_data.expected_delivery_date.date() if hasattr(po_data.expected_delivery_date, 'date') else po_data.expected_delivery_date
                        
                if po_data.delivery_address is not None:
                    existing_po.delivery_address = po_data.delivery_address
                if po_data.terms_and_conditions is not None:
                    existing_po.terms_and_conditions = po_data.terms_and_conditions
                if po_data.notes is not None:
                    existing_po.notes = po_data.notes
                
                existing_po.updated_at = datetime.utcnow()
                
                # Update line items if provided
                if po_data.line_items is not None:
                    print(f"🔍 DEBUG [SERVICE]: Updating line items, count: {len(po_data.line_items)}")
                    
                    # Delete existing line items
                    await session.execute(
                        delete(PurchaseOrderItem).where(PurchaseOrderItem.po_id == existing_po.id)
                    )
                    
                    # Add new line items and recalculate totals
                    subtotal = 0
                    for i, item in enumerate(po_data.line_items):
                        print(f"🔍 DEBUG [SERVICE]: Adding line item {i}: {item}")
                        new_item = PurchaseOrderItem(
                            po_id=existing_po.id,
                            item_description=item.item_description,
                            unit=item.unit,
                            quantity=item.quantity,
                            unit_price=item.unit_price,
                            total_amount=item.total_amount
                        )
                        session.add(new_item)
                        subtotal += item.total_amount
                    
                    existing_po.subtotal = subtotal
                    existing_po.total_amount = subtotal
                    print(f"🔍 DEBUG [SERVICE]: Updated totals - subtotal: {subtotal}")
                
                # Commit changes
                print(f"🔍 DEBUG [SERVICE]: Committing PO updates...")
                await session.commit()
                await session.refresh(existing_po)
                print(f"🔍 DEBUG [SERVICE]: PO updated successfully")
                
                # Load line items for response
                line_items_result = await session.execute(
                    select(PurchaseOrderItem).where(PurchaseOrderItem.po_id == existing_po.id)
                )
                line_items = line_items_result.scalars().all()
                
                # Create response
                response = PurchaseOrderResponse(
                    id=str(existing_po.id),
                    po_number=existing_po.po_number,
                    vendor_id=str(existing_po.vendor_id),
                    po_date=existing_po.po_date,
                    expected_delivery_date=existing_po.expected_delivery_date,
                    subtotal=float(existing_po.subtotal),
                    total_amount=float(existing_po.total_amount),
                    status=existing_po.status,
                    operational_status=existing_po.status.value if hasattr(existing_po.status, 'value') else str(existing_po.status),
                    approval_status=existing_po.status.value if hasattr(existing_po.status, 'value') else str(existing_po.status),
                    delivery_address=existing_po.delivery_address,
                    terms_and_conditions=existing_po.terms_and_conditions,
                    notes=existing_po.notes,
                    line_items=[
                        POLineItemResponse(
                            id=str(item.id),
                            item_description=item.item_description or "",
                            unit=item.unit or "Nos",
                            quantity=float(item.quantity),
                            unit_price=float(item.unit_price),
                            total_amount=float(item.total_amount)
                        ) for item in line_items
                    ],
                    created_at=existing_po.created_at,
                    updated_at=existing_po.updated_at
                )
                
                print(f"🔍 DEBUG [SERVICE]: Update response created successfully")
                return response
                
            except IntegrityError as e:
                await session.rollback()
                print(f"🔍 DEBUG [SERVICE]: Database integrity error: {e}")
                raise ValueError(f"Database constraint violation: {str(e)}")
            except Exception as e:
                await session.rollback()
                print(f"🔍 DEBUG [SERVICE]: Update error: {e}")
                raise Exception(f"Failed to update purchase order: {str(e)}")
    
    async def get_purchase_orders(
        self, 
        user_id: str,
        skip: int = 0,
        limit: int = 100,
        operational_status: Optional[str] = None,
        approval_status: Optional[str] = None,
        vendor_id: Optional[str] = None,
        search: Optional[str] = None
    ) -> List[PurchaseOrderResponse]:
        """Get purchase orders with filtering."""
        
        async with get_postgres_session_direct() as session:
            try:
                # Build query with joinedload for items and vendor
                query = (
                    select(PurchaseOrder)
                    .options(
                        joinedload(PurchaseOrder.items),
                        joinedload(PurchaseOrder.vendor)
                    )
                    .where(PurchaseOrder.user_id == user_id)
                )
                
                # Apply filters
                if operational_status:
                    query = query.where(PurchaseOrder.status == operational_status)
                
                if approval_status:
                    # For backward compatibility, map approval_status to our unified status
                    query = query.where(PurchaseOrder.status == approval_status)
                    
                if vendor_id:
                    query = query.where(PurchaseOrder.vendor_id == vendor_id)
                    
                if search:
                    query = query.where(
                        or_(
                            PurchaseOrder.po_number.ilike(f"%{search}%"),
                            PurchaseOrder.notes.ilike(f"%{search}%")
                        )
                    )
                
                # Add ordering and pagination
                query = query.order_by(desc(PurchaseOrder.created_at)).offset(skip).limit(limit)
                
                # Execute query
                result = await session.execute(query)
                purchase_orders = result.unique().scalars().all()
                
                # Convert to response format
                responses = []
                for po in purchase_orders:
                    try:
                        status_value = po.status.value if hasattr(po.status, 'value') else str(po.status)
                        
                        response = PurchaseOrderResponse(
                            id=str(po.id),
                            po_number=po.po_number,
                            vendor_id=str(po.vendor_id),
                            vendor_name=po.vendor.business_name if po.vendor else "Unknown Vendor",
                            vendor_code=po.vendor.vendor_code if po.vendor else None,
                            po_date=po.po_date,
                            expected_delivery_date=po.expected_delivery_date,
                            subtotal=float(po.subtotal),
                            total_amount=float(po.total_amount),
                            status=po.status,
                            operational_status=status_value,  # For frontend compatibility
                            approval_status=status_value,     # For frontend compatibility
                            delivery_address=po.delivery_address,
                            terms_and_conditions=po.terms_and_conditions,
                            notes=po.notes,
                            line_items=[
                                POLineItemResponse(
                                    id=str(item.id),
                                    item_description=item.item_description or "",
                                    unit=item.unit or "Nos",
                                    quantity=float(item.quantity),
                                    unit_price=float(item.unit_price),
                                    total_amount=float(item.total_amount)
                                ) for item in po.items
                            ] if hasattr(po, 'items') and po.items else [],
                            created_at=po.created_at,
                            updated_at=po.updated_at
                        )
                        responses.append(response)
                        
                    except Exception as po_error:
                        # Log error but continue processing other POs
                        print(f"Error processing PO {po.id}: {po_error}")
                        continue
                
                return responses
                
            except Exception as e:
                print(f"Error in get_purchase_orders: {e}")
                raise Exception(f"Failed to get purchase orders: {str(e)}")

    async def get_purchase_order_by_id(self, po_id: str, user_id: str) -> Optional[PurchaseOrderResponse]:
        """Get a specific purchase order by ID."""
        
        async with get_postgres_session_direct() as session:
            result = await session.execute(
                select(PurchaseOrder)
                .options(
                    joinedload(PurchaseOrder.items),
                    joinedload(PurchaseOrder.vendor)
                )
                .where(
                    and_(
                        PurchaseOrder.id == po_id,
                        PurchaseOrder.user_id == user_id
                    )
                )
            )
            
            po = result.unique().scalar_one_or_none()
            
            if not po:
                return None
                
            return PurchaseOrderResponse(
                id=str(po.id),
                po_number=po.po_number,
                vendor_id=str(po.vendor_id),
                vendor_name=po.vendor.business_name if po.vendor else "Unknown Vendor",
                vendor_code=po.vendor.vendor_code if po.vendor else None,
                po_date=po.po_date,
                expected_delivery_date=po.expected_delivery_date,
                subtotal=float(po.subtotal),
                total_amount=float(po.total_amount),
                status=po.status,
                operational_status=po.status.value if hasattr(po.status, 'value') else str(po.status),
                approval_status=po.status.value if hasattr(po.status, 'value') else str(po.status),
                delivery_address=po.delivery_address,
                terms_and_conditions=po.terms_and_conditions,
                notes=po.notes,
                line_items=[
                    POLineItemResponse(
                        id=str(item.id),
                        item_description=item.item_description or "",
                        unit=item.unit or "Nos",
                        quantity=float(item.quantity),
                        unit_price=float(item.unit_price),
                        total_amount=float(item.total_amount)
                    ) for item in po.items
                ] if hasattr(po, 'items') and po.items else [],
                created_at=po.created_at,
                updated_at=po.updated_at
            )

    # =====================================================
    # APPROVAL WORKFLOW METHODS
    # =====================================================
    
    async def submit_for_approval(self, po_id: str, user_id: str) -> Dict[str, Any]:
        """Submit a purchase order for approval."""
        
        print(f"🔍 DEBUG [SERVICE]: Starting submit_for_approval for po_id: {po_id}")
        
        async with get_postgres_session_direct() as session:
            try:
                # Find the PO
                result = await session.execute(
                    select(PurchaseOrder).where(
                        and_(
                            PurchaseOrder.id == po_id,
                            PurchaseOrder.user_id == user_id
                        )
                    )
                )
                po = result.scalar_one_or_none()
                
                if not po:
                    raise ValueError(f"Purchase order not found: {po_id}")
                
                if po.status not in [PurchaseOrderStatus.DRAFT.value, PurchaseOrderStatus.REJECTED.value]:
                    raise ValueError(f"Purchase order must be in DRAFT or REJECTED status to submit for approval. Current status: {po.status}")
                
                # Update status to pending approval
                po.status = PurchaseOrderStatus.PENDING_APPROVAL.value
                po.updated_at = datetime.utcnow()
                
                await session.commit()
                
                print(f"🔍 DEBUG [SERVICE]: PO {po_id} submitted for approval successfully")
                
                return {
                    "success": True,
                    "message": "Purchase order submitted for approval",
                    "new_status": PurchaseOrderStatus.PENDING_APPROVAL.value
                }
                
            except Exception as e:
                await session.rollback()
                print(f"🔍 DEBUG [SERVICE]: Error in submit_for_approval: {e}")
                raise Exception(f"Failed to submit for approval: {str(e)}")

    async def process_approval(self, po_id: str, action: str, comments: Optional[str], user_id: str) -> Dict[str, Any]:
        """Process approval action on a purchase order."""
        
        print(f"🔍 DEBUG [SERVICE]: Starting process_approval for po_id: {po_id}, action: {action}")
        
        async with get_postgres_session_direct() as session:
            try:
                # Find the PO
                result = await session.execute(
                    select(PurchaseOrder).where(PurchaseOrder.id == po_id)
                )
                po = result.scalar_one_or_none()
                
                if not po:
                    raise ValueError(f"Purchase order not found: {po_id}")
                
                if po.status != PurchaseOrderStatus.PENDING_APPROVAL:
                    raise ValueError(f"Purchase order must be in PENDING_APPROVAL status")
                
                # Update status based on action
                if action == "approve":
                    po.status = PurchaseOrderStatus.APPROVED.value
                    new_status = "APPROVED"
                elif action == "reject":
                    po.status = PurchaseOrderStatus.REJECTED.value
                    new_status = "REJECTED"
                elif action == "request_changes":
                    po.status = PurchaseOrderStatus.DRAFT.value
                    new_status = "DRAFT"
                else:
                    raise ValueError(f"Invalid action: {action}")
                
                po.updated_at = datetime.utcnow()
                
                await session.commit()
                
                print(f"🔍 DEBUG [SERVICE]: PO {po_id} approval processed successfully")
                
                return {
                    "success": True,
                    "approval_status": new_status,
                    "operational_status": new_status,
                    "action": action,
                    "comments": comments
                }
                
            except Exception as e:
                await session.rollback()
                print(f"🔍 DEBUG [SERVICE]: Error in process_approval: {e}")
                raise Exception(f"Failed to process approval: {str(e)}")

    async def get_approval_history(self, po_id: str, user_id: str) -> List[Dict[str, Any]]:
        """Get approval history for a purchase order."""
        
        print(f"🔍 DEBUG [SERVICE]: Getting approval history for po_id: {po_id}")
        
        # For now, return empty history - can be enhanced later
        return []

    async def get_pending_approvals(self, user_id: str) -> List[PurchaseOrderResponse]:
        """Get purchase orders pending approval."""
        
        print(f"🔍 DEBUG [SERVICE]: Getting pending approvals for user: {user_id}")
        
        return await self.get_purchase_orders(
            user_id=user_id,
            operational_status=PurchaseOrderStatus.PENDING_APPROVAL.value
        )

    async def update_operational_status(self, po_id: str, status: PurchaseOrderStatus, user_id: str) -> bool:
        """Update operational status of a purchase order."""
        
        print(f"🔍 DEBUG [SERVICE]: Updating operational status for po_id: {po_id} to {status}")
        
        async with get_postgres_session_direct() as session:
            try:
                # Find the PO
                result = await session.execute(
                    select(PurchaseOrder).where(
                        and_(
                            PurchaseOrder.id == po_id,
                            PurchaseOrder.user_id == user_id
                        )
                    )
                )
                po = result.scalar_one_or_none()
                
                if not po:
                    return False
                
                po.status = status.value
                po.updated_at = datetime.utcnow()
                
                await session.commit()
                
                print(f"🔍 DEBUG [SERVICE]: Status updated successfully to {status}")
                return True
                
            except Exception as e:
                await session.rollback()
                print(f"🔍 DEBUG [SERVICE]: Error updating status: {e}")
                return False


# Create service instance
purchase_order_service = PurchaseOrderService()