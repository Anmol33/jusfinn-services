from datetime import datetime
from typing import Optional, List
from bson import ObjectId
from database import get_database
from models import User, UserResponse


class UserService:
    """Service for handling user data operations."""
    
    def __init__(self):
        self.db = None
        self.collection = None
    
    async def _ensure_db_connection(self):
        """Ensure database connection is established."""
        if self.db is None:
            from database import get_database
            self.db = get_database()
            self.collection = self.db.users
    
    async def create_user(self, user_data: User) -> User:
        """Create a new user in the database."""
        await self._ensure_db_connection()
        user_dict = user_data.dict(exclude={"id"})
        user_dict["updated_at"] = datetime.utcnow()
        
        result = await self.collection.insert_one(user_dict)
        user_dict["_id"] = str(result.inserted_id)
        
        return User(**user_dict)
    
    async def get_user_by_google_id(self, google_id: str) -> Optional[User]:
        """Get user by Google ID."""
        await self._ensure_db_connection()
        user_data = await self.collection.find_one({"google_id": google_id})
        if user_data:
            user_data["_id"] = str(user_data["_id"])
            return User(**user_data)
        return None
    
    async def get_user_by_email(self, email: str) -> Optional[User]:
        """Get user by email."""
        await self._ensure_db_connection()
        user_data = await self.collection.find_one({"email": email})
        if user_data:
            user_data["_id"] = str(user_data["_id"])
            return User(**user_data)
        return None
    
    async def get_user_by_id(self, user_id: str) -> Optional[User]:
        """Get user by ID."""
        await self._ensure_db_connection()
        user_data = await self.collection.find_one({"_id": ObjectId(user_id)})
        if user_data:
            user_data["_id"] = str(user_data["_id"])
            return User(**user_data)
        return None
    
    async def update_user_tokens(self, user_id: str, access_token: str, 
                                refresh_token: Optional[str], expires_at: datetime) -> bool:
        """Update user's access token and refresh token."""
        await self._ensure_db_connection()
        update_data = {
            "access_token": access_token,
            "token_expires_at": expires_at,
            "updated_at": datetime.utcnow()
        }
        if refresh_token:
            update_data["refresh_token"] = refresh_token
        
        result = await self.collection.update_one(
            {"_id": ObjectId(user_id)},
            {"$set": update_data}
        )
        return result.modified_count > 0
    
    async def update_user_last_login(self, user_id: str) -> bool:
        """Update user's last login timestamp."""
        await self._ensure_db_connection()
        result = await self.collection.update_one(
            {"_id": ObjectId(user_id)},
            {"$set": {"updated_at": datetime.utcnow()}}
        )
        return result.modified_count > 0
    
    async def get_all_users(self) -> List[UserResponse]:
        """Get all users (without sensitive data)."""
        await self._ensure_db_connection()
        users = []
        async for user_data in self.collection.find():
            user_data["_id"] = str(user_data["_id"])
            user = User(**user_data)
            users.append(UserResponse(
                id=user.id,
                email=user.email,
                name=user.name,
                given_name=user.given_name,
                family_name=user.family_name,
                picture=user.picture,
                locale=user.locale,
                created_at=user.created_at,
                updated_at=user.updated_at
            ))
        return users
    
    async def delete_user(self, user_id: str) -> bool:
        """Delete a user by ID."""
        await self._ensure_db_connection()
        result = await self.collection.delete_one({"_id": ObjectId(user_id)})
        return result.deleted_count > 0


user_service = UserService() 