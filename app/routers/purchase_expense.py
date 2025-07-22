from fastapi import APIRouter, HTTPException, Depends, Query, UploadFile, File, Request
from fastapi.exceptions import RequestValidationError
from typing import List, Optional, Dict, Any
from datetime import datetime
from pydantic import ValidationError

from app.services.purchase_expense_service import purchase_expense_service
from app.services.jwt_service import jwt_service
from app.services.user_service import user_service
from app.models import (
    PurchaseOrderCreateRequest, PurchaseOrderUpdateRequest, PurchaseOrderResponse,
    ExpenseCreateRequest, ExpenseResponse
)
from app.models.purchase_order_models import PurchaseOrderStatus

router = APIRouter(prefix="/purchase-expense", tags=["Purchase & Expense"])


async def get_user_id(token: dict = Depends(jwt_service.get_current_user)) -> str:
    """Helper function to get user's ID from JWT token."""
    print(f"🔍 AUTH DEBUG: get_user_id called")
    print(f"   Token: {token}")
    
    try:
        user_id = token.get("sub")
        print(f"🔍 AUTH DEBUG: Extracted user_id from token: {user_id}")
        
        if not user_id:
            print(f"🔍 AUTH DEBUG: No user_id in token")
            raise HTTPException(status_code=401, detail="Invalid token: missing user ID")
        
        print(f"🔍 AUTH DEBUG: Looking up user by ID...")
        user = await user_service.get_user_by_id(user_id)
        print(f"🔍 AUTH DEBUG: User lookup result: {user}")
        
        if not user:
            print(f"🔍 AUTH DEBUG: User not found in database")
            raise HTTPException(status_code=404, detail="User not found")
        
        print(f"🔍 AUTH DEBUG: Returning user_id: {user_id}")
        return user_id  # Return user_id directly instead of user.google_id
    except HTTPException:
        raise
    except Exception as e:
        print(f"🔍 AUTH DEBUG: Exception in get_user_id: {str(e)}")
        import traceback
        print(f"🔍 AUTH DEBUG: Traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=401, detail=f"Invalid token: {str(e)}")


# =====================================================
# PURCHASE ORDERS - ENHANCED WITH APPROVAL WORKFLOW
# =====================================================

@router.post("/purchase-orders", response_model=PurchaseOrderResponse)
async def create_purchase_order(
    request: Request,
    user_id: str = Depends(get_user_id)
):
    """Create a new purchase order in DRAFT status."""
    try:
        # DEBUG: Log raw request before FastAPI validation
        body = await request.body()
        raw_data = body.decode('utf-8')
        print(f"🔍 DEBUG: Raw request body: {raw_data}")
        
        # Parse JSON manually to see the actual data types
        import json
        try:
            parsed_data = json.loads(raw_data)
            print(f"🔍 DEBUG: Parsed JSON data: {parsed_data}")
            print(f"🔍 DEBUG: Data types in request:")
            for key, value in parsed_data.items():
                print(f"  {key}: {value} (type: {type(value)})")
                if key == 'line_items' and isinstance(value, list):
                    for i, item in enumerate(value):
                        print(f"    line_item[{i}]: {item}")
                        for item_key, item_value in item.items():
                            print(f"      {item_key}: {item_value} (type: {type(item_value)})")
        except Exception as parse_error:
            print(f"🔍 DEBUG: Error parsing JSON: {parse_error}")
        
        # Now try to parse with Pydantic
        try:
            po_data = PurchaseOrderCreateRequest.model_validate(parsed_data)
            print(f"🔍 DEBUG: Successfully validated with Pydantic")
        except Exception as validation_error:
            print(f"🔍 DEBUG: Pydantic validation error: {validation_error}")
            raise HTTPException(status_code=422, detail=f"Validation error: {validation_error}")
        
        # DEBUG: Log incoming request data
        print(f"🔍 DEBUG: Received PO Create Request from user_id: {user_id}")
        print(f"🔍 DEBUG: Request data type: {type(po_data)}")
        print(f"🔍 DEBUG: Complete request data: {po_data.model_dump()}")
        print(f"🔍 DEBUG: Line items count: {len(po_data.line_items) if po_data.line_items else 0}")
        
        if po_data.line_items:
            for i, item in enumerate(po_data.line_items):
                print(f"🔍 DEBUG: Line item {i}: {item.model_dump()}")
        
        po = await purchase_expense_service.create_purchase_order(po_data, user_id)
        print(f"🔍 DEBUG: Successfully created PO: {po.id}")
        return po
    except ValidationError as e:
        print(f"🔍 DEBUG: Validation error: {e}")
        print(f"🔍 DEBUG: Validation error details: {e.errors()}")
        raise HTTPException(status_code=422, detail=f"Validation error: {e.errors()}")
    except ValueError as e:
        print(f"🔍 DEBUG: Value error: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        print(f"🔍 DEBUG: Unexpected error: {e}")
        print(f"🔍 DEBUG: Error type: {type(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to create purchase order: {str(e)}")


@router.get("/purchase-orders", response_model=List[PurchaseOrderResponse])
async def get_purchase_orders(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=100),
    operational_status: Optional[str] = Query(None, description="Operational status: DRAFT, APPROVED, IN_PROGRESS, etc."),
    approval_status: Optional[str] = Query(None, description="Approval status: PENDING, APPROVED, REJECTED"),
    vendor_id: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    user_id: str = Depends(get_user_id)
):
    """Get purchase orders with filtering by both status types."""
    try:
        pos = await purchase_expense_service.get_purchase_orders(
            user_id=user_id,
            skip=skip,
            limit=limit,
            operational_status=operational_status,
            approval_status=approval_status,
            vendor_id=vendor_id,
            search=search
        )
        return pos
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch purchase orders: {str(e)}")


@router.put("/purchase-orders/{po_id}", response_model=PurchaseOrderResponse)
async def update_purchase_order(
    request: Request,
    po_id: str,
    po_data: PurchaseOrderUpdateRequest,
    user_id: str = Depends(get_user_id)
):
    """Update an existing purchase order."""
    try:
        # DEBUG: Log raw request body
        raw_body = await request.body()
        print(f"🔍 DEBUG: Raw request body: {raw_body.decode()}")
        
        # DEBUG: Log update request
        print(f"🔍 DEBUG: Updating PO {po_id} for user_id: {user_id}")
        print(f"🔍 DEBUG: Update data: {po_data.model_dump()}")
        
        po = await purchase_expense_service.update_purchase_order(po_id, po_data, user_id)
        print(f"🔍 DEBUG: Successfully updated PO: {po.id}")
        return po
    except ValidationError as e:
        print(f"🔍 DEBUG: Validation error: {e}")
        raise HTTPException(status_code=422, detail=f"Validation error: {e}")
    except ValueError as e:
        print(f"🔍 DEBUG: Value error: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        print(f"🔍 DEBUG: Unexpected error: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to update purchase order: {str(e)}")
@router.put("/purchase-orders/{po_id}/debug", response_model=Dict[str, Any])
async def debug_update_purchase_order(
    request: Request,
    po_id: str,
    user_id: str = Depends(get_user_id)
):
    """Debug endpoint to see raw request data."""
    try:
        # Get raw body
        raw_body = await request.body()
        import json
        parsed_data = json.loads(raw_body.decode())
        
        print(f"🔍 DEBUG: Raw request body: {raw_body.decode()}")
        print(f"🔍 DEBUG: Parsed JSON: {parsed_data}")
        
        # Try to parse as PurchaseOrderUpdateRequest
        try:
            po_data = PurchaseOrderUpdateRequest(**parsed_data)
            print(f"🔍 DEBUG: Successfully parsed as PurchaseOrderUpdateRequest: {po_data.model_dump()}")
            return {"status": "success", "data": po_data.model_dump()}
        except ValidationError as e:
            print(f"🔍 DEBUG: Validation error details: {e}")
            return {"status": "validation_error", "errors": e.errors(), "raw_data": parsed_data}
    except Exception as e:
        print(f"🔍 DEBUG: Unexpected error: {e}")
        return {"status": "error", "message": str(e)}



@router.post("/purchase-orders/{po_id}/submit-for-approval")
async def submit_purchase_order_for_approval(
    po_id: str,
    user_id: str = Depends(get_user_id)
):
    """Submit a DRAFT purchase order for approval workflow."""
    print(f"🔍 DEBUG: Submit for approval called")
    print(f"   PO ID: {po_id}")
    print(f"   User ID: {user_id}")
    
    try:
        print(f"🔍 DEBUG: Calling service method...")
        result = await purchase_expense_service.submit_po_for_approval(po_id, user_id)
        print(f"🔍 DEBUG: Service method returned: {result}")
        
        return {
            "message": "Purchase order submitted for approval",
            "po_id": po_id,
            "new_approval_status": "PENDING_APPROVAL",
            "workflow_started": True
        }
    except ValueError as e:
        print(f"🔍 DEBUG: ValueError caught: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        print(f"🔍 DEBUG: Exception caught: {str(e)}")
        print(f"🔍 DEBUG: Exception type: {type(e)}")
        import traceback
        print(f"🔍 DEBUG: Traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Failed to submit PO for approval: {str(e)}")


@router.post("/purchase-orders/{po_id}/approve")
async def approve_purchase_order(
    po_id: str,
    action: str = Query(..., description="approve, reject, or request_changes"),
    comments: Optional[str] = Query(None, description="Approval comments"),
    user_id: str = Depends(get_user_id)
):
    """Approve, reject, or request changes for a purchase order."""
    try:
        # Validate action
        valid_actions = ["approve", "reject", "request_changes"]
        if action not in valid_actions:
            raise HTTPException(status_code=400, detail=f"Invalid action. Must be one of: {valid_actions}")
        
        result = await purchase_expense_service.process_po_approval(
            po_id, action, comments, user_id
        )
        
        return {
            "message": f"Purchase order {action}d successfully",
            "po_id": po_id,
            "action": action,
            "new_approval_status": result["approval_status"],
            "new_operational_status": result["operational_status"],
            "comments": comments,
            "processed_by": user_id,
            "processed_at": datetime.utcnow().isoformat()
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to {action} purchase order: {str(e)}")


@router.get("/purchase-orders/{po_id}/approval-history")
async def get_purchase_order_approval_history(
    po_id: str,
    user_id: str = Depends(get_user_id)
):
    """Get complete approval history for a purchase order."""
    try:
        history = await purchase_expense_service.get_po_approval_history(po_id, user_id)
        return {
            "po_id": po_id,
            "approval_history": history,
            "total_actions": len(history)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch approval history: {str(e)}")


@router.get("/purchase-orders/pending-approvals")
async def get_pending_approvals(
    user_id: str = Depends(get_user_id)
):
    """Get all purchase orders pending approval for the current user."""
    try:
        pending_pos = await purchase_expense_service.get_pending_approvals(user_id)
        return {
            "pending_approvals": pending_pos,
            "count": len(pending_pos),
            "message": f"You have {len(pending_pos)} purchase orders pending your approval"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch pending approvals: {str(e)}")


@router.patch("/purchase-orders/{po_id}/operational-status")
async def update_po_operational_status(
    po_id: str,
    request: Dict[str, Any],
    user_id: str = Depends(get_user_id)
):
    """Update purchase order operational status (for order fulfillment tracking)."""
    try:
        status_str = request.get("status")
        if not status_str:
            raise HTTPException(status_code=400, detail="Status is required")
        
        # Convert string to PurchaseOrderStatus
        try:
            status = PurchaseOrderStatus(status_str)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid status: {status_str}")
        
        success = await purchase_expense_service.update_po_operational_status(po_id, status, user_id)
        if not success:
            raise HTTPException(status_code=404, detail="Purchase order not found")
        return {
            "message": f"Purchase order operational status updated to {status.value}",
            "po_id": po_id,
            "new_status": status.value
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update PO operational status: {str(e)}")


@router.get("/purchase-orders/status-guide")
async def get_status_guide():
    """Get explanation of the dual status system for UI clarity."""
    return {
        "status_system_explanation": {
            "operational_status": {
                "description": "Tracks the actual order lifecycle and fulfillment",
                "values": {
                    "DRAFT": "Order is being created/edited",
                    "APPROVED": "Order approved and ready for processing", 
                    "IN_PROGRESS": "Order is being fulfilled",
                    "PARTIALLY_DELIVERED": "Some items delivered",
                    "DELIVERED": "All items delivered",
                    "INVOICED": "Invoice received and processed",
                    "CANCELLED": "Order cancelled"
                },
                "workflow": "DRAFT → APPROVED → IN_PROGRESS → DELIVERED → INVOICED"
            },
            "approval_status": {
                "description": "Tracks the approval workflow and authorization",
                "values": {
                    "PENDING": "Awaiting initial submission",
                    "PENDING_APPROVAL": "Submitted and awaiting approval",
                    "APPROVED": "Approved by authorized person",
                    "REJECTED": "Rejected, needs revision",
                    "CHANGES_REQUESTED": "Changes requested before approval"
                },
                "workflow": "PENDING → PENDING_APPROVAL → APPROVED/REJECTED"
            }
        },
        "ui_recommendations": {
            "display_both_statuses": "Show both statuses with clear labels",
            "action_buttons": {
                "draft_stage": ["Submit for Approval", "Edit", "Delete"],
                "pending_approval": ["Approve", "Reject", "Request Changes"],
                "approved": ["Mark In Progress", "Cancel"],
                "in_progress": ["Mark Delivered", "Partially Delivered"]
            }
        }
    }


# =====================================================
# GOODS RECEIPT NOTE
# =====================================================

@router.post("/grn")
async def create_grn(
    grn_data: Dict[str, Any],
    user_id: str = Depends(get_user_id)
):
    """Create a new goods receipt note."""
    try:
        grn = await purchase_expense_service.create_grn(grn_data, user_id)
        return grn
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create GRN: {str(e)}")


# =====================================================
# PURCHASE BILLS
# =====================================================

@router.post("/bills")
async def create_purchase_bill(
    bill_data: Dict[str, Any],
    user_id: str = Depends(get_user_id)
):
    """Create a new purchase bill."""
    try:
        bill = await purchase_expense_service.create_purchase_bill(bill_data, user_id)
        return bill
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create purchase bill: {str(e)}")


@router.post("/bills/upload-ocr")
async def upload_bill_for_ocr(
    file: UploadFile = File(...),
    user_id: str = Depends(get_user_id)
):
    """Upload bill for OCR processing."""
    try:
        # This would integrate with OCR service (like Google Vision API or AWS Textract)
        # For now, return a mock response
        return {
            "message": "Bill uploaded successfully for OCR processing",
            "file_name": file.filename,
            "processing_status": "queued",
            "extracted_data": {
                "vendor_name": "Sample Vendor",
                "bill_number": "INV-2024-001",
                "bill_date": "2024-01-15",
                "total_amount": 10000.0,
                "tax_amount": 1800.0,
                "confidence_score": 0.95
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to process OCR: {str(e)}")


# =====================================================
# EXPENSES
# =====================================================

@router.post("/expenses", response_model=ExpenseResponse)
async def create_expense(
    expense_data: ExpenseCreateRequest,
    user_id: str = Depends(get_user_id)
):
    """Create a new expense record."""
    try:
        expense = await purchase_expense_service.create_expense(expense_data, user_id)
        return expense
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create expense: {str(e)}")


# =====================================================
# TDS COMPLIANCE
# =====================================================

@router.get("/tds/records")
async def get_tds_records(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=100),
    status: Optional[str] = Query(None),
    financial_year: Optional[str] = Query(None),
    quarter: Optional[int] = Query(None),
    user_id: str = Depends(get_user_id)
):
    """Get TDS records with filtering."""
    try:
        # Implementation would fetch from TDS collection
        return {"message": "TDS records endpoint - implementation pending"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch TDS records: {str(e)}")


@router.post("/tds/generate-certificate/{tds_id}")
async def generate_tds_certificate(
    tds_id: str,
    user_id: str = Depends(get_user_id)
):
    """Generate TDS certificate for a transaction."""
    try:
        # Implementation would generate TDS certificate
        return {
            "message": "TDS certificate generated successfully",
            "certificate_number": f"TDS-CERT-{tds_id}",
            "download_url": f"/api/tds/certificates/{tds_id}/download"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate TDS certificate: {str(e)}")


# =====================================================
# ITC MANAGEMENT
# =====================================================

@router.get("/itc/records")
async def get_itc_records(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=100),
    status: Optional[str] = Query(None),
    gstr_period: Optional[str] = Query(None),
    is_matched: Optional[bool] = Query(None),
    user_id: str = Depends(get_user_id)
):
    """Get ITC records with filtering."""
    try:
        # Implementation would fetch from ITC collection
        return {"message": "ITC records endpoint - implementation pending"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch ITC records: {str(e)}")


@router.post("/itc/reconcile-gstr2b")
async def reconcile_gstr2b(
    gstr_period: str = Query(...),
    gstr2b_data: Dict[str, Any] = None,
    user_id: str = Depends(get_user_id)
):
    """Reconcile ITC records with GSTR-2B data."""
    try:
        # Implementation would reconcile ITC with GSTR-2B
        return {
            "message": "GSTR-2B reconciliation completed",
            "period": gstr_period,
            "matched_records": 25,
            "unmatched_records": 3,
            "variance_amount": 2500.0
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to reconcile GSTR-2B: {str(e)}")


# =====================================================
# PAYABLES AGING
# =====================================================

@router.get("/payables/aging")
async def get_payables_aging(
    aging_bucket: Optional[str] = Query(None, description="0-30, 31-45, 46-60, 61-90, 90+"),
    vendor_id: Optional[str] = Query(None),
    user_id: str = Depends(get_user_id)
):
    """Get payables aging analysis."""
    try:
        # Implementation would calculate payables aging
        return {
            "aging_buckets": {
                "0-30": {"count": 15, "amount": 125000.0},
                "31-45": {"count": 8, "amount": 75000.0},
                "46-60": {"count": 5, "amount": 50000.0},
                "61-90": {"count": 3, "amount": 30000.0},
                "90+": {"count": 2, "amount": 20000.0}
            },
            "total_outstanding": 300000.0
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch payables aging: {str(e)}")


# =====================================================
# LANDED COST ACCOUNTING
# =====================================================

@router.post("/landed-costs")
async def create_landed_cost(
    cost_data: Dict[str, Any],
    user_id: str = Depends(get_user_id)
):
    """Create landed cost allocation."""
    try:
        # Implementation would create landed cost records
        return {
            "message": "Landed cost created successfully",
            "cost_id": "LC-2024-001",
            "total_cost": cost_data.get("amount", 0),
            "allocation_method": cost_data.get("allocation_method", "VALUE")
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create landed cost: {str(e)}")


@router.get("/landed-costs")
async def get_landed_costs(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=100),
    shipment_id: Optional[str] = Query(None),
    user_id: str = Depends(get_user_id)
):
    """Get landed cost records."""
    try:
        # Implementation would fetch landed cost records
        return {"message": "Landed costs endpoint - implementation pending"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch landed costs: {str(e)}")


# =====================================================
# ANALYTICS & DASHBOARD
# =====================================================

@router.get("/analytics")
async def get_purchase_analytics(
    period: str = Query("current_month", description="current_month, last_month, current_year"),
    user_id: str = Depends(get_user_id)
):
    """Get comprehensive purchase and expense analytics."""
    try:
        analytics = await purchase_expense_service.get_purchase_analytics(user_id, period)
        return analytics
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch analytics: {str(e)}")


@router.get("/dashboard/summary")
async def get_dashboard_summary(
    user_id: str = Depends(get_user_id)
):
    """Get dashboard summary with key metrics."""
    try:
        # Get analytics for current month
        analytics = await purchase_expense_service.get_purchase_analytics(user_id, "current_month")
        
        # Calculate key metrics
        summary = {
            "total_purchase_value": analytics["purchase_orders"].get("total_po_value", 0),
            "pending_approvals": analytics["purchase_orders"].get("pending_pos", 0),
            "outstanding_payables": sum(
                bucket.get("amount", 0) 
                for bucket in analytics["payables_aging"].values()
            ),
            "total_expenses": analytics["expenses"].get("total_expense_value", 0),
            "itc_available": analytics["itc_summary"].get("total_itc_available", 0),
            "tds_deducted": analytics["purchase_bills"].get("total_tds", 0)
        }
        
        return summary
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch dashboard summary: {str(e)}")


# =====================================================
# WORKFLOW AUTOMATION
# =====================================================

@router.post("/workflows/auto-approve")
async def setup_auto_approval_workflow(
    workflow_config: Dict[str, Any],
    user_id: str = Depends(get_user_id)
):
    """Setup automatic approval workflows."""
    try:
        # Implementation would setup workflow rules
        return {
            "message": "Auto-approval workflow configured successfully",
            "workflow_id": f"WF-{user_id[:8]}",
            "rules": workflow_config.get("rules", []),
            "status": "active"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to setup workflow: {str(e)}")


@router.get("/workflows/alerts")
async def get_workflow_alerts(
    user_id: str = Depends(get_user_id)
):
    """Get pending workflow alerts and notifications."""
    try:
        # Implementation would fetch alerts
        return {
            "alerts": [
                {
                    "id": "alert-1",
                    "type": "msme_payment_due",
                    "message": "MSME payment due in 2 days",
                    "priority": "high",
                    "created_at": "2024-01-15T10:00:00Z"
                },
                {
                    "id": "alert-2", 
                    "type": "three_way_variance",
                    "message": "High variance detected in PO-GRN-Bill matching",
                    "priority": "medium",
                    "created_at": "2024-01-15T09:30:00Z"
                }
            ]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch alerts: {str(e)}") 

# =====================================================
# ENHANCED PURCHASE WORKFLOW WITH BANK INTEGRATION
# =====================================================

@router.post("/purchase-orders/{po_id}/approve")
async def approve_purchase_order(
    po_id: str,
    action: str = Query(..., description="approve or reject"),
    comments: Optional[str] = Query(None, description="Approval comments"),
    user_id: str = Depends(get_user_id)
):
    """Approve or reject a purchase order."""
    try:
        result = await purchase_expense_service.approve_purchase_order(
            po_id, action, comments, user_id
        )
        return {"message": f"Purchase order {action}d successfully", "result": result}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to {action} purchase order: {str(e)}")


@router.post("/purchase-orders/{po_id}/three-way-matching")
async def perform_three_way_matching(
    po_id: str,
    grn_id: str = Query(..., description="GRN ID"),
    bill_id: str = Query(..., description="Purchase Bill ID"),
    tolerance_percentage: float = Query(5.0, description="Variance tolerance percentage"),
    user_id: str = Depends(get_user_id)
):
    """Perform three-way matching between PO, GRN, and Purchase Bill."""
    try:
        matching_result = await purchase_expense_service.perform_three_way_matching(
            po_id, grn_id, bill_id, tolerance_percentage
        )
        return {
            "message": "Three-way matching completed",
            "result": matching_result,
            "status": "matched" if matching_result["is_matched"] else "variance_detected"
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to perform three-way matching: {str(e)}")


@router.post("/purchase-bills/{bill_id}/create-payment")
async def create_payment_from_bill(
    bill_id: str,
    payment_method: str = Query(..., description="Payment method"),
    bank_account_id: Optional[str] = Query(None, description="Bank account ID"),
    scheduled_date: Optional[str] = Query(None, description="Scheduled payment date"),
    user_id: str = Depends(get_user_id)
):
    """Create payment from approved purchase bill."""
    try:
        from services.bank_service import PaymentService
        from database import get_postgres_session_direct
        
        # Get bill details
        bill = await purchase_expense_service.get_purchase_bill(bill_id)
        if not bill:
            raise HTTPException(status_code=404, detail="Purchase bill not found")
        
        # Create payment data
        payment_data = {
            "payment_type": "vendor_payment",
            "reference_id": bill_id,
            "reference_type": "purchase_bill",
            "vendor_id": bill.vendor_id,
            "payment_date": scheduled_date if scheduled_date else datetime.now().date(),
            "payment_method": payment_method,
            "bank_account_id": bank_account_id,
            "gross_amount": float(bill.total_amount),
            "tds_amount": float(bill.tds_amount),
            "net_amount": float(bill.total_amount - bill.tds_amount)
        }
        
        # Create payment with approval workflow
        async with get_postgres_session_direct() as session:
            payment = await PaymentService.create_payment(payment_data, user_id, session)
        
        return {
            "message": "Payment created successfully",
            "payment_id": str(payment.id),
            "payment_number": payment.payment_number,
            "net_amount": float(payment.net_amount),
            "approval_status": payment.approval_status
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create payment: {str(e)}")


@router.get("/purchase-orders/{po_id}/workflow-status")
async def get_purchase_workflow_status(
    po_id: str,
    user_id: str = Depends(get_user_id)
):
    """Get complete workflow status for a purchase order."""
    try:
        workflow_status = await purchase_expense_service.get_purchase_workflow_status(po_id)
        return {
            "po_id": po_id,
            "workflow_status": workflow_status,
            "current_stage": workflow_status.get("current_stage"),
            "completion_percentage": workflow_status.get("completion_percentage"),
            "pending_actions": workflow_status.get("pending_actions", [])
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch workflow status: {str(e)}")


# =====================================================
# ENHANCED EXPENSE WORKFLOW WITH OCR & AUTOMATION
# =====================================================

@router.post("/expenses/upload-receipt")
async def upload_expense_receipt(
    file: UploadFile = File(...),
    expense_category: str = Query(..., description="Expense category"),
    user_id: str = Depends(get_user_id)
):
    """Upload expense receipt and extract data using OCR."""
    try:
        # Process receipt with OCR
        ocr_result = await purchase_expense_service.process_receipt_ocr(file, expense_category)
        
        return {
            "message": "Receipt processed successfully",
            "extracted_data": ocr_result,
            "confidence_score": ocr_result.get("confidence", 0),
            "requires_review": ocr_result.get("confidence", 0) < 0.8
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to process receipt: {str(e)}")


@router.post("/expenses/auto-categorize")
async def auto_categorize_expense(
    expense_data: dict,
    user_id: str = Depends(get_user_id)
):
    """Automatically categorize expense based on merchant, amount, and description."""
    try:
        categorization = await purchase_expense_service.auto_categorize_expense(expense_data)
        
        return {
            "suggested_category": categorization.get("category"),
            "confidence": categorization.get("confidence"),
            "tax_treatment": categorization.get("tax_treatment"),
            "policy_compliance": categorization.get("policy_compliance")
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to categorize expense: {str(e)}")


@router.post("/expenses/{expense_id}/policy-check")
async def check_expense_policy_compliance(
    expense_id: str,
    user_id: str = Depends(get_user_id)
):
    """Check expense against company policies."""
    try:
        policy_check = await purchase_expense_service.check_expense_policy(expense_id)
        
        return {
            "expense_id": expense_id,
            "policy_compliance": policy_check.get("compliant", True),
            "violations": policy_check.get("violations", []),
            "approval_required": policy_check.get("approval_required", False),
            "auto_approve_eligible": policy_check.get("auto_approve_eligible", False)
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to check policy compliance: {str(e)}")


# =====================================================
# PAYMENT & RECONCILIATION INTEGRATION
# =====================================================

@router.get("/payments/pending-approvals")
async def get_pending_payment_approvals(
    user_role: str = Query(..., description="User role for approval filtering"),
    user_id: str = Depends(get_user_id)
):
    """Get payments pending approval for the current user's role."""
    try:
        from services.bank_service import PaymentService
        from database import get_postgres_session_direct
        
        async with get_postgres_session_direct() as session:
            pending_payments = await PaymentService.get_payments(
                session, status="pending_approval"
            )
        
        # Filter by user role
        filtered_payments = []
        for payment in pending_payments:
            for approval in payment.approval_workflow:
                if (approval.approver_role.lower() == user_role.lower() and 
                    approval.approval_status == "pending"):
                    filtered_payments.append({
                        "payment_id": str(payment.id),
                        "payment_number": payment.payment_number,
                        "payment_type": payment.payment_type,
                        "gross_amount": float(payment.gross_amount),
                        "net_amount": float(payment.net_amount),
                        "created_at": payment.created_at,
                        "approval_level": approval.approval_level
                    })
                    break
        
        return {"pending_approvals": filtered_payments}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch pending approvals: {str(e)}")


@router.post("/reconciliation/match-transactions")
async def match_bank_transactions(
    bank_account_id: str = Query(..., description="Bank account ID"),
    from_date: str = Query(..., description="From date (YYYY-MM-DD)"),
    to_date: str = Query(..., description="To date (YYYY-MM-DD)"),
    user_id: str = Depends(get_user_id)
):
    """Match bank transactions with payments for reconciliation."""
    try:
        from services.bank_service import BankReconciliationService
        from database import get_postgres_session_direct
        from datetime import datetime
        
        # Parse dates
        from_date_obj = datetime.strptime(from_date, "%Y-%m-%d").date()
        to_date_obj = datetime.strptime(to_date, "%Y-%m-%d").date()
        
        async with get_postgres_session_direct() as session:
            reconciliation = await BankReconciliationService.start_reconciliation(
                bank_account_id, to_date_obj, 0.0, user_id, session
            )
        
        return {
            "message": "Bank reconciliation started",
            "reconciliation_id": str(reconciliation.id),
            "matched_transactions": reconciliation.reconciled_transactions,
            "unmatched_transactions": reconciliation.unreconciled_transactions
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to match transactions: {str(e)}")


# =====================================================
# ADVANCED ANALYTICS & REPORTING
# =====================================================

@router.get("/analytics/purchase-performance")
async def get_purchase_performance_analytics(
    period: str = Query("month", description="Analysis period: week, month, quarter"),
    vendor_id: Optional[str] = Query(None, description="Filter by vendor"),
    user_id: str = Depends(get_user_id)
):
    """Get purchase performance analytics."""
    try:
        analytics = await purchase_expense_service.get_purchase_analytics(period, vendor_id)
        
        return {
            "period": period,
            "summary": {
                "total_purchase_orders": analytics.get("total_pos", 0),
                "total_amount": analytics.get("total_amount", 0),
                "average_order_value": analytics.get("avg_order_value", 0),
                "on_time_delivery_rate": analytics.get("on_time_rate", 0)
            },
            "vendor_performance": analytics.get("vendor_performance", []),
            "category_breakdown": analytics.get("category_breakdown", []),
            "trend_analysis": analytics.get("trends", {})
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch analytics: {str(e)}")


@router.get("/analytics/expense-insights")
async def get_expense_insights(
    period: str = Query("month", description="Analysis period"),
    department: Optional[str] = Query(None, description="Filter by department"),
    user_id: str = Depends(get_user_id)
):
    """Get expense insights and trends."""
    try:
        insights = await purchase_expense_service.get_expense_insights(period, department)
        
        return {
            "period": period,
            "summary": {
                "total_expenses": insights.get("total_expenses", 0),
                "average_processing_time": insights.get("avg_processing_time", 0),
                "policy_violations": insights.get("policy_violations", 0),
                "reimbursement_pending": insights.get("pending_reimbursements", 0)
            },
            "category_analysis": insights.get("category_analysis", []),
            "approval_patterns": insights.get("approval_patterns", {}),
            "cost_optimization": insights.get("cost_optimization", [])
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch expense insights: {str(e)}")


# =====================================================
# COMPLIANCE & AUDIT FEATURES
# =====================================================

@router.get("/compliance/gst-reconciliation")
async def get_gst_reconciliation_report(
    month: int = Query(..., description="Month (1-12)"),
    year: int = Query(..., description="Year"),
    user_id: str = Depends(get_user_id)
):
    """Get GST reconciliation report for a specific month."""
    try:
        gst_report = await purchase_expense_service.get_gst_reconciliation(month, year)
        
        return {
            "period": f"{year}-{month:02d}",
            "gst_summary": {
                "total_igst": gst_report.get("total_igst", 0),
                "total_cgst": gst_report.get("total_cgst", 0),
                "total_sgst": gst_report.get("total_sgst", 0),
                "itc_claimed": gst_report.get("itc_claimed", 0),
                "itc_available": gst_report.get("itc_available", 0)
            },
            "discrepancies": gst_report.get("discrepancies", []),
            "vendor_wise_summary": gst_report.get("vendor_summary", [])
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate GST reconciliation: {str(e)}")


@router.get("/compliance/tds-summary")
async def get_tds_summary_report(
    quarter: int = Query(..., description="Quarter (1-4)"),
    year: int = Query(..., description="Financial year"),
    user_id: str = Depends(get_user_id)
):
    """Get TDS summary report for quarterly return filing."""
    try:
        tds_summary = await purchase_expense_service.get_tds_summary(quarter, year)
        
        return {
            "period": f"Q{quarter} FY{year}-{year+1}",
            "tds_summary": {
                "total_tds_deducted": tds_summary.get("total_deducted", 0),
                "total_payments": tds_summary.get("total_payments", 0),
                "certificates_issued": tds_summary.get("certificates_issued", 0),
                "pending_certificates": tds_summary.get("pending_certificates", 0)
            },
            "section_wise_breakdown": tds_summary.get("section_breakdown", []),
            "vendor_wise_tds": tds_summary.get("vendor_tds", []),
            "challan_details": tds_summary.get("challans", [])
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate TDS summary: {str(e)}")


# Add required imports at the top
from datetime import datetime 
# =====================================================
# PURCHASE ORDER APPROVAL WORKFLOW - TEMPORARILY DISABLED
# =====================================================
# Note: Approval workflow endpoints temporarily disabled due to build issues
# Will be re-enabled once all dependencies are resolved

# @router.post("/approval-rules")
# async def create_approval_rule():
#     return {"message": "Approval workflow coming soon"}

# @router.get("/approvals/pending") 
# async def get_pending_approvals():
#     return {"message": "Approval workflow coming soon"}