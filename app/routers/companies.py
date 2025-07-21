from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.security import HTTPBearer
from typing import List, Optional
from pydantic import BaseModel, Field
from datetime import datetime
import uuid

router = APIRouter()
security = HTTPBearer()

# Pydantic models for request/response
class CompanyAddress(BaseModel):
    line1: str
    line2: Optional[str] = None
    city: str
    state_id: int
    pincode: str
    country: str = "India"

class CompanyCreate(BaseModel):
    company_code: str = Field(..., max_length=20)
    legal_name: str = Field(..., max_length=255)
    trade_name: Optional[str] = Field(None, max_length=255)
    gstin: str = Field(..., pattern=r'^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z]{1}[A-Z0-9]{1}[Z]{1}[A-Z0-9]{1}$')
    pan: str = Field(..., pattern=r'^[A-Z]{5}[0-9]{4}[A-Z]{1}$')
    email: str = Field(..., pattern=r'^[^@]+@[^@]+\.[^@]+$')
    phone: str = Field(..., max_length=15)
    address: CompanyAddress
    subscription_plan: str = Field("BASIC", pattern=r'^(BASIC|PROFESSIONAL|ENTERPRISE)$')

class CompanyResponse(BaseModel):
    id: str
    company_code: str
    legal_name: str
    trade_name: Optional[str]
    gstin: str
    pan: str
    email: str
    phone: str
    address: CompanyAddress
    subscription_plan: str
    is_active: bool
    created_at: datetime
    updated_at: datetime

class GSTConfig(BaseModel):
    gst_registration_type: str
    annual_turnover: float
    einvoice_applicable: bool
    api_provider: Optional[str]
    api_credentials: Optional[dict]

# Mock database - replace with actual database calls
companies_db = {}

@router.post("", response_model=dict)
async def create_company(
    company: CompanyCreate,
    token: str = Depends(security)
):
    """Register a new company in the system."""
    
    # Check if company code or GSTIN already exists
    for existing_company in companies_db.values():
        if existing_company.get("company_code") == company.company_code:
            raise HTTPException(status_code=409, detail="Company code already exists")
        if existing_company.get("gstin") == company.gstin:
            raise HTTPException(status_code=409, detail="GSTIN already registered")
    
    # Generate new company ID
    company_id = str(uuid.uuid4())
    
    # Create company record
    new_company = {
        "id": company_id,
        **company.dict(),
        "is_active": True,
        "created_at": datetime.now(),
        "updated_at": datetime.now()
    }
    
    companies_db[company_id] = new_company
    
    return {
        "success": True,
        "data": new_company,
        "message": "Company registered successfully",
        "errors": [],
        "meta": {
            "timestamp": datetime.now().isoformat(),
            "request_id": f"req_{uuid.uuid4().hex[:12]}"
        }
    }

@router.get("/{company_id}", response_model=dict)
async def get_company(
    company_id: str,
    token: str = Depends(security)
):
    """Get company details by ID."""
    
    if company_id not in companies_db:
        raise HTTPException(status_code=404, detail="Company not found")
    
    company = companies_db[company_id]
    
    return {
        "success": True,
        "data": company,
        "message": "Company details retrieved successfully",
        "errors": [],
        "meta": {
            "timestamp": datetime.now().isoformat(),
            "request_id": f"req_{uuid.uuid4().hex[:12]}"
        }
    }

@router.put("/{company_id}", response_model=dict)
async def update_company(
    company_id: str,
    company_update: CompanyCreate,
    token: str = Depends(security)
):
    """Update company information."""
    
    if company_id not in companies_db:
        raise HTTPException(status_code=404, detail="Company not found")
    
    # Update company record
    companies_db[company_id].update({
        **company_update.dict(),
        "updated_at": datetime.now()
    })
    
    return {
        "success": True,
        "data": companies_db[company_id],
        "message": "Company updated successfully",
        "errors": [],
        "meta": {
            "timestamp": datetime.now().isoformat(),
            "request_id": f"req_{uuid.uuid4().hex[:12]}"
        }
    }

@router.get("/{company_id}/gst-config", response_model=dict)
async def get_gst_config(
    company_id: str,
    token: str = Depends(security)
):
    """Get company GST configuration."""
    
    if company_id not in companies_db:
        raise HTTPException(status_code=404, detail="Company not found")
    
    # Mock GST configuration
    gst_config = {
        "gst_registration_type": "REGULAR",
        "annual_turnover": 50000000.00,  # 5 crores
        "einvoice_applicable": True,
        "api_provider": "MASTERGST",
        "eway_bill_threshold": {
            "interstate": 50000,
            "intrastate": 100000
        },
        "gstr1_filing_frequency": "MONTHLY",
        "last_gstr1_filed": "02-2024",
        "compliance_status": "ACTIVE"
    }
    
    return {
        "success": True,
        "data": gst_config,
        "message": "GST configuration retrieved successfully",
        "errors": [],
        "meta": {
            "timestamp": datetime.now().isoformat(),
            "request_id": f"req_{uuid.uuid4().hex[:12]}"
        }
    }

@router.get("", response_model=dict)
async def list_companies(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    search: Optional[str] = Query(None),
    token: str = Depends(security)
):
    """List companies with pagination and search."""
    
    # Filter companies based on search
    filtered_companies = list(companies_db.values())
    
    if search:
        filtered_companies = [
            company for company in filtered_companies
            if search.lower() in company.get("legal_name", "").lower() or
               search.lower() in company.get("company_code", "").lower()
        ]
    
    # Pagination
    total = len(filtered_companies)
    start = (page - 1) * limit
    end = start + limit
    companies_page = filtered_companies[start:end]
    
    return {
        "success": True,
        "data": {
            "companies": companies_page,
            "pagination": {
                "page": page,
                "limit": limit,
                "total": total,
                "pages": (total + limit - 1) // limit
            }
        },
        "message": f"Retrieved {len(companies_page)} companies",
        "errors": [],
        "meta": {
            "timestamp": datetime.now().isoformat(),
            "request_id": f"req_{uuid.uuid4().hex[:12]}"
        }
    } 