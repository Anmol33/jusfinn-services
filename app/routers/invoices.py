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
class InvoiceStatus(str, Enum):
    DRAFT = "DRAFT"
    PENDING_APPROVAL = "PENDING_APPROVAL"
    APPROVED = "APPROVED"
    EINVOICE_PENDING = "EINVOICE_PENDING"
    EINVOICE_GENERATED = "EINVOICE_GENERATED"
    EINVOICE_CANCELLED = "EINVOICE_CANCELLED"
    SENT = "SENT"
    PARTIALLY_PAID = "PARTIALLY_PAID"
    PAID = "PAID"
    OVERDUE = "OVERDUE"
    CANCELLED = "CANCELLED"
    CREDIT_NOTE_ISSUED = "CREDIT_NOTE_ISSUED"

class SupplyType(str, Enum):
    GOODS = "GOODS"
    SERVICES = "SERVICES"
    BOTH = "BOTH"

class PaymentMethod(str, Enum):
    CASH = "CASH"
    BANK_TRANSFER = "BANK_TRANSFER"
    CHEQUE = "CHEQUE"
    CARD = "CARD"
    UPI = "UPI"
    OTHER = "OTHER"

# Pydantic models
class InvoiceItem(BaseModel):
    item_service_id: str
    item_name: str
    item_code: str
    hsn_sac_code: str
    quantity: float = Field(..., gt=0)
    unit_price: float = Field(..., ge=0)
    discount_percent: float = Field(0, ge=0, le=100)
    taxable_amount: float = Field(..., ge=0)
    gst_rate: float = Field(..., ge=0)
    cgst_rate: float = Field(..., ge=0)
    sgst_rate: float = Field(..., ge=0)
    igst_rate: float = Field(..., ge=0)
    cgst_amount: float = Field(0, ge=0)
    sgst_amount: float = Field(0, ge=0)
    igst_amount: float = Field(0, ge=0)
    cess_amount: float = Field(0, ge=0)
    total_amount: float = Field(..., ge=0)

class InvoiceCreate(BaseModel):
    customer_id: str
    sales_order_id: Optional[str] = None
    delivery_challan_id: Optional[str] = None
    invoice_date: date = Field(default_factory=date.today)
    place_of_supply_state_id: int
    supply_type: SupplyType = SupplyType.GOODS
    items: List[InvoiceItem] = Field(..., min_items=1)
    payment_terms: str = "NET_30"
    notes: Optional[str] = None
    reverse_charge_applicable: bool = False

class PaymentCreate(BaseModel):
    payment_amount: float = Field(..., gt=0)
    payment_date: date = Field(default_factory=date.today)
    payment_method: PaymentMethod
    reference_number: str
    notes: Optional[str] = None

class EInvoiceCancel(BaseModel):
    cancel_reason: str
    cancel_remarks: str

# Mock databases
invoices_db = {}
customers_db = {
    "customer_1": {
        "id": "customer_1",
        "business_name": "Sample Customer Ltd",
        "gstin": "01AAAAP1208Q1ZS",
        "email": "customer@example.com",
        "state_id": 2
    }
}

def is_einvoice_applicable(total_amount: float, customer_gstin: str = None) -> bool:
    """Check if E-Invoice is applicable."""
    # E-Invoice applicable for B2B invoices >= 5 lakhs
    return total_amount >= 500000 and customer_gstin is not None

def calculate_invoice_totals(items: List[InvoiceItem]):
    """Calculate invoice totals."""
    subtotal = sum(item.taxable_amount for item in items)
    cgst_total = sum(item.cgst_amount for item in items)
    sgst_total = sum(item.sgst_amount for item in items)
    igst_total = sum(item.igst_amount for item in items)
    cess_total = sum(item.cess_amount for item in items)
    
    total_amount = subtotal + cgst_total + sgst_total + igst_total + cess_total
    
    return {
        "subtotal": subtotal,
        "cgst_amount": cgst_total,
        "sgst_amount": sgst_total,
        "igst_amount": igst_total,
        "cess_amount": cess_total,
        "total_amount": total_amount,
        "outstanding_amount": total_amount
    }

