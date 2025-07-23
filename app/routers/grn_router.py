from fastapi import APIRouter, HTTPException, Depends, Query
from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_postgres_session
from app.services.jwt_service import jwt_service
from app.services.grn_service import GRNService
from app.models.grn_models import GRNCreateRequest, GRNUpdateRequest, GRNResponse, GRNStatus, StatusChangeRequest, StatusChangeResponse

router = APIRouter(prefix="/grns", tags=["GRN - Goods Receipt Note"])


async def get_user_id(token: dict = Depends(jwt_service.get_current_user)) -> str:
    user_id = token.get('sub') or token.get('user_id')
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid token: no user ID found")
    return user_id


@router.post("/from-po/{po_id}", response_model=GRNResponse)
async def create_grn_from_po(
    po_id: str,
    grn_data: GRNCreateRequest,
    user_id: str = Depends(get_user_id),
    session: AsyncSession = Depends(get_postgres_session)
):
    """Create GRN from Purchase Order"""
    try:
        service = GRNService(session)
        grn = await service.create_grn_from_po(po_id, grn_data, user_id)
        return grn
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create GRN: {str(e)}")


@router.get("", response_model=List[GRNResponse])
async def get_grns(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=100),
    status: Optional[str] = Query(None),
    po_id: Optional[str] = Query(None),
    user_id: str = Depends(get_user_id),
    session: AsyncSession = Depends(get_postgres_session)
):
    """Get GRNs with filtering"""
    try:
        service = GRNService(session)
        grns = await service.get_grns(user_id, skip, limit, status, po_id)
        return grns
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch GRNs: {str(e)}")


@router.get("/{grn_id}", response_model=GRNResponse)
async def get_grn(
    grn_id: str,
    user_id: str = Depends(get_user_id),
    session: AsyncSession = Depends(get_postgres_session)
):
    """Get specific GRN"""
    try:
        service = GRNService(session)
        grn = await service.get_grn_by_id(grn_id, user_id)
        if not grn:
            raise HTTPException(status_code=404, detail="GRN not found")
        return grn
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch GRN: {str(e)}")


@router.put("/{grn_id}", response_model=GRNResponse)
async def update_grn(
    grn_id: str,
    grn_data: GRNUpdateRequest,
    user_id: str = Depends(get_user_id),
    session: AsyncSession = Depends(get_postgres_session)
):
    """Update existing GRN"""
    try:
        service = GRNService(session)
        grn = await service.update_grn(grn_id, grn_data, user_id)
        if not grn:
            raise HTTPException(status_code=404, detail="GRN not found")
        return grn
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update GRN: {str(e)}")


