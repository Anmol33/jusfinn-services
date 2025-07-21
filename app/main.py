import os
from contextlib import asynccontextmanager
from dotenv import load_dotenv
from fastapi import FastAPI, APIRouter
from fastapi.middleware.cors import CORSMiddleware



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

from config import settings
from database import connect_to_mongo, close_mongo_connection
from routers import auth, users, clients, companies, quotations, invoices, inventory

# Lifespan context manager for startup/shutdown events
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for startup and shutdown events."""
    # Startup
    print(f"🚀 Starting JusFinn Services on {settings.host}:{settings.port}")
    await connect_to_mongo()
    yield
    # Shutdown
    await close_mongo_connection()

# Create FastAPI app
app = FastAPI(
    title="JusFinn Services API",
    description="GST-compliant Sales Workflow Management System",
    version="1.0.0",
    lifespan=lifespan
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",  # React frontend
        "http://localhost:8080", 
        "http://127.0.0.1:8080",
        "https://jusfinn.com",
        "https://www.jusfinn.com",
        settings.frontend_url
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Create v1 API router
v1_router = APIRouter(prefix="")

# Include routers under v1 prefix
v1_router.include_router(auth.router, tags=["Authentication"])
v1_router.include_router(users.router, tags=["Users"])
v1_router.include_router(companies.router, prefix="/companies", tags=["Companies"])
v1_router.include_router(clients.router, tags=["Customers"])  # clients = customers
v1_router.include_router(quotations.router, tags=["Sales Quotations"])
v1_router.include_router(invoices.router, tags=["Tax Invoices"])
v1_router.include_router(inventory.router, tags=["Inventory"])

# Include the v1 router in the main app
app.include_router(v1_router)

@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "message": "Welcome to JusFinn Services API",
        "version": "1.0.0",
        "docs": "/docs",
        "redoc": "/redoc",
        "api_base": "/v1",
        "status": "active"
    }

@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "service": "JusFinn Services API"}

@app.get("/v1")
async def api_info():
    """API v1 information endpoint."""
    return {
        "version": "1.0.0",
        "title": "JusFinn GST-Compliant Sales API",
        "description": "Complete sales workflow management with GST compliance",
        "endpoints": {
            "companies": "/v1/companies",
            "customers": "/v1/companies/{company_id}/customers", 
            "quotations": "/v1/companies/{company_id}/quotations",
            "invoices": "/v1/companies/{company_id}/tax-invoices",
            "inventory": "/v1/companies/{company_id}/inventory",
            "gstr1": "/v1/companies/{company_id}/gstr1",
            "auth": "/v1/auth",
            "docs": "/docs"
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