@router.post("/companies/{company_id}/tax-invoices", response_model=dict)
async def create_tax_invoice(
    company_id: str = Path(...),
    invoice: InvoiceCreate = ...,
    token: str = Depends(security)
):
    """Create a new tax invoice."""
    
    # Validate customer exists
    if invoice.customer_id not in customers_db:
        raise HTTPException(status_code=404, detail="Customer not found")
    
    customer = customers_db[invoice.customer_id]
    
    # Generate invoice number
    invoice_id = str(uuid.uuid4())
    invoice_number = f"INV-2024-25-A-{len(invoices_db) + 1:04d}"
    
    # Calculate totals
    totals = calculate_invoice_totals(invoice.items)
    
    # Check E-Invoice applicability
    einvoice_applicable = is_einvoice_applicable(totals["total_amount"], customer.get("gstin"))
    
    # Create invoice record
    new_invoice = {
        "id": invoice_id,
        "invoice_number": invoice_number,
        "company_id": company_id,
        "customer_id": invoice.customer_id,
        "customer_name": customer["business_name"],
        "customer_gstin": customer.get("gstin"),
        "sales_order_id": invoice.sales_order_id,
        "delivery_challan_id": invoice.delivery_challan_id,
        "invoice_date": invoice.invoice_date,
        "place_of_supply_state_id": invoice.place_of_supply_state_id,
        "supply_type": invoice.supply_type,
        "reverse_charge_applicable": invoice.reverse_charge_applicable,
        "status": InvoiceStatus.DRAFT,
        "items": [item.dict() for item in invoice.items],
        "payment_terms": invoice.payment_terms,
        "notes": invoice.notes,
        **totals,
        "einvoice_applicable": einvoice_applicable,
        "einvoice_status": "NOT_APPLICABLE" if not einvoice_applicable else "PENDING",
        "payments": [],
        "created_at": datetime.now(),
        "updated_at": datetime.now()
    }
    
    invoices_db[invoice_id] = new_invoice
    
    return {
        "success": True,
        "data": new_invoice,
        "message": "Tax invoice created successfully",
        "errors": [],
        "meta": {
            "timestamp": datetime.now().isoformat(),
            "request_id": f"req_{uuid.uuid4().hex[:12]}"
        }
    }

@router.get("/companies/{company_id}/tax-invoices", response_model=dict)
async def list_tax_invoices(
    company_id: str = Path(...),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    status: Optional[InvoiceStatus] = Query(None),
    customer_id: Optional[str] = Query(None),
    date_from: Optional[date] = Query(None),
    date_to: Optional[date] = Query(None),
    einvoice_status: Optional[str] = Query(None),
    token: str = Depends(security)
):
    """List tax invoices with filters."""
    
    # Filter invoices by company_id
    company_invoices = [
        inv for inv in invoices_db.values() 
        if inv.get("company_id") == company_id
    ]
    
    # Apply filters
    if status:
        company_invoices = [inv for inv in company_invoices if inv.get("status") == status]
    
    if customer_id:
        company_invoices = [inv for inv in company_invoices if inv.get("customer_id") == customer_id]
    
    if date_from:
        company_invoices = [inv for inv in company_invoices if inv.get("invoice_date") >= date_from]
    
    if date_to:
        company_invoices = [inv for inv in company_invoices if inv.get("invoice_date") <= date_to]
    
    if einvoice_status:
        company_invoices = [inv for inv in company_invoices if inv.get("einvoice_status") == einvoice_status]
    
    # Pagination
    total = len(company_invoices)
    start = (page - 1) * limit
    end = start + limit
    invoices_page = company_invoices[start:end]
    
    return {
        "success": True,
        "data": {
            "invoices": invoices_page,
            "pagination": {
                "page": page,
                "limit": limit,
                "total": total,
                "pages": (total + limit - 1) // limit
            }
        },
        "message": f"Retrieved {len(invoices_page)} invoices",
        "errors": [],
        "meta": {
            "timestamp": datetime.now().isoformat(),
            "request_id": f"req_{uuid.uuid4().hex[:12]}"
        }
    }

