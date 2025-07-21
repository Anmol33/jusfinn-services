from fastapi import APIRouter, Depends, HTTPException, Query, Path
from fastapi.security import HTTPBearer
from typing import List, Optional
from pydantic import BaseModel, Field
from datetime import datetime, date
from enum import Enum
import uuid

router = APIRouter()
security = HTTPBearer()

# Enums
class MovementType(str, Enum):
    OPENING_STOCK = "OPENING_STOCK"
    PURCHASE = "PURCHASE"
    SALES = "SALES"
    SALES_RETURN = "SALES_RETURN"
    PURCHASE_RETURN = "PURCHASE_RETURN"
    STOCK_ADJUSTMENT = "STOCK_ADJUSTMENT"
    STOCK_TRANSFER = "STOCK_TRANSFER"
    MANUFACTURING = "MANUFACTURING"
    CONSUMPTION = "CONSUMPTION"

class AlertType(str, Enum):
    OUT_OF_STOCK = "OUT_OF_STOCK"
    LOW_STOCK = "LOW_STOCK"
    OVERSTOCK = "OVERSTOCK"
    EXPIRY_ALERT = "EXPIRY_ALERT"

# Pydantic models
class StockLevel(BaseModel):
    item_id: str
    item_name: str
    item_code: str
    warehouse_id: str
    warehouse_name: str
    physical_stock: float
    available_stock: float
    reserved_stock: float
    in_transit_stock: float
    average_cost: float
    total_value: float
    reorder_level: float
    max_stock_level: float
    last_updated: datetime

class StockMovement(BaseModel):
    id: str
    item_id: str
    item_name: str
    warehouse_id: str
    warehouse_name: str
    movement_type: MovementType
    movement_date: date
    quantity: float
    rate: float
    total_value: float
    reference_type: Optional[str]
    reference_id: Optional[str]
    reference_number: Optional[str]
    stock_before: float
    stock_after: float
    created_at: datetime

class StockAdjustmentItem(BaseModel):
    item_id: str
    current_quantity: float
    adjusted_quantity: float
    unit_cost: float
    reason: Optional[str] = None

class StockAdjustmentCreate(BaseModel):
    warehouse_id: str
    adjustment_date: date = Field(default_factory=date.today)
    reason: str
    items: List[StockAdjustmentItem] = Field(..., min_items=1)

class StockAlert(BaseModel):
    id: str
    warehouse_name: str
    item_name: str
    item_code: str
    alert_type: AlertType
    current_stock: float
    reorder_level: float
    shortage_quantity: float
    message: str
    created_at: datetime

# Mock databases
stock_levels_db = {
    "stock_1": {
        "id": "stock_1",
        "item_id": "item_1",
        "item_name": "Sample Product A",
        "item_code": "PROD001",
        "warehouse_id": "warehouse_1",
        "warehouse_name": "Main Warehouse",
        "physical_stock": 50.0,
        "available_stock": 45.0,
        "reserved_stock": 5.0,
        "in_transit_stock": 0.0,
        "average_cost": 1000.0,
        "total_value": 50000.0,
        "reorder_level": 10.0,
        "max_stock_level": 100.0,
        "last_updated": datetime.now()
    },
    "stock_2": {
        "id": "stock_2",
        "item_id": "item_2",
        "item_name": "Sample Product B",
        "item_code": "PROD002",
        "warehouse_id": "warehouse_1",
        "warehouse_name": "Main Warehouse",
        "physical_stock": 5.0,
        "available_stock": 5.0,
        "reserved_stock": 0.0,
        "in_transit_stock": 0.0,
        "average_cost": 2000.0,
        "total_value": 10000.0,
        "reorder_level": 15.0,
        "max_stock_level": 50.0,
        "last_updated": datetime.now()
    }
}

movements_db = {}
warehouses_db = {
    "warehouse_1": {
        "id": "warehouse_1",
        "name": "Main Warehouse",
        "address": "123 Warehouse Street",
        "is_default": True
    }
}

