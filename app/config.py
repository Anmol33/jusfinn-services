import os
from typing import Optional


class Settings:
    def __init__(self):
        # MongoDB Configuration
        self.mongodb_url = os.environ.get("MONGODB_URL")
        self.database_name = os.environ.get("DATABASE_NAME")
        self.user_mongo_collection = os.environ.get("USER_MONGO_COLLECTION")

        # Google OAuth2 Configuration
        self.google_client_id = os.environ.get("GOOGLE_CLIENT_ID")
        self.google_client_secret = os.environ.get("GOOGLE_CLIENT_SECRET")
        self.google_redirect_uri = os.environ.get("GOOGLE_REDIRECT_URI")

        # JWT Configuration
        self.jwt_secret_key = os.environ.get("JWT_SECRET_KEY")
        self.jwt_algorithm = os.environ.get("JWT_ALGORITHM", "HS256")
        self.access_token_expire_minutes = int(os.environ.get("ACCESS_TOKEN_EXPIRE_MINUTES", "30"))

        # Server Configuration
        self.host = os.environ.get("HOST", "0.0.0.0")
        self.port = int(os.environ.get("PORT", "8000"))


settings = Settings()