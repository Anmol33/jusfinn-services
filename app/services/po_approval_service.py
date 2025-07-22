import json
from datetime import datetime, timedelta
from decimal import Decimal
from typing import List, Optional, Dict, Any
from sqlalchemy import select, and_, or_, desc, func
from sqlalchemy.orm import joinedload
from app.database import get_postgres_session_direct
from app.models import (
    POApprovalRule, POApprovalHistory, POApprovalWorkflow, PurchaseOrder,
    POApprovalStatusEnum, ApprovalStatusEnum, ApprovalActionEnum, ApprovalLevelEnum,
    POApprovalRuleRequest, POApprovalRuleResponse, POApprovalActionRequest,
    POApprovalHistoryResponse, POApprovalWorkflowResponse, POApprovalSummaryResponse
)
import logging

logger = logging.getLogger(__name__)

class POApprovalService:
    """Service to handle Purchase Order approval workflow"""
    
    async def create_approval_rule(
        self, 
        rule_data: POApprovalRuleRequest, 
        user_id: str
    ) -> POApprovalRuleResponse:
        """Create a new approval rule"""
        
        async with get_postgres_session_direct() as session:
            try:
                # Convert approver lists to JSON
                new_rule = POApprovalRule(
                    user_id=user_id,
                    rule_name=rule_data.rule_name,
                    min_amount=rule_data.min_amount,
                    max_amount=rule_data.max_amount,
                    level_1_required=rule_data.level_1_required,
                    level_2_required=rule_data.level_2_required,
                    level_3_required=rule_data.level_3_required,
                    finance_approval_required=rule_data.finance_approval_required,
                    level_1_approvers=json.dumps(rule_data.level_1_approvers),
                    level_2_approvers=json.dumps(rule_data.level_2_approvers),
                    level_3_approvers=json.dumps(rule_data.level_3_approvers),
                    finance_approvers=json.dumps(rule_data.finance_approvers),
                    auto_approve_below=rule_data.auto_approve_below,
                    created_by=user_id,
                    updated_by=user_id
                )
                
                session.add(new_rule)
                await session.commit()
                await session.refresh(new_rule)
                
                return await self._convert_rule_to_response(new_rule)
                
            except Exception as e:
                await session.rollback()
                logger.error(f"Error creating approval rule: {e}")
                raise Exception(f"Failed to create approval rule: {str(e)}")
    
    async def get_approval_rules(self, user_id: str) -> List[POApprovalRuleResponse]:
        """Get all active approval rules for a user"""
        
        async with get_postgres_session_direct() as session:
            try:
                result = await session.execute(
                    select(POApprovalRule)
                    .where(and_(
                        POApprovalRule.user_id == user_id,
                        POApprovalRule.is_active == True
                    ))
                    .order_by(POApprovalRule.min_amount)
                )
                rules = result.scalars().all()
                
                return [await self._convert_rule_to_response(rule) for rule in rules]
                
            except Exception as e:
                logger.error(f"Error fetching approval rules: {e}")
                raise Exception(f"Failed to fetch approval rules: {str(e)}")
    
    async def submit_po_for_approval(
        self, 
        po_id: str, 
        submitted_by: str, 
        user_id: str
    ) -> POApprovalWorkflowResponse:
        """Submit a purchase order for approval"""
        
        async with get_postgres_session_direct() as session:
            try:
                # Get the purchase order
                po_result = await session.execute(
                    select(PurchaseOrder)
                    .where(and_(
                        PurchaseOrder.id == po_id,
                        PurchaseOrder.user_id == user_id
                    ))
                )
                po = po_result.scalar_one_or_none()
                if not po:
                    raise Exception("Purchase order not found")
                
                # Find applicable approval rule
                applicable_rule = await self._find_applicable_rule(po.total_amount, user_id, session)
                if not applicable_rule:
                    raise Exception("No applicable approval rule found")
                
                # Check for auto-approval
                if po.total_amount <= applicable_rule.auto_approve_below:
                    return await self._auto_approve_po(po, applicable_rule, submitted_by, session)
                
                # Create workflow record
                workflow = POApprovalWorkflow(
                    po_id=po_id,
                    applied_rule_id=applicable_rule.id,
                    approval_status=POApprovalStatusEnum.PENDING_APPROVAL,
                    current_level=ApprovalLevelEnum.LEVEL_1 if applicable_rule.level_1_required else (
                        ApprovalLevelEnum.LEVEL_2 if applicable_rule.level_2_required else ApprovalLevelEnum.FINANCE
                    ),
                    submitted_at=datetime.utcnow(),
                    submitted_by=submitted_by,
                    expected_approval_date=datetime.utcnow() + timedelta(days=3)  # Default 3-day SLA
                )
                
                session.add(workflow)
                
                # Update PO status
                po.approval_status = POApprovalStatusEnum.PENDING_APPROVAL
                
                # Add to approval history
                await self._add_approval_history(
                    po_id, ApprovalLevelEnum.LEVEL_1, ApprovalActionEnum.SUBMIT,
                    submitted_by, None, POApprovalStatusEnum.DRAFT, 
                    POApprovalStatusEnum.PENDING_APPROVAL, po.total_amount, session
                )
                
                await session.commit()
                await session.refresh(workflow)
                
                return await self._convert_workflow_to_response(workflow, session)
                
            except Exception as e:
                await session.rollback()
                logger.error(f"Error submitting PO for approval: {e}")
                raise Exception(f"Failed to submit PO for approval: {str(e)}")
    
    async def process_approval_action(
        self, 
        po_id: str, 
        action_data: POApprovalActionRequest,
        approver_id: str,
        user_id: str
    ) -> POApprovalWorkflowResponse:
        """Process an approval action (approve, reject, etc.)"""
        
        async with get_postgres_session_direct() as session:
            try:
                # Get workflow and PO
                workflow_result = await session.execute(
                    select(POApprovalWorkflow)
                    .options(joinedload(POApprovalWorkflow.applied_rule))
                    .where(POApprovalWorkflow.po_id == po_id)
                )
                workflow = workflow_result.scalar_one_or_none()
                if not workflow:
                    raise Exception("Approval workflow not found")
                
                po_result = await session.execute(
                    select(PurchaseOrder)
                    .where(and_(
                        PurchaseOrder.id == po_id,
                        PurchaseOrder.user_id == user_id
                    ))
                )
                po = po_result.scalar_one_or_none()
                if not po:
                    raise Exception("Purchase order not found")
                
                # Validate approver authorization
                if not await self._is_authorized_approver(workflow, approver_id, session):
                    raise Exception("User not authorized to approve at current level")
                
                previous_status = workflow.approval_status
                
                # Process the action
                if action_data.action == ApprovalActionEnum.APPROVE:
                    new_status = await self._process_approval(workflow, approver_id, session)
                elif action_data.action == ApprovalActionEnum.REJECT:
                    new_status = await self._process_rejection(workflow, approver_id, session)
                elif action_data.action == ApprovalActionEnum.REQUEST_CHANGES:
                    new_status = await self._process_change_request(workflow, approver_id, session)
                else:
                    raise Exception(f"Unsupported action: {action_data.action}")
                
                # Update PO status
                po.approval_status = new_status
                if new_status == POApprovalStatusEnum.FINAL_APPROVED:
                    po.approved_by = approver_id
                    po.approved_at = datetime.utcnow()
                
                # Add to approval history
                await self._add_approval_history(
                    po_id, workflow.current_level, action_data.action,
                    approver_id, action_data.comments, previous_status,
                    new_status, po.total_amount, session
                )
                
                await session.commit()
                
                return await self._convert_workflow_to_response(workflow, session)
                
            except Exception as e:
                await session.rollback()
                logger.error(f"Error processing approval action: {e}")
                raise Exception(f"Failed to process approval action: {str(e)}")
    
    async def get_pending_approvals(
        self, 
        approver_id: str, 
        user_id: str,
        skip: int = 0,
        limit: int = 100
    ) -> List[POApprovalSummaryResponse]:
        """Get purchase orders pending approval for a specific approver"""
        
        async with get_postgres_session_direct() as session:
            try:
                # Build query to find POs where the user is an authorized approver
                query = (
                    select(POApprovalWorkflow, PurchaseOrder)
                    .join(PurchaseOrder, POApprovalWorkflow.po_id == PurchaseOrder.id)
                    .join(POApprovalRule, POApprovalWorkflow.applied_rule_id == POApprovalRule.id)
                    .where(and_(
                        PurchaseOrder.user_id == user_id,
                        POApprovalWorkflow.approval_status.in_([
                            POApprovalStatusEnum.PENDING_APPROVAL,
                            POApprovalStatusEnum.LEVEL_1_APPROVED,
                            POApprovalStatusEnum.LEVEL_2_APPROVED
                        ])
                    ))
                    .order_by(desc(POApprovalWorkflow.submitted_at))
                    .offset(skip)
                    .limit(limit)
                )
                
                result = await session.execute(query)
                workflow_pos = result.all()
                
                pending_approvals = []
                for workflow, po in workflow_pos:
                    # Check if user is authorized approver for current level
                    if await self._is_authorized_approver(workflow, approver_id, session):
                        # Calculate days pending
                        days_pending = None
                        if workflow.submitted_at:
                            days_pending = (datetime.utcnow() - workflow.submitted_at).days
                        
                        pending_approvals.append(POApprovalSummaryResponse(
                            po_id=str(po.id),
                            po_number=po.po_number,
                            vendor_name="Vendor Name",  # Would need vendor join
                            total_amount=po.total_amount,
                            approval_status=workflow.approval_status,
                            current_level=workflow.current_level,
                            submitted_at=workflow.submitted_at,
                            is_overdue=workflow.is_overdue,
                            days_pending=days_pending,
                            next_approver=approver_id
                        ))
                
                return pending_approvals
                
            except Exception as e:
                logger.error(f"Error fetching pending approvals: {e}")
                raise Exception(f"Failed to fetch pending approvals: {str(e)}")
    
    async def get_approval_workflow_status(
        self, 
        po_id: str, 
        user_id: str
    ) -> POApprovalWorkflowResponse:
        """Get detailed approval workflow status for a purchase order"""
        
        async with get_postgres_session_direct() as session:
            try:
                workflow_result = await session.execute(
                    select(POApprovalWorkflow)
                    .options(joinedload(POApprovalWorkflow.applied_rule))
                    .where(POApprovalWorkflow.po_id == po_id)
                )
                workflow = workflow_result.scalar_one_or_none()
                if not workflow:
                    raise Exception("Approval workflow not found")
                
                return await self._convert_workflow_to_response(workflow, session)
                
            except Exception as e:
                logger.error(f"Error fetching workflow status: {e}")
                raise Exception(f"Failed to fetch workflow status: {str(e)}")
    
    # Helper methods
    
    async def _find_applicable_rule(self, amount: Decimal, user_id: str, session):
        """Find the applicable approval rule for the given amount"""
        result = await session.execute(
            select(POApprovalRule)
            .where(and_(
                POApprovalRule.user_id == user_id,
                POApprovalRule.is_active == True,
                POApprovalRule.min_amount <= amount,
                or_(
                    POApprovalRule.max_amount >= amount,
                    POApprovalRule.max_amount.is_(None)
                )
            ))
            .order_by(POApprovalRule.min_amount.desc())
        )
        return result.scalar_one_or_none()
    
    async def _auto_approve_po(self, po, rule, submitted_by, session):
        """Handle auto-approval for POs below threshold"""
        workflow = POApprovalWorkflow(
            po_id=po.id,
            applied_rule_id=rule.id,
            approval_status=POApprovalStatusEnum.FINAL_APPROVED,
            submitted_at=datetime.utcnow(),
            submitted_by=submitted_by,
            final_approved_at=datetime.utcnow(),
            final_approved_by="SYSTEM_AUTO_APPROVAL"
        )
        
        session.add(workflow)
        po.approval_status = POApprovalStatusEnum.FINAL_APPROVED
        po.approved_by = "SYSTEM_AUTO_APPROVAL"
        po.approved_at = datetime.utcnow()
        
        await self._add_approval_history(
            po.id, ApprovalLevelEnum.ADMIN, ApprovalActionEnum.APPROVE,
            "SYSTEM_AUTO_APPROVAL", "Auto-approved below threshold",
            POApprovalStatusEnum.DRAFT, POApprovalStatusEnum.FINAL_APPROVED,
            po.total_amount, session
        )
        
        return workflow
    
    async def _is_authorized_approver(self, workflow, approver_id, session):
        """Check if user is authorized to approve at current level"""
        rule = workflow.applied_rule
        if not rule:
            return False
        
        current_level = workflow.current_level
        if current_level == ApprovalLevelEnum.LEVEL_1:
            approvers = json.loads(rule.level_1_approvers or '[]')
        elif current_level == ApprovalLevelEnum.LEVEL_2:
            approvers = json.loads(rule.level_2_approvers or '[]')
        elif current_level == ApprovalLevelEnum.LEVEL_3:
            approvers = json.loads(rule.level_3_approvers or '[]')
        elif current_level == ApprovalLevelEnum.FINANCE:
            approvers = json.loads(rule.finance_approvers or '[]')
        else:
            return False
        
        return approver_id in approvers
    
    async def _process_approval(self, workflow, approver_id, session):
        """Process approval action and move to next level"""
        current_level = workflow.current_level
        rule = workflow.applied_rule
        
        # Update current level status
        if current_level == ApprovalLevelEnum.LEVEL_1:
            workflow.level_1_status = ApprovalStatusEnum.APPROVED
            workflow.level_1_approver = approver_id
            workflow.level_1_approved_at = datetime.utcnow()
            
            # Move to next level
            if rule.level_2_required:
                workflow.current_level = ApprovalLevelEnum.LEVEL_2
                workflow.approval_status = POApprovalStatusEnum.LEVEL_1_APPROVED
            elif rule.level_3_required:
                workflow.current_level = ApprovalLevelEnum.LEVEL_3
                workflow.approval_status = POApprovalStatusEnum.LEVEL_1_APPROVED
            elif rule.finance_approval_required:
                workflow.current_level = ApprovalLevelEnum.FINANCE
                workflow.approval_status = POApprovalStatusEnum.LEVEL_1_APPROVED
            else:
                workflow.approval_status = POApprovalStatusEnum.FINAL_APPROVED
                workflow.final_approved_at = datetime.utcnow()
                workflow.final_approved_by = approver_id
        
        elif current_level == ApprovalLevelEnum.LEVEL_2:
            workflow.level_2_status = ApprovalStatusEnum.APPROVED
            workflow.level_2_approver = approver_id
            workflow.level_2_approved_at = datetime.utcnow()
            
            if rule.level_3_required:
                workflow.current_level = ApprovalLevelEnum.LEVEL_3
                workflow.approval_status = POApprovalStatusEnum.LEVEL_2_APPROVED
            elif rule.finance_approval_required:
                workflow.current_level = ApprovalLevelEnum.FINANCE
                workflow.approval_status = POApprovalStatusEnum.LEVEL_2_APPROVED
            else:
                workflow.approval_status = POApprovalStatusEnum.FINAL_APPROVED
                workflow.final_approved_at = datetime.utcnow()
                workflow.final_approved_by = approver_id
        
        elif current_level == ApprovalLevelEnum.LEVEL_3:
            workflow.level_3_status = ApprovalStatusEnum.APPROVED
            workflow.level_3_approver = approver_id
            workflow.level_3_approved_at = datetime.utcnow()
            
            if rule.finance_approval_required:
                workflow.current_level = ApprovalLevelEnum.FINANCE
                workflow.approval_status = POApprovalStatusEnum.LEVEL_2_APPROVED
            else:
                workflow.approval_status = POApprovalStatusEnum.FINAL_APPROVED
                workflow.final_approved_at = datetime.utcnow()
                workflow.final_approved_by = approver_id
        
        elif current_level == ApprovalLevelEnum.FINANCE:
            workflow.finance_status = ApprovalStatusEnum.APPROVED
            workflow.finance_approver = approver_id
            workflow.finance_approved_at = datetime.utcnow()
            workflow.approval_status = POApprovalStatusEnum.FINAL_APPROVED
            workflow.final_approved_at = datetime.utcnow()
            workflow.final_approved_by = approver_id
        
        return workflow.approval_status
    
    async def _process_rejection(self, workflow, approver_id, session):
        """Process rejection action"""
        workflow.approval_status = POApprovalStatusEnum.REJECTED
        return POApprovalStatusEnum.REJECTED
    
    async def _process_change_request(self, workflow, approver_id, session):
        """Process request for changes"""
        workflow.approval_status = POApprovalStatusEnum.DRAFT
        return POApprovalStatusEnum.DRAFT
    
    async def _add_approval_history(
        self, po_id, level, action, approver_id, comments, 
        previous_status, new_status, amount, session
    ):
        """Add entry to approval history"""
        history = POApprovalHistory(
            po_id=po_id,
            approval_level=level,
            action=action,
            approver_id=approver_id,
            comments=comments,
            previous_status=previous_status,
            new_status=new_status,
            po_amount_at_time=amount
        )
        session.add(history)
    
    async def _convert_rule_to_response(self, rule: POApprovalRule) -> POApprovalRuleResponse:
        """Convert SQLAlchemy rule to Pydantic response"""
        return POApprovalRuleResponse(
            id=str(rule.id),
            rule_name=rule.rule_name,
            min_amount=rule.min_amount,
            max_amount=rule.max_amount,
            level_1_required=rule.level_1_required,
            level_2_required=rule.level_2_required,
            level_3_required=rule.level_3_required,
            finance_approval_required=rule.finance_approval_required,
            level_1_approvers=json.loads(rule.level_1_approvers or '[]'),
            level_2_approvers=json.loads(rule.level_2_approvers or '[]'),
            level_3_approvers=json.loads(rule.level_3_approvers or '[]'),
            finance_approvers=json.loads(rule.finance_approvers or '[]'),
            auto_approve_below=rule.auto_approve_below,
            is_active=rule.is_active,
            created_at=rule.created_at,
            updated_at=rule.updated_at
        )
    
    async def _convert_workflow_to_response(self, workflow: POApprovalWorkflow, session) -> POApprovalWorkflowResponse:
        """Convert SQLAlchemy workflow to Pydantic response"""
        # Get approval history
        history_result = await session.execute(
            select(POApprovalHistory)
            .where(POApprovalHistory.po_id == workflow.po_id)
            .order_by(POApprovalHistory.action_date)
        )
        history_records = history_result.scalars().all()
        
        approval_history = [
            POApprovalHistoryResponse(
                id=str(h.id),
                approval_level=h.approval_level,
                action=h.action,
                approver_id=h.approver_id,
                approver_name=h.approver_name,
                approver_email=h.approver_email,
                action_date=h.action_date,
                comments=h.comments,
                previous_status=h.previous_status,
                new_status=h.new_status,
                po_amount_at_time=h.po_amount_at_time
            ) for h in history_records
        ]
        
        applied_rule = None
        if workflow.applied_rule:
            applied_rule = await self._convert_rule_to_response(workflow.applied_rule)
        
        return POApprovalWorkflowResponse(
            id=str(workflow.id),
            po_id=str(workflow.po_id),
            current_level=workflow.current_level,
            approval_status=workflow.approval_status,
            level_1_status=workflow.level_1_status,
            level_1_approver=workflow.level_1_approver,
            level_1_approved_at=workflow.level_1_approved_at,
            level_2_status=workflow.level_2_status,
            level_2_approver=workflow.level_2_approver,
            level_2_approved_at=workflow.level_2_approved_at,
            level_3_status=workflow.level_3_status,
            level_3_approver=workflow.level_3_approver,
            level_3_approved_at=workflow.level_3_approved_at,
            finance_status=workflow.finance_status,
            finance_approver=workflow.finance_approver,
            finance_approved_at=workflow.finance_approved_at,
            submitted_at=workflow.submitted_at,
            submitted_by=workflow.submitted_by,
            final_approved_at=workflow.final_approved_at,
            final_approved_by=workflow.final_approved_by,
            expected_approval_date=workflow.expected_approval_date,
            is_overdue=workflow.is_overdue,
            escalation_count=workflow.escalation_count,
            applied_rule=applied_rule,
            approval_history=approval_history
        )

# Create singleton instance
po_approval_service = POApprovalService()