@router.get("/companies/{company_id}/inventory/stock-levels", response_model=dict)
async def get_stock_levels(
    company_id: str = Path(...),
    warehouse_id: Optional[str] = Query(None),
    item_id: Optional[str] = Query(None),
    low_stock: Optional[bool] = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    token: str = Depends(security)
):
    """Get stock levels with filters."""
    
    # Filter stock levels
    filtered_stocks = list(stock_levels_db.values())
    
    if warehouse_id:
        filtered_stocks = [s for s in filtered_stocks if s.get("warehouse_id") == warehouse_id]
    
    if item_id:
        filtered_stocks = [s for s in filtered_stocks if s.get("item_id") == item_id]
    
    if low_stock:
        filtered_stocks = [
            s for s in filtered_stocks 
            if s.get("available_stock", 0) <= s.get("reorder_level", 0)
        ]
    
    # Pagination
    total = len(filtered_stocks)
    start = (page - 1) * limit
    end = start + limit
    stocks_page = filtered_stocks[start:end]
    
    return {
        "success": True,
        "data": {
            "stock_levels": stocks_page,
            "pagination": {
                "page": page,
                "limit": limit,
                "total": total,
                "pages": (total + limit - 1) // limit
            }
        },
        "message": f"Retrieved {len(stocks_page)} stock levels",
        "errors": [],
        "meta": {
            "timestamp": datetime.now().isoformat(),
            "request_id": f"req_{uuid.uuid4().hex[:12]}"
        }
    }

@router.get("/companies/{company_id}/inventory/movements", response_model=dict)
async def get_stock_movements(
    company_id: str = Path(...),
    warehouse_id: Optional[str] = Query(None),
    item_id: Optional[str] = Query(None),
    movement_type: Optional[MovementType] = Query(None),
    date_from: Optional[date] = Query(None),
    date_to: Optional[date] = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    token: str = Depends(security)
):
    """Get stock movement history with filters."""
    
    # Filter movements
    filtered_movements = list(movements_db.values())
    
    if warehouse_id:
        filtered_movements = [m for m in filtered_movements if m.get("warehouse_id") == warehouse_id]
    
    if item_id:
        filtered_movements = [m for m in filtered_movements if m.get("item_id") == item_id]
    
    if movement_type:
        filtered_movements = [m for m in filtered_movements if m.get("movement_type") == movement_type]
    
    if date_from:
        filtered_movements = [m for m in filtered_movements if m.get("movement_date") >= date_from]
    
    if date_to:
        filtered_movements = [m for m in filtered_movements if m.get("movement_date") <= date_to]
    
    # Sort by date descending
    filtered_movements.sort(key=lambda x: x.get("created_at", datetime.now()), reverse=True)
    
    # Pagination
    total = len(filtered_movements)
    start = (page - 1) * limit
    end = start + limit
    movements_page = filtered_movements[start:end]
    
    return {
        "success": True,
        "data": {
            "movements": movements_page,
            "pagination": {
                "page": page,
                "limit": limit,
                "total": total,
                "pages": (total + limit - 1) // limit
            }
        },
        "message": f"Retrieved {len(movements_page)} stock movements",
        "errors": [],
        "meta": {
            "timestamp": datetime.now().isoformat(),
            "request_id": f"req_{uuid.uuid4().hex[:12]}"
        }
    }

@router.post("/companies/{company_id}/inventory/adjustments", response_model=dict)
async def create_stock_adjustment(
    company_id: str = Path(...),
    adjustment: StockAdjustmentCreate = ...,
    token: str = Depends(security)
):
    """Create stock adjustment."""
    
    # Validate warehouse exists
    if adjustment.warehouse_id not in warehouses_db:
        raise HTTPException(status_code=404, detail="Warehouse not found")
    
    adjustment_id = str(uuid.uuid4())
    adjustment_number = f"ADJ-{datetime.now().strftime('%Y%m%d')}-{len(movements_db) + 1:04d}"
    
    created_movements = []
    
    for item in adjustment.items:
        # Check if stock record exists
        stock_key = f"{adjustment.warehouse_id}_{item.item_id}"
        
        if stock_key not in stock_levels_db:
            # Create new stock record
            stock_levels_db[stock_key] = {
                "id": stock_key,
                "item_id": item.item_id,
                "item_name": f"Item {item.item_id}",
                "item_code": f"CODE{item.item_id}",
                "warehouse_id": adjustment.warehouse_id,
                "warehouse_name": warehouses_db[adjustment.warehouse_id]["name"],
                "physical_stock": 0.0,
                "available_stock": 0.0,
                "reserved_stock": 0.0,
                "in_transit_stock": 0.0,
                "average_cost": item.unit_cost,
                "total_value": 0.0,
                "reorder_level": 10.0,
                "max_stock_level": 100.0,
                "last_updated": datetime.now()
            }
        
        stock_record = stock_levels_db[stock_key]
        
        # Calculate adjustment quantity
        adjustment_qty = item.adjusted_quantity - item.current_quantity
        
        if adjustment_qty != 0:
            # Create movement record
            movement_id = str(uuid.uuid4())
            movement = {
                "id": movement_id,
                "item_id": item.item_id,
                "item_name": stock_record["item_name"],
                "warehouse_id": adjustment.warehouse_id,
                "warehouse_name": stock_record["warehouse_name"],
                "movement_type": MovementType.STOCK_ADJUSTMENT,
                "movement_date": adjustment.adjustment_date,
                "quantity": adjustment_qty,
                "rate": item.unit_cost,
                "total_value": adjustment_qty * item.unit_cost,
                "reference_type": "ADJUSTMENT",
                "reference_id": adjustment_id,
                "reference_number": adjustment_number,
                "stock_before": item.current_quantity,
                "stock_after": item.adjusted_quantity,
                "notes": item.reason or adjustment.reason,
                "created_at": datetime.now()
            }
            
            movements_db[movement_id] = movement
            created_movements.append(movement)
            
            # Update stock levels
            stock_record.update({
                "physical_stock": item.adjusted_quantity,
                "available_stock": item.adjusted_quantity - stock_record["reserved_stock"],
                "average_cost": item.unit_cost,
                "total_value": item.adjusted_quantity * item.unit_cost,
                "last_updated": datetime.now()
            })
    
    adjustment_record = {
        "id": adjustment_id,
        "adjustment_number": adjustment_number,
        "company_id": company_id,
        "warehouse_id": adjustment.warehouse_id,
        "adjustment_date": adjustment.adjustment_date,
        "reason": adjustment.reason,
        "items_count": len(adjustment.items),
        "movements": created_movements,
        "created_at": datetime.now()
    }
    
    return {
        "success": True,
        "data": adjustment_record,
        "message": "Stock adjustment created successfully",
        "errors": [],
        "meta": {
            "timestamp": datetime.now().isoformat(),
            "request_id": f"req_{uuid.uuid4().hex[:12]}"
        }
    }

