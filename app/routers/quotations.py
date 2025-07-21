from fastapi import APIRouter, Depends, HTTPException, Query, Path
from fastapi.security import HTTPBearer
from typing import List, Optional
from pydantic import BaseModel, Field
from datetime import datetime, date
from enum import Enum
import uuid

router = APIRouter()
security = HTTPBearer()

# Enums
class QuotationStatus(str, Enum):
    DRAFT = "DRAFT"
    PENDING_APPROVAL = "PENDING_APPROVAL"
    APPROVED = "APPROVED"
    SENT = "SENT"
    ACCEPTED = "ACCEPTED"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"
    CANCELLED = "CANCELLED"

class TermType(str, Enum):
    PAYMENT = "PAYMENT"
    DELIVERY = "DELIVERY"
    WARRANTY = "WARRANTY"
    VALIDITY = "VALIDITY"
    OTHER = "OTHER"

# Pydantic models
class QuotationItem(BaseModel):
    item_service_id: str
    item_name: str
    item_code: str
    hsn_sac_code: str
    quantity: float = Field(..., gt=0)
    unit_price: float = Field(..., ge=0)
    discount_percent: float = Field(0, ge=0, le=100)
    taxable_amount: float = Field(..., ge=0)
    gst_rate: float = Field(..., ge=0)
    cgst_amount: float = Field(0, ge=0)
    sgst_amount: float = Field(0, ge=0)
    igst_amount: float = Field(0, ge=0)
    total_amount: float = Field(..., ge=0)

class TermCondition(BaseModel):
    term_type: TermType
    description: str
    sort_order: int = 1

class QuotationCreate(BaseModel):
    customer_id: str
    quotation_date: date = Field(default_factory=date.today)
    valid_until: date
    items: List[QuotationItem] = Field(..., min_items=1)
    terms_conditions: List[TermCondition] = []
    notes: Optional[str] = None
    discount_percent: float = Field(0, ge=0, le=100)
    
class QuotationResponse(BaseModel):
    id: str
    quotation_number: str
    customer_id: str
    customer_name: str
    quotation_date: date
    valid_until: date
    status: QuotationStatus
    items: List[QuotationItem]
    terms_conditions: List[TermCondition]
    notes: Optional[str]
    subtotal: float
    discount_amount: float
    cgst_amount: float
    sgst_amount: float
    igst_amount: float
    total_amount: float
    created_at: datetime
    updated_at: datetime

class StatusUpdate(BaseModel):
    status: QuotationStatus
    notes: Optional[str] = None

# Mock databases
quotations_db = {}
customers_db = {
    "customer_1": {
        "id": "customer_1",
        "business_name": "Sample Customer Ltd",
        "gstin": "01AAAAP1208Q1ZS",
        "email": "customer@example.com"
    }
}

def calculate_quotation_totals(items: List[QuotationItem], discount_percent: float = 0):
    """Calculate quotation totals."""
    subtotal = sum(item.taxable_amount for item in items)
    discount_amount = subtotal * (discount_percent / 100)
    final_subtotal = subtotal - discount_amount
    
    cgst_total = sum(item.cgst_amount for item in items)
    sgst_total = sum(item.sgst_amount for item in items)
    igst_total = sum(item.igst_amount for item in items)
    
    total_amount = final_subtotal + cgst_total + sgst_total + igst_total
    
    return {
        "subtotal": subtotal,
        "discount_amount": discount_amount,
        "cgst_amount": cgst_total,
        "sgst_amount": sgst_total,
        "igst_amount": igst_total,
        "total_amount": total_amount
    }

