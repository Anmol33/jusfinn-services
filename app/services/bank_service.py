"""
Bank Service Module for JusFinn ERP
Handles payment processing, bank reconciliation, and approval workflows.
"""

from datetime import datetime, date
from typing import List, Optional, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete, and_, or_, func
from sqlalchemy.orm import selectinload
import uuid
import logging

from app.models import (
    BankAccount, BankTransaction, Payment, PaymentApproval, ApprovalMatrix,
    BankReconciliation, PaymentTypeEnum, PaymentMethodEnum, PaymentStatusEnum,
    ApprovalStatusEnum, ReconciliationStatusEnum, ModuleTypeEnum
)
from app.database import get_postgres_session_direct

# Set up logging
logger = logging.getLogger(__name__)


class BankService:
    """Service class for Bank operations."""
    
    @staticmethod
    async def create_bank_account(account_data: dict, session: AsyncSession) -> BankAccount:
        """Create a new bank account."""
        try:
            # If this is set as primary, unset other primary accounts
            if account_data.get("is_primary", False):
                await session.execute(
                    update(BankAccount).where(BankAccount.is_primary == True).values(is_primary=False)
                )
            
            # Set current_balance to opening_balance for new account
            account_data["current_balance"] = account_data.get("opening_balance", 0.0)
            
            bank_account = BankAccount(**account_data)
            session.add(bank_account)
            await session.commit()
            await session.refresh(bank_account)
            
            logger.info(f"Created bank account: {bank_account.account_name}")
            return bank_account
            
        except Exception as e:
            await session.rollback()
            logger.error(f"Error creating bank account: {str(e)}")
            raise

    @staticmethod
    async def get_bank_accounts(session: AsyncSession, active_only: bool = True) -> List[BankAccount]:
        """Get all bank accounts."""
        try:
            query = select(BankAccount).order_by(BankAccount.is_primary.desc(), BankAccount.account_name)
            if active_only:
                query = query.where(BankAccount.is_active == True)
            
            result = await session.execute(query)
            return result.scalars().all()
            
        except Exception as e:
            logger.error(f"Error fetching bank accounts: {str(e)}")
            raise

    @staticmethod
    async def update_account_balance(account_id: str, amount: float, session: AsyncSession) -> None:
        """Update bank account balance."""
        try:
            await session.execute(
                update(BankAccount)
                .where(BankAccount.id == account_id)
                .values(
                    current_balance=BankAccount.current_balance + amount,
                    updated_at=datetime.utcnow()
                )
            )
            await session.commit()
            
        except Exception as e:
            await session.rollback()
            logger.error(f"Error updating account balance: {str(e)}")
            raise


