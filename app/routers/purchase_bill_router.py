
from fastapi import APIRouter, HTTPException, Depends, Query
from typing import List, Optional
from app.services.jwt_service import jwt_service
from app.services.purchase_bill_service import purchase_bill_service
from app.models.purchase_bill_models import PurchaseBillCreateRequest, PurchaseBillResponse

router = APIRouter(prefix="/purchase-bills", tags=["Purchase Bills"])

async def get_user_id(token: dict = Depends(jwt_service.get_current_user)) -> str:
    user_id = token.get("sub")
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid token: missing user ID")
    return user_id

@router.post("", response_model=PurchaseBillResponse)
async def create_purchase_bill(
    bill_data: PurchaseBillCreateRequest,
    user_id: str = Depends(get_user_id)
):
    try:
        bill = await purchase_bill_service.create_purchase_bill(bill_data, user_id)
        return bill
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create purchase bill: {str(e)}")

@router.get("", response_model=List[PurchaseBillResponse])
async def get_purchase_bills(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=100),
    status: Optional[str] = Query(None),
    po_id: Optional[str] = Query(None),
    user_id: str = Depends(get_user_id)
):
    try:
        bills = await purchase_bill_service.get_purchase_bills(
            user_id=user_id,
            skip=skip,
            limit=limit,
            status=status,
            po_id=po_id
        )
        return bills
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch purchase bills: {str(e)}")

@router.get("/{bill_id}", response_model=PurchaseBillResponse)
async def get_purchase_bill_by_id(
    bill_id: str,
    user_id: str = Depends(get_user_id)
):
    try:
        bill = await purchase_bill_service.get_purchase_bill_by_id(bill_id, user_id)
        if not bill:
            raise HTTPException(status_code=404, detail="Purchase Bill not found")
        return bill
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch purchase bill: {str(e)}")