@router.post("/{grn_id}/approve", response_model=StatusChangeResponse)
async def approve_grn(
    grn_id: str,
    comments: Optional[str] = Query(None),
    user_id: str = Depends(get_user_id),
    session: AsyncSession = Depends(get_postgres_session)
):
    """Approve GRN"""
    try:
        service = GRNService(session)
        success = await service.approve_grn(grn_id, user_id, comments)
        if not success:
            raise HTTPException(status_code=404, detail="GRN not found")
        
        return StatusChangeResponse(
            success=True,
            message="GRN approved successfully",
            new_status=GRNStatus.APPROVED
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to approve GRN: {str(e)}")


@router.post("/{grn_id}/reject", response_model=StatusChangeResponse)
async def reject_grn(
    grn_id: str,
    reason: str = Query(..., description="Reason for rejection"),
    user_id: str = Depends(get_user_id),
    session: AsyncSession = Depends(get_postgres_session)
):
    """Reject GRN"""
    try:
        service = GRNService(session)
        success = await service.reject_grn(grn_id, user_id, reason)
        if not success:
            raise HTTPException(status_code=404, detail="GRN not found")
        
        return StatusChangeResponse(
            success=True,
            message="GRN rejected successfully",
            new_status=GRNStatus.REJECTED
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to reject GRN: {str(e)}")


@router.patch("/{grn_id}/status", response_model=StatusChangeResponse)
async def change_grn_status(
    grn_id: str,
    status_data: StatusChangeRequest,
    user_id: str = Depends(get_user_id),
    session: AsyncSession = Depends(get_postgres_session)
):
    """Change GRN status"""
    try:
        service = GRNService(session)
        
        # Create update request with just status
        update_request = GRNUpdateRequest(
            status=status_data.status,
            notes=status_data.notes
        )
        
        grn = await service.update_grn(grn_id, update_request, user_id)
        if not grn:
            raise HTTPException(status_code=404, detail="GRN not found")
        
        return StatusChangeResponse(
            success=True,
            message=f"GRN status changed to {status_data.status}",
            new_status=status_data.status
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to change GRN status: {str(e)}")


@router.get("/po/{po_id}/available-items")
async def get_po_items_for_grn(
    po_id: str,
    user_id: str = Depends(get_user_id),
    session: AsyncSession = Depends(get_postgres_session)
):
    """Get PO items available for GRN creation"""
    try:
        from app.models.purchase_order_models import PurchaseOrder, PurchaseOrderItem
        from sqlalchemy import select, and_
        
        # Verify PO exists and belongs to user
        po_query = select(PurchaseOrder).where(
            and_(
                PurchaseOrder.id == po_id,
                PurchaseOrder.user_id == user_id
            )
        )
        po_result = await session.execute(po_query)
        po = po_result.scalar_one_or_none()
        
        if not po:
            raise HTTPException(status_code=404, detail="Purchase Order not found")
        
        # Get PO items
        items_query = select(PurchaseOrderItem).where(PurchaseOrderItem.po_id == po_id)
        items_result = await session.execute(items_query)
        items = items_result.scalars().all()
        
        # Format response
        return {
            "po_id": str(po.id),
            "po_number": po.po_number,
            "vendor_id": str(po.vendor_id),
            "items": [
                {
                    "id": str(item.id),
                    "item_description": item.item_description,
                    "unit": item.unit,
                    "ordered_quantity": float(item.quantity),
                    "received_quantity": float(item.received_quantity or 0),
                    "pending_quantity": float(item.quantity - (item.received_quantity or 0)),
                    "unit_price": float(item.unit_price),
                    "total_amount": float(item.total_amount)
                }
                for item in items
            ]
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch PO items: {str(e)}")


@router.get("/dashboard/summary")
async def get_grn_dashboard_summary(
    user_id: str = Depends(get_user_id),
    session: AsyncSession = Depends(get_postgres_session)
):
    """Get GRN dashboard summary statistics"""
    try:
        from sqlalchemy import select, func, and_
        from datetime import datetime, timedelta
        
        # Total GRNs by status
        status_query = select(
            GRN.status,
            func.count(GRN.id).label('count')
        ).where(GRN.user_id == user_id).group_by(GRN.status)
        
        status_result = await session.execute(status_query)
        status_counts = {row.status: row.count for row in status_result}
        
        # Recent GRNs (last 30 days)
        thirty_days_ago = datetime.now() - timedelta(days=30)
        recent_query = select(func.count(GRN.id)).where(
            and_(
                GRN.user_id == user_id,
                GRN.created_at >= thirty_days_ago
            )
        )
        recent_result = await session.execute(recent_query)
        recent_count = recent_result.scalar() or 0
        
        # Pending approvals
        pending_count = status_counts.get(GRNStatus.PENDING_APPROVAL, 0)
        
        # Total value received
        value_query = select(func.sum(GRN.total_accepted_amount)).where(
            and_(
                GRN.user_id == user_id,
                GRN.status == GRNStatus.APPROVED
            )
        )
        value_result = await session.execute(value_query)
        total_value = float(value_result.scalar() or 0)
        
        return {
            "total_grns": sum(status_counts.values()),
            "status_breakdown": status_counts,
            "pending_approvals": pending_count,
            "recent_grns": recent_count,
            "total_value_received": total_value,
            "average_grn_value": total_value / max(sum(status_counts.values()), 1)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch dashboard summary: {str(e)}")