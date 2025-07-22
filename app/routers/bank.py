"""
Bank API Router for JusFinn ERP
Handles bank accounts, payments, transactions, and reconciliation.
"""

from datetime import datetime, date
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_postgres_session
from app.models import (
    BankAccountCreateRequest, BankAccountResponse,
    PaymentCreateRequest, PaymentResponse,
    BankTransactionImportRequest, BankTransactionResponse
)
from app.services.bank_service import (
    BankService, PaymentService, BankTransactionService,
    BankReconciliationService, ApprovalMatrixService
)

router = APIRouter(prefix="/api/bank", tags=["Bank Management"])


# =====================================================
# BANK ACCOUNT ENDPOINTS
# =====================================================

@router.post("/accounts", response_model=BankAccountResponse, status_code=status.HTTP_201_CREATED)
async def create_bank_account(
    account_data: BankAccountCreateRequest,
    session: AsyncSession = Depends(get_postgres_session)
):
    """Create a new bank account."""
    try:
        account = await BankService.create_bank_account(account_data.dict(), session)
        return BankAccountResponse.from_orm(account)
    
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Error creating bank account: {str(e)}"
        )


@router.get("/accounts", response_model=List[BankAccountResponse])
async def get_bank_accounts(
    active_only: bool = Query(True, description="Filter active accounts only"),
    session: AsyncSession = Depends(get_postgres_session)
):
    """Get all bank accounts."""
    try:
        accounts = await BankService.get_bank_accounts(session, active_only)
        return [BankAccountResponse.from_orm(account) for account in accounts]
    
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error fetching bank accounts: {str(e)}"
        )


@router.get("/accounts/{account_id}", response_model=BankAccountResponse)
async def get_bank_account(
    account_id: str,
    session: AsyncSession = Depends(get_postgres_session)
):
    """Get a specific bank account."""
    try:
        account = await session.get(BankAccount, account_id)
        if not account:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Bank account not found"
            )
        return BankAccountResponse.from_orm(account)
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error fetching bank account: {str(e)}"
        )


@router.put("/accounts/{account_id}/status")
async def update_account_status(
    account_id: str,
    is_active: bool,
    session: AsyncSession = Depends(get_postgres_session)
):
    """Activate or deactivate a bank account."""
    try:
        account = await session.get(BankAccount, account_id)
        if not account:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Bank account not found"
            )
        
        account.is_active = is_active
        account.updated_at = datetime.utcnow()
        await session.commit()
        
        return {"message": f"Account {'activated' if is_active else 'deactivated'} successfully"}
    
    except HTTPException:
        raise
    except Exception as e:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error updating account status: {str(e)}"
        )


# =====================================================
# PAYMENT ENDPOINTS
# =====================================================

@router.post("/payments", response_model=PaymentResponse, status_code=status.HTTP_201_CREATED)
async def create_payment(
    payment_data: PaymentCreateRequest,
    created_by: str = Query(..., description="User creating the payment"),
    session: AsyncSession = Depends(get_postgres_session)
):
    """Create a new payment with approval workflow."""
    try:
        payment = await PaymentService.create_payment(payment_data.dict(), created_by, session)
        return PaymentResponse.from_orm(payment)
    
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Error creating payment: {str(e)}"
        )


@router.get("/payments", response_model=List[PaymentResponse])
async def get_payments(
    status: Optional[str] = Query(None, description="Filter by payment status"),
    payment_type: Optional[str] = Query(None, description="Filter by payment type"),
    session: AsyncSession = Depends(get_postgres_session)
):
    """Get payments with optional filters."""
    try:
        payments = await PaymentService.get_payments(session, status, payment_type)
        return [PaymentResponse.from_orm(payment) for payment in payments]
    
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error fetching payments: {str(e)}"
        )


@router.get("/payments/{payment_id}", response_model=PaymentResponse)
async def get_payment(
    payment_id: str,
    session: AsyncSession = Depends(get_postgres_session)
):
    """Get a specific payment."""
    try:
        payment = await session.get(Payment, payment_id)
        if not payment:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Payment not found"
            )
        return PaymentResponse.from_orm(payment)
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error fetching payment: {str(e)}"
        )


@router.post("/payments/{payment_id}/approve")
async def approve_payment(
    payment_id: str,
    action: str = Query(..., description="Action: approve or reject"),
    comments: Optional[str] = Query(None, description="Approval comments"),
    approver_email: str = Query(..., description="Email of the approver"),
    session: AsyncSession = Depends(get_postgres_session)
):
    """Approve or reject a payment."""
    try:
        success = await PaymentService.approve_payment(
            payment_id, approver_email, action, 
            comments, session
        )
        
        if success:
            return {"message": f"Payment {action}d successfully"}
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to process approval"
            )
    
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error processing approval: {str(e)}"
        )


