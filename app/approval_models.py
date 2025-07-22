from datetime import datetime
from typing import Optional, List
from decimal import Decimal
from pydantic import BaseModel
from models import POApprovalStatusEnum, ApprovalActionEnum, ApprovalLevelEnum, ApprovalStatusEnum

# Purchase Order Approval Workflow Pydantic Models

class POApprovalRuleRequest(BaseModel):
    """Request model for creating/updating approval rules"""
    rule_name: str
    min_amount: Decimal = 0
    max_amount: Optional[Decimal] = None
    level_1_required: bool = True
    level_2_required: bool = False
    level_3_required: bool = False
    finance_approval_required: bool = False
    level_1_approvers: List[str] = []
    level_2_approvers: List[str] = []
    level_3_approvers: List[str] = []
    finance_approvers: List[str] = []
    auto_approve_below: Decimal = 0

class POApprovalRuleResponse(BaseModel):
    """Response model for approval rules"""
    id: str
    rule_name: str
    min_amount: Decimal
    max_amount: Optional[Decimal]
    level_1_required: bool
    level_2_required: bool
    level_3_required: bool
    finance_approval_required: bool
    level_1_approvers: List[str]
    level_2_approvers: List[str]
    level_3_approvers: List[str]
    finance_approvers: List[str]
    auto_approve_below: Decimal
    is_active: bool
    created_at: datetime
    updated_at: datetime

class POApprovalActionRequest(BaseModel):
    """Request model for approval actions"""
    action: ApprovalActionEnum
    comments: Optional[str] = None
    
class POApprovalHistoryResponse(BaseModel):
    """Response model for approval history"""
    id: str
    approval_level: ApprovalLevelEnum
    action: ApprovalActionEnum
    approver_id: str
    approver_name: Optional[str]
    approver_email: Optional[str]
    action_date: datetime
    comments: Optional[str]
    previous_status: Optional[POApprovalStatusEnum]
    new_status: Optional[POApprovalStatusEnum]
    po_amount_at_time: Optional[Decimal]

class POApprovalWorkflowResponse(BaseModel):
    """Response model for approval workflow status"""
    id: str
    po_id: str
    current_level: Optional[ApprovalLevelEnum]
    approval_status: POApprovalStatusEnum
    
    # Level Status
    level_1_status: ApprovalStatusEnum
    level_1_approver: Optional[str]
    level_1_approved_at: Optional[datetime]
    
    level_2_status: ApprovalStatusEnum
    level_2_approver: Optional[str]
    level_2_approved_at: Optional[datetime]
    
    level_3_status: ApprovalStatusEnum
    level_3_approver: Optional[str]
    level_3_approved_at: Optional[datetime]
    
    finance_status: ApprovalStatusEnum
    finance_approver: Optional[str]
    finance_approved_at: Optional[datetime]
    
    # Workflow Metadata
    submitted_at: Optional[datetime]
    submitted_by: Optional[str]
    final_approved_at: Optional[datetime]
    final_approved_by: Optional[str]
    
    # SLA Information
    expected_approval_date: Optional[datetime]
    is_overdue: bool
    escalation_count: int
    
    # Related Data
    applied_rule: Optional[POApprovalRuleResponse] = None
    approval_history: List[POApprovalHistoryResponse] = []

class POApprovalSummaryResponse(BaseModel):
    """Summary response for purchase order with approval details"""
    po_id: str
    po_number: str
    vendor_name: str
    total_amount: Decimal
    approval_status: POApprovalStatusEnum
    current_level: Optional[ApprovalLevelEnum]
    submitted_at: Optional[datetime]
    is_overdue: bool
    days_pending: Optional[int]
    next_approver: Optional[str]