class PaymentService:
    """Service class for Payment operations."""
    
    @staticmethod
    async def create_payment(payment_data: dict, created_by: str, session: AsyncSession) -> Payment:
        """Create a new payment with approval workflow."""
        try:
            # Generate payment number
            payment_number = await PaymentService._generate_payment_number(session)
            
            # Calculate net amount
            gross_amount = payment_data["gross_amount"]
            tds_amount = payment_data.get("tds_amount", 0.0)
            other_deductions = payment_data.get("other_deductions", 0.0)
            net_amount = gross_amount - tds_amount - other_deductions
            
            payment_data.update({
                "payment_number": payment_number,
                "net_amount": net_amount,
                "created_by": created_by
            })
            
            payment = Payment(**payment_data)
            session.add(payment)
            await session.flush()  # Get the payment ID
            
            # Create approval workflow
            await PaymentService._create_approval_workflow(payment, session)
            
            await session.commit()
            await session.refresh(payment)
            
            logger.info(f"Created payment: {payment.payment_number}")
            return payment
            
        except Exception as e:
            await session.rollback()
            logger.error(f"Error creating payment: {str(e)}")
            raise

    @staticmethod
    async def _generate_payment_number(session: AsyncSession) -> str:
        """Generate unique payment number."""
        today = datetime.now()
        prefix = f"PAY{today.year:04d}{today.month:02d}"
        
        # Get the last payment number for this month
        result = await session.execute(
            select(func.count(Payment.id))
            .where(Payment.payment_number.like(f"{prefix}%"))
        )
        count = result.scalar() or 0
        
        return f"{prefix}{count + 1:04d}"

    @staticmethod
    async def _create_approval_workflow(payment: Payment, session: AsyncSession) -> None:
        """Create approval workflow based on approval matrix."""
        try:
            # Get approval matrix for this payment type and amount
            query = select(ApprovalMatrix).where(
                and_(
                    ApprovalMatrix.module_type == ModuleTypeEnum.PURCHASE if payment.payment_type == PaymentTypeEnum.VENDOR_PAYMENT else ModuleTypeEnum.EXPENSE,
                    ApprovalMatrix.min_amount <= payment.gross_amount,
                    or_(ApprovalMatrix.max_amount >= payment.gross_amount, ApprovalMatrix.max_amount.is_(None)),
                    ApprovalMatrix.is_active == True
                )
            ).order_by(ApprovalMatrix.approval_level)
            
            result = await session.execute(query)
            approval_rules = result.scalars().all()
            
            if not approval_rules:
                # Auto-approve if no rules found for small amounts
                if payment.gross_amount <= 5000:
                    payment.approval_status = ApprovalStatusEnum.APPROVED
                    payment.approved_by = "system"
                    payment.approved_at = datetime.utcnow()
                return
            
            # Create approval records
            for rule in approval_rules:
                approval = PaymentApproval(
                    payment_id=payment.id,
                    approval_level=rule.approval_level,
                    approver_role=rule.approver_role,
                    approver_email=f"{rule.approver_role.lower()}@company.com",  # This should come from user management
                    approval_status=ApprovalStatusEnum.PENDING
                )
                session.add(approval)
            
            # Set payment status
            payment.payment_status = PaymentStatusEnum.PENDING_APPROVAL
            
        except Exception as e:
            logger.error(f"Error creating approval workflow: {str(e)}")
            raise

    @staticmethod
    async def approve_payment(payment_id: str, approver_email: str, action: str, 
                            session: AsyncSession, comments: str = None) -> bool:
        """Approve or reject a payment."""
        try:
            # Get the payment with approval workflow
            query = select(Payment).options(selectinload(Payment.approval_workflow)).where(Payment.id == payment_id)
            result = await session.execute(query)
            payment = result.scalar_one_or_none()
            
            if not payment:
                raise ValueError("Payment not found")
            
            # Find the current approval level
            pending_approvals = [a for a in payment.approval_workflow if a.approval_status == ApprovalStatusEnum.PENDING]
            if not pending_approvals:
                raise ValueError("No pending approvals found")
            
            # Get the lowest level pending approval
            current_approval = min(pending_approvals, key=lambda x: x.approval_level)
            
            # Update the approval
            if action.lower() == "approve":
                current_approval.approval_status = ApprovalStatusEnum.APPROVED
                current_approval.approved_at = datetime.utcnow()
            else:
                current_approval.approval_status = ApprovalStatusEnum.REJECTED
                current_approval.rejection_reason = comments
                
            current_approval.comments = comments
            
            # Check if all approvals are complete
            all_approvals = payment.approval_workflow
            approved_count = sum(1 for a in all_approvals if a.approval_status == ApprovalStatusEnum.APPROVED)
            rejected_count = sum(1 for a in all_approvals if a.approval_status == ApprovalStatusEnum.REJECTED)
            
            if rejected_count > 0:
                payment.approval_status = ApprovalStatusEnum.REJECTED
                payment.payment_status = PaymentStatusEnum.CANCELLED
            elif approved_count == len(all_approvals):
                payment.approval_status = ApprovalStatusEnum.APPROVED
                payment.payment_status = PaymentStatusEnum.APPROVED
                payment.approved_by = approver_email
                payment.approved_at = datetime.utcnow()
            
            await session.commit()
            
            # If fully approved, trigger payment processing
            if payment.payment_status == PaymentStatusEnum.APPROVED:
                await PaymentService.process_payment(payment_id, session)
            
            return True
            
        except Exception as e:
            await session.rollback()
            logger.error(f"Error approving payment: {str(e)}")
            raise

    @staticmethod
    async def process_payment(payment_id: str, session: AsyncSession) -> bool:
        """Process an approved payment."""
        try:
            payment = await session.get(Payment, payment_id)
            if not payment:
                raise ValueError("Payment not found")
            
            if payment.payment_status != PaymentStatusEnum.APPROVED:
                raise ValueError("Payment is not approved")
            
            # Update bank account balance if bank payment
            if payment.bank_account_id and payment.payment_method in [PaymentMethodEnum.RTGS, PaymentMethodEnum.NEFT, PaymentMethodEnum.IMPS, PaymentMethodEnum.UPI]:
                await BankService.update_account_balance(
                    payment.bank_account_id, 
                    -payment.net_amount,  # Debit the account
                    session
                )
            
            # Update payment status
            payment.payment_status = PaymentStatusEnum.PROCESSED
            payment.updated_at = datetime.utcnow()
            
            # Generate transaction reference if not provided
            if not payment.transaction_reference:
                payment.transaction_reference = f"TXN{datetime.now().strftime('%Y%m%d%H%M%S')}"
            
            await session.commit()
            
            logger.info(f"Processed payment: {payment.payment_number}")
            return True
            
        except Exception as e:
            await session.rollback()
            logger.error(f"Error processing payment: {str(e)}")
            raise

    @staticmethod
    async def get_payments(session: AsyncSession, status: Optional[str] = None, 
                          payment_type: Optional[str] = None) -> List[Payment]:
        """Get payments with optional filters."""
        try:
            query = select(Payment).options(selectinload(Payment.approval_workflow))
            
            if status:
                query = query.where(Payment.payment_status == status)
            
            if payment_type:
                query = query.where(Payment.payment_type == payment_type)
            
            query = query.order_by(Payment.created_at.desc())
            
            result = await session.execute(query)
            return result.scalars().all()
            
        except Exception as e:
            logger.error(f"Error fetching payments: {str(e)}")
            raise


