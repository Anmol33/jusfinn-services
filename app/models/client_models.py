from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field, validator
from enum import Enum

# =====================================================
# CLIENT MODELS
# =====================================================

class ClientType(str, Enum):
    """Enum for client types."""
    INDIVIDUAL = "individual"
    BUSINESS = "business"
    PARTNERSHIP = "partnership"
    COMPANY = "company"

class ClientStatus(str, Enum):
    """Enum for client status."""
    ACTIVE = "active"
    INACTIVE = "inactive"
    PENDING = "pending"

class ClientAddress(BaseModel):
    """Model for client address information."""
    street: str
    city: str
    state: str
    postal_code: str
    country: str = "India"

class Client(BaseModel):
    """Model for client data stored in MongoDB."""
    id: Optional[str] = Field(None, alias="_id")
    user_google_id: str  # Maps client to the CA user

    # Basic Information
    name: str
    email: str
    phone: str

    # Business Information
    company_name: Optional[str] = None
    client_type: ClientType = ClientType.INDIVIDUAL

    # Tax Information
    pan_number: str  # Made mandatory
    gst_number: Optional[str] = None
    aadhar_number: Optional[str] = None

    # Address Information
    address: ClientAddress

    # Status and Metadata
    status: ClientStatus = ClientStatus.ACTIVE
    notes: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    @validator('pan_number')
    def validate_pan_number(cls, v):
        if not v:
            raise ValueError('PAN number is required')
        # PAN format: 5 letters + 4 digits + 1 letter
        import re
        if not re.match(r'^[A-Z]{5}[0-9]{4}[A-Z]{1}$', v.upper()):
            raise ValueError('PAN number must be in format: ABCPD1234E')
        return v.upper()

    class Config:
        populate_by_name = True

class ClientResponse(BaseModel):
    """Model for client response."""
    id: str
    user_google_id: str
    name: str
    email: str
    phone: str
    company_name: Optional[str] = None
    client_type: ClientType
    pan_number: str  # Made mandatory
    gst_number: Optional[str] = None
    aadhar_number: Optional[str] = None
    address: ClientAddress
    status: ClientStatus
    notes: Optional[str] = None
    created_at: datetime
    updated_at: datetime

class ClientCreateRequest(BaseModel):
    """Model for creating a new client."""
    name: str
    email: str
    phone: str
    company_name: Optional[str] = None
    client_type: ClientType = ClientType.INDIVIDUAL
    pan_number: str  # Made mandatory
    gst_number: Optional[str] = None
    aadhar_number: Optional[str] = None
    address: ClientAddress
    notes: Optional[str] = None

    @validator('pan_number')
    def validate_pan_number(cls, v):
        if not v:
            raise ValueError('PAN number is required')
        # PAN format: 5 letters + 4 digits + 1 letter
        import re
        if not re.match(r'^[A-Z]{5}[0-9]{4}[A-Z]{1}$', v.upper()):
            raise ValueError('PAN number must be in format: ABCPD1234E')
        return v.upper()

class ClientUpdateRequest(BaseModel):
    """Model for updating an existing client."""
    name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    company_name: Optional[str] = None
    client_type: Optional[ClientType] = None
    pan_number: Optional[str] = None
    gst_number: Optional[str] = None
    aadhar_number: Optional[str] = None
    address: Optional[ClientAddress] = None
    status: Optional[ClientStatus] = None
    notes: Optional[str] = None