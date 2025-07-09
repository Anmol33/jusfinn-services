from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
from services.google_oauth import google_oauth_service
from services.user_service import user_service
from services.jwt_service import jwt_service
from models import User, UserResponse
from database import get_database
import json
import urllib.parse

router = APIRouter(prefix="/auth", tags=["Authentication"])


class GoogleIdTokenRequest(BaseModel):
    id_token: str


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
                picture=user_info.picture,
                locale=user_info.locale
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
                locale=user.locale,
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
            locale=user.locale,
            created_at=user.created_at,
            updated_at=user.updated_at
        )
    except Exception as e:
        raise HTTPException(status_code=401, detail=f"Invalid token: {str(e)}")


@router.get("/google/login")
async def google_login():
    """Initiate Google OAuth2 login flow."""
    authorization_url = google_oauth_service.get_authorization_url()
    return {"authorization_url": authorization_url}


@router.post("/google/callback")
async def google_callback(request):
    """Handle Google OAuth2 callback and save user data."""
    try:
        # Exchange authorization code for access token
        token_response = await google_oauth_service.exchange_code_for_token(request.code)
        
        # Get user information from Google
        user_info = await google_oauth_service.get_user_info(token_response.access_token)
        
        # Calculate token expiry
        token_expires_at = google_oauth_service.calculate_token_expiry(token_response.expires_in)
        
        # Check if user already exists
        existing_user = await user_service.get_user_by_google_id(user_info.id)
        
        if existing_user:
            # Update existing user's tokens
            await user_service.update_user_tokens(
                existing_user.id,
                token_response.access_token,
                token_response.refresh_token,
                token_expires_at
            )
            user = existing_user
        else:
            # Create new user
            new_user = User(
                google_id=user_info.id,
                email=user_info.email,
                name=user_info.name,
                given_name=user_info.given_name,
                family_name=user_info.family_name,
                picture=user_info.picture,
                locale=user_info.locale,
                access_token=token_response.access_token,
                refresh_token=token_response.refresh_token,
                token_expires_at=token_expires_at
            )
            user = await user_service.create_user(new_user)
        
        # Return user data (without sensitive information)
        return UserResponse(
            id=user.id,
            email=user.email,
            name=user.name,
            given_name=user.given_name,
            family_name=user.family_name,
            picture=user.picture,
            locale=user.locale,
            created_at=user.created_at,
            updated_at=user.updated_at
        )
        
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Authentication failed: {str(e)}")


@router.get("/google/callback/redirect")
async def google_callback_redirect(code: str, redirect_url: str = "http://localhost:3000/dashboard"):
    """Handle Google OAuth2 callback and redirect to frontend with user data."""
    try:
        # Exchange authorization code for access token
        token_response = await google_oauth_service.exchange_code_for_token(code)
        
        # Get user information from Google
        user_info = await google_oauth_service.get_user_info(token_response.access_token)
        
        # Calculate token expiry
        token_expires_at = google_oauth_service.calculate_token_expiry(token_response.expires_in)
        
        # Check if user already exists
        existing_user = await user_service.get_user_by_google_id(user_info.id)
        
        if existing_user:
            # Update existing user's tokens
            await user_service.update_user_tokens(
                existing_user.id,
                token_response.access_token,
                token_response.refresh_token,
                token_expires_at
            )
            user = existing_user
        else:
            # Create new user
            new_user = User(
                google_id=user_info.id,
                email=user_info.email,
                name=user_info.name,
                given_name=user_info.given_name,
                family_name=user_info.family_name,
                picture=user_info.picture,
                locale=user_info.locale,
                access_token=token_response.access_token,
                refresh_token=token_response.refresh_token,
                token_expires_at=token_expires_at
            )
            user = await user_service.create_user(new_user)
        
        # Create JWT token for the user
        token_data = {"sub": user.id, "email": user.email}
        access_token = jwt_service.create_access_token(data=token_data)
        
        # Prepare user data for frontend
        user_data = {
            "id": user.id,
            "email": user.email,
            "name": user.name,
            "given_name": user.given_name,
            "family_name": user.family_name,
            "picture": user.picture,
            "locale": user.locale,
            "created_at": user.created_at.isoformat(),
            "updated_at": user.updated_at.isoformat(),
            "access_token": access_token
        }
        
        # Encode user data for URL parameters
        user_data_encoded = urllib.parse.quote(json.dumps(user_data))
        
        # Redirect to frontend with user data and token
        redirect_url_with_data = f"{redirect_url}?auth=success&user={user_data_encoded}"
        return RedirectResponse(url=redirect_url_with_data)
        
    except Exception as e:
        # Redirect to frontend with error
        error_encoded = urllib.parse.quote(str(e))
        redirect_url_with_error = f"{redirect_url}?auth=error&error={error_encoded}"
        return RedirectResponse(url=redirect_url_with_error)


@router.get("/google/redirect")
async def google_redirect():
    """Redirect to Google OAuth2 authorization URL."""
    authorization_url = google_oauth_service.get_authorization_url()
    return RedirectResponse(url=authorization_url) 