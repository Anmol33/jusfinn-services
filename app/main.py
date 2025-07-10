import os
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from database import connect_to_mongo, close_mongo_connection
from routers import auth, users
from config import settings

# Load environment variables from .env file at startup
def load_environment():
    """Load environment variables from .env file"""
    env_file = ".env"
    
    # Check if .env file exists in current directory or parent directory
    if os.path.exists(env_file):
        load_dotenv(env_file)
        print(f"✅ Environment variables loaded from {env_file}")
    elif os.path.exists(os.path.join("..", env_file)):
        load_dotenv(os.path.join("..", env_file))
        print(f"✅ Environment variables loaded from ../{env_file}")
    else:
        print(f"⚠️  {env_file} file not found. Using system environment variables.")

# Load environment variables before importing config
load_environment()

# Create FastAPI app
app = FastAPI(
    title="JusFinn Services API",
    description="FastAPI backend with MongoDB and Google OAuth2 integration",
    version="1.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8080", "http://127.0.0.1:8080"],  # Frontend URLs
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(auth.router)
app.include_router(users.router)


@app.on_event("startup")
async def startup_event():
    """Connect to MongoDB on startup."""
    print(f"🚀 Starting JusFinn Services on {settings.host}:{settings.port}")
    await connect_to_mongo()


@app.on_event("shutdown")
async def shutdown_event():
    """Close MongoDB connection on shutdown."""
    await close_mongo_connection()


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "message": "Welcome to JusFinn Services API",
        "version": "1.0.0",
        "docs": "/docs",
        "redoc": "/redoc"
    }


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "service": "JusFinn Services API"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        reload=True
    ) 