"""
PDF Service - Generate GST-compliant invoice PDFs
"""

import uuid
import os
import qrcode
from io import BytesIO
from datetime import date, datetime
from decimal import Decimal
from typing import Dict, List, Optional, Any
from sqlalchemy.orm import Session

# PDF generation libraries
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter, A4
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader

from ..models import *

class PDFService:
    """Service for generating GST-compliant PDF documents"""
    
    def __init__(self, db: Session):
        self.db = db
        self.styles = getSampleStyleSheet()
        self.setup_custom_styles()
    
    def setup_custom_styles(self):
        """Setup custom PDF styles"""
        
        # Company header style
        self.styles.add(ParagraphStyle(
            name='CompanyHeader',
            parent=self.styles['Heading1'],
            fontSize=16,
            textColor=colors.darkblue,
            alignment=1,  # Center
            spaceAfter=6
        ))
        
        # Invoice title style
        self.styles.add(ParagraphStyle(
            name='InvoiceTitle',
            parent=self.styles['Heading2'],
            fontSize=14,
            textColor=colors.black,
            alignment=1,
            spaceAfter=12
        ))
        
        # Section header style
        self.styles.add(ParagraphStyle(
            name='SectionHeader',
            parent=self.styles['Heading3'],
            fontSize=10,
            textColor=colors.darkblue,
            spaceBefore=8,
            spaceAfter=4
        ))
        
        # Normal text style
        self.styles.add(ParagraphStyle(
            name='InvoiceText',
            parent=self.styles['Normal'],
            fontSize=9,
            leading=11
        ))
        
        # Small text style
        self.styles.add(ParagraphStyle(
            name='SmallText',
            parent=self.styles['Normal'],
            fontSize=8,
            leading=9
        ))
    
    def generate_invoice_pdf(self, invoice_id: uuid.UUID, template_id: Optional[uuid.UUID] = None) -> Dict[str, Any]:
        """Generate GST-compliant invoice PDF"""
        
        try:
            # Get invoice with all related data
            invoice = self.db.query(TaxInvoice).filter(TaxInvoice.id == invoice_id).first()
            if not invoice:
                raise ValueError("Invoice not found")
            
            company = self.db.query(Company).filter(Company.id == invoice.company_id).first()
            customer = self.db.query(Customer).filter(Customer.id == invoice.customer_id).first()
            
            # Get template or use default
            template = None
            if template_id:
                template = self.db.query(DocumentTemplate).filter(
                    and_(
                        DocumentTemplate.id == template_id,
                        DocumentTemplate.company_id == invoice.company_id,
                        DocumentTemplate.document_type == 'INVOICE'
                    )
                ).first()
            
            if not template:
                template = self.db.query(DocumentTemplate).filter(
                    and_(
                        DocumentTemplate.company_id == invoice.company_id,
                        DocumentTemplate.document_type == 'INVOICE',
                        DocumentTemplate.is_default == True
                    )
                ).first()
            
            # Create PDF filename
            filename = f"invoice_{invoice.invoice_number.replace('/', '_')}.pdf"
            file_path = f"/tmp/{filename}"  # Use appropriate path
            
            # Generate PDF
            doc = SimpleDocTemplate(
                file_path,
                pagesize=A4,
                rightMargin=40,
                leftMargin=40,
                topMargin=40,
                bottomMargin=40
            )
            
            # Build PDF content
            story = []
            
            # Add company header
            story.extend(self._build_company_header(company, template))
            
            # Add invoice title and details
            story.extend(self._build_invoice_header(invoice))
            
            # Add customer details
            story.extend(self._build_customer_details(customer, invoice))
            
            # Add invoice items table
            story.extend(self._build_items_table(invoice))
            
            # Add tax summary
            story.extend(self._build_tax_summary(invoice))
            
            # Add payment terms and notes
            story.extend(self._build_footer_info(invoice, company))
            
            # Add QR code if E-Invoice
            if invoice.qr_code:
                story.extend(self._build_qr_code(invoice))
            
            # Generate PDF
            doc.build(story)
            
            # Get file size
            file_size = os.path.getsize(file_path)
            
            return {
                "status": "success",
                "file_path": file_path,
                "filename": filename,
                "file_size": file_size,
                "invoice_number": invoice.invoice_number,
                "total_amount": float(invoice.total_amount)
            }
            
        except Exception as e:
            raise ValueError(f"PDF generation failed: {str(e)}")
    
    def _build_company_header(self, company: Company, template: Optional[DocumentTemplate] = None) -> List:
        """Build company header section"""
        
        elements = []
        
        # Company name
        elements.append(Paragraph(company.legal_name, self.styles['CompanyHeader']))
        
        if company.trade_name and company.trade_name != company.legal_name:
            elements.append(Paragraph(f"({company.trade_name})", self.styles['InvoiceText']))
        
        # Company address
        address_parts = [company.address_line1]
        if company.address_line2:
            address_parts.append(company.address_line2)
        
        address_parts.append(f"{company.city}, {company.pincode}")
        
        # Get state name
        state = self.db.query(State).filter(State.id == company.state_id).first()
        if state:
            address_parts.append(state.name)
        
        address_text = "<br/>".join(address_parts)
        elements.append(Paragraph(address_text, self.styles['InvoiceText']))
        
        # Contact details
        contact_parts = []
        if company.phone:
            contact_parts.append(f"Ph: {company.phone}")
        if company.email:
            contact_parts.append(f"Email: {company.email}")
        if company.website:
            contact_parts.append(f"Web: {company.website}")
        
        if contact_parts:
            contact_text = " | ".join(contact_parts)
            elements.append(Paragraph(contact_text, self.styles['SmallText']))
        
        # GST details
        gst_info = []
        if company.gstin:
            gst_info.append(f"GSTIN: {company.gstin}")
        if company.pan:
            gst_info.append(f"PAN: {company.pan}")
        if company.cin:
            gst_info.append(f"CIN: {company.cin}")
        
        if gst_info:
            gst_text = " | ".join(gst_info)
            elements.append(Paragraph(gst_text, self.styles['SmallText']))
        
        elements.append(Spacer(1, 20))
        
        return elements
    
    def _build_invoice_header(self, invoice: TaxInvoice) -> List:
        """Build invoice header with invoice details"""
        
        elements = []
        
        # Invoice title
        invoice_title = "TAX INVOICE"
        if invoice.irn:
            invoice_title += " (E-INVOICE)"
        
        elements.append(Paragraph(invoice_title, self.styles['InvoiceTitle']))
        
        # Invoice details table
        invoice_data = [
            ['Invoice No:', invoice.invoice_number, 'Invoice Date:', invoice.invoice_date.strftime('%d-%m-%Y')],
            ['Due Date:', invoice.due_date.strftime('%d-%m-%Y'), '', '']
        ]
        
        if invoice.irn:
            invoice_data.append(['IRN:', invoice.irn, '', ''])
            if invoice.ack_number:
                invoice_data.append(['Ack No:', invoice.ack_number, 'Ack Date:', invoice.ack_date.strftime('%d-%m-%Y %H:%M')])
        
        invoice_table = Table(invoice_data, colWidths=[1.2*inch, 2*inch, 1.2*inch, 1.5*inch])
        invoice_table.setStyle(TableStyle([
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('LEFTPADDING', (0, 0), (-1, -1), 0),
            ('RIGHTPADDING', (0, 0), (-1, -1), 0),
        ]))
        
        elements.append(invoice_table)
        elements.append(Spacer(1, 15))
        
        return elements
    
    def _build_customer_details(self, customer: Customer, invoice: TaxInvoice) -> List:
        """Build customer details section"""
        
        elements = []
        
        # Bill to and Ship to sections
        bill_to_data = [
            ['BILL TO:', 'SHIP TO:']
        ]
        
        # Customer name
        customer_name = customer.business_name
        if customer.legal_name and customer.legal_name != customer.business_name:
            customer_name += f"\n({customer.legal_name})"
        
        # Billing address
        bill_address = [customer_name]
        if customer.billing_address_line1:
            bill_address.append(customer.billing_address_line1)
        if customer.billing_address_line2:
            bill_address.append(customer.billing_address_line2)
        if customer.billing_city:
            city_line = customer.billing_city
            if customer.billing_pincode:
                city_line += f" - {customer.billing_pincode}"
            bill_address.append(city_line)
        
        # Shipping address (if different)
        ship_address = bill_address.copy()  # Default to billing address
        if (customer.shipping_address_line1 and 
            customer.shipping_address_line1 != customer.billing_address_line1):
            ship_address = [customer_name]
            if customer.shipping_address_line1:
                ship_address.append(customer.shipping_address_line1)
            if customer.shipping_address_line2:
                ship_address.append(customer.shipping_address_line2)
            if customer.shipping_city:
                city_line = customer.shipping_city
                if customer.shipping_pincode:
                    city_line += f" - {customer.shipping_pincode}"
                ship_address.append(city_line)
        
        bill_to_data.append([
            '\n'.join(bill_address),
            '\n'.join(ship_address)
        ])
        
        # Add GST details
        gst_details = []
        if customer.gstin:
            gst_details.append(f"GSTIN: {customer.gstin}")
        if customer.pan:
            gst_details.append(f"PAN: {customer.pan}")
        
        gst_line = ' | '.join(gst_details) if gst_details else "Unregistered Customer"
        
        bill_to_data.append([gst_line, ''])
        
        # Get place of supply
        place_of_supply = ""
        if invoice.place_of_supply:
            state = self.db.query(State).filter(State.id == invoice.place_of_supply).first()
            if state:
                place_of_supply = f"Place of Supply: {state.name} ({state.gst_state_code})"
        
        bill_to_data.append([place_of_supply, ''])
        
        customer_table = Table(bill_to_data, colWidths=[3*inch, 3*inch])
        customer_table.setStyle(TableStyle([
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('BOX', (0, 0), (-1, -1), 0.5, colors.black),
            ('INNERGRID', (0, 0), (-1, -1), 0.25, colors.gray),
            ('LEFTPADDING', (0, 0), (-1, -1), 5),
            ('RIGHTPADDING', (0, 0), (-1, -1), 5),
            ('TOPPADDING', (0, 0), (-1, -1), 5),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ]))
        
        elements.append(customer_table)
        elements.append(Spacer(1, 15))
        
        return elements
    
    def _build_items_table(self, invoice: TaxInvoice) -> List:
        """Build invoice items table"""
        
        elements = []
        
        # Get invoice items
        items = self.db.query(TaxInvoiceItem).filter(
            TaxInvoiceItem.invoice_id == invoice.id
        ).order_by(TaxInvoiceItem.created_at).all()
        
        # Table headers
        headers = [
            'S.No.', 'Description', 'HSN/SAC', 'Qty', 'Rate', 
            'Discount', 'Taxable\nValue', 'CGST', 'SGST', 'IGST', 'CESS', 'Total'
        ]
        
        # Table data
        table_data = [headers]
        
        for idx, item in enumerate(items, 1):
            # Get item details
            item_service = self.db.query(ItemService).filter(
                ItemService.id == item.item_service_id
            ).first()
            
            # Get HSN/SAC code
            hsn_sac = ""
            if item_service.hsn_sac_code_id:
                hsn_code = self.db.query(HSNSACCode).filter(
                    HSNSACCode.id == item_service.hsn_sac_code_id
                ).first()
                if hsn_code:
                    hsn_sac = hsn_code.code
            
            # Format discount
            discount_text = ""
            if item.discount_percentage > 0:
                discount_text = f"{item.discount_percentage}%"
            elif item.discount_amount > 0:
                discount_text = f"₹{item.discount_amount:.2f}"
            
            # Format tax columns
            cgst_text = f"{item.cgst_rate}%\n₹{item.cgst_amount:.2f}" if item.cgst_amount > 0 else "-"
            sgst_text = f"{item.sgst_rate}%\n₹{item.sgst_amount:.2f}" if item.sgst_amount > 0 else "-"
            igst_text = f"{item.igst_rate}%\n₹{item.igst_amount:.2f}" if item.igst_amount > 0 else "-"
            cess_text = f"{item.cess_rate}%\n₹{item.cess_amount:.2f}" if item.cess_amount > 0 else "-"
            
            row_data = [
                str(idx),
                item_service.name,
                hsn_sac,
                f"{item.quantity:.2f}",
                f"₹{item.unit_price:.2f}",
                discount_text,
                f"₹{item.taxable_amount:.2f}",
                cgst_text,
                sgst_text,
                igst_text,
                cess_text,
                f"₹{item.total_amount:.2f}"
            ]
            
            table_data.append(row_data)
        
        # Create table
        items_table = Table(
            table_data,
            colWidths=[0.4*inch, 2.2*inch, 0.8*inch, 0.6*inch, 0.8*inch, 
                      0.6*inch, 0.8*inch, 0.7*inch, 0.7*inch, 0.7*inch, 0.6*inch, 0.8*inch]
        )
        
        # Table style
        items_table.setStyle(TableStyle([
            ('FONTSIZE', (0, 0), (-1, -1), 8),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('ALIGN', (1, 1), (1, -1), 'LEFT'),  # Item name left aligned
            ('ALIGN', (3, 1), (-1, -1), 'RIGHT'),  # Numbers right aligned
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('BOX', (0, 0), (-1, -1), 1, colors.black),
            ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.gray),
            ('LEFTPADDING', (0, 0), (-1, -1), 3),
            ('RIGHTPADDING', (0, 0), (-1, -1), 3),
            ('TOPPADDING', (0, 0), (-1, -1), 3),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
        ]))
        
        elements.append(items_table)
        elements.append(Spacer(1, 10))
        
        return elements
    
    def _build_tax_summary(self, invoice: TaxInvoice) -> List:
        """Build tax summary and totals"""
        
        elements = []
        
        # Tax summary table
        summary_data = []
        
        # Subtotal
        summary_data.append(['Subtotal:', f"₹{invoice.subtotal:.2f}"])
        
        # Discount
        if invoice.discount_amount and invoice.discount_amount > 0:
            summary_data.append(['Discount:', f"₹{invoice.discount_amount:.2f}"])
        
        # Taxes
        if invoice.cgst_amount > 0:
            summary_data.append(['CGST:', f"₹{invoice.cgst_amount:.2f}"])
        
        if invoice.sgst_amount > 0:
            summary_data.append(['SGST:', f"₹{invoice.sgst_amount:.2f}"])
        
        if invoice.igst_amount > 0:
            summary_data.append(['IGST:', f"₹{invoice.igst_amount:.2f}"])
        
        if invoice.cess_amount and invoice.cess_amount > 0:
            summary_data.append(['CESS:', f"₹{invoice.cess_amount:.2f}"])
        
        # TCS
        if invoice.tcs_amount and invoice.tcs_amount > 0:
            summary_data.append(['TCS:', f"₹{invoice.tcs_amount:.2f}"])
        
        # Total
        summary_data.append(['', ''])  # Empty row
        summary_data.append(['Total Amount:', f"₹{invoice.total_amount:.2f}"])
        
        # Amount in words
        amount_words = self._number_to_words(invoice.total_amount)
        summary_data.append(['Amount in Words:', amount_words])
        
        summary_table = Table(summary_data, colWidths=[2*inch, 2*inch])
        summary_table.setStyle(TableStyle([
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('ALIGN', (0, 0), (0, -1), 'LEFT'),
            ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
            ('FONTNAME', (0, -2), (-1, -2), 'Helvetica-Bold'),
            ('FONTSIZE', (0, -2), (-1, -2), 11),
            ('BACKGROUND', (0, -2), (-1, -2), colors.lightgrey),
            ('BOX', (0, 0), (-1, -1), 1, colors.black),
            ('LINEBELOW', (0, -3), (-1, -3), 1, colors.black),
            ('LEFTPADDING', (0, 0), (-1, -1), 5),
            ('RIGHTPADDING', (0, 0), (-1, -1), 5),
            ('TOPPADDING', (0, 0), (-1, -1), 3),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
        ]))
        
        # Right align the table
        summary_table.hAlign = 'RIGHT'
        
        elements.append(summary_table)
        elements.append(Spacer(1, 15))
        
        return elements
    
    def _build_footer_info(self, invoice: TaxInvoice, company: Company) -> List:
        """Build footer information"""
        
        elements = []
        
        # Payment terms
        if invoice.terms_and_conditions:
            elements.append(Paragraph("Terms & Conditions:", self.styles['SectionHeader']))
            elements.append(Paragraph(invoice.terms_and_conditions, self.styles['InvoiceText']))
            elements.append(Spacer(1, 10))
        
        # Notes
        if invoice.notes:
            elements.append(Paragraph("Notes:", self.styles['SectionHeader']))
            elements.append(Paragraph(invoice.notes, self.styles['InvoiceText']))
            elements.append(Spacer(1, 10))
        
        # Bank details
        if company.bank_name:
            elements.append(Paragraph("Bank Details:", self.styles['SectionHeader']))
            bank_details = []
            bank_details.append(f"Bank: {company.bank_name}")
            if company.bank_account_number:
                bank_details.append(f"A/c No: {company.bank_account_number}")
            if company.bank_ifsc:
                bank_details.append(f"IFSC: {company.bank_ifsc}")
            if company.bank_branch:
                bank_details.append(f"Branch: {company.bank_branch}")
            
            bank_text = " | ".join(bank_details)
            elements.append(Paragraph(bank_text, self.styles['InvoiceText']))
            elements.append(Spacer(1, 15))
        
        # Signature area
        elements.append(Spacer(1, 30))
        
        signature_data = [
            ['Customer Signature', 'Authorized Signatory'],
            ['', ''],
            ['', f'For {company.legal_name}']
        ]
        
        signature_table = Table(signature_data, colWidths=[3*inch, 3*inch])
        signature_table.setStyle(TableStyle([
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('LINEABOVE', (0, 1), (-1, 1), 1, colors.black),
            ('TOPPADDING', (0, 1), (-1, 1), 20),
        ]))
        
        elements.append(signature_table)
        
        return elements
    
    def _build_qr_code(self, invoice: TaxInvoice) -> List:
        """Build QR code for E-Invoice"""
        
        elements = []
        
        if invoice.signed_qr_code:
            try:
                # Generate QR code
                qr = qrcode.QRCode(version=1, box_size=3, border=1)
                qr.add_data(invoice.signed_qr_code)
                qr.make(fit=True)
                
                qr_img = qr.make_image(fill_color="black", back_color="white")
                
                # Convert to BytesIO for reportlab
                img_buffer = BytesIO()
                qr_img.save(img_buffer, format='PNG')
                img_buffer.seek(0)
                
                # Add QR code to PDF
                qr_image = Image(ImageReader(img_buffer), width=1*inch, height=1*inch)
                qr_image.hAlign = 'CENTER'
                
                elements.append(Spacer(1, 10))
                elements.append(Paragraph("E-Invoice QR Code:", self.styles['SectionHeader']))
                elements.append(qr_image)
                
            except Exception as e:
                # If QR code generation fails, just add the text
                elements.append(Paragraph("E-Invoice QR Code (Text):", self.styles['SectionHeader']))
                elements.append(Paragraph(invoice.signed_qr_code[:100] + "...", self.styles['SmallText']))
        
        return elements
    
    def _number_to_words(self, amount: Decimal) -> str:
        """Convert number to words (Indian currency format)"""
        
        # Simplified implementation - you might want to use a library like num2words
        try:
            # Split into rupees and paise
            rupees = int(amount)
            paise = int((amount - rupees) * 100)
            
            # This is a basic implementation
            # For production, use a proper number-to-words library
            
            if rupees == 0:
                return "Zero Rupees Only"
            
            # Basic implementation for demonstration
            ones = ['', 'One', 'Two', 'Three', 'Four', 'Five', 'Six', 'Seven', 'Eight', 'Nine']
            teens = ['Ten', 'Eleven', 'Twelve', 'Thirteen', 'Fourteen', 'Fifteen', 'Sixteen', 'Seventeen', 'Eighteen', 'Nineteen']
            tens = ['', '', 'Twenty', 'Thirty', 'Forty', 'Fifty', 'Sixty', 'Seventy', 'Eighty', 'Ninety']
            
            # Very basic conversion - implement proper Indian numbering system
            if rupees < 10:
                words = ones[rupees]
            elif rupees < 100:
                words = f"{tens[rupees // 10]} {ones[rupees % 10]}".strip()
            else:
                words = f"Rupees {rupees}"  # Simplified
            
            result = f"{words} Rupees"
            
            if paise > 0:
                result += f" and {paise} Paise"
            
            result += " Only"
            
            return result
            
        except:
            return f"Rupees {amount:.2f} Only"
    
    def generate_quotation_pdf(self, quotation_id: uuid.UUID) -> Dict[str, Any]:
        """Generate quotation PDF"""
        
        # Similar to invoice PDF but with quotation-specific formatting
        # Implementation would be similar to generate_invoice_pdf
        pass
    
    def generate_credit_note_pdf(self, credit_note_id: uuid.UUID) -> Dict[str, Any]:
        """Generate credit note PDF"""
        
        # Similar to invoice PDF but for credit notes
        # Implementation would be similar to generate_invoice_pdf
        pass 