class BankTransactionService:
    """Service class for Bank Transaction operations."""
    
    @staticmethod
    async def import_transactions(bank_account_id: str, transactions: List[Dict], session: AsyncSession) -> int:
        """Import bank transactions from bank statement."""
        try:
            imported_count = 0
            
            for trans_data in transactions:
                # Check if transaction already exists
                existing = await session.execute(
                    select(BankTransaction).where(
                        and_(
                            BankTransaction.bank_account_id == bank_account_id,
                            BankTransaction.reference_number == trans_data["reference_number"],
                            BankTransaction.transaction_date == trans_data["transaction_date"]
                        )
                    )
                )
                
                if existing.scalar_one_or_none():
                    continue  # Skip duplicate transaction
                
                # Create new transaction
                transaction = BankTransaction(
                    bank_account_id=bank_account_id,
                    **trans_data
                )
                session.add(transaction)
                imported_count += 1
            
            await session.commit()
            
            # Update account balance
            if imported_count > 0:
                await BankTransactionService._update_account_balance_from_transactions(bank_account_id, session)
            
            logger.info(f"Imported {imported_count} bank transactions")
            return imported_count
            
        except Exception as e:
            await session.rollback()
            logger.error(f"Error importing transactions: {str(e)}")
            raise

    @staticmethod
    async def _update_account_balance_from_transactions(bank_account_id: str, session: AsyncSession) -> None:
        """Update account balance based on latest transaction."""
        try:
            # Get the latest transaction balance
            result = await session.execute(
                select(BankTransaction.balance)
                .where(BankTransaction.bank_account_id == bank_account_id)
                .order_by(BankTransaction.transaction_date.desc(), BankTransaction.created_at.desc())
                .limit(1)
            )
            
            latest_balance = result.scalar()
            if latest_balance is not None:
                await session.execute(
                    update(BankAccount)
                    .where(BankAccount.id == bank_account_id)
                    .values(current_balance=latest_balance, updated_at=datetime.utcnow())
                )
                await session.commit()
                
        except Exception as e:
            logger.error(f"Error updating account balance: {str(e)}")
            raise


