from fastapi import APIRouter, HTTPException, Depends, Query
from typing import List, Dict, Any, Optional
from app.services.jwt_service import jwt_service
from app.services.grn_service import grn_service
from app.models.grn_models import GRNCreateRequest, GRNResponse

router = APIRouter(prefix="/grns", tags=["GRN - Goods Receipt Note"])

async def get_user_id(token: dict = Depends(jwt_service.get_current_user)) -> str:
    """Helper function to get user's ID from JWT token."""
    print(f"🔍 GRN AUTH DEBUG: get_user_id called")
    print(f"   Token: {token}")
    
    try:
        user_id = token.get("sub")
        print(f"🔍 GRN AUTH DEBUG: Extracted user_id from token: {user_id}")
        
        if not user_id:
            print(f"🔍 GRN AUTH DEBUG: No user_id in token")
            raise HTTPException(status_code=401, detail="Invalid token: missing user ID")
        
        print(f"🔍 GRN AUTH DEBUG: Returning user_id: {user_id}")
        return user_id
    except HTTPException:
        raise
    except Exception as e:
        print(f"🔍 GRN AUTH DEBUG: Exception in get_user_id: {str(e)}")
        raise HTTPException(status_code=401, detail=f"Invalid token: {str(e)}")

@router.post("", response_model=GRNResponse)
async def create_grn(
    grn_data: GRNCreateRequest,
    user_id: str = Depends(get_user_id)
):
    """Create a new Goods Receipt Note."""
    try:
        print(f"🔍 Creating GRN for user: {user_id}")
        print(f"🔍 GRN data: {grn_data}")
        
        grn = await grn_service.create_grn(grn_data, user_id)
        return grn
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        print(f"❌ Error creating GRN: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to create GRN: {str(e)}")

@router.get("", response_model=List[GRNResponse])
async def get_grns(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=100),
    status: Optional[str] = Query(None),
    po_id: Optional[str] = Query(None),
    user_id: str = Depends(get_user_id)
):
    """Get GRNs for user with optional filtering."""
    try:
        print(f"🔍 Fetching GRNs for user: {user_id}")
        print(f"🔍 Filters - skip: {skip}, limit: {limit}, status: {status}, po_id: {po_id}")
        
        grns = await grn_service.get_grns(
            user_id=user_id,
            skip=skip,
            limit=limit,
            status=status,
            po_id=po_id
        )
        print(f"🔍 Found {len(grns)} GRNs")
        return grns
    except Exception as e:
        print(f"❌ Error fetching GRNs: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch GRNs: {str(e)}")

