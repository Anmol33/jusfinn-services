from motor.motor_asyncio import AsyncIOMotorClient
from config import settings


class Database:
    client: AsyncIOMotorClient = None
    database = None


db = Database()


async def connect_to_mongo():
    """Create database connection."""
    # Use the MongoDB Atlas connection string directly
    connection_string = settings.mongodb_url
    
    db.client = AsyncIOMotorClient(connection_string)
    db.database = db.client[settings.database_name]
    print("Connected to MongoDB Atlas.")


async def close_mongo_connection():
    """Close database connection."""
    if db.client:
        db.client.close()
        print("Disconnected from MongoDB.")


def get_database():
    """Get database instance."""
    return db.database 