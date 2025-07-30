import os
from contextlib import asynccontextmanager
from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import ValidationError

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

from app.config import settings
from app.database import connect_databases, close_databases
from app.routers import auth, users, clients, vendors, purchase_order_router, bank, grn_router, purchase_bill_router

# Lifespan context manager for startup/shutdown events
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for startup and shutdown events."""
    # Startup
    print(f"🚀 Starting JusFinn Services on {settings.host}:{settings.port}")
    await connect_databases()
    yield
    # Shutdown
    await close_databases()

# Create FastAPI app
app = FastAPI(
    title="JusFinn Services API",
    description="FastAPI backend with MongoDB (auth/clients) and PostgreSQL (purchase/expense) integration",
    version="1.0.0",
    lifespan=lifespan
)

# Add validation error handler
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Handle validation errors with detailed logging."""
    print(f"🔍 VALIDATION ERROR: {exc}")
    print(f"🔍 REQUEST URL: {request.url}")
    print(f"🔍 REQUEST METHOD: {request.method}")
    
    # Try to get request body for debugging
    try:
        body = await request.body()
        print(f"🔍 REQUEST BODY: {body.decode()}")
    except Exception as e:
        print(f"🔍 Could not read request body: {e}")
    
    return JSONResponse(
        status_code=422,
        content={
            "detail": exc.errors(),
            "body": exc.body,
            "message": "Validation error - check request format"
        }
    )

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:8080", 
        "http://127.0.0.1:8080",
        "https://jusfinn.com",
        "https://www.jusfinn.com",
        settings.frontend_url
    ],  # Frontend URLs
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(auth.router)
app.include_router(users.router)
app.include_router(clients.router)
app.include_router(vendors.router)
app.include_router(purchase_order_router.router)
app.include_router(bank.router)
app.include_router(grn_router.router)
app.include_router(purchase_bill_router.router)

@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "message": "Welcome to JusFinn Services API",
        "version": "1.0.0",
        "docs": "/docs",
        "redoc": "/redoc",
        "database": {
            "mongodb": "Connected (auth & clients)",
            "postgresql": "Connected (purchase & expense)"
        }
    }

@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy", 
        "service": "JusFinn Services API",
        "databases": {
            "mongodb": "operational",
            "postgresql": "operational"
        }
    }

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host=settings.host,
        port=settings.port,
        reload=True
    )
