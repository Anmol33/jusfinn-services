import os
from typing import Optional
from pydantic_settings import BaseSettings



class Settings(BaseSettings):
    # MongoDB Configuration
    mongodb_url: str = "mongodb+srv://sanchit:sanchit123@cluster0.wdorp9f.mongodb.net/?retryWrites=true&w=majority"
    database_name: str = "jusfinn"
    user_mongo_collection: str = "user"
    
    # Google OAuth2 Configuration
    google_client_id: str = "581557555470-mq47gdjjn1a79auusu23pm532562kv8d.apps.googleusercontent.com"
    google_client_secret: str = "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"
    google_redirect_uri: str = "http://localhost:8000/auth/google/callback"
    
    # JWT Configuration
    jwt_secret_key: str = "your_super_secret_jwt_key_change_this_in_production"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    
    # Server Configuration
    host: str = "0.0.0.0"
    port: int = 8000
    
    class Config:
        env_file = ".env"
        case_sensitive = False


settings = Settings() 