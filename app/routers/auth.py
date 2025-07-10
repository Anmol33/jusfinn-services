from fastapi import APIRouter, HTTPException, Depends, Request
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
from services.google_oauth import google_oauth_service
from services.user_service import user_service
from services.jwt_service import jwt_service
from models import User, UserResponse
from database import get_database
from config import settings
import json
import urllib.parse

router = APIRouter(prefix="/auth", tags=["Authentication"])


class GoogleIdTokenRequest(BaseModel):
    id_token: str


@router.get("/google/login")
async def google_login():
    """Initiate Google OAuth2 login flow."""
    authorization_url = google_oauth_service.get_authorization_url()
    return {"authorization_url": authorization_url}


@router.get("/google/callback")
async def google_callback(code: str, state: str = None):
    """Handle Google OAuth2 callback and exchange code for tokens."""
    try:
        # Exchange authorization code for access token
        token_response = await google_oauth_service.exchange_code_for_token(code)
        
        # Get user information from Google
        user_info = await google_oauth_service.get_user_info(token_response.access_token)
        
        # Check if user already exists
        existing_user = await user_service.get_user_by_google_id(user_info.id)
        
        if existing_user:
            # Update existing user's tokens and last login
            await user_service.update_user_tokens(
                existing_user.id,
                token_response.access_token,
                token_response.refresh_token,
                token_response.expires_in
            )
            await user_service.update_user_last_login(existing_user.id)
            user = existing_user
        else:
            # Create new user with tokens
            new_user = User(
                google_id=user_info.id,
                email=user_info.email,
                name=user_info.name,
                given_name=user_info.given_name,
                family_name=user_info.family_name,
                picture=user_info.picture,
                access_token=token_response.access_token,
                refresh_token=token_response.refresh_token,
                token_expires_at=google_oauth_service.calculate_token_expiry(token_response.expires_in)
            )
            user = await user_service.create_user(new_user)
        
        # Create JWT token for the user
        token_data = {"sub": str(user.id), "email": user.email}
        access_token = jwt_service.create_access_token(data=token_data)
        
        # Prepare user data for frontend
        user_data = {
            "access_token": access_token,
            "user": {
                "id": str(user.id),
                "email": user.email,
                "name": user.name,
                "given_name": user.given_name,
                "family_name": user.family_name,
                "picture": user.picture,
                "created_at": user.created_at.isoformat() if user.created_at else None,
                "updated_at": user.updated_at.isoformat() if user.updated_at else None
            }
        }
        
        # Encode user data for URL parameter
        encoded_data = urllib.parse.quote(json.dumps(user_data))
        
        # Redirect to frontend with user data
        frontend_url = f"{settings.frontend_url}/auth/callback?data={encoded_data}"
        return RedirectResponse(url=frontend_url)
        
    except Exception as e:
        print(f"Authentication failed: {str(e)}")
        # Redirect to frontend with error
        error_data = {"error": "Authentication failed"}
        encoded_error = urllib.parse.quote(json.dumps(error_data))
        frontend_url = f"{settings.frontend_url}/auth/callback?error={encoded_error}"
        return RedirectResponse(url=frontend_url)


@router.post("/google/verify")
async def verify_google_token(request: GoogleIdTokenRequest):
    """Verify Google ID token and create/update user."""
    try:
        # Verify the ID token with Google
        user_info = await google_oauth_service.verify_id_token(request.id_token)
        
        if not user_info:
            raise HTTPException(status_code=401, detail="Invalid Google token")
        
        # Check if user already exists
        existing_user = await user_service.get_user_by_google_id(user_info.id)
        
        if existing_user:
            # Update existing user
            await user_service.update_user_last_login(existing_user.id)
            user = existing_user
        else:
            # Create new user
            new_user = User(
                google_id=user_info.id,
                email=user_info.email,
                name=user_info.name,
                given_name=user_info.given_name,
                family_name=user_info.family_name,
                picture=user_info.picture
            )
            user = await user_service.create_user(new_user)
        
        # Create JWT token for the user
        token_data = {"sub": str(user.id), "email": user.email}
        access_token = jwt_service.create_access_token(data=token_data)
        
        # Return user data and JWT token
        return {
            "access_token": access_token,
            "user": UserResponse(
                id=user.id,
                email=user.email,
                name=user.name,
                given_name=user.given_name,
                family_name=user.family_name,
                picture=user.picture,
                created_at=user.created_at,
                updated_at=user.updated_at
            )
        }
        
    except Exception as e:
        print(e)
        raise HTTPException(status_code=400, detail=f"Authentication failed: {str(e)}")


@router.get("/me")
async def get_current_user(token: str = Depends(jwt_service.get_current_user)):
    """Get current user information."""
    try:
        user_id = token.get("sub")
        user = await user_service.get_user_by_id(user_id)
        
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        return UserResponse(
            id=user.id,
            email=user.email,
            name=user.name,
            given_name=user.given_name,
            family_name=user.family_name,
            picture=user.picture,
            created_at=user.created_at,
            updated_at=user.updated_at
        )
    except Exception as e:
        raise HTTPException(status_code=401, detail=f"Invalid token: {str(e)}")


@router.get("/google/redirect")
async def google_redirect():
    """Redirect to Google OAuth2 authorization URL."""
    authorization_url = google_oauth_service.get_authorization_url()
    return RedirectResponse(url=authorization_url) 