@router.post("/companies/{company_id}/quotations", response_model=dict)
async def create_quotation(
    company_id: str = Path(...),
    quotation: QuotationCreate = ...,
    token: str = Depends(security)
):
    """Create a new sales quotation."""
    
    # Validate customer exists
    if quotation.customer_id not in customers_db:
        raise HTTPException(status_code=404, detail="Customer not found")
    
    # Generate quotation number
    quotation_id = str(uuid.uuid4())
    quotation_number = f"QUO-2024-25-A-{len(quotations_db) + 1:04d}"
    
    # Calculate totals
    totals = calculate_quotation_totals(quotation.items, quotation.discount_percent)
    
    # Create quotation record
    new_quotation = {
        "id": quotation_id,
        "quotation_number": quotation_number,
        "company_id": company_id,
        "customer_id": quotation.customer_id,
        "customer_name": customers_db[quotation.customer_id]["business_name"],
        "quotation_date": quotation.quotation_date,
        "valid_until": quotation.valid_until,
        "status": QuotationStatus.DRAFT,
        "items": [item.dict() for item in quotation.items],
        "terms_conditions": [term.dict() for term in quotation.terms_conditions],
        "notes": quotation.notes,
        "discount_percent": quotation.discount_percent,
        **totals,
        "created_at": datetime.now(),
        "updated_at": datetime.now()
    }
    
    quotations_db[quotation_id] = new_quotation
    
    return {
        "success": True,
        "data": new_quotation,
        "message": "Quotation created successfully",
        "errors": [],
        "meta": {
            "timestamp": datetime.now().isoformat(),
            "request_id": f"req_{uuid.uuid4().hex[:12]}"
        }
    }

@router.get("/companies/{company_id}/quotations", response_model=dict)
async def list_quotations(
    company_id: str = Path(...),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    status: Optional[QuotationStatus] = Query(None),
    customer_id: Optional[str] = Query(None),
    date_from: Optional[date] = Query(None),
    date_to: Optional[date] = Query(None),
    token: str = Depends(security)
):
    """List quotations with filters."""
    
    # Filter quotations by company_id
    company_quotations = [
        q for q in quotations_db.values() 
        if q.get("company_id") == company_id
    ]
    
    # Apply filters
    if status:
        company_quotations = [q for q in company_quotations if q.get("status") == status]
    
    if customer_id:
        company_quotations = [q for q in company_quotations if q.get("customer_id") == customer_id]
    
    if date_from:
        company_quotations = [q for q in company_quotations if q.get("quotation_date") >= date_from]
    
    if date_to:
        company_quotations = [q for q in company_quotations if q.get("quotation_date") <= date_to]
    
    # Pagination
    total = len(company_quotations)
    start = (page - 1) * limit
    end = start + limit
    quotations_page = company_quotations[start:end]
    
    return {
        "success": True,
        "data": {
            "quotations": quotations_page,
            "pagination": {
                "page": page,
                "limit": limit,
                "total": total,
                "pages": (total + limit - 1) // limit
            }
        },
        "message": f"Retrieved {len(quotations_page)} quotations",
        "errors": [],
        "meta": {
            "timestamp": datetime.now().isoformat(),
            "request_id": f"req_{uuid.uuid4().hex[:12]}"
        }
    }

@router.get("/companies/{company_id}/quotations/{quotation_id}", response_model=dict)
async def get_quotation(
    company_id: str = Path(...),
    quotation_id: str = Path(...),
    token: str = Depends(security)
):
    """Get quotation details."""
    
    if quotation_id not in quotations_db:
        raise HTTPException(status_code=404, detail="Quotation not found")
    
    quotation = quotations_db[quotation_id]
    
    # Verify quotation belongs to company
    if quotation.get("company_id") != company_id:
        raise HTTPException(status_code=403, detail="Access denied")
    
    return {
        "success": True,
        "data": quotation,
        "message": "Quotation retrieved successfully",
        "errors": [],
        "meta": {
            "timestamp": datetime.now().isoformat(),
            "request_id": f"req_{uuid.uuid4().hex[:12]}"
        }
    }

