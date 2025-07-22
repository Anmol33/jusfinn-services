from fastapi import APIRouter, HTTPException, Depends
from typing import List
from app.models import UserResponse
from app.services.user_service import user_service
from app.services.jwt_service import jwt_service

router = APIRouter(prefix="/users", tags=["Users"])


@router.get("/", response_model=List[UserResponse])
async def get_users(skip: int = 0, limit: int = 100, current_user: dict = Depends(jwt_service.get_current_user)):
    """Get all users (admin only)."""
    try:
        # Check if current user is admin (you can implement admin logic here)
        users = await user_service.list_users(skip=skip, limit=limit)
        return users
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get users: {str(e)}")


@router.get("/me", response_model=UserResponse)
async def get_current_user_info(current_user: dict = Depends(jwt_service.get_current_user)):
    """Get current user information."""
    try:
        user_id = current_user.get("sub")
        user = await user_service.get_user_by_id(user_id)
        
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        return UserResponse(
            id=user.id,
            email=user.email,
            name=user.name,
            given_name=user.given_name,
            family_name=user.family_name,
            picture=user.picture,
            created_at=user.created_at,
            updated_at=user.updated_at
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get user info: {str(e)}")


@router.delete("/{user_id}")
async def delete_user(user_id: str, current_user: dict = Depends(jwt_service.get_current_user)):
    """Delete a user (admin only)."""
    try:
        # Check if current user is admin or is deleting their own account
        current_user_id = current_user.get("sub")
        if current_user_id != user_id:
            # Add admin check here if needed
            raise HTTPException(status_code=403, detail="Not authorized to delete this user")
        
        success = await user_service.delete_user(user_id)
        if not success:
            raise HTTPException(status_code=404, detail="User not found")
        
        return {"message": "User deleted successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete user: {str(e)}")


@router.get("/{user_id}", response_model=UserResponse)
async def get_user(user_id: str, current_user: dict = Depends(jwt_service.get_current_user)):
    """Get a specific user by ID."""
    try:
        # Check if current user is requesting their own data or is admin
        current_user_id = current_user.get("sub")
        if current_user_id != user_id:
            # Add admin check here if needed
            raise HTTPException(status_code=403, detail="Not authorized to view this user")
        
        user = await user_service.get_user_by_id(user_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        return UserResponse(
            id=user.id,
            email=user.email,
            name=user.name,
            given_name=user.given_name,
            family_name=user.family_name,
            picture=user.picture,
            created_at=user.created_at,
            updated_at=user.updated_at
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get user: {str(e)}") 