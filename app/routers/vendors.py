from fastapi import APIRouter, HTTPException, Depends, Query
from typing import List, Optional, Dict, Any

from app.services.vendor_service import vendor_service
from app.services.jwt_service import jwt_service
from app.services.user_service import user_service
from app.models import (
    VendorResponse, VendorCreateRequest, VendorUpdateRequest
)

router = APIRouter(prefix="/vendors", tags=["Vendors"])


async def get_user_id(token: dict = Depends(jwt_service.get_current_user)) -> str:
    """Helper function to get user's ID from JWT token."""
    try:
        user_id = token.get("sub")
        if not user_id:
            raise HTTPException(status_code=401, detail="Invalid token: missing user ID")
        
        user = await user_service.get_user_by_id(user_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        return user_id  # Return user_id directly instead of user.google_id
    except Exception as e:
        raise HTTPException(status_code=401, detail=f"Invalid token: {str(e)}")
    """Helper function to get user's Google ID from JWT token."""
    try:
        user_id = token.get("sub")
        if not user_id:
            raise HTTPException(status_code=401, detail="Invalid token: missing user ID")
        
        user = await user_service.get_user_by_id(user_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        return user.google_id
    except Exception as e:
        raise HTTPException(status_code=401, detail=f"Invalid token: {str(e)}")


@router.post("/", response_model=VendorResponse)
async def create_vendor(
    vendor_data: VendorCreateRequest,
    user_id: str = Depends(get_user_id)
):
    """Create a new vendor."""
    try:
        vendor = await vendor_service.create_vendor(vendor_data, user_id)
        return vendor
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create vendor: {str(e)}")


@router.get("/", response_model=List[VendorResponse])
async def get_vendors(
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(100, ge=1, le=100, description="Maximum number of records to return"),
    status: Optional[str] = Query(None, description="Filter by vendor status (active/inactive)"),
    is_msme: Optional[bool] = Query(None, description="Filter by MSME status"),
    search: Optional[str] = Query(None, description="Search by name, code, email, PAN, or GST"),
    user_id: str = Depends(get_user_id)
):
    """Get all vendors for the current user with optional filtering."""
    try:
        vendors = await vendor_service.get_vendors(
            user_id=user_id,
            skip=skip,
            limit=limit,
            status=status,
            is_msme=is_msme,
            search=search
        )
        return vendors
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch vendors: {str(e)}")


@router.get("/search", response_model=List[Dict[str, Any]])
async def search_vendors(
    q: str = Query(..., description="Search term for vendor name or code"),
    user_id: str = Depends(get_user_id)
):
    """Search vendors by name or code for dropdown/autocomplete."""
    try:
        vendors = await vendor_service.search_vendors_by_name_or_code(q, user_id)
        return vendors
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to search vendors: {str(e)}")


@router.get("/stats", response_model=Dict[str, Any])
async def get_vendor_stats(
    user_id: str = Depends(get_user_id)
):
    """Get vendor statistics and analytics."""
    try:
        stats = await vendor_service.get_vendor_stats(user_id)
        return stats
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch vendor stats: {str(e)}")


@router.get("/{vendor_id}", response_model=VendorResponse)
async def get_vendor(
    vendor_id: str,
    user_id: str = Depends(get_user_id)
):
    """Get vendor by ID."""
    try:
        vendor = await vendor_service.get_vendor_by_id(vendor_id, user_id)
        if not vendor:
            raise HTTPException(status_code=404, detail="Vendor not found")
        return vendor
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch vendor: {str(e)}")


@router.put("/{vendor_id}", response_model=VendorResponse)
async def update_vendor(
    vendor_id: str,
    update_data: VendorUpdateRequest,
    user_id: str = Depends(get_user_id)
):
    """Update vendor information."""
    try:
        vendor = await vendor_service.update_vendor(vendor_id, update_data, user_id)
        if not vendor:
            raise HTTPException(status_code=404, detail="Vendor not found or no changes made")
        return vendor
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update vendor: {str(e)}")


@router.delete("/{vendor_id}")
async def delete_vendor(
    vendor_id: str,
    user_id: str = Depends(get_user_id)
):
    """Delete vendor (soft delete by setting is_active to False)."""
    try:
        success = await vendor_service.delete_vendor(vendor_id, user_id)
        if not success:
            raise HTTPException(status_code=404, detail="Vendor not found")
        return {"message": "Vendor deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete vendor: {str(e)}")


@router.patch("/{vendor_id}/status")
async def update_vendor_status(
    vendor_id: str,
    is_active: bool,
    user_id: str = Depends(get_user_id)
):
    """Update vendor status (active/inactive)."""
    try:
        update_data = VendorUpdateRequest(is_active=is_active)
        vendor = await vendor_service.update_vendor(
            vendor_id, 
            update_data, 
            user_id
        )
        if not vendor:
            raise HTTPException(status_code=404, detail="Vendor not found")
        status_text = "active" if is_active else "inactive"
        return {"message": f"Vendor status updated to {status_text}"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update vendor status: {str(e)}") 