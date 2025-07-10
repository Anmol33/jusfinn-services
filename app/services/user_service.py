from datetime import datetime, timedelta
from typing import Optional
from database import get_database
from models import User, UserResponse
from bson import ObjectId
import logging

logger = logging.getLogger(__name__)


class UserService:
    def __init__(self):
        self.db = None
        self.users_collection = None

    async def _ensure_db_connection(self):
        """Ensure database connection is established."""
        if self.db is None:
            self.db = get_database()
            if self.db is None:
                raise Exception(
                    "Database connection not established. Please ensure the application has started properly.")
            self.users_collection = self.db["user"]

    def _convert_objectid_to_string(self, doc):
        """Convert ObjectId to string in document."""
        if doc and "_id" in doc:
            doc["id"] = str(doc["_id"])
            del doc["_id"]
        return doc

    async def create_user(self, user: User) -> User:
        """Create a new user in the database."""
        await self._ensure_db_connection()
        try:
            user_dict = user.model_dump(exclude={"id"})
            user_dict["created_at"] = datetime.utcnow()
            user_dict["updated_at"] = datetime.utcnow()

            result = await self.users_collection.insert_one(user_dict)
            user.id = str(result.inserted_id)
            return user
        except Exception as e:
            logger.error(f"Error creating user: {e}")
            raise

    async def get_user_by_id(self, user_id: str) -> Optional[User]:
        """Get user by ID."""
        await self._ensure_db_connection()
        try:
            user_doc = await self.users_collection.find_one({"_id": ObjectId(user_id)})
            if user_doc:
                user_doc = self._convert_objectid_to_string(user_doc)
                return User(**user_doc)
            return None
        except Exception as e:
            logger.error(f"Error getting user by ID: {e}")
            return None

    async def get_user_by_google_id(self, google_id: str) -> Optional[User]:
        """Get user by Google ID."""
        await self._ensure_db_connection()
        try:
            user_doc = await self.users_collection.find_one({"google_id": google_id})
            if user_doc:
                user_doc = self._convert_objectid_to_string(user_doc)
                return User(**user_doc)
            return None
        except Exception as e:
            logger.error(f"Error getting user by Google ID: {e}")
            return None

    async def get_user_by_email(self, email: str) -> Optional[User]:
        """Get user by email."""
        await self._ensure_db_connection()
        try:
            user_doc = await self.users_collection.find_one({"email": email})
            if user_doc:
                user_doc = self._convert_objectid_to_string(user_doc)
                return User(**user_doc)
            return None
        except Exception as e:
            logger.error(f"Error getting user by email: {e}")
            return None

    async def update_user_last_login(self, user_id: str) -> bool:
        """Update user's last login timestamp."""
        await self._ensure_db_connection()
        try:
            result = await self.users_collection.update_one(
                {"_id": ObjectId(user_id)},
                {"$set": {"updated_at": datetime.utcnow()}}
            )
            return result.modified_count > 0
        except Exception as e:
            logger.error(f"Error updating user last login: {e}")
            return False

    async def update_user_tokens(self, user_id: str, access_token: str, refresh_token: Optional[str],
                                 expires_in: int) -> bool:
        """Update user's access and refresh tokens."""
        await self._ensure_db_connection()
        try:
            # Calculate token expiry time
            token_expires_at = datetime.utcnow() + timedelta(seconds=expires_in)

            update_data = {
                "access_token": access_token,
                "token_expires_at": token_expires_at,
                "updated_at": datetime.utcnow()
            }

            # Only update refresh_token if provided
            if refresh_token:
                update_data["refresh_token"] = refresh_token

            result = await self.users_collection.update_one(
                {"_id": ObjectId(user_id)},
                {"$set": update_data}
            )
            return result.modified_count > 0
        except Exception as e:
            logger.error(f"Error updating user tokens: {e}")
            return False

    async def refresh_user_tokens(self, user_id: str, new_access_token: str, new_refresh_token: Optional[str],
                                  expires_in: int) -> bool:
        """Refresh user's tokens (for token refresh flow)."""
        return await self.update_user_tokens(user_id, new_access_token, new_refresh_token, expires_in)

    async def get_user_tokens(self, user_id: str) -> Optional[dict]:
        """Get user's current tokens."""
        await self._ensure_db_connection()
        try:
            user_doc = await self.users_collection.find_one(
                {"_id": ObjectId(user_id)},
                {"access_token": 1, "refresh_token": 1, "token_expires_at": 1}
            )
            if user_doc:
                return {
                    "access_token": user_doc.get("access_token"),
                    "refresh_token": user_doc.get("refresh_token"),
                    "token_expires_at": user_doc.get("token_expires_at")
                }
            return None
        except Exception as e:
            logger.error(f"Error getting user tokens: {e}")
            return None

    async def is_token_expired(self, user_id: str) -> bool:
        """Check if user's access token is expired."""
        try:
            tokens = await self.get_user_tokens(user_id)
            if not tokens or not tokens.get("token_expires_at"):
                return True

            return datetime.utcnow() > tokens["token_expires_at"]
        except Exception as e:
            logger.error(f"Error checking token expiry: {e}")
            return True

    async def list_users(self, skip: int = 0, limit: int = 100) -> list[UserResponse]:
        """List all users (paginated)."""
        await self._ensure_db_connection()
        try:
            cursor = self.users_collection.find().skip(skip).limit(limit)
            users = []
            async for user_doc in cursor:
                user_doc = self._convert_objectid_to_string(user_doc)
                user = User(**user_doc)
                users.append(UserResponse(
                    id=user.id,
                    email=user.email,
                    name=user.name,
                    given_name=user.given_name,
                    family_name=user.family_name,
                    picture=user.picture,
                    created_at=user.created_at,
                    updated_at=user.updated_at
                ))
            return users
        except Exception as e:
            logger.error(f"Error listing users: {e}")
            return []

    async def delete_user(self, user_id: str) -> bool:
        """Delete a user from the database."""
        await self._ensure_db_connection()
        try:
            result = await self.users_collection.delete_one({"_id": ObjectId(user_id)})
            return result.deleted_count > 0
        except Exception as e:
            logger.error(f"Error deleting user: {e}")
            return False


# Create a singleton instance
user_service = UserService()