
from typing import List, Optional
from datetime import datetime
from decimal import Decimal
from sqlalchemy import select, insert, update, func, and_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import selectinload
from app.database import AsyncSessionFactory
from app.models.purchase_bill_models import (
    PurchaseBill, PurchaseBillItem, PurchaseBillCreateRequest, 
    PurchaseBillResponse, PurchaseBillStatus, PurchaseBillItemDB
)
from app.models.purchase_order_models import PurchaseOrder
import uuid

class PurchaseBillService:
    def __init__(self):
        pass

    async def create_purchase_bill(
        self, 
        bill_data: PurchaseBillCreateRequest, 
        user_id: str
    ) -> PurchaseBillResponse:
        async with AsyncSessionFactory() as session:
            try:
                po_result = await session.execute(
                    select(PurchaseOrder).options(selectinload(PurchaseOrder.vendor))
                    .where(
                        and_(
                            PurchaseOrder.id == bill_data.po_id,
                            PurchaseOrder.user_id == user_id
                        )
                    )
                )
                purchase_order = po_result.scalar_one_or_none()

                if not purchase_order:
                    raise ValueError("Purchase Order not found or access denied")

                total_amount = sum(Decimal(str(item.total_price)) for item in bill_data.items)

                bill_id = uuid.uuid4()
                await session.execute(
                    insert(PurchaseBill).values(
                        id=bill_id,
                        user_google_id=user_id,
                        bill_number=bill_data.bill_number,
                        po_id=bill_data.po_id,
                        vendor_id=purchase_order.vendor_id,
                        bill_date=bill_data.bill_date.date(),
                        due_date=bill_data.due_date.date(),
                        total_amount=total_amount,
                        status=bill_data.status.value,
                        notes=bill_data.notes,
                        attachments=','.join(bill_data.attachments) if bill_data.attachments else None,
                        created_at=datetime.utcnow(),
                        created_by=user_id,
                        updated_by=user_id
                    )
                )

                for item in bill_data.items:
                    await session.execute(
                        insert(PurchaseBillItemDB).values(
                            id=uuid.uuid4(),
                            purchase_bill_id=bill_id,
                            po_item_id=item.po_item_id,
                            item_description=item.item_description,
                            quantity=item.quantity,
                            unit_price=item.unit_price,
                            total_price=item.total_price,
                            notes=item.notes
                        )
                    )

                await session.commit()

                return PurchaseBillResponse(
                    id=str(bill_id),
                    bill_number=bill_data.bill_number,
                    po_id=bill_data.po_id,
                    po_number=purchase_order.po_number,
                    vendor_name=purchase_order.vendor.business_name if purchase_order.vendor else "Unknown Vendor",
                    bill_date=bill_data.bill_date,
                    due_date=bill_data.due_date,
                    total_amount=float(total_amount),
                    status=bill_data.status,
                    items=bill_data.items,
                    notes=bill_data.notes,
                    attachments=bill_data.attachments,
                    created_at=datetime.utcnow(),
                    updated_at=datetime.utcnow(),
                    created_by=user_id
                )

            except IntegrityError as e:
                await session.rollback()
                if "unique constraint" in str(e).lower():
                    raise ValueError(f"Purchase Bill number '{bill_data.bill_number}' already exists")
                raise ValueError(f"Database constraint error: {str(e)}")
            except Exception as e:
                await session.rollback()
                raise Exception(f"Failed to create purchase bill: {str(e)}")

    async def get_purchase_bills(
        self, 
        user_id: str, 
        skip: int = 0, 
        limit: int = 100,
        status: Optional[str] = None,
        po_id: Optional[str] = None
    ) -> List[PurchaseBillResponse]:
        async with AsyncSessionFactory() as session:
            try:
                query = select(PurchaseBill).where(PurchaseBill.user_google_id == user_id)

                if status:
                    query = query.where(PurchaseBill.status == status)
                if po_id:
                    query = query.where(PurchaseBill.po_id == po_id)

                query = query.offset(skip).limit(limit).order_by(PurchaseBill.created_at.desc())

                result = await session.execute(query)
                bill_records = result.scalars().all()

                bills = []
                for bill in bill_records:
                    # Create basic response without relationships for now
                    bills.append(PurchaseBillResponse(
                        id=str(bill.id),
                        bill_number=bill.bill_number,
                        po_id=str(bill.po_id) if bill.po_id else '',
                        po_number='', # Will be populated from PO lookup if needed
                        vendor_name='', # Will be populated from vendor lookup if needed
                        bill_date=datetime.combine(bill.bill_date, datetime.min.time()),
                        due_date=datetime.combine(bill.due_date, datetime.min.time()),
                        taxable_amount=float(bill.taxable_amount or 0),
                        total_cgst=float(bill.total_cgst or 0),
                        total_sgst=float(bill.total_sgst or 0),
                        total_igst=float(bill.total_igst or 0),
                        total_amount=float(bill.total_amount or 0),
                        grand_total=float(bill.grand_total or 0),
                        status=PurchaseBillStatus(bill.status.lower()) if bill.status else PurchaseBillStatus.DRAFT,
                        items=[], # Will be populated from items lookup if needed
                        notes=bill.notes,
                        attachments=bill.attachments.split(',') if bill.attachments else [],
                        created_at=bill.created_at,
                        updated_at=bill.updated_at,
                        created_by=bill.created_by
                    ))
                
                return bills
                
            except Exception as e:
                raise Exception(f"Failed to fetch purchase bills: {str(e)}")

    async def get_purchase_bill_by_id(
        self, 
        bill_id: str, 
        user_id: str
    ) -> Optional[PurchaseBillResponse]:
        async with AsyncSessionFactory() as session:
            try:
                query = select(PurchaseBill).options(
                    selectinload(PurchaseBill.items),
                    selectinload(PurchaseBill.purchase_order),
                    selectinload(PurchaseBill.vendor)
                ).where(
                    and_(
                        PurchaseBill.id == bill_id,
                        PurchaseBill.user_google_id == user_id
                    )
                )

                result = await session.execute(query)
                bill = result.scalar_one_or_none()

                if not bill:
                    return None

                items = [item.__dict__ for item in bill.items]
                return PurchaseBillResponse(
                    id=str(bill.id),
                    bill_number=bill.bill_number,
                    po_id=str(bill.po_id),
                    po_number=bill.purchase_order.po_number if bill.purchase_order else "Unknown",
                    vendor_name=bill.vendor.business_name if bill.vendor else "Unknown Vendor",
                    bill_date=datetime.combine(bill.bill_date, datetime.min.time()),
                    due_date=datetime.combine(bill.due_date, datetime.min.time()),
                    total_amount=float(bill.total_amount),
                    status=PurchaseBillStatus(bill.status.lower()) if bill.status else PurchaseBillStatus.DRAFT,
                    items=items,
                    notes=bill.notes,
                    attachments=bill.attachments.split(',') if bill.attachments else None,
                    created_at=bill.created_at,
                    updated_at=bill.updated_at,
                    created_by=bill.created_by
                )

            except Exception as e:
                raise Exception(f"Failed to fetch purchase bill: {str(e)}")

purchase_bill_service = PurchaseBillService()
