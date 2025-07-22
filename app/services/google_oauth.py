import httpx
from datetime import datetime, timedelta
from typing import Optional
import secrets
from app.config import settings
from app.models import GoogleOAuth2Response, GoogleUserInfo
import logging

logger = logging.getLogger(__name__)


class GoogleOAuth2Service:
    """Service for handling Google OAuth2 authentication."""
    
    def __init__(self):
        self.client_id = settings.google_client_id
        self.client_secret = settings.google_client_secret
        self.redirect_uri = settings.google_redirect_uri
        self.token_url = "https://oauth2.googleapis.com/token"
        self.userinfo_url = "https://www.googleapis.com/oauth2/v2/userinfo"
        self.id_token_verify_url = "https://oauth2.googleapis.com/tokeninfo"
    
    def get_authorization_url(self) -> str:
        """Generate Google OAuth2 authorization URL with state parameter for security."""
        # Generate a random state parameter for CSRF protection
        state = secrets.token_urlsafe(32)
        
        params = {
            "client_id": self.client_id,
            "redirect_uri": self.redirect_uri,
            "response_type": "code",
            "scope": "openid email profile",
            "access_type": "offline",
            "prompt": "consent",
            "state": state
        }
        
        query_string = "&".join([f"{k}={v}" for k, v in params.items()])
        return f"https://accounts.google.com/o/oauth2/v2/auth?{query_string}"
    
    async def exchange_code_for_token(self, code: str) -> GoogleOAuth2Response:
        """Exchange authorization code for access token."""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                self.token_url,
                data={
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                    "code": code,
                    "grant_type": "authorization_code",
                    "redirect_uri": self.redirect_uri
                }
            )
            response.raise_for_status()
            token_data = response.json()
            
            return GoogleOAuth2Response(
                access_token=token_data["access_token"],
                token_type=token_data["token_type"],
                expires_in=token_data["expires_in"],
                refresh_token=token_data.get("refresh_token"),
                scope=token_data["scope"]
            )
    
    async def get_user_info(self, access_token: str) -> GoogleUserInfo:
        """Get user information from Google using access token."""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                self.userinfo_url,
                headers={"Authorization": f"Bearer {access_token}"}
            )
            response.raise_for_status()
            user_data = response.json()
            
            return GoogleUserInfo(
                id=user_data["id"],
                email=user_data["email"],
                verified_email=user_data["verified_email"],
                name=user_data["name"],
                given_name=user_data["given_name"],
                family_name=user_data["family_name"],
                picture=user_data["picture"]
            )
    
    def calculate_token_expiry(self, expires_in: int) -> datetime:
        """Calculate when the access token expires."""
        return datetime.utcnow() + timedelta(seconds=expires_in)

    async def verify_id_token(self, id_token: str) -> Optional[GoogleUserInfo]:
        """Verify Google ID token and return user info."""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    self.id_token_verify_url,
                    params={"id_token": id_token}
                )
                response.raise_for_status()
                token_data = response.json()
                
                # Verify the token is for our client
                if token_data.get("aud") != self.client_id:
                    return None
                
                # Check if token is expired
                if "exp" in token_data:
                    import time
                    if time.time() > token_data["exp"]:
                        return None
                
                return GoogleUserInfo(
                    id=token_data["sub"],
                    email=token_data["email"],
                    verified_email=token_data.get("email_verified", False),
                    name=token_data.get("name", ""),
                    given_name=token_data.get("given_name", ""),
                    family_name=token_data.get("family_name", ""),
                    picture=token_data.get("picture", "")
                )
        except Exception:
            return None


google_oauth_service = GoogleOAuth2Service() 