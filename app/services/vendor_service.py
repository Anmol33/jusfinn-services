from typing import List, Optional, Dict, Any
from datetime import datetime
from sqlalchemy import select, insert, update, delete, func, and_, or_
from sqlalchemy.exc import IntegrityError
from app.database import get_postgres_session_direct
from app.models import (
    Vendor, VendorCreateRequest, VendorUpdateRequest, VendorResponse, VendorAddress,
    VendorPaymentTerms, State
)


class VendorService:
    """Service class for vendor management operations using PostgreSQL."""
    
    def __init__(self):
        pass
    
    async def create_vendor(
        self, 
        vendor_data: VendorCreateRequest, 
        user_id: str
    ) -> VendorResponse:
        """Create a new vendor."""
        
        async with get_postgres_session_direct() as session:
            try:
                # Check if vendor code already exists for this user
                existing_vendor = await session.execute(
                    select(Vendor).where(
                        and_(
                            Vendor.user_id == user_id,
                            Vendor.vendor_code == vendor_data.vendor_code
                        )
                    )
                )
                existing_vendor = existing_vendor.scalar_one_or_none()
                
                if existing_vendor:
                    raise ValueError(f"Vendor code '{vendor_data.vendor_code}' already exists")
                
                # Check if vendor with same PAN exists for this user (if PAN provided)
                if vendor_data.pan:
                    existing_pan = await session.execute(
                        select(Vendor).where(
                            and_(
                                Vendor.user_id == user_id,
                                Vendor.pan == vendor_data.pan
                            )
                        )
                    )
                    existing_pan = existing_pan.scalar_one_or_none()
                    
                    if existing_pan:
                        raise ValueError(f"Vendor with PAN '{vendor_data.pan}' already exists")
                
                # Create vendor record - Updated to match new schema
                new_vendor = Vendor(
                    user_id=user_id,
                    vendor_code=vendor_data.vendor_code,
                    business_name=vendor_data.business_name,
                    legal_name=vendor_data.legal_name,
                    gstin=vendor_data.gstin,
                    pan=vendor_data.pan,
                    
                    # --- Critical Compliance Fields ---
                    is_msme=vendor_data.is_msme,
                    udyam_registration_number=vendor_data.udyam_registration_number,
                    
                    contact_person=vendor_data.contact_person,
                    phone=vendor_data.phone,
                    email=vendor_data.email,
                    website=vendor_data.website,
                    
                    # --- Payment & Terms ---
                    credit_limit=vendor_data.credit_limit,
                    credit_days=vendor_data.credit_days,
                    payment_terms=vendor_data.payment_terms.value,
                    
                    # --- Critical Banking Fields ---
                    bank_account_number=vendor_data.bank_account_number,
                    bank_ifsc_code=vendor_data.bank_ifsc_code,
                    bank_account_holder_name=vendor_data.bank_account_holder_name,

                    # --- Address ---
                    address_line1=vendor_data.address.address_line1,
                    address_line2=vendor_data.address.address_line2,
                    city=vendor_data.address.city,
                    state_id=vendor_data.address.state_id,
                    pincode=vendor_data.address.pincode,
                    country=vendor_data.address.country,
                    
                    # --- Critical Tax & Accounting Fields ---
                    tds_applicable=vendor_data.tds_applicable,
                    default_tds_section=vendor_data.default_tds_section,
                    default_expense_ledger_id=vendor_data.default_expense_ledger_id,

                    # --- System Fields ---
                    is_active=True,
                    created_at=datetime.utcnow(),
                    updated_at=datetime.utcnow()
                )
                
                # Add and commit vendor
                session.add(new_vendor)
                await session.commit()
                await session.refresh(new_vendor)
                
                return self._vendor_obj_to_response(new_vendor)
                
            except IntegrityError as e:
                await session.rollback()
                raise ValueError(f"Database constraint violation: {str(e)}")
            except Exception as e:
                await session.rollback()
                raise Exception(f"Failed to create vendor: {str(e)}")
    
    async def get_vendors(
        self, 
        user_id: str,
        skip: int = 0,
        limit: int = 100,
        status: Optional[str] = None,
        is_msme: Optional[bool] = None,
        search: Optional[str] = None
    ) -> List[VendorResponse]:
        """Get vendors with filtering and pagination."""
        
        async with get_postgres_session_direct() as session:
            # Build query
            query = select(Vendor).where(Vendor.user_id == user_id)
            
            # Add filters
            if status:
                if status.lower() == 'active':
                    query = query.where(Vendor.is_active == True)
                elif status.lower() == 'inactive':
                    query = query.where(Vendor.is_active == False)
            
            if is_msme is not None:
                query = query.where(Vendor.is_msme == is_msme)
            
            if search:
                search_term = f"%{search}%"
                query = query.where(
                    or_(
                        Vendor.business_name.ilike(search_term),
                        Vendor.vendor_code.ilike(search_term),
                        Vendor.email.ilike(search_term),
                        Vendor.pan.ilike(search_term),
                        Vendor.gstin.ilike(search_term)
                    )
                )
            
            # Add pagination and ordering
            query = query.order_by(Vendor.created_at.desc()).offset(skip).limit(limit)

            try:
                result = await session.execute(query)
            except Exception as e:
                print(f"Failed to execute query: {e}")
                raise

            vendors = result.scalars().all()

            print(f"vendors: {len(vendors)}")
            
            return [self._vendor_obj_to_response(vendor) for vendor in vendors]
    
    async def get_vendor_by_id(
        self, 
        vendor_id: str, 
        user_id: str
    ) -> Optional[VendorResponse]:
        """Get vendor by ID."""
        
        async with get_postgres_session_direct() as session:
            try:
                result = await session.execute(
                    select(Vendor).where(
                        and_(
                            Vendor.id == vendor_id,
                            Vendor.user_id == user_id
                        )
                    )
                )
                vendor = result.scalar_one_or_none()
                
                if vendor:
                    return self._vendor_obj_to_response(vendor)
                return None
                
            except Exception:
                return None
    
    async def update_vendor(
        self, 
        vendor_id: str, 
        update_data: VendorUpdateRequest, 
        user_id: str
    ) -> Optional[VendorResponse]:
        """Update vendor information."""
        
        async with get_postgres_session_direct() as session:
            try:
                # Get the vendor first
                result = await session.execute(
                    select(Vendor).where(
                        and_(
                            Vendor.id == vendor_id,
                            Vendor.user_id == user_id
                        )
                    )
                )
                vendor = result.scalar_one_or_none()
                
                if not vendor:
                    return None
                
                # Update fields from VendorUpdateRequest
                update_fields = update_data.model_dump(exclude_unset=True)
                
                # Handle address separately
                if 'address' in update_fields and update_fields['address']:
                    address_data = update_fields['address']
                    vendor.address_line1 = address_data.get('address_line1')
                    vendor.address_line2 = address_data.get('address_line2')
                    vendor.city = address_data.get('city')
                    vendor.state_id = address_data.get('state_id')
                    vendor.pincode = address_data.get('pincode')
                    vendor.country = address_data.get('country')
                    del update_fields['address']
                
                # Handle payment_terms enum
                if 'payment_terms' in update_fields and update_fields['payment_terms']:
                    update_fields['payment_terms'] = update_fields['payment_terms'].value
                
                # Update other fields
                for key, value in update_fields.items():
                    if hasattr(vendor, key) and value is not None:
                        setattr(vendor, key, value)
                
                vendor.updated_at = datetime.utcnow()
                
                await session.commit()
                await session.refresh(vendor)
                
                return self._vendor_obj_to_response(vendor)
                
            except Exception as e:
                await session.rollback()
                raise Exception(f"Failed to update vendor: {str(e)}")
    
    async def delete_vendor(
        self, 
        vendor_id: str, 
        user_id: str
    ) -> bool:
        """Delete vendor (soft delete by changing status)."""
        
        async with get_postgres_session_direct() as session:
            try:
                # Get the vendor first
                result = await session.execute(
                    select(Vendor).where(
                        and_(
                            Vendor.id == vendor_id,
                            Vendor.user_id == user_id
                        )
                    )
                )
                vendor = result.scalar_one_or_none()
                
                if not vendor:
                    return False
                
                vendor.is_active = False
                vendor.updated_at = datetime.utcnow()
                
                await session.commit()
                return True
                
            except Exception:
                await session.rollback()
                return False
    
    async def search_vendors_by_name_or_code(
        self, 
        search_term: str, 
        user_id: str
    ) -> List[Dict[str, Any]]:
        """Search vendors by name or code for dropdowns."""
        
        async with get_postgres_session_direct() as session:
            search_pattern = f"%{search_term}%"
            
            query = (
                select(
                    Vendor.id,
                    Vendor.vendor_code,
                    Vendor.business_name,
                    Vendor.is_msme,
                    Vendor.default_tds_section,
                    Vendor.tds_applicable
                )
                .where(
                    and_(
                        Vendor.user_id == user_id,
                        Vendor.is_active == True,
                        or_(
                            Vendor.business_name.ilike(search_pattern),
                            Vendor.vendor_code.ilike(search_pattern)
                        )
                    )
                )
                .limit(10)
            )
            
            result = await session.execute(query)
            vendors = result.all()
            
            return [
                {
                    "id": str(vendor.id),
                    "vendor_code": vendor.vendor_code,
                    "name": vendor.business_name,
                    "is_msme": vendor.is_msme,
                    "default_tds_section": vendor.default_tds_section,
                    "tds_applicable": vendor.tds_applicable
                }
                for vendor in vendors
            ]
    
    async def get_vendor_stats(self, user_id: str) -> Dict[str, Any]:
        """Get vendor statistics."""
        
        async with get_postgres_session_direct() as session:
            try:
                # Total vendors
                total_result = await session.execute(
                    select(func.count(Vendor.id)).where(Vendor.user_id == user_id)
                )
                total_vendors = total_result.scalar()
                
                # Active vendors
                active_result = await session.execute(
                    select(func.count(Vendor.id)).where(
                        and_(
                            Vendor.user_id == user_id,
                            Vendor.is_active == True
                        )
                    )
                )
                active_vendors = active_result.scalar()
                
                # MSME vendors
                msme_result = await session.execute(
                    select(func.count(Vendor.id)).where(
                        and_(
                            Vendor.user_id == user_id,
                            Vendor.is_msme == True
                        )
                    )
                )
                msme_vendors = msme_result.scalar()
                
                # Average credit limit
                avg_result = await session.execute(
                    select(func.avg(Vendor.credit_limit)).where(Vendor.user_id == user_id)
                )
                avg_credit_limit = avg_result.scalar()
                
                return {
                    "total_vendors": total_vendors or 0,
                    "active_vendors": active_vendors or 0,
                    "msme_vendors": msme_vendors or 0,
                    "avg_credit_limit": round(float(avg_credit_limit or 0), 2)
                }
                
            except Exception:
                return {
                    "total_vendors": 0,
                    "active_vendors": 0,
                    "msme_vendors": 0,
                    "avg_credit_limit": 0.0
                }
    
    def _vendor_obj_to_response(self, vendor: Vendor) -> VendorResponse:
        """Convert SQLAlchemy object to VendorResponse."""
        
        return VendorResponse(
            id=str(vendor.id),
            vendor_code=vendor.vendor_code,
            business_name=vendor.business_name,
            legal_name=vendor.legal_name,
            gstin=vendor.gstin,
            pan=vendor.pan,
            
            # --- Critical Compliance Fields ---
            is_msme=vendor.is_msme,
            udyam_registration_number=vendor.udyam_registration_number,
            
            # Contact Information
            contact_person=vendor.contact_person,
            phone=vendor.phone,
            email=vendor.email,
            website=vendor.website,
            
            # --- Payment & Terms ---
            credit_limit=float(vendor.credit_limit),
            credit_days=vendor.credit_days,
            payment_terms=vendor.payment_terms,
            
            # --- Critical Banking Fields ---
            bank_account_number=vendor.bank_account_number,
            bank_ifsc_code=vendor.bank_ifsc_code,
            bank_account_holder_name=vendor.bank_account_holder_name,
            
            # Address
            address_line1=vendor.address_line1,
            address_line2=vendor.address_line2,
            city=vendor.city,
            state_id=vendor.state_id,
            pincode=vendor.pincode,
            country=vendor.country,
            
            # --- Critical Tax & Accounting Fields ---
            tds_applicable=vendor.tds_applicable,
            default_tds_section=vendor.default_tds_section,
            default_expense_ledger_id=vendor.default_expense_ledger_id,
            
            # Business Metrics
            vendor_rating=vendor.vendor_rating,
            total_purchases=float(vendor.total_purchases),
            outstanding_amount=float(vendor.outstanding_amount),
            last_transaction_date=vendor.last_transaction_date.isoformat() if vendor.last_transaction_date else None,
            
            # Status and Audit
            is_active=vendor.is_active,
            created_at=vendor.created_at,
            updated_at=vendor.updated_at
        )


# Create service instance
vendor_service = VendorService() 