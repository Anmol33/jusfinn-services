from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field, validator
from enum import Enum


class GoogleOAuth2Response(BaseModel):
    """Model for Google OAuth2 response data."""
    access_token: str
    token_type: str
    expires_in: int
    refresh_token: Optional[str] = None
    scope: str


class GoogleUserInfo(BaseModel):
    """Model for Google user information."""
    id: str
    email: str
    verified_email: bool
    name: str
    given_name: str
    family_name: str
    picture: str


class User(BaseModel):
    """Model for user data stored in MongoDB."""
    id: Optional[str] = Field(None, alias="_id")
    google_id: str
    email: str
    name: str
    given_name: str
    family_name: str
    picture: str
    access_token: Optional[str] = None
    refresh_token: Optional[str] = None
    token_expires_at: Optional[datetime] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        populate_by_name = True
        json_schema_extra = {
            "example": {
                "google_id": "123456789",
                "email": "user@example.com",
                "name": "John Doe",
                "given_name": "John",
                "family_name": "Doe",
                "picture": "https://example.com/picture.jpg",
                "access_token": "ya29.a0AfH6SMB...",
                "refresh_token": "1//04dX...",
                "token_expires_at": "2024-01-01T12:00:00Z",
                "created_at": "2024-01-01T10:00:00Z",
                "updated_at": "2024-01-01T10:00:00Z"
            }
        }


class UserResponse(BaseModel):
    """Model for user response (without sensitive data)."""
    id: str
    email: str
    name: str
    given_name: str
    family_name: str
    picture: str
    created_at: datetime
    updated_at: datetime


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
        json_schema_extra = {
            "example": {
                "user_google_id": "123456789",
                "name": "John Doe",
                "email": "john@example.com",
                "phone": "+91-9876543210",
                "company_name": "ABC Industries",
                "client_type": "business",
                "pan_number": "ABCPD1234E",
                "gst_number": "27ABCPD1234E1Z5",
                "address": {
                    "street": "123 Business Park",
                    "city": "Mumbai",
                    "state": "Maharashtra",
                    "postal_code": "400001",
                    "country": "India"
                },
                "status": "active",
                "notes": "New client onboarded for GST services"
            }
        }


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
    pan_number: Optional[str] = None  # Optional for updates to allow partial updates
    gst_number: Optional[str] = None
    aadhar_number: Optional[str] = None
    address: Optional[ClientAddress] = None
    status: Optional[ClientStatus] = None
    notes: Optional[str] = None

    @validator('pan_number')
    def validate_pan_number(cls, v):
        if v is not None and v.strip():
            # PAN format: 5 letters + 4 digits + 1 letter
            import re
            if not re.match(r'^[A-Z]{5}[0-9]{4}[A-Z]{1}$', v.upper()):
                raise ValueError('PAN number must be in format: ABCPD1234E')
            return v.upper()
        return v 