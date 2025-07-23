from typing import List, Optional, Dict, Any
from decimal import Decimal
from datetime import datetime, date
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import and_, or_, func, select
from sqlalchemy.orm import selectinload

from app.database import get_postgres_session_direct
from app.models.grn_models import GRN, GRNItem, GRNStatus, GRNCreateRequest, GRNUpdateRequest, GRNResponse, GRNItemResponse
from app.models.purchase_order_models import PurchaseOrder, PurchaseOrderItem, PurchaseOrderStatus
from app.models.vendor_models import Vendor


class GRNService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def generate_grn_number(self, user_id: str) -> str:
        """Generate unique GRN number"""
        current_year = datetime.now().year
        
        # Get the last GRN for this user in the current year
        query = select(GRN).where(
            and_(
                GRN.user_id == user_id,
                func.extract('year', GRN.created_at) == current_year
            )
        ).order_by(GRN.created_at.desc()).limit(1)
        
        result = await self.session.execute(query)
        last_grn = result.scalar_one_or_none()
        
        if last_grn:
            last_number = int(last_grn.grn_number.split('-')[-1])
            new_number = last_number + 1
        else:
            new_number = 1
            
        return f"GRN-{current_year}-{new_number:04d}"

    async def create_grn_from_po(self, po_id: str, grn_data: GRNCreateRequest, user_id: str) -> GRNResponse:
        """Create GRN from Purchase Order"""
        # Validate PO exists and is approved
        po_query = select(PurchaseOrder).where(
            and_(
                PurchaseOrder.id == po_id,
                PurchaseOrder.user_id == user_id
            )
        )
        po_result = await self.session.execute(po_query)
        po = po_result.scalar_one_or_none()
        
        if not po:
            raise ValueError("Purchase Order not found")
            
        if po.status not in [PurchaseOrderStatus.APPROVED, PurchaseOrderStatus.IN_PROGRESS]:
            raise ValueError("Purchase Order must be approved to create GRN")

        # Generate GRN number
        grn_number = await self.generate_grn_number(user_id)
        
        # Create GRN
        grn = GRN(
            user_id=user_id,
            grn_number=grn_number,
            po_id=po_id,
            vendor_id=po.vendor_id,
            grn_date=grn_data.grn_date,
            received_date=grn_data.received_date,
            delivery_note_number=grn_data.delivery_note_number,
            vehicle_number=grn_data.vehicle_number,
            received_by=grn_data.received_by,
            quality_check_required=grn_data.quality_check_required,
            notes=grn_data.notes,
            status=GRNStatus.DRAFT,
            created_by=user_id
        )
        
        self.session.add(grn)
        await self.session.flush()  # Get GRN ID
        
        # Create GRN items
        total_received_amount = Decimal('0')
        total_accepted_amount = Decimal('0')
        total_rejected_amount = Decimal('0')
        
        for item_data in grn_data.items:
            # Get PO item
            po_item_query = select(PurchaseOrderItem).where(
                and_(
                    PurchaseOrderItem.id == item_data.po_item_id,
                    PurchaseOrderItem.po_id == po_id
                )
            )
            po_item_result = await self.session.execute(po_item_query)
            po_item = po_item_result.scalar_one_or_none()
            
            if not po_item:
                raise ValueError(f"PO Item {item_data.po_item_id} not found")
            
            # Validate quantities
            if item_data.received_quantity < 0:
                raise ValueError("Received quantity cannot be negative")
            if item_data.accepted_quantity + item_data.rejected_quantity != item_data.received_quantity:
                raise ValueError("Accepted + Rejected quantities must equal Received quantity")
            
            # Calculate amounts
            total_received_amount += Decimal(str(item_data.received_quantity)) * po_item.unit_price
            total_accepted_amount += Decimal(str(item_data.accepted_quantity)) * po_item.unit_price
            total_rejected_amount += Decimal(str(item_data.rejected_quantity)) * po_item.unit_price
            
            grn_item = GRNItem(
                grn_id=grn.id,
                po_item_id=item_data.po_item_id,
                item_description=po_item.item_description,
                hsn_code=po_item.hsn_code,
                unit=po_item.unit,
                ordered_quantity=po_item.quantity,
                received_quantity=item_data.received_quantity,
                accepted_quantity=item_data.accepted_quantity,
                rejected_quantity=item_data.rejected_quantity,
                unit_price=po_item.unit_price,
                total_ordered_amount=po_item.total_amount,
                total_received_amount=Decimal(str(item_data.received_quantity)) * po_item.unit_price,
                total_accepted_amount=Decimal(str(item_data.accepted_quantity)) * po_item.unit_price,
                quality_status='approved' if item_data.rejected_quantity == 0 else 'rejected',
                rejection_reason=item_data.rejection_reason,
                batch_number=item_data.batch_number,
                expiry_date=item_data.expiry_date,
                notes=item_data.notes
            )
            
            self.session.add(grn_item)
        
        # Update GRN totals
        grn.total_ordered_amount = po.total_amount
        grn.total_received_amount = total_received_amount
        grn.total_accepted_amount = total_accepted_amount
        grn.total_rejected_amount = total_rejected_amount
        
        await self.session.commit()
        
        # Update PO status if needed
        await self.update_po_delivery_status(po_id)
        
        return await self.get_grn_by_id(str(grn.id), user_id)

    async def update_po_delivery_status(self, po_id: str) -> None:
        """Update PO status based on GRN completion"""
        po_query = select(PurchaseOrder).where(PurchaseOrder.id == po_id)
        po_result = await self.session.execute(po_query)
        po = po_result.scalar_one_or_none()
        
        if not po:
            return
            
        # Calculate total ordered quantities
        total_ordered_query = select(func.sum(PurchaseOrderItem.quantity)).where(
            PurchaseOrderItem.po_id == po_id
        )
        total_ordered_result = await self.session.execute(total_ordered_query)
        total_ordered = total_ordered_result.scalar() or 0
        
        # Calculate total received quantities from approved GRNs
        total_received_query = select(func.sum(GRNItem.accepted_quantity)).join(
            GRN, GRNItem.grn_id == GRN.id
        ).where(
            and_(
                GRN.po_id == po_id,
                GRN.status.in_([GRNStatus.APPROVED, GRNStatus.COMPLETED])
            )
        )
        total_received_result = await self.session.execute(total_received_query)
        total_received = total_received_result.scalar() or 0
        
        # Update PO status
        if total_received == 0:
            new_status = PurchaseOrderStatus.APPROVED
        elif total_received < total_ordered:
            new_status = PurchaseOrderStatus.PARTIALLY_RECEIVED
        else:
            new_status = PurchaseOrderStatus.FULLY_RECEIVED
            
        if po.status != new_status:
            po.status = new_status
            po.updated_at = datetime.utcnow()
            await self.session.commit()

    async def get_grns(self, user_id: str, skip: int = 0, limit: int = 100, 
                      status: Optional[str] = None, po_id: Optional[str] = None) -> List[GRNResponse]:
        """Get GRNs with filtering"""
        query = select(GRN).where(GRN.user_id == user_id)
        
        if status:
            query = query.where(GRN.status == status)
        if po_id:
            query = query.where(GRN.po_id == po_id)
            
        query = query.offset(skip).limit(limit)
        result = await self.session.execute(query)
        grns = result.scalars().all()
        
        return [await self._convert_to_response(grn) for grn in grns]

    async def get_grn_by_id(self, grn_id: str, user_id: str) -> Optional[GRNResponse]:
        """Get specific GRN"""
        query = select(GRN).where(
            and_(
                GRN.id == grn_id,
                GRN.user_id == user_id
            )
        )
        result = await self.session.execute(query)
        grn = result.scalar_one_or_none()
        
        if not grn:
            return None
            
        return await self._convert_to_response(grn)

    async def update_grn(self, grn_id: str, grn_data: GRNUpdateRequest, user_id: str) -> Optional[GRNResponse]:
        """Update existing GRN"""
        query = select(GRN).where(
            and_(
                GRN.id == grn_id,
                GRN.user_id == user_id
            )
        )
        result = await self.session.execute(query)
        grn = result.scalar_one_or_none()
        
        if not grn:
            return None
            
        # Update fields
        if grn_data.grn_date:
            grn.grn_date = grn_data.grn_date
        if grn_data.received_date:
            grn.received_date = grn_data.received_date
        if grn_data.delivery_note_number is not None:
            grn.delivery_note_number = grn_data.delivery_note_number
        if grn_data.vehicle_number is not None:
            grn.vehicle_number = grn_data.vehicle_number
        if grn_data.received_by:
            grn.received_by = grn_data.received_by
        if grn_data.quality_check_required is not None:
            grn.quality_check_required = grn_data.quality_check_required
        if grn_data.quality_approved is not None:
            grn.quality_approved = grn_data.quality_approved
        if grn_data.quality_notes is not None:
            grn.quality_notes = grn_data.quality_notes
        if grn_data.notes is not None:
            grn.notes = grn_data.notes
        if grn_data.status:
            grn.status = grn_data.status
            
        grn.updated_at = datetime.utcnow()
        grn.updated_by = user_id
        
        await self.session.commit()
        return await self._convert_to_response(grn)

    async def approve_grn(self, grn_id: str, user_id: str, comments: Optional[str] = None) -> bool:
        """Approve GRN"""
        query = select(GRN).where(
            and_(
                GRN.id == grn_id,
                GRN.user_id == user_id
            )
        )
        result = await self.session.execute(query)
        grn = result.scalar_one_or_none()
        
        if not grn:
            return False
            
        if grn.status != GRNStatus.PENDING_APPROVAL:
            raise ValueError("GRN must be in pending approval status to approve")
            
        grn.status = GRNStatus.APPROVED
        grn.updated_at = datetime.utcnow()
        grn.updated_by = user_id
        
        if comments:
            grn.notes = f"{grn.notes or ''}\nApproval Comments: {comments}".strip()
            
        await self.session.commit()
        
        # Update PO delivery status
        await self.update_po_delivery_status(str(grn.po_id))
        
        return True

    async def reject_grn(self, grn_id: str, user_id: str, reason: str) -> bool:
        """Reject GRN"""
        query = select(GRN).where(
            and_(
                GRN.id == grn_id,
                GRN.user_id == user_id
            )
        )
        result = await self.session.execute(query)
        grn = result.scalar_one_or_none()
        
        if not grn:
            return False
            
        if grn.status != GRNStatus.PENDING_APPROVAL:
            raise ValueError("GRN must be in pending approval status to reject")
            
        grn.status = GRNStatus.REJECTED
        grn.rejection_reason = reason
        grn.updated_at = datetime.utcnow()
        grn.updated_by = user_id
        
        await self.session.commit()
        return True

    async def _convert_to_response(self, grn: GRN) -> GRNResponse:
        """Convert GRN model to response format"""
        # Load related data
        po_query = select(PurchaseOrder).where(PurchaseOrder.id == grn.po_id)
        po_result = await self.session.execute(po_query)
        po = po_result.scalar_one_or_none()
        
        vendor_query = select(Vendor).where(Vendor.id == grn.vendor_id)
        vendor_result = await self.session.execute(vendor_query)
        vendor = vendor_result.scalar_one_or_none()
        
        items_query = select(GRNItem).where(GRNItem.grn_id == grn.id)
        items_result = await self.session.execute(items_query)
        items = items_result.scalars().all()
        
        return GRNResponse(
            id=str(grn.id),
            grn_number=grn.grn_number,
            po_id=str(grn.po_id),
            po_number=po.po_number if po else "",
            vendor_id=str(grn.vendor_id),
            vendor_name=vendor.business_name if vendor else "",
            grn_date=grn.grn_date,
            received_date=grn.received_date,
            delivery_note_number=grn.delivery_note_number,
            vehicle_number=grn.vehicle_number,
            received_by=grn.received_by,
            status=grn.status,
            quality_check_required=grn.quality_check_required,
            quality_approved=grn.quality_approved,
            total_ordered_amount=float(grn.total_ordered_amount),
            total_received_amount=float(grn.total_received_amount),
            total_accepted_amount=float(grn.total_accepted_amount),
            total_rejected_amount=float(grn.total_rejected_amount),
            items=[self._convert_item_to_response(item) for item in items],
            notes=grn.notes,
            created_at=grn.created_at,
            updated_at=grn.updated_at
        )

    def _convert_item_to_response(self, item: GRNItem) -> GRNItemResponse:
        """Convert GRN item to response format"""
        return GRNItemResponse(
            id=str(item.id),
            po_item_id=str(item.po_item_id),
            item_description=item.item_description,
            unit=item.unit,
            ordered_quantity=float(item.ordered_quantity),
            received_quantity=float(item.received_quantity),
            accepted_quantity=float(item.accepted_quantity),
            rejected_quantity=float(item.rejected_quantity),
            unit_price=float(item.unit_price),
            total_received_amount=float(item.total_received_amount),
            quality_status=item.quality_status,
            rejection_reason=item.rejection_reason,
            batch_number=item.batch_number,
            expiry_date=item.expiry_date,
            notes=item.notes
        )


# Factory function to create service with session
async def get_grn_service() -> GRNService:
    """Get GRN service with database session"""
    session = get_postgres_session_direct()
    return GRNService(session)