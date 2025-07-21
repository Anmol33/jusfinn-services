"""
Inventory Service - Real-time stock management and tracking
"""

import uuid
from decimal import Decimal
from datetime import date, datetime
from typing import Dict, List, Optional, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import and_, func, desc

from ..models import *

class InventoryService:
    """Service for inventory management and stock tracking"""
    
    def __init__(self, db: Session):
        self.db = db
    
    def get_available_stock(self, company_id: uuid.UUID, item_id: uuid.UUID, warehouse_id: Optional[uuid.UUID] = None) -> Decimal:
        """Get current available stock for an item"""
        
        query = self.db.query(CurrentStock).filter(
            and_(
                CurrentStock.company_id == company_id,
                CurrentStock.item_service_id == item_id
            )
        )
        
        if warehouse_id:
            query = query.filter(CurrentStock.warehouse_id == warehouse_id)
        
        stock_records = query.all()
        
        return sum(record.current_quantity for record in stock_records)
    
    def update_stock(
        self,
        company_id: uuid.UUID,
        item_id: uuid.UUID,
        quantity: Decimal,
        rate: Decimal = Decimal('0'),
        movement_type: str = 'STOCK_ADJUSTMENT',
        reference_type: Optional[str] = None,
        reference_id: Optional[uuid.UUID] = None,
        reference_number: Optional[str] = None,
        warehouse_id: Optional[uuid.UUID] = None,
        batch_number: Optional[str] = None,
        expiry_date: Optional[date] = None,
        notes: Optional[str] = None
    ) -> Dict[str, any]:
        """Update stock levels with full audit trail"""
        
        try:
            # Get default warehouse if not specified
            if not warehouse_id:
                warehouse = self.db.query(Warehouse).filter(
                    and_(
                        Warehouse.company_id == company_id,
                        Warehouse.is_default == True,
                        Warehouse.is_active == True
                    )
                ).first()
                
                if not warehouse:
                    raise ValueError("No default warehouse found")
                
                warehouse_id = warehouse.id
            
            # Get current stock level
            current_stock_record = self.db.query(CurrentStock).filter(
                and_(
                    CurrentStock.company_id == company_id,
                    CurrentStock.item_service_id == item_id,
                    CurrentStock.warehouse_id == warehouse_id
                )
            ).first()
            
            current_quantity = current_stock_record.current_quantity if current_stock_record else Decimal('0')
            
            # Calculate new stock level
            if movement_type in ['SALES', 'CONSUMPTION', 'STOCK_ADJUSTMENT_OUT', 'PURCHASE_RETURN']:
                movement_quantity = -abs(quantity)
            else:
                movement_quantity = abs(quantity)
            
            new_quantity = current_quantity + movement_quantity
            
            # Validate stock availability for outward movements
            if new_quantity < 0:
                item = self.db.query(ItemService).filter(ItemService.id == item_id).first()
                raise ValueError(f"Insufficient stock for {item.name}. Available: {current_quantity}, Required: {abs(movement_quantity)}")
            
            # Create stock movement record
            stock_movement = StockMovement(
                company_id=company_id,
                item_service_id=item_id,
                warehouse_id=warehouse_id,
                movement_type=movement_type,
                movement_date=date.today(),
                quantity=movement_quantity,
                rate=rate,
                total_value=movement_quantity * rate,
                reference_type=reference_type,
                reference_id=reference_id,
                reference_number=reference_number,
                stock_before=current_quantity,
                stock_after=new_quantity,
                batch_number=batch_number,
                expiry_date=expiry_date,
                notes=notes
            )
            
            self.db.add(stock_movement)
            
            # Update current stock
            if current_stock_record:
                # Calculate weighted average rate for incoming stock
                if movement_quantity > 0 and rate > 0:
                    total_value = (current_stock_record.current_quantity * current_stock_record.average_rate) + (movement_quantity * rate)
                    current_stock_record.average_rate = total_value / new_quantity if new_quantity > 0 else rate
                
                current_stock_record.current_quantity = new_quantity
                current_stock_record.total_value = new_quantity * current_stock_record.average_rate
                current_stock_record.last_updated = datetime.now()
            else:
                # Create new stock record
                current_stock_record = CurrentStock(
                    company_id=company_id,
                    item_service_id=item_id,
                    warehouse_id=warehouse_id,
                    current_quantity=new_quantity,
                    average_rate=rate,
                    total_value=new_quantity * rate
                )
                self.db.add(current_stock_record)
            
            # Update item master stock levels
            item = self.db.query(ItemService).filter(ItemService.id == item_id).first()
            if item:
                total_stock = self.get_available_stock(company_id, item_id)
                item.current_stock = total_stock
            
            self.db.commit()
            
            return {
                "status": "success",
                "movement_id": stock_movement.id,
                "previous_stock": float(current_quantity),
                "movement_quantity": float(movement_quantity),
                "new_stock": float(new_quantity),
                "average_rate": float(current_stock_record.average_rate)
            }
            
        except Exception as e:
            self.db.rollback()
            raise e
    
    def get_stock_movements(
        self,
        company_id: uuid.UUID,
        item_id: Optional[uuid.UUID] = None,
        warehouse_id: Optional[uuid.UUID] = None,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        movement_type: Optional[str] = None,
        limit: int = 100
    ) -> List[Dict[str, any]]:
        """Get stock movement history with filters"""
        
        query = self.db.query(StockMovement).filter(
            StockMovement.company_id == company_id
        )
        
        if item_id:
            query = query.filter(StockMovement.item_service_id == item_id)
        
        if warehouse_id:
            query = query.filter(StockMovement.warehouse_id == warehouse_id)
        
        if start_date:
            query = query.filter(StockMovement.movement_date >= start_date)
        
        if end_date:
            query = query.filter(StockMovement.movement_date <= end_date)
        
        if movement_type:
            query = query.filter(StockMovement.movement_type == movement_type)
        
        movements = query.order_by(desc(StockMovement.created_at)).limit(limit).all()
        
        result = []
        for movement in movements:
            item = self.db.query(ItemService).filter(ItemService.id == movement.item_service_id).first()
            warehouse = self.db.query(Warehouse).filter(Warehouse.id == movement.warehouse_id).first()
            
            result.append({
                "id": movement.id,
                "movement_date": movement.movement_date.isoformat(),
                "movement_type": movement.movement_type,
                "item_name": item.name,
                "item_code": item.item_code,
                "warehouse_name": warehouse.name,
                "quantity": float(movement.quantity),
                "rate": float(movement.rate),
                "total_value": float(movement.total_value),
                "stock_before": float(movement.stock_before),
                "stock_after": float(movement.stock_after),
                "reference_type": movement.reference_type,
                "reference_number": movement.reference_number,
                "batch_number": movement.batch_number,
                "notes": movement.notes
            })
        
        return result
    
    def get_current_stock_report(
        self,
        company_id: uuid.UUID,
        warehouse_id: Optional[uuid.UUID] = None,
        category_filter: Optional[str] = None,
        low_stock_only: bool = False
    ) -> List[Dict[str, any]]:
        """Generate current stock report"""
        
        query = self.db.query(CurrentStock).filter(
            CurrentStock.company_id == company_id
        )
        
        if warehouse_id:
            query = query.filter(CurrentStock.warehouse_id == warehouse_id)
        
        stock_records = query.all()
        
        result = []
        for stock in stock_records:
            item = self.db.query(ItemService).filter(ItemService.id == stock.item_service_id).first()
            warehouse = self.db.query(Warehouse).filter(Warehouse.id == stock.warehouse_id).first()
            
            # Apply filters
            if category_filter and category_filter.lower() not in item.name.lower():
                continue
            
            if low_stock_only and stock.current_quantity > (item.reorder_level or 0):
                continue
            
            # Calculate stock status
            stock_status = "Normal"
            if stock.current_quantity <= 0:
                stock_status = "Out of Stock"
            elif stock.current_quantity <= (item.reorder_level or 0):
                stock_status = "Low Stock"
            
            result.append({
                "item_id": item.id,
                "item_code": item.item_code,
                "item_name": item.name,
                "warehouse_name": warehouse.name,
                "current_quantity": float(stock.current_quantity),
                "average_rate": float(stock.average_rate),
                "total_value": float(stock.total_value),
                "reorder_level": float(item.reorder_level or 0),
                "unit_of_measure": item.unit_of_measure,
                "stock_status": stock_status,
                "last_updated": stock.last_updated.isoformat() if stock.last_updated else None
            })
        
        return sorted(result, key=lambda x: x["item_name"])
    
    def get_stock_valuation_report(
        self,
        company_id: uuid.UUID,
        warehouse_id: Optional[uuid.UUID] = None,
        as_of_date: Optional[date] = None
    ) -> Dict[str, any]:
        """Generate stock valuation report"""
        
        if not as_of_date:
            as_of_date = date.today()
        
        # Get all stock movements up to the specified date
        movements_query = self.db.query(StockMovement).filter(
            and_(
                StockMovement.company_id == company_id,
                StockMovement.movement_date <= as_of_date
            )
        )
        
        if warehouse_id:
            movements_query = movements_query.filter(StockMovement.warehouse_id == warehouse_id)
        
        movements = movements_query.order_by(StockMovement.movement_date, StockMovement.created_at).all()
        
        # Calculate stock positions as of the date
        stock_positions = {}
        
        for movement in movements:
            key = f"{movement.item_service_id}_{movement.warehouse_id}"
            
            if key not in stock_positions:
                stock_positions[key] = {
                    "item_id": movement.item_service_id,
                    "warehouse_id": movement.warehouse_id,
                    "quantity": Decimal('0'),
                    "total_value": Decimal('0'),
                    "transactions": []
                }
            
            stock_positions[key]["quantity"] += movement.quantity
            stock_positions[key]["total_value"] += movement.total_value
            stock_positions[key]["transactions"].append({
                "date": movement.movement_date,
                "type": movement.movement_type,
                "quantity": movement.quantity,
                "rate": movement.rate,
                "value": movement.total_value
            })
        
        # Prepare report
        report_data = []
        total_inventory_value = Decimal('0')
        
        for key, position in stock_positions.items():
            if position["quantity"] > 0:  # Only include items with positive stock
                item = self.db.query(ItemService).filter(ItemService.id == position["item_id"]).first()
                warehouse = self.db.query(Warehouse).filter(Warehouse.id == position["warehouse_id"]).first()
                
                average_rate = position["total_value"] / position["quantity"] if position["quantity"] > 0 else Decimal('0')
                
                report_data.append({
                    "item_code": item.item_code,
                    "item_name": item.name,
                    "warehouse_name": warehouse.name,
                    "quantity": float(position["quantity"]),
                    "average_rate": float(average_rate),
                    "total_value": float(position["total_value"]),
                    "unit_of_measure": item.unit_of_measure
                })
                
                total_inventory_value += position["total_value"]
        
        return {
            "as_of_date": as_of_date.isoformat(),
            "total_inventory_value": float(total_inventory_value),
            "total_items": len(report_data),
            "items": sorted(report_data, key=lambda x: x["item_name"]),
            "summary_by_warehouse": self._get_warehouse_summary(report_data)
        }
    
    def _get_warehouse_summary(self, report_data: List[Dict[str, any]]) -> List[Dict[str, any]]:
        """Generate warehouse-wise summary"""
        
        warehouse_summary = {}
        
        for item in report_data:
            warehouse_name = item["warehouse_name"]
            
            if warehouse_name not in warehouse_summary:
                warehouse_summary[warehouse_name] = {
                    "warehouse_name": warehouse_name,
                    "total_items": 0,
                    "total_value": 0
                }
            
            warehouse_summary[warehouse_name]["total_items"] += 1
            warehouse_summary[warehouse_name]["total_value"] += item["total_value"]
        
        return list(warehouse_summary.values())
    
    def transfer_stock(
        self,
        company_id: uuid.UUID,
        item_id: uuid.UUID,
        from_warehouse_id: uuid.UUID,
        to_warehouse_id: uuid.UUID,
        quantity: Decimal,
        transfer_reference: Optional[str] = None,
        notes: Optional[str] = None
    ) -> Dict[str, any]:
        """Transfer stock between warehouses"""
        
        try:
            # Validate from warehouse has sufficient stock
            available_stock = self.get_available_stock(company_id, item_id, from_warehouse_id)
            
            if available_stock < quantity:
                raise ValueError(f"Insufficient stock in source warehouse. Available: {available_stock}, Required: {quantity}")
            
            # Get average rate from source warehouse
            source_stock = self.db.query(CurrentStock).filter(
                and_(
                    CurrentStock.company_id == company_id,
                    CurrentStock.item_service_id == item_id,
                    CurrentStock.warehouse_id == from_warehouse_id
                )
            ).first()
            
            transfer_rate = source_stock.average_rate if source_stock else Decimal('0')
            
            # Create outward movement from source warehouse
            outward_result = self.update_stock(
                company_id=company_id,
                item_id=item_id,
                quantity=quantity,
                rate=transfer_rate,
                movement_type='STOCK_TRANSFER',
                reference_type='TRANSFER_OUT',
                reference_number=transfer_reference,
                warehouse_id=from_warehouse_id,
                notes=f"Transfer to warehouse {to_warehouse_id}: {notes}" if notes else f"Transfer to warehouse {to_warehouse_id}"
            )
            
            # Create inward movement to destination warehouse
            inward_result = self.update_stock(
                company_id=company_id,
                item_id=item_id,
                quantity=quantity,
                rate=transfer_rate,
                movement_type='STOCK_TRANSFER',
                reference_type='TRANSFER_IN',
                reference_number=transfer_reference,
                warehouse_id=to_warehouse_id,
                notes=f"Transfer from warehouse {from_warehouse_id}: {notes}" if notes else f"Transfer from warehouse {from_warehouse_id}"
            )
            
            return {
                "status": "success",
                "transfer_reference": transfer_reference,
                "from_warehouse_id": from_warehouse_id,
                "to_warehouse_id": to_warehouse_id,
                "quantity_transferred": float(quantity),
                "transfer_rate": float(transfer_rate),
                "outward_movement_id": outward_result["movement_id"],
                "inward_movement_id": inward_result["movement_id"]
            }
            
        except Exception as e:
            self.db.rollback()
            raise e
    
    def adjust_stock(
        self,
        company_id: uuid.UUID,
        item_id: uuid.UUID,
        warehouse_id: uuid.UUID,
        actual_quantity: Decimal,
        reason: str,
        adjustment_reference: Optional[str] = None,
        notes: Optional[str] = None
    ) -> Dict[str, any]:
        """Adjust stock to match physical count"""
        
        try:
            # Get current system stock
            current_stock = self.get_available_stock(company_id, item_id, warehouse_id)
            
            # Calculate adjustment quantity
            adjustment_quantity = actual_quantity - current_stock
            
            if adjustment_quantity == 0:
                return {
                    "status": "no_adjustment_needed",
                    "current_stock": float(current_stock),
                    "actual_quantity": float(actual_quantity)
                }
            
            # Determine movement type
            movement_type = 'STOCK_ADJUSTMENT'
            
            # Get current average rate
            stock_record = self.db.query(CurrentStock).filter(
                and_(
                    CurrentStock.company_id == company_id,
                    CurrentStock.item_service_id == item_id,
                    CurrentStock.warehouse_id == warehouse_id
                )
            ).first()
            
            adjustment_rate = stock_record.average_rate if stock_record else Decimal('0')
            
            # Create adjustment movement
            adjustment_result = self.update_stock(
                company_id=company_id,
                item_id=item_id,
                quantity=adjustment_quantity,
                rate=adjustment_rate,
                movement_type=movement_type,
                reference_type='STOCK_ADJUSTMENT',
                reference_number=adjustment_reference,
                warehouse_id=warehouse_id,
                notes=f"Stock adjustment - {reason}: {notes}" if notes else f"Stock adjustment - {reason}"
            )
            
            return {
                "status": "success",
                "adjustment_type": "increase" if adjustment_quantity > 0 else "decrease",
                "system_stock": float(current_stock),
                "actual_stock": float(actual_quantity),
                "adjustment_quantity": float(adjustment_quantity),
                "adjustment_reference": adjustment_reference,
                "movement_id": adjustment_result["movement_id"]
            }
            
        except Exception as e:
            self.db.rollback()
            raise e
    
    def get_low_stock_alerts(self, company_id: uuid.UUID) -> List[Dict[str, any]]:
        """Get items with stock below reorder level"""
        
        alerts = []
        
        # Get all current stock records
        stock_records = self.db.query(CurrentStock).filter(
            CurrentStock.company_id == company_id
        ).all()
        
        for stock in stock_records:
            item = self.db.query(ItemService).filter(
                and_(
                    ItemService.id == stock.item_service_id,
                    ItemService.is_active == True,
                    ItemService.type == 'PRODUCT'  # Only for products
                )
            ).first()
            
            if item and item.reorder_level and stock.current_quantity <= item.reorder_level:
                warehouse = self.db.query(Warehouse).filter(Warehouse.id == stock.warehouse_id).first()
                
                alerts.append({
                    "item_id": item.id,
                    "item_code": item.item_code,
                    "item_name": item.name,
                    "warehouse_name": warehouse.name,
                    "current_stock": float(stock.current_quantity),
                    "reorder_level": float(item.reorder_level),
                    "shortage": float(item.reorder_level - stock.current_quantity),
                    "unit_of_measure": item.unit_of_measure,
                    "last_updated": stock.last_updated.isoformat() if stock.last_updated else None
                })
        
        return sorted(alerts, key=lambda x: x["shortage"], reverse=True)
    
    def get_item_movement_history(
        self,
        company_id: uuid.UUID,
        item_id: uuid.UUID,
        days: int = 30
    ) -> Dict[str, any]:
        """Get detailed movement history for an item"""
        
        from datetime import timedelta
        
        end_date = date.today()
        start_date = end_date - timedelta(days=days)
        
        movements = self.get_stock_movements(
            company_id=company_id,
            item_id=item_id,
            start_date=start_date,
            end_date=end_date,
            limit=1000
        )
        
        # Calculate summary statistics
        total_inward = sum(m["quantity"] for m in movements if m["quantity"] > 0)
        total_outward = sum(abs(m["quantity"]) for m in movements if m["quantity"] < 0)
        
        movement_types = {}
        for movement in movements:
            movement_type = movement["movement_type"]
            if movement_type not in movement_types:
                movement_types[movement_type] = {"count": 0, "quantity": 0}
            
            movement_types[movement_type]["count"] += 1
            movement_types[movement_type]["quantity"] += movement["quantity"]
        
        item = self.db.query(ItemService).filter(ItemService.id == item_id).first()
        current_stock = self.get_available_stock(company_id, item_id)
        
        return {
            "item_code": item.item_code,
            "item_name": item.name,
            "current_stock": float(current_stock),
            "period_days": days,
            "total_inward": float(total_inward),
            "total_outward": float(total_outward),
            "net_movement": float(total_inward - total_outward),
            "movement_types": movement_types,
            "movements": movements
        } 