@router.post("/payments/{payment_id}/process")
async def process_payment(
    payment_id: str,
    session: AsyncSession = Depends(get_postgres_session)
):
    """Process an approved payment."""
    try:
        success = await PaymentService.process_payment(payment_id, session)
        
        if success:
            return {"message": "Payment processed successfully"}
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to process payment"
            )
    
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error processing payment: {str(e)}"
        )


@router.get("/payments/{payment_id}/approvals")
async def get_payment_approvals(
    payment_id: str,
    session: AsyncSession = Depends(get_postgres_session)
):
    """Get approval workflow for a payment."""
    try:
        from sqlalchemy import select
        from sqlalchemy.orm import selectinload
        from app.models import Payment
        
        query = select(Payment).options(selectinload(Payment.approval_workflow)).where(Payment.id == payment_id)
        result = await session.execute(query)
        payment = result.scalar_one_or_none()
        
        if not payment:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Payment not found"
            )
        
        # Return simplified approval data since ApprovalResponse was removed
        return [
            {
                "id": str(approval.id),
                "action": approval.action,
                "comments": approval.comments,
                "approver_email": approval.approver_email,
                "approved_at": approval.approved_at
            } 
            for approval in payment.approval_workflow
        ]
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error fetching payment approvals: {str(e)}"
        )


# =====================================================
# BANK TRANSACTION ENDPOINTS
# =====================================================

@router.post("/transactions/import")
async def import_bank_transactions(
    import_data: BankTransactionImportRequest,
    session: AsyncSession = Depends(get_postgres_session)
):
    """Import bank transactions from bank statement."""
    try:
        imported_count = await BankTransactionService.import_transactions(
            import_data.bank_account_id, import_data.transactions, session
        )
        
        return {
            "message": f"Successfully imported {imported_count} transactions",
            "imported_count": imported_count
        }
    
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Error importing transactions: {str(e)}"
        )


@router.get("/transactions", response_model=List[BankTransactionResponse])
async def get_bank_transactions(
    bank_account_id: str = Query(..., description="Bank account ID"),
    from_date: Optional[date] = Query(None, description="Filter from date"),
    to_date: Optional[date] = Query(None, description="Filter to date"),
    reconciliation_status: Optional[str] = Query(None, description="Filter by reconciliation status"),
    session: AsyncSession = Depends(get_postgres_session)
):
    """Get bank transactions with filters."""
    try:
        from sqlalchemy import select, and_
        from app.models import BankTransaction
        
        query = select(BankTransaction).where(BankTransaction.bank_account_id == bank_account_id)
        
        if from_date:
            query = query.where(BankTransaction.transaction_date >= from_date)
        
        if to_date:
            query = query.where(BankTransaction.transaction_date <= to_date)
        
        if reconciliation_status:
            query = query.where(BankTransaction.reconciliation_status == reconciliation_status)
        
        query = query.order_by(BankTransaction.transaction_date.desc())
        
        result = await session.execute(query)
        transactions = result.scalars().all()
        
        return [BankTransactionResponse.from_orm(transaction) for transaction in transactions]
    
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error fetching transactions: {str(e)}"
        )


# =====================================================
# BANK RECONCILIATION ENDPOINTS
# =====================================================

@router.post("/reconciliation/start")
async def start_bank_reconciliation(
    bank_account_id: str = Query(..., description="Bank account ID"),
    reconciliation_date: date = Query(..., description="Reconciliation date"),
    statement_balance: float = Query(..., description="Bank statement balance"),
    reconciled_by: str = Query(..., description="User performing reconciliation"),
    session: AsyncSession = Depends(get_postgres_session)
):
    """Start a new bank reconciliation process."""
    try:
        reconciliation = await BankReconciliationService.start_reconciliation(
            bank_account_id, reconciliation_date, statement_balance, reconciled_by, session
        )
        
        return {
            "message": "Bank reconciliation started successfully",
            "reconciliation_id": str(reconciliation.id),
            "reconciled_transactions": reconciliation.reconciled_transactions,
            "unreconciled_transactions": reconciliation.unreconciled_transactions,
            "difference_amount": float(reconciliation.difference_amount)
        }
    
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error starting reconciliation: {str(e)}"
        )


