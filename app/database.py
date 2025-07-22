from motor.motor_asyncio import AsyncIOMotorClient
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy import MetaData, text
from sqlalchemy.ext.declarative import declarative_base
from app.config import settings
import logging
import ssl

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# =====================================================
# MONGODB CONNECTION (for auth and clients)
# =====================================================

class MongoDatabase:
    client: AsyncIOMotorClient = None
    database = None

db = MongoDatabase()



async def connect_to_mongo():
    """Create MongoDB database connection for auth and clients."""
    connection_strings = [
        # Option 1: With SSL certificate verification disabled
        settings.mongodb_url,
        
        # Option 2: Without SSL parameters (let MongoDB driver handle it)
        settings.mongodb_url.replace("&ssl=true&ssl_cert_reqs=CERT_NONE", ""),
        
        # Option 3: With explicit SSL context
        settings.mongodb_url + "&ssl_cert_reqs=CERT_NONE&tlsAllowInvalidCertificates=true",
    ]
    
    for i, connection_string in enumerate(connection_strings, 1):
        try:
            logger.info(f"Attempting MongoDB connection {i} with: {connection_string[:80]}...")
            
            # Create SSL context for option 3
            if i == 3:
                ssl_context = ssl.create_default_context()
                ssl_context.check_hostname = False
                ssl_context.verify_mode = ssl.CERT_NONE
                
                db.client = AsyncIOMotorClient(
                    connection_string,
                    serverSelectionTimeoutMS=30000,
                    connectTimeoutMS=30000,
                    socketTimeoutMS=30000,
                    ssl_context=ssl_context
                )
            else:
                db.client = AsyncIOMotorClient(
                    connection_string,
                    serverSelectionTimeoutMS=30000,
                    connectTimeoutMS=30000,
                    socketTimeoutMS=30000
                )
            
            # Test the connection by attempting to get server info
            await db.client.server_info()
            
            # Get the database
            db.database = db.client[settings.database_name]
            
            logger.info(f"✅ Successfully connected to MongoDB using connection string {i}")
            logger.info(f"📊 Connected to database: {settings.database_name}")
            return  # Exit the function on successful connection
            
        except Exception as e:
            logger.error(f"❌ MongoDB connection attempt {i} failed: {str(e)}")
            if db.client:
                db.client.close()
                db.client = None
            
            if i == len(connection_strings):
                logger.error("🚫 All MongoDB connection attempts failed!")
                raise Exception(f"Failed to connect to MongoDB after {len(connection_strings)} attempts: {str(e)}")

async def close_mongo_connection():
    """Close the MongoDB database connection."""
    if db.client:
        logger.info("🔌 Closing MongoDB connection...")
        db.client.close()
        logger.info("✅ MongoDB connection closed")

def get_database():
    """Get MongoDB database instance for auth and client operations."""
    return db.database

# =====================================================
# POSTGRESQL CONNECTION (for purchase and expense)
# =====================================================

# Construct proper PostgreSQL URL for SQLAlchemy
def get_postgres_url():
    """Construct PostgreSQL URL from individual components."""
    return f"postgresql+asyncpg://{settings.postgres_user}:{settings.postgres_password}@{settings.postgres_host}:{settings.postgres_port}/{settings.postgres_db}"

# Create async PostgreSQL engine
postgres_engine = create_async_engine(
    get_postgres_url(),
    echo=False,  # Set to True for SQL query logging
    future=True
)

# SQLAlchemy setup for schema definition
metadata = MetaData()
Base = declarative_base()

# Async session factory
AsyncSessionFactory = async_sessionmaker(
    postgres_engine,
    class_=AsyncSession,
    expire_on_commit=False
)

async def connect_to_postgres():
    """Connect to PostgreSQL database for purchase and expense modules."""
    try:
        # Test the connection
        async with postgres_engine.begin() as conn:
            await conn.execute(text("SELECT 1"))
        
        logger.info("✅ Successfully connected to PostgreSQL database")
        logger.info(f"📊 Connected to PostgreSQL database: {settings.postgres_db}")
    except Exception as e:
        logger.error(f"❌ Failed to connect to PostgreSQL: {str(e)}")
        raise Exception(f"Failed to connect to PostgreSQL: {str(e)}")

async def close_postgres_connection():
    """Close the PostgreSQL database connection."""
    try:
        await postgres_engine.dispose()
        logger.info("✅ PostgreSQL connection closed")
    except Exception as e:
        logger.error(f"❌ Error closing PostgreSQL connection: {str(e)}")

# Dependency to get PostgreSQL database session
async def get_postgres_session() -> AsyncSession:
    """Get PostgreSQL database session."""
    async with AsyncSessionFactory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()

# Helper function for direct session usage
def get_postgres_session_direct() -> AsyncSession:
    """Get PostgreSQL session for direct usage (not as dependency)."""
    return AsyncSessionFactory()

# =====================================================
# COMBINED CONNECTION FUNCTIONS
# =====================================================

async def connect_databases():
    """Connect to both MongoDB and PostgreSQL."""
    await connect_to_mongo()
    await connect_to_postgres()

async def close_databases():
    """Close both database connections."""
    await close_mongo_connection()
    await close_postgres_connection() 