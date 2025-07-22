from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field

# =====================================================
# AUTHENTICATION & USER MODELS
# =====================================================

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