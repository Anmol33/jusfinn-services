"""
GST Service - Handle E-Invoice generation and GSTR filing
Integrates with Government of India GST APIs
"""

import json
import uuid
import requests
import hashlib
import base64
from datetime import datetime, date, timedelta
from decimal import Decimal
from typing import Dict, List, Any, Optional
from sqlalchemy.orm import Session
from sqlalchemy import and_, func

from ..models import *
from ..config import settings

class GSTService:
    """Service for GST compliance and API integration"""
    
    def __init__(self, db: Session):
        self.db = db
        self.einvoice_base_url = settings.GST_EINVOICE_API_URL
        self.gst_base_url = settings.GST_API_URL
        self.api_timeout = 30
    
    async def generate_einvoice(self, invoice_id: uuid.UUID) -> Dict[str, Any]:
        """Generate E-Invoice using NIC APIs"""
        
        try:
            # Get invoice with all related data
            invoice = self.db.query(TaxInvoice).filter(
                TaxInvoice.id == invoice_id
            ).first()
            
            if not invoice:
                raise ValueError("Invoice not found")
            
            # Check if E-Invoice already generated
            if invoice.irn:
                return {
                    "status": "already_generated",
                    "irn": invoice.irn,
                    "ack_number": invoice.ack_number
                }
            
            # Get company and customer details
            company = self.db.query(Company).filter(Company.id == invoice.company_id).first()
            customer = self.db.query(Customer).filter(Customer.id == invoice.customer_id).first()
            
            if not company.gstin or not customer.gstin:
                raise ValueError("GSTIN required for both company and customer for E-Invoice")
            
            # Prepare E-Invoice JSON payload
            einvoice_payload = await self._prepare_einvoice_payload(invoice, company, customer)
            
            # Get authentication token
            auth_token = await self._get_gst_auth_token(company.gstin)
            
            # Call E-Invoice API
            response = await self._call_einvoice_api(einvoice_payload, auth_token)
            
            if response.get("Status") == "1":  # Success
                # Update invoice with E-Invoice details
                invoice.irn = response.get("Irn")
                invoice.ack_number = response.get("AckNo")
                invoice.ack_date = datetime.now()
                invoice.qr_code = response.get("QRCodeUrl")
                invoice.signed_qr_code = response.get("SignedQRCode")
                
                # Log API request
                self._log_gst_api_request(
                    company_id=invoice.company_id,
                    api_type="EINVOICE",
                    request_type="GENERATE",
                    reference_id=invoice.id,
                    reference_number=invoice.invoice_number,
                    request_payload=einvoice_payload,
                    response_payload=response,
                    status="SUCCESS",
                    irn=response.get("Irn"),
                    ack_number=response.get("AckNo")
                )
                
                self.db.commit()
                
                return {
                    "status": "success",
                    "irn": invoice.irn,
                    "ack_number": invoice.ack_number,
                    "qr_code": invoice.qr_code
                }
            else:
                # Handle API errors
                error_message = response.get("ErrorDetails", "Unknown error")
                
                self._log_gst_api_request(
                    company_id=invoice.company_id,
                    api_type="EINVOICE",
                    request_type="GENERATE",
                    reference_id=invoice.id,
                    reference_number=invoice.invoice_number,
                    request_payload=einvoice_payload,
                    response_payload=response,
                    status="FAILED",
                    error_message=error_message
                )
                
                raise ValueError(f"E-Invoice generation failed: {error_message}")
                
        except Exception as e:
            self.db.rollback()
            raise e
    
    async def _prepare_einvoice_payload(self, invoice: TaxInvoice, company: Company, customer: Customer) -> Dict[str, Any]:
        """Prepare E-Invoice JSON payload as per GST schema"""
        
        # Get invoice items
        items = self.db.query(TaxInvoiceItem).filter(
            TaxInvoiceItem.invoice_id == invoice.id
        ).all()
        
        # Get state details
        company_state = self.db.query(State).filter(State.id == company.state_id).first()
        customer_state = self.db.query(State).filter(State.id == customer.billing_state_id).first()
        
        # Determine transaction type
        transaction_type = "B2B"
        if not customer.gstin:
            transaction_type = "B2C"
        
        # Build item details
        item_list = []
        for idx, item in enumerate(items, 1):
            item_service = self.db.query(ItemService).filter(
                ItemService.id == item.item_service_id
            ).first()
            
            hsn_sac = self.db.query(HSNSACCode).filter(
                HSNSACCode.id == item_service.hsn_sac_code_id
            ).first()
            
            item_detail = {
                "SlNo": str(idx),
                "PrdDesc": item_service.name[:300],  # Max 300 chars
                "IsServc": "Y" if item_service.type == "SERVICE" else "N",
                "HsnCd": hsn_sac.code if hsn_sac else "",
                "Qty": float(item.quantity),
                "Unit": item_service.unit_of_measure[:8] if item_service.unit_of_measure else "NOS",
                "UnitPrice": float(item.unit_price),
                "TotAmt": float(item.total_amount),
                "Discount": float(item.discount_amount) if item.discount_amount else 0,
                "AssAmt": float(item.taxable_amount),
                "GstRt": float(item.cgst_rate + item.sgst_rate + item.igst_rate),
                "IgstAmt": float(item.igst_amount),
                "CgstAmt": float(item.cgst_amount),
                "SgstAmt": float(item.sgst_amount),
                "CesRt": float(item.cess_rate) if item.cess_rate else 0,
                "CesAmt": float(item.cess_amount) if item.cess_amount else 0,
                "CesNonAdvlAmt": 0,
                "StateCesRt": 0,
                "StateCesAmt": 0,
                "StateCesNonAdvlAmt": 0,
                "OthChrg": 0,
                "TotItemVal": float(item.total_amount)
            }
            item_list.append(item_detail)
        
        # Build main payload
        payload = {
            "Version": "1.1",
            "TranDtls": {
                "TaxSch": "GST",
                "SupTyp": transaction_type,
                "RegRev": "N",
                "EcmGstin": None,
                "IgstOnIntra": "N"
            },
            "DocDtls": {
                "Typ": "INV",
                "No": invoice.invoice_number,
                "Dt": invoice.invoice_date.strftime("%d/%m/%Y")
            },
            "SellerDtls": {
                "Gstin": company.gstin,
                "LglNm": company.legal_name[:100],
                "TrdNm": company.trade_name[:100] if company.trade_name else company.legal_name[:100],
                "Addr1": company.address_line1[:100],
                "Addr2": company.address_line2[:100] if company.address_line2 else "",
                "Loc": company.city[:50],
                "Pin": company.pincode,
                "Stcd": company_state.gst_state_code,
                "Ph": company.phone,
                "Em": company.email
            },
            "BuyerDtls": {
                "Gstin": customer.gstin if customer.gstin else "",
                "LglNm": customer.legal_name[:100] if customer.legal_name else customer.business_name[:100],
                "TrdNm": customer.business_name[:100],
                "Pos": customer_state.gst_state_code,
                "Addr1": customer.billing_address_line1[:100] if customer.billing_address_line1 else "",
                "Addr2": customer.billing_address_line2[:100] if customer.billing_address_line2 else "",
                "Loc": customer.billing_city[:50] if customer.billing_city else "",
                "Pin": customer.billing_pincode if customer.billing_pincode else "",
                "Stcd": customer_state.gst_state_code,
                "Ph": customer.phone,
                "Em": customer.email
            },
            "ItemList": item_list,
            "ValDtls": {
                "AssVal": float(invoice.subtotal),
                "CgstVal": float(invoice.cgst_amount),
                "SgstVal": float(invoice.sgst_amount),
                "IgstVal": float(invoice.igst_amount),
                "CesVal": float(invoice.cess_amount) if invoice.cess_amount else 0,
                "StCesVal": 0,
                "Discount": float(invoice.discount_amount) if invoice.discount_amount else 0,
                "OthChrg": 0,
                "RndOffAmt": 0,
                "TotInvVal": float(invoice.total_amount),
                "TotInvValFc": float(invoice.total_amount)
            }
        }
        
        # Add export details if applicable
        if customer.billing_country and customer.billing_country.upper() != "INDIA":
            payload["ExpDtls"] = {
                "ShipBNo": "",
                "ShipBDt": "",
                "Port": "",
                "RefClm": "N",
                "ForCur": "USD",  # Default to USD for exports
                "CntCode": customer.billing_country[:2].upper()
            }
        
        return payload
    
    async def _get_gst_auth_token(self, gstin: str) -> str:
        """Get authentication token for GST APIs"""
        
        # This is a simplified implementation
        # In production, implement proper OAuth flow with GST portal
        
        auth_payload = {
            "action": "ACCESSTOKEN",
            "username": settings.GST_USERNAME,
            "password": settings.GST_PASSWORD,
            "app_id": settings.GST_APP_ID
        }
        
        response = requests.post(
            f"{self.gst_base_url}/auth",
            json=auth_payload,
            timeout=self.api_timeout
        )
        
        if response.status_code == 200:
            return response.json().get("access_token")
        else:
            raise ValueError("Failed to get GST authentication token")
    
    async def _call_einvoice_api(self, payload: Dict[str, Any], auth_token: str) -> Dict[str, Any]:
        """Call the E-Invoice generation API"""
        
        headers = {
            "Authorization": f"Bearer {auth_token}",
            "Content-Type": "application/json",
            "user_name": settings.GST_USERNAME,
            "gstin": payload["SellerDtls"]["Gstin"]
        }
        
        response = requests.post(
            f"{self.einvoice_base_url}/generate",
            json=payload,
            headers=headers,
            timeout=self.api_timeout
        )
        
        return response.json()
    
    async def compile_gstr1_data(self, company_id: uuid.UUID, return_period: str) -> Dict[str, Any]:
        """Compile GSTR-1 data for the specified period"""
        
        try:
            # Parse return period
            month, year = return_period.split('-')
            month = int(month)
            year = int(year)
            
            # Calculate date range
            from datetime import date
            start_date = date(year, month, 1)
            if month == 12:
                end_date = date(year + 1, 1, 1) - timedelta(days=1)
            else:
                end_date = date(year, month + 1, 1) - timedelta(days=1)
            
            # Get all invoices for the period
            invoices = self.db.query(TaxInvoice).filter(
                and_(
                    TaxInvoice.company_id == company_id,
                    TaxInvoice.invoice_date >= start_date,
                    TaxInvoice.invoice_date <= end_date,
                    TaxInvoice.status.in_(['SENT', 'PAID', 'PARTIALLY_PAID'])
                )
            ).all()
            
            # Categorize invoices
            b2b_invoices = []
            b2c_large_invoices = []
            b2c_small_summary = {}
            exports = []
            
            total_taxable_value = Decimal('0')
            total_tax_amount = Decimal('0')
            
            for invoice in invoices:
                customer = self.db.query(Customer).filter(Customer.id == invoice.customer_id).first()
                
                # Get invoice items with tax details
                items = self.db.query(TaxInvoiceItem).filter(
                    TaxInvoiceItem.invoice_id == invoice.id
                ).all()
                
                invoice_data = {
                    "inum": invoice.invoice_number,
                    "idt": invoice.invoice_date.strftime("%d-%m-%Y"),
                    "val": float(invoice.total_amount),
                    "pos": customer.billing_state_id if customer.billing_state_id else "07",  # Default to Delhi
                    "rchrg": "Y" if invoice.reverse_charge_applicable else "N",
                    "etin": customer.gstin if customer.gstin else "",
                    "itms": []
                }
                
                # Group items by tax rate
                tax_groups = {}
                for item in items:
                    item_service = self.db.query(ItemService).filter(
                        ItemService.id == item.item_service_id
                    ).first()
                    
                    hsn_sac = self.db.query(HSNSACCode).filter(
                        HSNSACCode.id == item_service.hsn_sac_code_id
                    ).first()
                    
                    tax_rate = item.cgst_rate + item.sgst_rate + item.igst_rate
                    hsn_code = hsn_sac.code if hsn_sac else "99999"
                    
                    key = f"{hsn_code}_{tax_rate}"
                    
                    if key not in tax_groups:
                        tax_groups[key] = {
                            "num": 1,
                            "itm_det": {
                                "rt": float(tax_rate),
                                "txval": float(item.taxable_amount),
                                "iamt": float(item.igst_amount),
                                "camt": float(item.cgst_amount),
                                "samt": float(item.sgst_amount),
                                "csamt": float(item.cess_amount) if item.cess_amount else 0
                            }
                        }
                    else:
                        tax_groups[key]["itm_det"]["txval"] += float(item.taxable_amount)
                        tax_groups[key]["itm_det"]["iamt"] += float(item.igst_amount)
                        tax_groups[key]["itm_det"]["camt"] += float(item.cgst_amount)
                        tax_groups[key]["itm_det"]["samt"] += float(item.sgst_amount)
                        tax_groups[key]["itm_det"]["csamt"] += float(item.cess_amount) if item.cess_amount else 0
                
                # Add tax groups to invoice
                for key, tax_data in tax_groups.items():
                    hsn_code = key.split('_')[0]
                    invoice_data["itms"].append({
                        "num": tax_data["num"],
                        "itm_det": {
                            "hsn_sc": hsn_code,
                            **tax_data["itm_det"]
                        }
                    })
                
                # Categorize invoice
                if customer.gstin:
                    # B2B transaction
                    ctin = customer.gstin
                    if ctin not in [inv["ctin"] for inv in b2b_invoices]:
                        b2b_invoices.append({
                            "ctin": ctin,
                            "inv": [invoice_data]
                        })
                    else:
                        # Find existing customer and add invoice
                        for b2b_inv in b2b_invoices:
                            if b2b_inv["ctin"] == ctin:
                                b2b_inv["inv"].append(invoice_data)
                                break
                
                elif invoice.total_amount >= 250000:  # B2C Large (>= 2.5L)
                    b2c_large_invoices.append(invoice_data)
                
                else:  # B2C Small
                    # Summarize by state and tax rate
                    state_code = customer.billing_state_id if customer.billing_state_id else "07"
                    for item_group in invoice_data["itms"]:
                        rate = item_group["itm_det"]["rt"]
                        key = f"{state_code}_{rate}"
                        
                        if key not in b2c_small_summary:
                            b2c_small_summary[key] = {
                                "sply_ty": "INTRA" if state_code == "07" else "INTER",  # Assuming company in Delhi
                                "pos": state_code,
                                "typ": "OE",  # Others
                                "txval": 0,
                                "iamt": 0,
                                "camt": 0,
                                "samt": 0,
                                "csamt": 0,
                                "rt": rate
                            }
                        
                        b2c_small_summary[key]["txval"] += item_group["itm_det"]["txval"]
                        b2c_small_summary[key]["iamt"] += item_group["itm_det"]["iamt"]
                        b2c_small_summary[key]["camt"] += item_group["itm_det"]["camt"]
                        b2c_small_summary[key]["samt"] += item_group["itm_det"]["samt"]
                        b2c_small_summary[key]["csamt"] += item_group["itm_det"]["csamt"]
                
                total_taxable_value += invoice.subtotal
                total_tax_amount += (invoice.cgst_amount + invoice.sgst_amount + invoice.igst_amount + (invoice.cess_amount or 0))
            
            # Convert B2C small summary to list
            b2c_small_list = list(b2c_small_summary.values())
            
            # Get credit/debit notes
            credit_notes = await self._get_credit_debit_notes(company_id, start_date, end_date)
            
            # Compile final data
            gstr1_data = {
                "gstin": self.db.query(Company).filter(Company.id == company_id).first().gstin,
                "ret_period": return_period,
                "b2b": b2b_invoices,
                "b2cl": b2c_large_invoices,
                "b2cs": b2c_small_list,
                "cdnr": credit_notes,
                "exp": exports,
                "at": [],  # Advance tax
                "atadj": [],  # Advance tax adjustments
                "exemp": [],  # Exempt supplies
                "hsn": await self._get_hsn_summary(company_id, start_date, end_date)
            }
            
            # Save compiled data
            gstr1_record = GSTR1Data(
                company_id=company_id,
                return_period=return_period,
                b2b_invoices=b2b_invoices,
                b2c_large_invoices=b2c_large_invoices,
                b2c_small_invoices=b2c_small_list,
                credit_debit_notes=credit_notes,
                exports=exports,
                compilation_status='READY',
                total_taxable_value=total_taxable_value,
                total_tax_amount=total_tax_amount,
                compiled_at=datetime.now()
            )
            
            self.db.add(gstr1_record)
            self.db.commit()
            
            return gstr1_data
            
        except Exception as e:
            self.db.rollback()
            raise e
    
    async def _get_credit_debit_notes(self, company_id: uuid.UUID, start_date: date, end_date: date) -> List[Dict[str, Any]]:
        """Get credit/debit notes for GSTR-1"""
        
        credit_notes = self.db.query(CreditNote).filter(
            and_(
                CreditNote.company_id == company_id,
                CreditNote.credit_note_date >= start_date,
                CreditNote.credit_note_date <= end_date,
                CreditNote.status == 'APPROVED'
            )
        ).all()
        
        cdnr_data = []
        
        for note in credit_notes:
            customer = self.db.query(Customer).filter(Customer.id == note.customer_id).first()
            
            if customer.gstin:  # Only for registered customers
                note_data = {
                    "ctin": customer.gstin,
                    "nt": [{
                        "ntty": "C",  # Credit Note
                        "nt_num": note.credit_note_number,
                        "nt_dt": note.credit_note_date.strftime("%d-%m-%Y"),
                        "rsn": note.reason_description,
                        "val": float(note.total_amount),
                        "itms": []
                    }]
                }
                
                # Get note items
                note_items = self.db.query(CreditNoteItem).filter(
                    CreditNoteItem.credit_note_id == note.id
                ).all()
                
                for item in note_items:
                    item_service = self.db.query(ItemService).filter(
                        ItemService.id == item.item_service_id
                    ).first()
                    
                    hsn_sac = self.db.query(HSNSACCode).filter(
                        HSNSACCode.id == item_service.hsn_sac_code_id
                    ).first()
                    
                    note_data["nt"][0]["itms"].append({
                        "num": 1,
                        "itm_det": {
                            "hsn_sc": hsn_sac.code if hsn_sac else "99999",
                            "rt": float(item.cgst_rate + item.sgst_rate + item.igst_rate),
                            "txval": float(item.taxable_amount),
                            "iamt": float(item.igst_amount),
                            "camt": float(item.cgst_amount),
                            "samt": float(item.sgst_amount),
                            "csamt": float(item.cess_amount) if item.cess_amount else 0
                        }
                    })
                
                cdnr_data.append(note_data)
        
        return cdnr_data
    
    async def _get_hsn_summary(self, company_id: uuid.UUID, start_date: date, end_date: date) -> List[Dict[str, Any]]:
        """Get HSN-wise summary for GSTR-1"""
        
        # Query to get HSN-wise summary
        hsn_summary = self.db.query(
            HSNSACCode.code,
            HSNSACCode.description,
            func.sum(TaxInvoiceItem.quantity).label('total_qty'),
            func.sum(TaxInvoiceItem.taxable_amount).label('total_val'),
            func.sum(TaxInvoiceItem.igst_amount).label('iamt'),
            func.sum(TaxInvoiceItem.cgst_amount).label('camt'),
            func.sum(TaxInvoiceItem.sgst_amount).label('samt'),
            func.sum(TaxInvoiceItem.cess_amount).label('csamt')
        ).join(
            ItemService, HSNSACCode.id == ItemService.hsn_sac_code_id
        ).join(
            TaxInvoiceItem, ItemService.id == TaxInvoiceItem.item_service_id
        ).join(
            TaxInvoice, TaxInvoiceItem.invoice_id == TaxInvoice.id
        ).filter(
            and_(
                TaxInvoice.company_id == company_id,
                TaxInvoice.invoice_date >= start_date,
                TaxInvoice.invoice_date <= end_date,
                TaxInvoice.status.in_(['SENT', 'PAID', 'PARTIALLY_PAID'])
            )
        ).group_by(
            HSNSACCode.code, HSNSACCode.description
        ).all()
        
        hsn_data = []
        for row in hsn_summary:
            hsn_data.append({
                "num": len(hsn_data) + 1,
                "hsn_sc": row.code,
                "desc": row.description[:30],  # Max 30 chars
                "uqc": "NOS",  # Default unit
                "qty": float(row.total_qty or 0),
                "val": float(row.total_val or 0),
                "txval": float(row.total_val or 0),
                "iamt": float(row.iamt or 0),
                "camt": float(row.camt or 0),
                "samt": float(row.samt or 0),
                "csamt": float(row.csamt or 0)
            })
        
        return hsn_data
    
    def _log_gst_api_request(self, **kwargs):
        """Log GST API request for audit trail"""
        
        api_log = GSTAPIRequest(
            company_id=kwargs.get('company_id'),
            api_type=kwargs.get('api_type'),
            request_type=kwargs.get('request_type'),
            reference_id=kwargs.get('reference_id'),
            reference_number=kwargs.get('reference_number'),
            request_payload=kwargs.get('request_payload'),
            response_payload=kwargs.get('response_payload'),
            status=kwargs.get('status'),
            error_message=kwargs.get('error_message'),
            irn=kwargs.get('irn'),
            ack_number=kwargs.get('ack_number'),
            ack_date=kwargs.get('ack_date'),
            qr_code=kwargs.get('qr_code'),
            response_time=datetime.now()
        )
        
        self.db.add(api_log)
        self.db.commit()
    
    async def file_gstr1_return(self, gstr1_id: uuid.UUID) -> Dict[str, Any]:
        """File GSTR-1 return using GST APIs"""
        
        try:
            gstr1_record = self.db.query(GSTR1Data).filter(
                GSTR1Data.id == gstr1_id
            ).first()
            
            if not gstr1_record:
                raise ValueError("GSTR-1 record not found")
            
            company = self.db.query(Company).filter(
                Company.id == gstr1_record.company_id
            ).first()
            
            # Prepare filing payload
            filing_payload = {
                "gstin": company.gstin,
                "ret_period": gstr1_record.return_period,
                "b2b": gstr1_record.b2b_invoices,
                "b2cl": gstr1_record.b2c_large_invoices,
                "b2cs": gstr1_record.b2c_small_invoices,
                "cdnr": gstr1_record.credit_debit_notes,
                "exp": gstr1_record.exports
            }
            
            # Get auth token
            auth_token = await self._get_gst_auth_token(company.gstin)
            
            # File return
            headers = {
                "Authorization": f"Bearer {auth_token}",
                "Content-Type": "application/json",
                "gstin": company.gstin
            }
            
            response = requests.post(
                f"{self.gst_base_url}/returns/gstr1",
                json=filing_payload,
                headers=headers,
                timeout=self.api_timeout
            )
            
            response_data = response.json()
            
            if response.status_code == 200 and response_data.get("status_cd") == "1":
                # Update record with filing details
                gstr1_record.compilation_status = 'FILED'
                gstr1_record.filed_date = date.today()
                gstr1_record.acknowledgment_number = response_data.get("ack_num")
                gstr1_record.reference_id = response_data.get("reference_id")
                
                self.db.commit()
                
                return {
                    "status": "success",
                    "message": "GSTR-1 filed successfully",
                    "acknowledgment_number": gstr1_record.acknowledgment_number,
                    "reference_id": gstr1_record.reference_id
                }
            else:
                error_message = response_data.get("error", "Filing failed")
                raise ValueError(f"GSTR-1 filing failed: {error_message}")
                
        except Exception as e:
            self.db.rollback()
            raise e 