@router.get("/{grn_id}", response_model=GRNResponse)
async def get_grn_by_id(
    grn_id: str,
    user_id: str = Depends(get_user_id)
):
    """Get specific GRN by ID."""
    try:
        print(f"🔍 Fetching GRN {grn_id} for user: {user_id}")
        
        grn = await grn_service.get_grn_by_id(grn_id, user_id)
        
        if not grn:
            raise HTTPException(status_code=404, detail="GRN not found")
        
        return grn
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Error fetching GRN {grn_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch GRN: {str(e)}")

@router.get("/po/{po_id}/available-items")
async def get_po_available_items(
    po_id: str,
    user_id: str = Depends(get_user_id)
):
    """Get available items from Purchase Order for GRN creation."""
    try:
        print(f"🔍 Fetching PO {po_id} available items for user: {user_id}")
        
        po_items = await grn_service.get_po_available_items(po_id, user_id)
        return po_items
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        print(f"❌ Error fetching PO items for {po_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch PO items: {str(e)}")

@router.post("/from-po/{po_id}")
async def create_grn_from_po(
    po_id: str,
    grn_data: Dict[str, Any],
    user_id: str = Depends(get_user_id)
):
    """Create GRN from specific Purchase Order (simplified interface)."""
    try:
        print(f"🔍 Creating GRN from PO {po_id} for user: {user_id}")
        print(f"🔍 GRN data: {grn_data}")
        
        # Convert flexible dict to proper GRNCreateRequest
        from datetime import datetime
        
        # Extract data with defaults
        grn_request = GRNCreateRequest(
            po_id=po_id,
            grn_number=grn_data.get("grn_number"),
            received_date=datetime.fromisoformat(grn_data.get("received_date", datetime.now().isoformat())),
            received_by=grn_data.get("received_by", "System"),
            warehouse_location=grn_data.get("warehouse_location", "Main Warehouse"),
            items=grn_data.get("items", []),
            delivery_note_number=grn_data.get("delivery_note_number"),
            vehicle_number=grn_data.get("vehicle_number"),
            driver_name=grn_data.get("driver_name"),
            general_notes=grn_data.get("general_notes")
        )
        
        grn = await grn_service.create_grn(grn_request, user_id)
        
        # Return simple success response for frontend compatibility
        return {
            "success": True,
            "message": "GRN created successfully",
            "grn_id": grn.id,
            "grn_number": grn.grn_number,
            "po_id": po_id,
            "grn": grn
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        print(f"❌ Error creating GRN from PO {po_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to create GRN from PO: {str(e)}") 

@router.get("/po/{po_id}/grn-summary")
async def get_po_grn_summary(
    po_id: str,
    user_id: str = Depends(get_user_id)
):
    """Get summary of all GRNs created against a specific Purchase Order."""
    try:
        print(f"🔍 Fetching GRN summary for PO {po_id} for user: {user_id}")
        
        po_grn_summary = await grn_service.get_po_grn_summary(po_id, user_id)
        return po_grn_summary
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        print(f"❌ Error fetching PO GRN summary for {po_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch PO GRN summary: {str(e)}") 

@router.put("/{grn_id}/complete")
async def complete_draft_grn(
    grn_id: str,
    user_id: str = Depends(get_user_id)
):
    """Complete a draft GRN and update PO quantities."""
    try:
        print(f"🔄 Completing draft GRN {grn_id} for user: {user_id}")
        
        completed_grn = await grn_service.complete_draft_grn(grn_id, user_id)
        return completed_grn
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        print(f"❌ Error completing GRN {grn_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to complete GRN: {str(e)}")

@router.put("/{grn_id}")
async def update_grn(
    grn_id: str,
    grn_data: GRNCreateRequest,
    user_id: str = Depends(get_user_id)
):
    """Update a GRN (only allowed for draft status)."""
    try:
        print(f"✏️ Updating GRN {grn_id} for user: {user_id}")
        
        updated_grn = await grn_service.update_grn(grn_id, grn_data, user_id)
        return updated_grn
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        print(f"❌ Error updating GRN {grn_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to update GRN: {str(e)}") 

@router.put("/{grn_id}/cancel")
async def cancel_grn(
    grn_id: str,
    user_id: str = Depends(get_user_id)
):
    """Cancel a draft GRN."""
    try:
        print(f"🗑️ Cancelling GRN {grn_id} for user: {user_id}")
        
        cancelled_grn = await grn_service.cancel_grn(grn_id, user_id)
        return cancelled_grn
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        print(f"❌ Error cancelling GRN {grn_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to cancel GRN: {str(e)}") 

@router.post("/fix-po-statuses")
async def fix_po_statuses_for_completed_grns(
    user_id: str = Depends(get_user_id)
):
    """Fix PO statuses for all completed GRNs that may have missed the status update."""
    try:
        print(f"🔧 Fixing PO statuses for completed GRNs for user: {user_id}")
        
        fixed_pos = await grn_service.fix_po_statuses_for_completed_grns(user_id)
        
        return {
            "message": "PO statuses fixed successfully",
            "fixed_pos": fixed_pos,
            "count": len(fixed_pos)
        }
    except Exception as e:
        print(f"❌ Error fixing PO statuses: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to fix PO statuses: {str(e)}") 