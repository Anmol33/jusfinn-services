from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


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
    locale: str


class User(BaseModel):
    """Model for user data stored in MongoDB."""
    id: Optional[str] = Field(None, alias="_id")
    google_id: str
    email: str
    name: str
    given_name: str
    family_name: str
    picture: str
    locale: str
    access_token: str
    refresh_token: Optional[str] = None
    token_expires_at: datetime
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
                "locale": "en",
                "access_token": "ya29.a0AfH6SMB...",
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
    locale: str
    created_at: datetime
    updated_at: datetime 