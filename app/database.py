from motor.motor_asyncio import AsyncIOMotorClient
from config import settings
import logging
import ssl

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class Database:
    client: AsyncIOMotorClient = None
    database = None


db = Database()


async def connect_to_mongo():
    """Create database connection with SSL fallback options."""
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
            logger.info(f"Attempting connection {i} with: {connection_string[:80]}...")
            
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
            
            # Test the connection
            await db.client.admin.command('ping')
            db.database = db.client[settings.database_name]
            logger.info(f"✅ Connected to MongoDB Atlas successfully with option {i}!")
            return
            
        except Exception as e:
            logger.warning(f"❌ Connection attempt {i} failed: {str(e)}...")
            if db.client:
                try:
                    db.client.close()
                except:
                    pass
            continue
    
    # If all attempts failed
    error_msg = "❌ All MongoDB connection attempts failed. Please check:"
    error_msg += "\n1. MongoDB Atlas cluster is running"
    error_msg += "\n2. Username/password are correct"
    error_msg += "\n3. IP address is whitelisted in MongoDB Atlas"
    error_msg += "\n4. Network allows outbound connections to port 27017"
    error_msg += "\n5. Try connecting from MongoDB Compass to verify credentials"
    
    logger.error(error_msg)
    raise Exception("Failed to connect to MongoDB Atlas")


async def close_mongo_connection():
    """Close database connection."""
    if db.client:
        db.client.close()
        logger.info("Disconnected from MongoDB.")


def get_database():
    """Get database instance."""
    return db.database 