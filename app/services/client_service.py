from datetime import datetime
from typing import Optional, List
from bson import ObjectId
import logging
from fastapi import HTTPException

from app.config import settings
from app.database import get_database
from app.models import Client, ClientResponse, ClientCreateRequest, ClientUpdateRequest, ClientStatus

logger = logging.getLogger(__name__)


class ClientService:
    def __init__(self):
        self.db = None
        self.clients_collection = None

    async def _ensure_db_connection(self):
        """Ensure database connection is established."""
        if self.db is None:
            self.db = get_database()
            if self.db is None:
                raise Exception(
                    "Database connection not established. Please ensure the application has started properly.")
            self.clients_collection = self.db["client_db"]
            
            # Create compound index for better query performance (non-unique to avoid conflicts)
            try:
                await self.clients_collection.create_index([
                    ("user_id", 1),
                    ("pan_number", 1),
                    ("name", 1)
                ], name="idx_user_pan_name")
            except Exception as e:
                # Index might already exist, log and continue
                logger.info(f"Index creation info: {e}")

    def _convert_objectid_to_string(self, doc):
        """Convert ObjectId to string in document."""
        if doc and "_id" in doc:
            doc["id"] = str(doc["_id"])
            del doc["_id"]
        
        # Ensure all required fields have default values for existing clients
        if "status" not in doc or doc["status"] is None:
            doc["status"] = ClientStatus.ACTIVE
        
        return doc

    async def _check_client_uniqueness(self, pan_number: str, client_name: str, user_id: str, exclude_client_id: str = None):
        """Check if combination of PAN number and client name is unique for the user."""
        await self._ensure_db_connection()
        
        query = {
            "user_id": user_id,
            "pan_number": pan_number.upper(),
            "name": client_name
        }
        
        # Exclude current client when updating
        if exclude_client_id:
            query["_id"] = {"$ne": ObjectId(exclude_client_id)}
        
        existing_client = await self.clients_collection.find_one(query)
        if existing_client:
            raise HTTPException(
                status_code=400,
                detail=f"A client with PAN number {pan_number} and name '{client_name}' already exists."
            )

    async def create_client(self, client_data: ClientCreateRequest, user_id: str) -> ClientResponse:
        """Create a new client in the database."""
        await self._ensure_db_connection()
        try:
            # Check client uniqueness (user_id + pan_number + client_name)
            await self._check_client_uniqueness(client_data.pan_number, client_data.name, user_id)
            
            # Create client document
            client_dict = client_data.model_dump()
            client_dict["user_id"] = user_id
            client_dict["status"] = ClientStatus.ACTIVE  # Set default status for new clients
            client_dict["created_at"] = datetime.utcnow()
            client_dict["updated_at"] = datetime.utcnow()

            result = await self.clients_collection.insert_one(client_dict)
            
            # Retrieve the created client
            client_doc = await self.clients_collection.find_one({"_id": result.inserted_id})
            client_doc = self._convert_objectid_to_string(client_doc)
            
            return ClientResponse(**client_doc)
        except HTTPException:
            # Re-raise HTTP exceptions (like uniqueness error)
            raise
        except Exception as e:
            logger.error(f"Error creating client: {e}")
            raise HTTPException(status_code=500, detail="Failed to create client")

    async def get_client_by_id(self, client_id: str, user_id: str) -> Optional[ClientResponse]:
        """Get client by ID for a specific user."""
        await self._ensure_db_connection()
        try:
            client_doc = await self.clients_collection.find_one({
                "_id": ObjectId(client_id),
                "user_id": user_id
            })
            if client_doc:
                client_doc = self._convert_objectid_to_string(client_doc)
                return ClientResponse(**client_doc)
            return None
        except Exception as e:
            logger.error(f"Error getting client by ID: {e}")
            return None

    async def get_clients_by_user(self, user_id: str, skip: int = 0, limit: int = 100) -> List[ClientResponse]:
        """Get all clients for a specific user."""
        await self._ensure_db_connection()
        try:
            cursor = self.clients_collection.find({"user_id": user_id}).skip(skip).limit(limit)
            clients = []
            async for client_doc in cursor:
                client_doc = self._convert_objectid_to_string(client_doc)
                clients.append(ClientResponse(**client_doc))
            return clients
        except Exception as e:
            logger.error(f"Error getting clients for user: {e}")
            return []

    async def update_client(self, client_id: str, client_data: ClientUpdateRequest, user_id: str) -> Optional[ClientResponse]:
        """Update an existing client."""
        await self._ensure_db_connection()
        try:
            # Check client uniqueness if PAN or name is being updated
            if client_data.pan_number or client_data.name:
                # Get current client to check what values to use for uniqueness check
                current_client = await self.get_client_by_id(client_id, user_id)
                if not current_client:
                    raise HTTPException(status_code=404, detail="Client not found")
                
                # Use updated values or fall back to current values
                pan_to_check = client_data.pan_number if client_data.pan_number else current_client.pan_number
                name_to_check = client_data.name if client_data.name else current_client.name
                
                await self._check_client_uniqueness(pan_to_check, name_to_check, user_id, client_id)
            
            # Build update document (only include non-None values)
            update_data = {}
            for field, value in client_data.model_dump().items():
                if value is not None:
                    update_data[field] = value
            
            if not update_data:
                # No fields to update
                return await self.get_client_by_id(client_id, user_id)

            update_data["updated_at"] = datetime.utcnow()

            result = await self.clients_collection.update_one(
                {"_id": ObjectId(client_id), "user_id": user_id},
                {"$set": update_data}
            )

            if result.modified_count > 0:
                return await self.get_client_by_id(client_id, user_id)
            return None
        except HTTPException:
            # Re-raise HTTP exceptions (like uniqueness error)
            raise
        except Exception as e:
            logger.error(f"Error updating client: {e}")
            raise HTTPException(status_code=500, detail="Failed to update client")

    async def delete_client(self, client_id: str, user_id: str) -> bool:
        """Delete a client from the database."""
        await self._ensure_db_connection()
        try:
            result = await self.clients_collection.delete_one({
                "_id": ObjectId(client_id),
                "user_id": user_id
            })
            return result.deleted_count > 0
        except Exception as e:
            logger.error(f"Error deleting client: {e}")
            return False

    async def search_clients(self, user_id: str, search_query: str, skip: int = 0, limit: int = 100) -> List[ClientResponse]:
        """Search clients by name, email, or company name."""
        await self._ensure_db_connection()
        try:
            search_filter = {
                "user_id": user_id,
                "$or": [
                    {"name": {"$regex": search_query, "$options": "i"}},
                    {"email": {"$regex": search_query, "$options": "i"}},
                    {"company_name": {"$regex": search_query, "$options": "i"}},
                    {"pan_number": {"$regex": search_query, "$options": "i"}},
                    {"gst_number": {"$regex": search_query, "$options": "i"}}
                ]
            }
            
            cursor = self.clients_collection.find(search_filter).skip(skip).limit(limit)
            clients = []
            async for client_doc in cursor:
                client_doc = self._convert_objectid_to_string(client_doc)
                clients.append(ClientResponse(**client_doc))
            return clients
        except Exception as e:
            logger.error(f"Error searching clients: {e}")
            return []

    async def get_client_count(self, user_id: str) -> int:
        """Get total number of clients for a user."""
        await self._ensure_db_connection()
        try:
            count = await self.clients_collection.count_documents({"user_id": user_id})
            return count
        except Exception as e:
            logger.error(f"Error getting client count: {e}")
            return 0

    async def get_clients_by_status(self, user_id: str, status: str, skip: int = 0, limit: int = 100) -> List[ClientResponse]:
        """Get clients by status for a specific user."""
        await self._ensure_db_connection()
        try:
            cursor = self.clients_collection.find({
                "user_id": user_id,
                "status": status
            }).skip(skip).limit(limit)
            
            clients = []
            async for client_doc in cursor:
                client_doc = self._convert_objectid_to_string(client_doc)
                clients.append(ClientResponse(**client_doc))
            return clients
        except Exception as e:
            logger.error(f"Error getting clients by status: {e}")
            return []

    async def get_client_statistics(self, user_id: str) -> dict:
        """Get client statistics for dashboard metrics."""
        await self._ensure_db_connection()
        try:
            # Get all clients for the user
            total_clients = await self.clients_collection.count_documents({"user_id": user_id})
            
            # Get counts by status
            active_clients = await self.clients_collection.count_documents({
                "user_id": user_id,
                "status": ClientStatus.ACTIVE
            })
            
            inactive_clients = await self.clients_collection.count_documents({
                "user_id": user_id,
                "status": ClientStatus.INACTIVE
            })
            
            pending_clients = await self.clients_collection.count_documents({
                "user_id": user_id,
                "status": ClientStatus.PENDING
            })
            
            # Get clients created this month
            from datetime import datetime
            current_month_start = datetime.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            
            this_month_clients = await self.clients_collection.count_documents({
                "user_id": user_id,
                "created_at": {"$gte": current_month_start}
            })
            
            return {
                "total": total_clients,
                "active": active_clients,
                "inactive": inactive_clients,
                "pending": pending_clients,
                "this_month": this_month_clients
            }
        except Exception as e:
            logger.error(f"Error getting client statistics: {e}")
            return {
                "total": 0,
                "active": 0,
                "inactive": 0,
                "pending": 0,
                "this_month": 0
            }


# Create a singleton instance
client_service = ClientService() 