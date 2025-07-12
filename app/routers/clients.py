from fastapi import APIRouter, HTTPException, Depends, Query
from typing import List, Optional
from services.client_service import client_service
from services.user_service import user_service
from services.jwt_service import jwt_service
from models import ClientResponse, ClientCreateRequest, ClientUpdateRequest

router = APIRouter(prefix="/clients", tags=["Clients"])


async def get_user_google_id(token: dict = Depends(jwt_service.get_current_user)) -> str:
    """Helper function to get user's Google ID from JWT token."""
    try:
        user_id = token.get("sub")
        if not user_id:
            raise HTTPException(status_code=401, detail="Invalid token: missing user ID")
        
        user = await user_service.get_user_by_id(user_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        return user.google_id
    except Exception as e:
        raise HTTPException(status_code=401, detail=f"Invalid token: {str(e)}")


@router.post("/", response_model=ClientResponse)
async def create_client(
    client_data: ClientCreateRequest,
    user_google_id: str = Depends(get_user_google_id)
):
    """Create a new client."""
    try:
        client = await client_service.create_client(client_data, user_google_id)
        return client
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to create client: {str(e)}")


@router.get("/", response_model=List[ClientResponse])
async def get_clients(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=100),
    status: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    user_google_id: str = Depends(get_user_google_id)
):
    """Get all clients for the current user with optional filtering."""
    try:
        if search:
            clients = await client_service.search_clients(user_google_id, search, skip, limit)
        elif status:
            clients = await client_service.get_clients_by_status(user_google_id, status, skip, limit)
        else:
            clients = await client_service.get_clients_by_user(user_google_id, skip, limit)
        
        return clients
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to get clients: {str(e)}")


@router.get("/{client_id}", response_model=ClientResponse)
async def get_client(
    client_id: str,
    user_google_id: str = Depends(get_user_google_id)
):
    """Get a specific client by ID."""
    try:
        client = await client_service.get_client_by_id(client_id, user_google_id)
        if not client:
            raise HTTPException(status_code=404, detail="Client not found")
        return client
    except Exception as e:
        if "Client not found" in str(e):
            raise e
        raise HTTPException(status_code=400, detail=f"Failed to get client: {str(e)}")


@router.put("/{client_id}", response_model=ClientResponse)
async def update_client(
    client_id: str,
    client_data: ClientUpdateRequest,
    user_google_id: str = Depends(get_user_google_id)
):
    """Update an existing client."""
    try:
        client = await client_service.update_client(client_id, client_data, user_google_id)
        if not client:
            raise HTTPException(status_code=404, detail="Client not found")
        return client
    except Exception as e:
        if "Client not found" in str(e):
            raise e
        raise HTTPException(status_code=400, detail=f"Failed to update client: {str(e)}")


@router.delete("/{client_id}")
async def delete_client(
    client_id: str,
    user_google_id: str = Depends(get_user_google_id)
):
    """Delete a client."""
    try:
        success = await client_service.delete_client(client_id, user_google_id)
        if not success:
            raise HTTPException(status_code=404, detail="Client not found")
        return {"message": "Client deleted successfully"}
    except Exception as e:
        if "Client not found" in str(e):
            raise e
        raise HTTPException(status_code=400, detail=f"Failed to delete client: {str(e)}")


@router.get("/stats/count")
async def get_client_count(
    user_google_id: str = Depends(get_user_google_id)
):
    """Get total number of clients for the current user."""
    try:
        count = await client_service.get_client_count(user_google_id)
        return {"count": count}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to get client count: {str(e)}")


@router.get("/stats/by-status")
async def get_clients_stats(
    user_google_id: str = Depends(get_user_google_id)
):
    """Get client statistics by status."""
    try:
        active_clients = await client_service.get_clients_by_status(user_google_id, "active")
        inactive_clients = await client_service.get_clients_by_status(user_google_id, "inactive")
        pending_clients = await client_service.get_clients_by_status(user_google_id, "pending")
        
        return {
            "active": len(active_clients),
            "inactive": len(inactive_clients),
            "pending": len(pending_clients),
            "total": len(active_clients) + len(inactive_clients) + len(pending_clients)
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to get client statistics: {str(e)}")


@router.get("/stats/dashboard")
async def get_dashboard_statistics(
    user_google_id: str = Depends(get_user_google_id)
):
    """Get comprehensive client statistics for dashboard."""
    try:
        stats = await client_service.get_client_statistics(user_google_id)
        return stats
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to get dashboard statistics: {str(e)}") 