@router.patch("/companies/{company_id}/quotations/{quotation_id}/status", response_model=dict)
async def update_quotation_status(
    company_id: str = Path(...),
    quotation_id: str = Path(...),
    status_update: StatusUpdate = ...,
    token: str = Depends(security)
):
    """Update quotation status."""
    
    if quotation_id not in quotations_db:
        raise HTTPException(status_code=404, detail="Quotation not found")
    
    quotation = quotations_db[quotation_id]
    
    # Verify quotation belongs to company
    if quotation.get("company_id") != company_id:
        raise HTTPException(status_code=403, detail="Access denied")
    
    # Validate status transition
    current_status = quotation.get("status")
    new_status = status_update.status
    
    # Define valid transitions (simplified)
    valid_transitions = {
        QuotationStatus.DRAFT: [QuotationStatus.PENDING_APPROVAL, QuotationStatus.CANCELLED],
        QuotationStatus.PENDING_APPROVAL: [QuotationStatus.APPROVED, QuotationStatus.DRAFT],
        QuotationStatus.APPROVED: [QuotationStatus.SENT],
        QuotationStatus.SENT: [QuotationStatus.ACCEPTED, QuotationStatus.REJECTED, QuotationStatus.EXPIRED]
    }
    
    if current_status not in valid_transitions or new_status not in valid_transitions[current_status]:
        raise HTTPException(
            status_code=422, 
            detail=f"Invalid status transition from {current_status} to {new_status}"
        )
    
    # Update quotation
    quotation["status"] = new_status
    quotation["updated_at"] = datetime.now()
    
    if status_update.notes:
        quotation["status_notes"] = status_update.notes
    
    # Special handling for status changes
    if new_status == QuotationStatus.SENT:
        quotation["sent_at"] = datetime.now()
    elif new_status == QuotationStatus.APPROVED:
        quotation["approved_at"] = datetime.now()
    
    return {
        "success": True,
        "data": quotation,
        "message": f"Quotation status updated to {new_status}",
        "errors": [],
        "meta": {
            "timestamp": datetime.now().isoformat(),
            "request_id": f"req_{uuid.uuid4().hex[:12]}"
        }
    }

@router.post("/companies/{company_id}/quotations/{quotation_id}/convert-to-order", response_model=dict)
async def convert_to_sales_order(
    company_id: str = Path(...),
    quotation_id: str = Path(...),
    token: str = Depends(security)
):
    """Convert quotation to sales order."""
    
    if quotation_id not in quotations_db:
        raise HTTPException(status_code=404, detail="Quotation not found")
    
    quotation = quotations_db[quotation_id]
    
    # Verify quotation belongs to company
    if quotation.get("company_id") != company_id:
        raise HTTPException(status_code=403, detail="Access denied")
    
    # Check if quotation is accepted
    if quotation.get("status") != QuotationStatus.ACCEPTED:
        raise HTTPException(
            status_code=422, 
            detail="Only accepted quotations can be converted to sales orders"
        )
    
    # Generate sales order (mock)
    order_id = str(uuid.uuid4())
    order_number = f"SO-2024-25-A-{len(quotations_db) + 1:04d}"
    
    sales_order = {
        "id": order_id,
        "order_number": order_number,
        "quotation_id": quotation_id,
        "company_id": company_id,
        "customer_id": quotation["customer_id"],
        "order_date": date.today(),
        "status": "DRAFT",
        "items": quotation["items"],
        "total_amount": quotation["total_amount"],
        "created_at": datetime.now()
    }
    
    # Update quotation status
    quotation["status"] = QuotationStatus.CONVERTED
    quotation["converted_to_order_id"] = order_id
    quotation["updated_at"] = datetime.now()
    
    return {
        "success": True,
        "data": {
            "sales_order": sales_order,
            "quotation": quotation
        },
        "message": "Quotation converted to sales order successfully",
        "errors": [],
        "meta": {
            "timestamp": datetime.now().isoformat(),
            "request_id": f"req_{uuid.uuid4().hex[:12]}"
        }
    }

@router.get("/companies/{company_id}/quotations/{quotation_id}/pdf", response_model=dict)
async def generate_quotation_pdf(
    company_id: str = Path(...),
    quotation_id: str = Path(...),
    token: str = Depends(security)
):
    """Generate quotation PDF."""
    
    if quotation_id not in quotations_db:
        raise HTTPException(status_code=404, detail="Quotation not found")
    
    quotation = quotations_db[quotation_id]
    
    # Mock PDF generation
    pdf_url = f"https://api.jusfinn.com/v1/documents/quotations/{quotation_id}.pdf"
    
    return {
        "success": True,
        "data": {
            "pdf_url": pdf_url,
            "quotation_number": quotation["quotation_number"],
            "generated_at": datetime.now().isoformat()
        },
        "message": "Quotation PDF generated successfully",
        "errors": [],
        "meta": {
            "timestamp": datetime.now().isoformat(),
            "request_id": f"req_{uuid.uuid4().hex[:12]}"
        }
    } 