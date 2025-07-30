from typing import List, Optional, Dict, Any
from datetime import datetime
from decimal import Decimal
from sqlalchemy import select, insert, update, delete, func, and_, or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import selectinload

from app.database import AsyncSessionFactory
from app.models.grn_models import (
    GRNCreateRequest, GRNResponse, GRNStatus, GRNItem as GRNItemModel, 
    GoodsReceiptNoteV2, GoodsReceiptNoteOrderItem
)
from app.models.purchase_order_models import PurchaseOrder, PurchaseOrderItem
import uuid


class GRNService:
    """Service class for Goods Receipt Note (GRN) management operations using PostgreSQL."""
    
    def __init__(self):
        pass
    
    async def create_grn(
        self, 
        grn_data: GRNCreateRequest, 
        user_id: str
    ) -> GRNResponse:
        """Create a new Goods Receipt Note with complete item tracking and PO status updates."""
        
        async with AsyncSessionFactory() as session:
            try:
                # Verify the Purchase Order exists and belongs to the user
                po_result = await session.execute(
                    select(PurchaseOrder).options(selectinload(PurchaseOrder.items))
                    .where(
                        and_(
                            PurchaseOrder.id == grn_data.po_id,
                            PurchaseOrder.user_id == user_id
                        )
                    )
                )
                purchase_order = po_result.scalar_one_or_none()
                
                if not purchase_order:
                    raise ValueError(f"Purchase Order not found or access denied")
                
                # Generate GRN number if not provided
                grn_number = grn_data.grn_number
                if not grn_number:
                    count_result = await session.execute(
                        select(func.count(GoodsReceiptNoteV2.id)).where(
                            GoodsReceiptNoteV2.user_google_id == user_id
                        )
                    )
                    count = count_result.scalar() or 0
                    grn_number = f"GRN-{datetime.now().year}-{count + 1:04d}"
                
                # Create GRN header record
                grn_id = uuid.uuid4()
                await session.execute(
                    insert(GoodsReceiptNoteV2).values(
                        id=grn_id,
                        user_google_id=user_id,
                        grn_number=grn_number,
                        po_id=grn_data.po_id,
                        vendor_id=purchase_order.vendor_id,
                        grn_date=grn_data.received_date.date(),
                        received_by=grn_data.received_by,  # Now storing received_by
                        warehouse_location=grn_data.warehouse_location,  # Now storing warehouse_location
                        vehicle_number=grn_data.vehicle_number,
                        vendor_challan_number=grn_data.delivery_note_number,
                        transporter_name=grn_data.driver_name,
                        status=grn_data.status.value,  # Use status from request
                        remarks=grn_data.general_notes,
                        created_at=datetime.utcnow(),
                        created_by=user_id,
                        updated_by=user_id
                    )
                )
                
                # Create GRN items and update PO item quantities
                grn_items_data = []
                for item in grn_data.items:
                    # Validate PO item exists
                    po_item = next((po_item for po_item in purchase_order.items 
                                  if str(po_item.id) == item.po_item_id), None)
                    if not po_item:
                        raise ValueError(f"PO item {item.po_item_id} not found in PO {grn_data.po_id}")
                    
                    # Create GRN item
                    grn_item_id = uuid.uuid4()
                    await session.execute(
                        insert(GoodsReceiptNoteOrderItem).values(
                            id=grn_item_id,
                            grn_id=grn_id,
                            po_item_id=item.po_item_id,
                            item_description=item.item_description,
                            unit=item.unit,
                            ordered_quantity=item.ordered_quantity,
                            received_quantity=item.received_quantity,
                            rejected_quantity=item.rejected_quantity,
                            rejection_reason=item.rejection_reason,
                            unit_price=item.unit_price,
                            item_remarks=item.notes or ''
                        )
                    )
                    
                    # Only update PO quantities if GRN is completed
                    if grn_data.status == GRNStatus.COMPLETED:
                        # This will be done after all items are processed
                        pass
                    
                    grn_items_data.append(item)
                
                # Only update PO quantities if GRN is completed
                if grn_data.status == GRNStatus.COMPLETED:
                    print(f"🔄 GRN is completed, updating PO quantities for: {grn_data.po_id}")
                    
                    # Update PO item quantities BEFORE status update
                    for item in grn_data.items:
                        # Get the PO item
                        po_item_result = await session.execute(
                            select(PurchaseOrderItem).where(PurchaseOrderItem.id == item.po_item_id)
                        )
                        po_item = po_item_result.scalar_one_or_none()
                        
                        if po_item:
                            # Update PO item received quantity
                            new_received_qty = po_item.received_quantity + Decimal(str(item.received_quantity))
                            new_pending_qty = po_item.quantity - new_received_qty
                            
                            print(f"📊 Updating PO item {po_item.item_description}:")
                            print(f"   Old received: {po_item.received_quantity}")
                            print(f"   Adding: {item.received_quantity}")
                            print(f"   New received: {new_received_qty}")
                            print(f"   New pending: {max(Decimal('0'), new_pending_qty)}")
                            
                            await session.execute(
                                update(PurchaseOrderItem)
                                .where(PurchaseOrderItem.id == item.po_item_id)
                                .values(
                                    received_quantity=new_received_qty,
                                    pending_quantity=max(Decimal('0'), new_pending_qty)
                                )
                            )
                    
                    # Flush changes to ensure they're visible for status calculation
                    await session.flush()
                    
                    # NOW update PO status based on updated quantities
                    await self._update_po_status(session, grn_data.po_id)
                else:
                    print(f"📝 GRN is draft, skipping PO quantity and status updates for: {grn_data.po_id}")
                
                # Commit the transaction
                await session.commit()
                
                # Calculate totals for response
                total_ordered = sum(Decimal(str(item.ordered_quantity)) for item in grn_data.items)
                total_received = sum(Decimal(str(item.received_quantity)) for item in grn_data.items)
                total_rejected = sum(Decimal(str(item.rejected_quantity)) for item in grn_data.items)
                
                return GRNResponse(
                    id=str(grn_id),
                    grn_number=grn_number,
                    po_id=grn_data.po_id,
                    po_number=purchase_order.po_number,
                    vendor_name=purchase_order.vendor.business_name if purchase_order.vendor else "Unknown Vendor",
                    received_date=grn_data.received_date,
                    received_by=grn_data.received_by,
                    warehouse_location=grn_data.warehouse_location,
                    status=grn_data.status,  # Return the actual status from request
                    total_ordered_quantity=float(total_ordered),
                    total_received_quantity=float(total_received),
                    total_rejected_quantity=float(total_rejected),
                    items=grn_data.items,
                    delivery_note_number=grn_data.delivery_note_number,
                    vehicle_number=grn_data.vehicle_number,
                    driver_name=grn_data.driver_name,
                    general_notes=grn_data.general_notes,
                    created_at=datetime.utcnow(),
                    updated_at=datetime.utcnow(),
                    created_by=user_id
                )
                
            except IntegrityError as e:
                await session.rollback()
                if "unique constraint" in str(e).lower():
                    raise ValueError(f"GRN number '{grn_number}' already exists")
                raise ValueError(f"Database constraint error: {str(e)}")
            except Exception as e:
                await session.rollback()
                raise Exception(f"Failed to create GRN: {str(e)}")
    
    async def _update_po_status(self, session, po_id: str):
        """Update PO status based on received quantities from all GRNs."""
        
        print(f"🔄 Updating PO status for PO: {po_id}")
        
        try:
            # Get all PO items with their received quantities
            po_items_result = await session.execute(
                select(PurchaseOrderItem).where(PurchaseOrderItem.po_id == po_id)
            )
            po_items = po_items_result.scalars().all()
            
            if not po_items:
                print(f"⚠️ No PO items found for PO: {po_id}")
                return
            
            total_ordered = sum(item.quantity for item in po_items)
            total_received = sum(item.received_quantity for item in po_items)
            
            print(f"📊 PO {po_id} - Total Ordered: {total_ordered}, Total Received: {total_received}")
            
            # Determine new status
            if total_received == Decimal('0'):
                new_status = "approved"  # No items received yet
            elif total_received >= total_ordered:
                new_status = "fully_received"  # All items received (database compatible)
            else:
                new_status = "partially_received"  # Some items received
            
            print(f"🎯 Setting PO {po_id} status to: {new_status}")
            
            # Update PO status
            update_result = await session.execute(
                update(PurchaseOrder)
                .where(PurchaseOrder.id == po_id)
                .values(
                    status=new_status,
                    updated_at=datetime.utcnow()
                )
            )
            
            print(f"🔧 Update result rowcount: {update_result.rowcount}")
            
            if update_result.rowcount > 0:
                print(f"✅ PO {po_id} status updated to: {new_status}")
            else:
                print(f"⚠️ No rows updated for PO: {po_id}")
                
        except Exception as e:
            print(f"❌ Error updating PO status for {po_id}: {str(e)}")
            raise
    
    async def get_grns(
        self, 
        user_id: str, 
        skip: int = 0, 
        limit: int = 100,
        status: Optional[str] = None,
        po_id: Optional[str] = None
    ) -> List[GRNResponse]:
        """Get GRNs for a user with optional filtering and complete item data."""
        
        async with AsyncSessionFactory() as session:
            try:
                # Build query with relationships
                query = select(GoodsReceiptNoteV2).options(
                    selectinload(GoodsReceiptNoteV2.items),
                    selectinload(GoodsReceiptNoteV2.purchase_order),
                    selectinload(GoodsReceiptNoteV2.vendor)
                ).where(GoodsReceiptNoteV2.user_google_id == user_id)
                
                # Apply filters
                if status:
                    query = query.where(GoodsReceiptNoteV2.status == status)
                if po_id:
                    query = query.where(GoodsReceiptNoteV2.po_id == po_id)
                
                # Apply pagination and ordering
                query = query.offset(skip).limit(limit).order_by(GoodsReceiptNoteV2.created_at.desc())

                result = await session.execute(query)
                grn_records = result.scalars().all()
                
                # Convert to response format
                grns = []
                for grn in grn_records:
                    # Convert GRN items
                    grn_items = []
                    for item in grn.items:
                        grn_items.append(GRNItemModel(
                            po_item_id=str(item.po_item_id),
                            item_description=item.item_description,
                            ordered_quantity=Decimal(item.ordered_quantity),
                            received_quantity=Decimal(item.received_quantity),
                            rejected_quantity=Decimal(item.rejected_quantity),
                            rejection_reason=item.rejection_reason,
                            unit_price=Decimal(item.unit_price),
                            unit=item.unit,
                            notes=item.item_remarks
                        ))
                    
                    # Calculate totals
                    total_ordered = sum(Decimal(item.ordered_quantity) for item in grn.items)
                    total_received = sum(Decimal(item.received_quantity) for item in grn.items)
                    total_rejected = sum(Decimal(item.rejected_quantity) for item in grn.items)
                    
                    grns.append(GRNResponse(
                        id=str(grn.id),
                        grn_number=grn.grn_number,
                        po_id=str(grn.po_id),
                        po_number=grn.purchase_order.po_number if grn.purchase_order else "Unknown",
                        vendor_name=grn.vendor.business_name if grn.vendor else "Unknown Vendor",
                        received_date=datetime.combine(grn.grn_date, datetime.min.time()),
                        received_by=grn.received_by or "System",  # Use stored received_by
                        warehouse_location=grn.warehouse_location or "Main Warehouse",  # Use stored warehouse_location
                        status=GRNStatus(grn.status.lower()) if grn.status else GRNStatus.COMPLETED,
                        total_ordered_quantity=total_ordered,
                        total_received_quantity=total_received,
                        total_rejected_quantity=total_rejected,
                        items=grn_items,
                        delivery_note_number=grn.vendor_challan_number,
                        vehicle_number=grn.vehicle_number,
                        driver_name=grn.transporter_name,
                        general_notes=grn.remarks,
                        created_at=grn.created_at,
                        updated_at=grn.updated_at,
                        created_by=grn.created_by
                    ))
                
                return grns
                
            except Exception as e:
                raise Exception(f"Failed to fetch GRNs: {str(e)}")
    
    async def get_grn_by_id(
        self, 
        grn_id: str, 
        user_id: str
    ) -> Optional[GRNResponse]:
        """Get a specific GRN by ID with complete item data."""
        
        async with AsyncSessionFactory() as session:
            try:
                query = select(GoodsReceiptNoteV2).options(
                    selectinload(GoodsReceiptNoteV2.items),
                    selectinload(GoodsReceiptNoteV2.purchase_order),
                    selectinload(GoodsReceiptNoteV2.vendor)
                ).where(
                    and_(
                        GoodsReceiptNoteV2.id == grn_id,
                        GoodsReceiptNoteV2.user_google_id == user_id
                    )
                )
                
                result = await session.execute(query)
                grn = result.scalar_one_or_none()
                
                if not grn:
                    return None
                
                # Convert GRN items
                grn_items = []
                for item in grn.items:
                    grn_items.append(GRNItemModel(
                        po_item_id=str(item.po_item_id),
                        item_description=item.item_description,
                        ordered_quantity=Decimal(item.ordered_quantity),
                        received_quantity=Decimal(item.received_quantity),
                        rejected_quantity=Decimal(item.rejected_quantity),
                        rejection_reason=item.rejection_reason,
                        unit_price=Decimal(item.unit_price),
                        unit=item.unit,
                        notes=item.item_remarks
                    ))
                
                # Calculate totals
                total_ordered = sum(Decimal(item.ordered_quantity) for item in grn.items)
                total_received = sum(Decimal(item.received_quantity) for item in grn.items)
                total_rejected = sum(Decimal(item.rejected_quantity) for item in grn.items)
                
                return GRNResponse(
                    id=str(grn.id),
                    grn_number=grn.grn_number,
                    po_id=str(grn.po_id),
                    po_number=grn.purchase_order.po_number if grn.purchase_order else "Unknown",
                    vendor_name=grn.vendor.business_name if grn.vendor else "Unknown Vendor",
                    received_date=datetime.combine(grn.grn_date, datetime.min.time()),
                    received_by=grn.received_by or "System",  # Use stored received_by
                    warehouse_location=grn.warehouse_location or "Main Warehouse",  # Use stored warehouse_location
                    status=GRNStatus(grn.status.lower()) if grn.status else GRNStatus.COMPLETED,
                    total_ordered_quantity=total_ordered,
                    total_received_quantity=total_received,
                    total_rejected_quantity=total_rejected,
                    items=grn_items,
                    delivery_note_number=grn.vendor_challan_number,
                    vehicle_number=grn.vehicle_number,
                    driver_name=grn.transporter_name,
                    general_notes=grn.remarks,
                    created_at=grn.created_at,
                    updated_at=grn.updated_at,
                    created_by=grn.created_by
                )
                
            except Exception as e:
                raise Exception(f"Failed to fetch GRN: {str(e)}")
    
    async def get_po_available_items(
        self, 
        po_id: str, 
        user_id: str
    ) -> Dict[str, Any]:
        """Get available items from a Purchase Order for GRN creation - REAL DATA."""
        
        async with AsyncSessionFactory() as session:
            try:
                # Get PO with items
                po_result = await session.execute(
                    select(PurchaseOrder).options(
                        selectinload(PurchaseOrder.items),
                        selectinload(PurchaseOrder.vendor)
                    ).where(
                        and_(
                            PurchaseOrder.id == po_id,
                            PurchaseOrder.user_id == user_id
                        )
                    )
                )
                purchase_order = po_result.scalar_one_or_none()
                
                if not purchase_order:
                    raise ValueError("Purchase Order not found or access denied")
                
                # Convert PO items to available items format
                available_items = []
                for po_item in purchase_order.items:
                    pending_qty = Decimal(po_item.quantity) - Decimal(po_item.received_quantity)
                    if pending_qty > 0:  # Only include items with pending quantity
                        available_items.append({
                            "id": str(po_item.id),
                            "item_description": po_item.item_description,
                            "unit": po_item.unit,
                            "ordered_quantity": Decimal(po_item.quantity),
                            "received_quantity": Decimal(po_item.received_quantity),
                            "pending_quantity": pending_qty,
                            "unit_price": Decimal(po_item.unit_price),
                            "total_amount": Decimal(po_item.total_amount)
                        })
                
                return {
                    "po_id": po_id,
                    "po_number": purchase_order.po_number,
                    "vendor_id": str(purchase_order.vendor_id) if purchase_order.vendor_id else None,
                    "vendor_name": purchase_order.vendor.business_name if purchase_order.vendor else "Unknown Vendor",
                    "items": available_items
                }
                
            except Exception as e:
                raise Exception(f"Failed to fetch PO items: {str(e)}")
    
    async def get_po_grn_summary(
        self, 
        po_id: str, 
        user_id: str
    ) -> Dict[str, Any]:
        """Get summary of all GRNs created against a PO for multiple GRN tracking."""
        
        async with AsyncSessionFactory() as session:
            try:
                # Get all GRNs for this PO
                grns_result = await session.execute(
                    select(GoodsReceiptNoteV2).options(
                        selectinload(GoodsReceiptNoteV2.items)
                    ).where(
                        and_(
                            GoodsReceiptNoteV2.po_id == po_id,
                            GoodsReceiptNoteV2.user_google_id == user_id
                        )
                    )
                )
                grns = grns_result.scalars().all()
                
                # Get PO items
                po_items_result = await session.execute(
                    select(PurchaseOrderItem).where(PurchaseOrderItem.po_id == po_id)
                )
                po_items = po_items_result.scalars().all()
                
                # Aggregate data
                grn_summaries = []
                for grn in grns:
                    total_received = sum(Decimal(item.received_quantity) for item in grn.items)
                    total_rejected = sum(Decimal(item.rejected_quantity) for item in grn.items)
                    
                    grn_summaries.append({
                        "grn_id": str(grn.id),
                        "grn_number": grn.grn_number,
                        "grn_date": grn.grn_date.isoformat(),
                        "status": grn.status,
                        "total_received": total_received,
                        "total_rejected": total_rejected,
                        "items_count": len(grn.items)
                    })
                
                # Calculate overall PO completion
                total_ordered = sum(Decimal(item.quantity) for item in po_items)
                total_received_overall = sum(Decimal(item.received_quantity) for item in po_items)
                completion_percentage = (total_received_overall / total_ordered * 100) if total_ordered > 0 else 0
                
                return {
                    "po_id": po_id,
                    "total_grns": len(grns),
                    "total_ordered_quantity": total_ordered,
                    "total_received_quantity": total_received_overall,
                    "completion_percentage": round(completion_percentage, 2),
                    "grn_summaries": grn_summaries
                }
                
            except Exception as e:
                raise Exception(f"Failed to fetch PO GRN summary: {str(e)}")
    
    async def complete_draft_grn(
        self, 
        grn_id: str, 
        user_id: str
    ) -> GRNResponse:
        """Complete a draft GRN and update PO quantities."""
        
        async with AsyncSessionFactory() as session:
            try:
                # Get the GRN with items
                grn_result = await session.execute(
                    select(GoodsReceiptNoteV2).options(
                        selectinload(GoodsReceiptNoteV2.items),
                        selectinload(GoodsReceiptNoteV2.purchase_order),
                        selectinload(GoodsReceiptNoteV2.vendor)
                    ).where(
                        and_(
                            GoodsReceiptNoteV2.id == grn_id,
                            GoodsReceiptNoteV2.user_google_id == user_id
                        )
                    )
                )
                grn = grn_result.scalar_one_or_none()
                
                if not grn:
                    raise ValueError("GRN not found or access denied")
                
                if grn.status != "DRAFT":
                    raise ValueError("Only draft GRNs can be completed")
                
                # Update PO item quantities for each GRN item
                for grn_item in grn.items:
                    po_item_result = await session.execute(
                        select(PurchaseOrderItem).where(PurchaseOrderItem.id == grn_item.po_item_id)
                    )
                    po_item = po_item_result.scalar_one_or_none()
                    
                    if po_item:
                        new_received_qty = po_item.received_quantity + grn_item.received_quantity
                        new_pending_qty = po_item.quantity - new_received_qty
                        
                        await session.execute(
                            update(PurchaseOrderItem)
                            .where(PurchaseOrderItem.id == grn_item.po_item_id)
                            .values(
                                received_quantity=new_received_qty,
                                pending_quantity=max(Decimal('0'), new_pending_qty)
                            )
                        )
                
                # Update GRN status to completed
                await session.execute(
                    update(GoodsReceiptNoteV2)
                    .where(GoodsReceiptNoteV2.id == grn_id)
                    .values(
                        status="COMPLETED",
                        updated_at=datetime.utcnow(),
                        updated_by=user_id
                    )
                )
                
                # Update PO status
                await self._update_po_status(session, str(grn.po_id))
                
                await session.commit()
                
                # Return updated GRN
                return await self.get_grn_by_id(grn_id, user_id)
                
            except Exception as e:
                await session.rollback()
                raise Exception(f"Failed to complete GRN: {str(e)}")
    
    async def update_grn(
        self, 
        grn_id: str, 
        grn_data: GRNCreateRequest, 
        user_id: str
    ) -> GRNResponse:
        """Update a GRN (only allowed for draft status)."""
        
        async with AsyncSessionFactory() as session:
            try:
                # Check if GRN exists and is editable
                grn_result = await session.execute(
                    select(GoodsReceiptNoteV2).where(
                        and_(
                            GoodsReceiptNoteV2.id == grn_id,
                            GoodsReceiptNoteV2.user_google_id == user_id
                        )
                    )
                )
                existing_grn = grn_result.scalar_one_or_none()
                
                if not existing_grn:
                    raise ValueError("GRN not found or access denied")
                
                if existing_grn.status != "DRAFT":
                    raise ValueError("Only draft GRNs can be edited")
                
                # Update GRN header
                await session.execute(
                    update(GoodsReceiptNoteV2)
                    .where(GoodsReceiptNoteV2.id == grn_id)
                    .values(
                        grn_date=grn_data.received_date.date(),
                        vehicle_number=grn_data.vehicle_number,
                        vendor_challan_number=grn_data.delivery_note_number,
                        transporter_name=grn_data.driver_name,
                        status=grn_data.status.value,
                        remarks=grn_data.general_notes,
                        updated_at=datetime.utcnow(),
                        updated_by=user_id
                    )
                )
                
                # Delete existing items
                await session.execute(
                    delete(GoodsReceiptNoteOrderItem).where(
                        GoodsReceiptNoteOrderItem.grn_id == grn_id
                    )
                )
                
                # Create new items
                for item in grn_data.items:
                    grn_item_id = uuid.uuid4()
                    await session.execute(
                        insert(GoodsReceiptNoteOrderItem).values(
                            id=grn_item_id,
                            grn_id=grn_id,
                            po_item_id=item.po_item_id,
                            item_description=item.item_description,
                            unit=item.unit,
                            ordered_quantity=item.ordered_quantity,
                            received_quantity=item.received_quantity,
                            rejected_quantity=item.rejected_quantity,
                            rejection_reason=item.rejection_reason,
                            unit_price=item.unit_price,
                            item_remarks=item.notes or ''
                        )
                    )
                
                await session.commit()
                
                # Return updated GRN
                return await self.get_grn_by_id(grn_id, user_id)
                
            except Exception as e:
                await session.rollback()
                raise Exception(f"Failed to update GRN: {str(e)}")

    async def cancel_grn(
        self, 
        grn_id: str, 
        user_id: str
    ) -> GRNResponse:
        """Cancel a draft GRN."""
        
        async with AsyncSessionFactory() as session:
            try:
                # Get the GRN
                grn_result = await session.execute(
                    select(GoodsReceiptNoteV2).options(
                        selectinload(GoodsReceiptNoteV2.items),
                        selectinload(GoodsReceiptNoteV2.purchase_order),
                        selectinload(GoodsReceiptNoteV2.vendor)
                    ).where(
                        and_(
                            GoodsReceiptNoteV2.id == grn_id,
                            GoodsReceiptNoteV2.user_google_id == user_id
                        )
                    )
                )
                grn = grn_result.scalar_one_or_none()
                
                if not grn:
                    raise ValueError("GRN not found or access denied")
                
                if grn.status != "DRAFT":
                    raise ValueError("Only draft GRNs can be cancelled")
                
                # Update GRN status to cancelled
                await session.execute(
                    update(GoodsReceiptNoteV2)
                    .where(GoodsReceiptNoteV2.id == grn_id)
                    .values(
                        status="CANCELLED",
                        updated_at=datetime.utcnow(),
                        updated_by=user_id
                    )
                )
                
                await session.commit()
                
                # Return updated GRN
                return await self.get_grn_by_id(grn_id, user_id)
                
            except Exception as e:
                await session.rollback()
                raise Exception(f"Failed to cancel GRN: {str(e)}")

    async def fix_po_statuses_for_completed_grns(self, user_id: str) -> Dict[str, str]:
        """Fix PO statuses for all completed GRNs that may have missed the status update."""
        
        async with AsyncSessionFactory() as session:
            try:
                # Get all completed GRNs
                grns_result = await session.execute(
                    select(GoodsReceiptNoteV2).where(
                        and_(
                            GoodsReceiptNoteV2.user_google_id == user_id,
                            GoodsReceiptNoteV2.status == "COMPLETED"
                        )
                    )
                )
                completed_grns = grns_result.scalars().all()
                
                fixed_pos = {}
                
                for grn in completed_grns:
                    print(f"🔄 Checking GRN: {grn.grn_number} for PO: {grn.po_id}")
                    
                    # Get current PO status
                    po_result = await session.execute(
                        select(PurchaseOrder).where(PurchaseOrder.id == grn.po_id)
                    )
                    po = po_result.scalar_one_or_none()
                    
                    if po:
                        old_status = po.status
                        print(f"📋 PO {po.po_number} current status: {old_status}")
                        
                        # Update PO status based on received quantities
                        await self._update_po_status(session, str(grn.po_id))
                        
                        # Get updated status
                        po_updated_result = await session.execute(
                            select(PurchaseOrder).where(PurchaseOrder.id == grn.po_id)
                        )
                        po_updated = po_updated_result.scalar_one_or_none()
                        
                        if po_updated and po_updated.status != old_status:
                            fixed_pos[po.po_number] = f"{old_status} → {po_updated.status}"
                            print(f"✅ Fixed PO {po.po_number}: {old_status} → {po_updated.status}")
                
                await session.commit()
                return fixed_pos
                
            except Exception as e:
                await session.rollback()
                raise Exception(f"Failed to fix PO statuses: {str(e)}")


# Create service instance
grn_service = GRNService() 