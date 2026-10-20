
import os
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP
from io import BytesIO

from dotenv import load_dotenv
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user
from app.db.session import get_db
from app.models import Invoice, Payment, PaymentStatus, Reservation, User, UserRole
from app.schemas.invoice import InvoiceResponse

load_dotenv()

router = APIRouter(prefix="/invoices", tags=["Invoices"])

TAX_RATE = Decimal(os.getenv("INVOICE_TAX_RATE", "0"))


def money(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def create_pdf(invoice: Invoice, document_title: str) -> BytesIO:
    buffer = BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4

    pdf.setTitle(document_title)
    pdf.setFont("Helvetica-Bold", 18)
    pdf.drawString(50, height - 60, document_title)

    pdf.setFont("Helvetica", 11)
    lines = [
        f"Invoice number: {invoice.invoice_number}",
        f"Reservation ID: {invoice.reservation_id}",
        f"Payment reference: {invoice.payment_id}",
        f"Customer ID: {invoice.customer_id}",
        f"Subtotal: {invoice.currency.upper()} {invoice.subtotal}",
        f"Tax rate: {invoice.tax_rate}%",
        f"Tax amount: {invoice.currency.upper()} {invoice.tax_amount}",
        f"Total: {invoice.currency.upper()} {invoice.total_amount}",
        f"Created at: {invoice.created_at}",
    ]

    y = height - 110
    for line in lines:
        pdf.drawString(50, y, line)
        y -= 25

    pdf.save()
    buffer.seek(0)
    return buffer


def get_authorized_invoice(
    invoice_id: int,
    db: Session,
    current_user: User,
) -> Invoice:
    invoice = db.query(Invoice).filter(Invoice.id == invoice_id).first()

    if invoice is None:
        raise HTTPException(status_code=404, detail="Invoice not found.")

    if (
        current_user.role != UserRole.ADMIN
        and invoice.customer_id != current_user.id
    ):
        raise HTTPException(status_code=403, detail="Access denied.")

    return invoice


@router.post(
    "/{payment_id}/generate",
    response_model=InvoiceResponse,
    status_code=201,
)
def generate_invoice(
    payment_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    payment = db.query(Payment).filter(Payment.id == payment_id).first()

    if payment is None:
        raise HTTPException(status_code=404, detail="Payment not found.")

    if (
        current_user.role != UserRole.ADMIN
        and payment.customer_id != current_user.id
    ):
        raise HTTPException(status_code=403, detail="Access denied.")

    if payment.status != PaymentStatus.SUCCEEDED:
        raise HTTPException(
            status_code=409,
            detail="An invoice can only be generated for a successful payment.",
        )

    existing = db.query(Invoice).filter(Invoice.payment_id == payment.id).first()
    if existing is not None:
        return existing

    reservation = (
        db.query(Reservation)
        .filter(Reservation.id == payment.reservation_id)
        .first()
    )
    if reservation is None or reservation.customer_id != payment.customer_id:
        raise HTTPException(status_code=409, detail="Reservation is invalid.")

    subtotal = money(Decimal(str(payment.amount)))
    tax_rate = TAX_RATE

    if tax_rate < 0 or tax_rate > 100:
        raise HTTPException(
            status_code=500,
            detail="INVOICE_TAX_RATE must be between 0 and 100.",
        )

    tax_amount = money(subtotal * tax_rate / Decimal("100"))
    total_amount = money(subtotal + tax_amount)

    invoice_number = (
        f"INV-{datetime.now().strftime('%Y%m%d')}-{payment.id:06d}"
    )

    invoice = Invoice(
        invoice_number=invoice_number,
        reservation_id=reservation.id,
        customer_id=payment.customer_id,
        payment_id=payment.id,
        subtotal=subtotal,
        tax_rate=tax_rate,
        tax_amount=tax_amount,
        total_amount=total_amount,
        currency=payment.currency,
    )

    try:
        db.add(invoice)
        db.commit()
        db.refresh(invoice)
    except IntegrityError:
        db.rollback()
        existing = (
            db.query(Invoice)
            .filter(Invoice.payment_id == payment.id)
            .first()
        )
        if existing is not None:
            return existing
        raise HTTPException(status_code=409, detail="Invoice could not be created.")

    return invoice


@router.get("/my", response_model=list[InvoiceResponse])
def get_my_invoices(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role != UserRole.CUSTOMER:
        raise HTTPException(
            status_code=403,
            detail="Only customers can view their invoice history.",
        )

    return (
        db.query(Invoice)
        .filter(Invoice.customer_id == current_user.id)
        .order_by(Invoice.created_at.desc())
        .all()
    )


@router.get("/{invoice_id}/download")
def download_invoice(
    invoice_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    invoice = get_authorized_invoice(invoice_id, db, current_user)
    buffer = create_pdf(invoice, "StayNestPro Invoice")

    return StreamingResponse(
        buffer,
        media_type="application/pdf",
        headers={
            "Content-Disposition": (
                f'attachment; filename="{invoice.invoice_number}.pdf"'
            )
        },
    )


@router.get("/{invoice_id}/receipt")
def download_receipt(
    invoice_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    invoice = get_authorized_invoice(invoice_id, db, current_user)
    buffer = create_pdf(invoice, "StayNestPro Booking Receipt")

    return StreamingResponse(
        buffer,
        media_type="application/pdf",
        headers={
            "Content-Disposition": (
                f'attachment; filename="receipt-{invoice.invoice_number}.pdf"'
            )
        },
    )