@router.get("/companies/{company_id}/inventory/reservations", response_model=dict)
async def get_stock_reservations(
    company_id: str = Path(...),
    warehouse_id: Optional[str] = Query(None),
    item_id: Optional[str] = Query(None),
    reference_type: Optional[str] = Query(None),
    status: Optional[str] = Query("ACTIVE"),
    token: str = Depends(security)
):
    """Get stock reservations."""
    
    # Mock reservations data
    reservations = [
        {
            "id": "res_1",
            "warehouse_id": "warehouse_1",
            "warehouse_name": "Main Warehouse",
            "item_id": "item_1",
            "item_name": "Sample Product A",
            "reference_type": "SALES_ORDER",
            "reference_id": "order_1",
            "reference_number": "SO-2024-25-A-0001",
            "reserved_quantity": 5.0,
            "fulfilled_quantity": 0.0,
            "remaining_quantity": 5.0,
            "status": "ACTIVE",
            "reserved_at": datetime.now(),
            "expires_at": None
        }
    ]
    
    # Apply filters
    if warehouse_id:
        reservations = [r for r in reservations if r.get("warehouse_id") == warehouse_id]
    
    if item_id:
        reservations = [r for r in reservations if r.get("item_id") == item_id]
    
    if reference_type:
        reservations = [r for r in reservations if r.get("reference_type") == reference_type]
    
    if status:
        reservations = [r for r in reservations if r.get("status") == status]
    
    return {
        "success": True,
        "data": {
            "reservations": reservations,
            "total": len(reservations)
        },
        "message": f"Retrieved {len(reservations)} reservations",
        "errors": [],
        "meta": {
            "timestamp": datetime.now().isoformat(),
            "request_id": f"req_{uuid.uuid4().hex[:12]}"
        }
    }