class BankReconciliationService:
    """Service class for Bank Reconciliation operations."""
    
    @staticmethod
    async def start_reconciliation(bank_account_id: str, reconciliation_date: date, 
                                 statement_balance: float, reconciled_by: str, session: AsyncSession) -> BankReconciliation:
        """Start a new bank reconciliation."""
        try:
            # Get account balance
            account = await session.get(BankAccount, bank_account_id)
            if not account:
                raise ValueError("Bank account not found")
            
            # Create reconciliation record
            reconciliation = BankReconciliation(
                bank_account_id=bank_account_id,
                reconciliation_date=reconciliation_date,
                opening_balance=account.current_balance,
                closing_balance=account.current_balance,
                statement_balance=statement_balance,
                difference_amount=statement_balance - account.current_balance,
                reconciled_by=reconciled_by
            )
            
            session.add(reconciliation)
            await session.commit()
            await session.refresh(reconciliation)
            
            # Perform auto-reconciliation
            await BankReconciliationService._auto_reconcile_transactions(reconciliation.id, session)
            
            return reconciliation
            
        except Exception as e:
            await session.rollback()
            logger.error(f"Error starting reconciliation: {str(e)}")
            raise

    @staticmethod
    async def _auto_reconcile_transactions(reconciliation_id: str, session: AsyncSession) -> None:
        """Automatically reconcile transactions with payments."""
        try:
            reconciliation = await session.get(BankReconciliation, reconciliation_id)
            
            # Get unreconciled transactions
            unreconciled_transactions = await session.execute(
                select(BankTransaction)
                .where(
                    and_(
                        BankTransaction.bank_account_id == reconciliation.bank_account_id,
                        BankTransaction.reconciliation_status == ReconciliationStatusEnum.UNRECONCILED,
                        BankTransaction.transaction_date <= reconciliation.reconciliation_date
                    )
                )
                .order_by(BankTransaction.transaction_date)
            )
            
            transactions = unreconciled_transactions.scalars().all()
            reconciled_count = 0
            
            for transaction in transactions:
                # Try to find matching payment
                matching_payment = await BankReconciliationService._find_matching_payment(transaction, session)
                
                if matching_payment:
                    # Mark as reconciled
                    transaction.reconciliation_status = ReconciliationStatusEnum.RECONCILED
                    transaction.reconciled_with = matching_payment.id
                    transaction.reconciled_date = datetime.utcnow()
                    transaction.reconciled_by = reconciliation.reconciled_by
                    
                    # Update payment reconciliation status
                    matching_payment.reconciled = True
                    matching_payment.reconciled_with_transaction = transaction.id
                    matching_payment.reconciled_date = datetime.utcnow()
                    
                    reconciled_count += 1
            
            # Update reconciliation summary
            total_transactions = len(transactions)
            reconciliation.reconciled_transactions = reconciled_count
            reconciliation.unreconciled_transactions = total_transactions - reconciled_count
            
            if reconciliation.unreconciled_transactions == 0:
                reconciliation.reconciliation_status = ReconciliationStatusEnum.RECONCILED
                reconciliation.completed_at = datetime.utcnow()
            else:
                reconciliation.reconciliation_status = ReconciliationStatusEnum.PARTIALLY_RECONCILED
            
            await session.commit()
            
        except Exception as e:
            logger.error(f"Error in auto-reconciliation: {str(e)}")
            raise

    @staticmethod
    async def _find_matching_payment(transaction: BankTransaction, session: AsyncSession) -> Optional[Payment]:
        """Find matching payment for a bank transaction."""
        try:
            # Match criteria: amount, date range (±3 days), and transaction reference
            date_from = transaction.transaction_date - timedelta(days=3)
            date_to = transaction.transaction_date + timedelta(days=3)
            
            amount_to_match = transaction.debit_amount if transaction.debit_amount > 0 else transaction.credit_amount
            
            query = select(Payment).where(
                and_(
                    Payment.net_amount == amount_to_match,
                    Payment.payment_date.between(date_from, date_to),
                    Payment.payment_status == PaymentStatusEnum.PROCESSED,
                    Payment.reconciled == False
                )
            )
            
            # Try exact reference match first
            if transaction.reference_number:
                exact_match = await session.execute(
                    query.where(
                        or_(
                            Payment.transaction_reference == transaction.reference_number,
                            Payment.utr_number == transaction.reference_number,
                            Payment.cheque_number == transaction.reference_number
                        )
                    )
                )
                
                result = exact_match.scalar_one_or_none()
                if result:
                    return result
            
            # Try amount and date match
            result = await session.execute(query.limit(1))
            return result.scalar_one_or_none()
            
        except Exception as e:
            logger.error(f"Error finding matching payment: {str(e)}")
            return None


class ApprovalMatrixService:
    """Service class for Approval Matrix configuration."""
    
    @staticmethod
    async def create_approval_rule(rule_data: dict, session: AsyncSession) -> ApprovalMatrix:
        """Create a new approval rule."""
        try:
            rule = ApprovalMatrix(**rule_data)
            session.add(rule)
            await session.commit()
            await session.refresh(rule)
            
            return rule
            
        except Exception as e:
            await session.rollback()
            logger.error(f"Error creating approval rule: {str(e)}")
            raise

    @staticmethod
    async def get_approval_rules(session: AsyncSession, module_type: Optional[str] = None) -> List[ApprovalMatrix]:
        """Get approval rules."""
        try:
            query = select(ApprovalMatrix).where(ApprovalMatrix.is_active == True)
            
            if module_type:
                query = query.where(ApprovalMatrix.module_type == module_type)
            
            query = query.order_by(ApprovalMatrix.module_type, ApprovalMatrix.approval_level)
            
            result = await session.execute(query)
            return result.scalars().all()
            
        except Exception as e:
            logger.error(f"Error fetching approval rules: {str(e)}")
            raise


# Import timedelta for reconciliation
from datetime import timedelta 