@router.get("/companies/{company_id}/tax-invoices/{invoice_id}", response_model=dict)
async def get_invoice(
    company_id: str = Path(...),
    invoice_id: str = Path(...),
    token: str = Depends(security)
):
    """Get invoice details."""
    
    if invoice_id not in invoices_db:
        raise HTTPException(status_code=404, detail="Invoice not found")
    
    invoice = invoices_db[invoice_id]
    
    # Verify invoice belongs to company
    if invoice.get("company_id") != company_id:
        raise HTTPException(status_code=403, detail="Access denied")
    
    return {
        "success": True,
        "data": invoice,
        "message": "Invoice retrieved successfully",
        "errors": [],
        "meta": {
            "timestamp": datetime.now().isoformat(),
            "request_id": f"req_{uuid.uuid4().hex[:12]}"
        }
    }

@router.patch("/companies/{company_id}/tax-invoices/{invoice_id}/status", response_model=dict)
async def update_invoice_status(
    company_id: str = Path(...),
    invoice_id: str = Path(...),
    status_update: dict = ...,
    token: str = Depends(security)
):
    """Update invoice status."""
    
    if invoice_id not in invoices_db:
        raise HTTPException(status_code=404, detail="Invoice not found")
    
    invoice = invoices_db[invoice_id]
    
    # Verify invoice belongs to company
    if invoice.get("company_id") != company_id:
        raise HTTPException(status_code=403, detail="Access denied")
    
    new_status = status_update.get("status")
    
    # Update invoice
    invoice["status"] = new_status
    invoice["updated_at"] = datetime.now()
    
    # Special handling for specific statuses
    if new_status == InvoiceStatus.APPROVED:
        invoice["approved_at"] = datetime.now()
    elif new_status == InvoiceStatus.SENT:
        invoice["sent_at"] = datetime.now()
    
    return {
        "success": True,
        "data": invoice,
        "message": f"Invoice status updated to {new_status}",
        "errors": [],
        "meta": {
            "timestamp": datetime.now().isoformat(),
            "request_id": f"req_{uuid.uuid4().hex[:12]}"
        }
    }

@router.post("/companies/{company_id}/tax-invoices/{invoice_id}/generate-einvoice", response_model=dict)
async def generate_einvoice(
    company_id: str = Path(...),
    invoice_id: str = Path(...),
    token: str = Depends(security)
):
    """Generate E-Invoice."""
    
    if invoice_id not in invoices_db:
        raise HTTPException(status_code=404, detail="Invoice not found")
    
    invoice = invoices_db[invoice_id]
    
    # Verify invoice belongs to company
    if invoice.get("company_id") != company_id:
        raise HTTPException(status_code=403, detail="Access denied")
    
    # Check if E-Invoice is applicable
    if not invoice.get("einvoice_applicable"):
        raise HTTPException(
            status_code=422, 
            detail="E-Invoice not applicable for this invoice"
        )
    
    # Check invoice status
    if invoice.get("status") != InvoiceStatus.APPROVED:
        raise HTTPException(
            status_code=422, 
            detail="Only approved invoices can generate E-Invoice"
        )
    
    # Mock E-Invoice generation
    irn = f"{''.join([str(uuid.uuid4().hex[:8])])}{invoice_id[:8]}"
    ack_number = f"ACK{datetime.now().strftime('%Y%m%d%H%M%S')}"
    qr_code_data = f"IRN:{irn}|DATE:{invoice['invoice_date']}|AMT:{invoice['total_amount']}"
    
    # Update invoice with E-Invoice details
    invoice.update({
        "einvoice_status": "GENERATED",
        "irn": irn,
        "ack_number": ack_number,
        "ack_date": datetime.now(),
        "qr_code_data": qr_code_data,
        "status": InvoiceStatus.EINVOICE_GENERATED,
        "updated_at": datetime.now()
    })
    
    return {
        "success": True,
        "data": {
            "irn": irn,
            "ack_number": ack_number,
            "ack_date": datetime.now().isoformat(),
            "qr_code_data": qr_code_data,
            "invoice": invoice
        },
        "message": "E-Invoice generated successfully",
        "errors": [],
        "meta": {
            "timestamp": datetime.now().isoformat(),
            "request_id": f"req_{uuid.uuid4().hex[:12]}"
        }
    }