@router.get("/reconciliation/{account_id}/history")
async def get_reconciliation_history(
    account_id: str,
    limit: int = Query(10, description="Number of reconciliations to return"),
    session: AsyncSession = Depends(get_postgres_session)
):
    """Get reconciliation history for a bank account."""
    try:
        from sqlalchemy import select
        from app.models import BankReconciliation
        
        query = select(BankReconciliation).where(
            BankReconciliation.bank_account_id == account_id
        ).order_by(BankReconciliation.reconciliation_date.desc()).limit(limit)
        
        result = await session.execute(query)
        reconciliations = result.scalars().all()
        
        return [
            {
                "id": str(rec.id),
                "reconciliation_date": rec.reconciliation_date,
                "opening_balance": float(rec.opening_balance),
                "closing_balance": float(rec.closing_balance),
                "statement_balance": float(rec.statement_balance),
                "difference_amount": float(rec.difference_amount),
                "reconciled_transactions": rec.reconciled_transactions,
                "unreconciled_transactions": rec.unreconciled_transactions,
                "reconciliation_status": rec.reconciliation_status,
                "reconciled_by": rec.reconciled_by,
                "created_at": rec.created_at,
                "completed_at": rec.completed_at
            }
            for rec in reconciliations
        ]
    
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error fetching reconciliation history: {str(e)}"
        )


# =====================================================
# APPROVAL MATRIX ENDPOINTS
# =====================================================

@router.post("/approval-matrix")
async def create_approval_rule(
    rule_data: dict,
    session: AsyncSession = Depends(get_postgres_session)
):
    """Create a new approval rule."""
    try:
        rule = await ApprovalMatrixService.create_approval_rule(rule_data, session)
        
        return {
            "message": "Approval rule created successfully",
            "rule_id": str(rule.id)
        }
    
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Error creating approval rule: {str(e)}"
        )


@router.get("/approval-matrix")
async def get_approval_rules(
    module_type: Optional[str] = Query(None, description="Filter by module type"),
    session: AsyncSession = Depends(get_postgres_session)
):
    """Get approval rules."""
    try:
        rules = await ApprovalMatrixService.get_approval_rules(session, module_type)
        
        return [
            {
                "id": str(rule.id),
                "module_type": rule.module_type,
                "transaction_type": rule.transaction_type,
                "min_amount": float(rule.min_amount),
                "max_amount": float(rule.max_amount) if rule.max_amount else None,
                "approval_level": rule.approval_level,
                "approver_role": rule.approver_role,
                "is_mandatory": rule.is_mandatory,
                "is_active": rule.is_active,
                "created_at": rule.created_at,
                "updated_at": rule.updated_at
            }
            for rule in rules
        ]
    
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error fetching approval rules: {str(e)}"
        )


# =====================================================
# DASHBOARD & ANALYTICS ENDPOINTS
# =====================================================

@router.get("/dashboard/summary")
async def get_bank_dashboard_summary(
    session: AsyncSession = Depends(get_postgres_session)
):
    """Get bank dashboard summary with key metrics."""
    try:
        from sqlalchemy import select, func
        from app.models import BankAccount, Payment, BankTransaction
        
        # Get total balance across all accounts
        balance_result = await session.execute(
            select(func.sum(BankAccount.current_balance)).where(BankAccount.is_active == True)
        )
        total_balance = balance_result.scalar() or 0
        
        # Get pending payments count and amount
        pending_payments = await session.execute(
            select(func.count(Payment.id), func.sum(Payment.net_amount))
            .where(Payment.payment_status == 'pending_approval')
        )
        pending_count, pending_amount = pending_payments.first()
        
        # Get processed payments for current month
        from datetime import datetime
        current_month_start = datetime.now().replace(day=1)
        processed_payments = await session.execute(
            select(func.count(Payment.id), func.sum(Payment.net_amount))
            .where(
                and_(
                    Payment.payment_status == 'processed',
                    Payment.created_at >= current_month_start
                )
            )
        )
        processed_count, processed_amount = processed_payments.first()
        
        # Get unreconciled transactions count
        unreconciled_result = await session.execute(
            select(func.count(BankTransaction.id))
            .where(BankTransaction.reconciliation_status == 'unreconciled')
        )
        unreconciled_count = unreconciled_result.scalar() or 0
        
        return {
            "total_bank_balance": float(total_balance),
            "pending_approvals": {
                "count": pending_count or 0,
                "amount": float(pending_amount or 0)
            },
            "current_month_payments": {
                "count": processed_count or 0,
                "amount": float(processed_amount or 0)
            },
            "unreconciled_transactions": unreconciled_count
        }
    
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error fetching dashboard summary: {str(e)}"
        )


# Add required imports
from app.models import BankAccount, Payment 