@router.get("/companies/{company_id}/inventory/alerts", response_model=dict)
async def get_stock_alerts(
    company_id: str = Path(...),
    alert_type: Optional[AlertType] = Query(None),
    warehouse_id: Optional[str] = Query(None),
    token: str = Depends(security)
):
    """Get stock alerts."""
    
    alerts = []
    
    # Generate alerts based on current stock levels
    for stock in stock_levels_db.values():
        current_stock = stock.get("available_stock", 0)
        reorder_level = stock.get("reorder_level", 0)
        max_level = stock.get("max_stock_level", 0)
        
        # Out of stock alert
        if current_stock <= 0:
            alerts.append({
                "id": f"alert_{stock['id']}_out_of_stock",
                "warehouse_name": stock["warehouse_name"],
                "item_name": stock["item_name"],
                "item_code": stock["item_code"],
                "alert_type": AlertType.OUT_OF_STOCK,
                "current_stock": current_stock,
                "reorder_level": reorder_level,
                "shortage_quantity": reorder_level - current_stock,
                "message": f"{stock['item_name']} is out of stock",
                "created_at": datetime.now()
            })
        # Low stock alert
        elif current_stock <= reorder_level:
            alerts.append({
                "id": f"alert_{stock['id']}_low_stock",
                "warehouse_name": stock["warehouse_name"],
                "item_name": stock["item_name"],
                "item_code": stock["item_code"],
                "alert_type": AlertType.LOW_STOCK,
                "current_stock": current_stock,
                "reorder_level": reorder_level,
                "shortage_quantity": reorder_level - current_stock,
                "message": f"{stock['item_name']} is below reorder level",
                "created_at": datetime.now()
            })
        # Overstock alert
        elif current_stock >= max_level:
            alerts.append({
                "id": f"alert_{stock['id']}_overstock",
                "warehouse_name": stock["warehouse_name"],
                "item_name": stock["item_name"],
                "item_code": stock["item_code"],
                "alert_type": AlertType.OVERSTOCK,
                "current_stock": current_stock,
                "reorder_level": reorder_level,
                "shortage_quantity": 0,
                "message": f"{stock['item_name']} is overstocked",
                "created_at": datetime.now()
            })
    
    # Apply filters
    if alert_type:
        alerts = [a for a in alerts if a.get("alert_type") == alert_type]
    
    if warehouse_id:
        alerts = [a for a in alerts if stock_levels_db.get(a.get("item_id", {}).get("warehouse_id")) == warehouse_id]
    
    # Sort by severity (out of stock first)
    severity_order = {
        AlertType.OUT_OF_STOCK: 1,
        AlertType.LOW_STOCK: 2,
        AlertType.OVERSTOCK: 3,
        AlertType.EXPIRY_ALERT: 4
    }
    alerts.sort(key=lambda x: severity_order.get(x.get("alert_type"), 5))
    
    return {
        "success": True,
        "data": {
            "alerts": alerts,
            "total": len(alerts),
            "summary": {
                "out_of_stock": len([a for a in alerts if a.get("alert_type") == AlertType.OUT_OF_STOCK]),
                "low_stock": len([a for a in alerts if a.get("alert_type") == AlertType.LOW_STOCK]),
                "overstock": len([a for a in alerts if a.get("alert_type") == AlertType.OVERSTOCK])
            }
        },
        "message": f"Retrieved {len(alerts)} stock alerts",
        "errors": [],
        "meta": {
            "timestamp": datetime.now().isoformat(),
            "request_id": f"req_{uuid.uuid4().hex[:12]}"
        }
    }

@router.post("/companies/{company_id}/inventory/reconciliation", response_model=dict)
async def inventory_reconciliation(
    company_id: str = Path(...),
    warehouse_id: Optional[str] = Query(None),
    reconciliation_date: Optional[date] = Query(None),
    token: str = Depends(security)
):
    """Perform inventory reconciliation."""
    
    if not reconciliation_date:
        reconciliation_date = date.today()
    
    reconciliation_id = str(uuid.uuid4())
    
    # Mock reconciliation results
    reconciliation_items = []
    
    for stock in stock_levels_db.values():
        if warehouse_id and stock.get("warehouse_id") != warehouse_id:
            continue
        
        # Mock calculated vs recorded variance
        calculated_stock = stock.get("physical_stock", 0)
        recorded_stock = calculated_stock + (5 if stock["id"] == "stock_1" else 0)  # Mock variance
        variance = calculated_stock - recorded_stock
        
        if abs(variance) > 0.001:  # Only include items with variance
            reconciliation_items.append({
                "item_id": stock["item_id"],
                "item_name": stock["item_name"],
                "item_code": stock["item_code"],
                "warehouse_id": stock["warehouse_id"],
                "calculated_stock": calculated_stock,
                "recorded_stock": recorded_stock,
                "variance_quantity": variance,
                "variance_value": variance * stock.get("average_cost", 0),
                "unit_cost": stock.get("average_cost", 0)
            })
    
    reconciliation = {
        "id": reconciliation_id,
        "company_id": company_id,
        "warehouse_id": warehouse_id,
        "reconciliation_date": reconciliation_date,
        "total_items_checked": len(stock_levels_db),
        "items_with_variance": len(reconciliation_items),
        "total_variance_value": sum(item["variance_value"] for item in reconciliation_items),
        "reconciliation_items": reconciliation_items,
        "status": "COMPLETED",
        "created_at": datetime.now()
    }
    
    return {
        "success": True,
        "data": reconciliation,
        "message": "Inventory reconciliation completed successfully",
        "errors": [],
        "meta": {
            "timestamp": datetime.now().isoformat(),
            "request_id": f"req_{uuid.uuid4().hex[:12]}"
        }
    } 