@router.post("/companies/{company_id}/tax-invoices/{invoice_id}/cancel-einvoice", response_model=dict)
async def cancel_einvoice(
    company_id: str = Path(...),
    invoice_id: str = Path(...),
    cancel_data: EInvoiceCancel = ...,
    token: str = Depends(security)
):
    """Cancel E-Invoice."""
    
    if invoice_id not in invoices_db:
        raise HTTPException(status_code=404, detail="Invoice not found")
    
    invoice = invoices_db[invoice_id]
    
    # Verify invoice belongs to company
    if invoice.get("company_id") != company_id:
        raise HTTPException(status_code=403, detail="Access denied")
    
    # Check if E-Invoice exists
    if not invoice.get("irn"):
        raise HTTPException(status_code=422, detail="No E-Invoice found to cancel")
    
    # Check if already cancelled
    if invoice.get("einvoice_status") == "CANCELLED":
        raise HTTPException(status_code=422, detail="E-Invoice already cancelled")
    
    # Update invoice
    invoice.update({
        "einvoice_status": "CANCELLED",
        "cancel_reason": cancel_data.cancel_reason,
        "cancel_remarks": cancel_data.cancel_remarks,
        "cancelled_at": datetime.now(),
        "status": InvoiceStatus.EINVOICE_CANCELLED,
        "updated_at": datetime.now()
    })
    
    return {
        "success": True,
        "data": invoice,
        "message": "E-Invoice cancelled successfully",
        "errors": [],
        "meta": {
            "timestamp": datetime.now().isoformat(),
            "request_id": f"req_{uuid.uuid4().hex[:12]}"
        }
    }

@router.get("/companies/{company_id}/tax-invoices/{invoice_id}/pdf", response_model=dict)
async def generate_invoice_pdf(
    company_id: str = Path(...),
    invoice_id: str = Path(...),
    token: str = Depends(security)
):
    """Generate invoice PDF."""
    
    if invoice_id not in invoices_db:
        raise HTTPException(status_code=404, detail="Invoice not found")
    
    invoice = invoices_db[invoice_id]
    
    # Mock PDF generation
    pdf_url = f"https://api.jusfinn.com/v1/documents/invoices/{invoice_id}.pdf"
    
    return {
        "success": True,
        "data": {
            "pdf_url": pdf_url,
            "invoice_number": invoice["invoice_number"],
            "generated_at": datetime.now().isoformat()
        },
        "message": "Invoice PDF generated successfully",
        "errors": [],
        "meta": {
            "timestamp": datetime.now().isoformat(),
            "request_id": f"req_{uuid.uuid4().hex[:12]}"
        }
    }

@router.post("/companies/{company_id}/tax-invoices/{invoice_id}/payments", response_model=dict)
async def record_payment(
    company_id: str = Path(...),
    invoice_id: str = Path(...),
    payment: PaymentCreate = ...,
    token: str = Depends(security)
):
    """Record payment for invoice."""
    
    if invoice_id not in invoices_db:
        raise HTTPException(status_code=404, detail="Invoice not found")
    
    invoice = invoices_db[invoice_id]
    
    # Verify invoice belongs to company
    if invoice.get("company_id") != company_id:
        raise HTTPException(status_code=403, detail="Access denied")
    
    # Validate payment amount
    outstanding = invoice.get("outstanding_amount", 0)
    if payment.payment_amount > outstanding:
        raise HTTPException(
            status_code=422, 
            detail=f"Payment amount {payment.payment_amount} exceeds outstanding amount {outstanding}"
        )
    
    # Create payment record
    payment_record = {
        "id": str(uuid.uuid4()),
        **payment.dict(),
        "recorded_at": datetime.now()
    }
    
    # Update invoice
    if "payments" not in invoice:
        invoice["payments"] = []
    
    invoice["payments"].append(payment_record)
    
    # Update outstanding amount
    new_outstanding = outstanding - payment.payment_amount
    invoice["outstanding_amount"] = new_outstanding
    
    # Update status based on outstanding amount
    if new_outstanding == 0:
        invoice["status"] = InvoiceStatus.PAID
        invoice["paid_at"] = datetime.now()
    elif new_outstanding < invoice["total_amount"]:
        invoice["status"] = InvoiceStatus.PARTIALLY_PAID
    
    invoice["updated_at"] = datetime.now()
    
    return {
        "success": True,
        "data": {
            "payment": payment_record,
            "invoice": invoice,
            "new_outstanding": new_outstanding
        },
        "message": "Payment recorded successfully",
        "errors": [],
        "meta": {
            "timestamp": datetime.now().isoformat(),
            "request_id": f"req_{uuid.uuid4().hex[:12]}"
        }
    } 