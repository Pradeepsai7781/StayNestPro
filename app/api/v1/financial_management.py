import os
from decimal import Decimal, ROUND_HALF_UP

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user
from app.db.session import get_db
from app.models import Hotel, Payment, PaymentStatus, Reservation, Room, User, UserRole
from app.models.financial_management import (
    FinancialRecord, Settlement, PayoutStatus,
    PaymentReconciliation, ReconciliationStatus,
)
from app.schemas.financial_management import (
    FinancialRecordResponse, SettlementCreate, SettlementStatusUpdate,
    SettlementResponse, ReconciliationCreate, ReconciliationResponse,
)

router = APIRouter(prefix="/financial-management", tags=["Financial Management"])


def require_admin(user: User) -> None:
    if user.role != UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="Administrator access required.")


def money(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


@router.post("/payments/{payment_id}/calculate", response_model=FinancialRecordResponse, status_code=201)
def calculate_financial_record(payment_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    require_admin(user)
    payment = db.get(Payment, payment_id)
    if payment is None:
        raise HTTPException(status_code=404, detail="Payment not found.")
    if payment.status != PaymentStatus.SUCCEEDED:
        raise HTTPException(status_code=409, detail="Only successful payments can be calculated.")
    existing = db.scalar(select(FinancialRecord).where(FinancialRecord.payment_id == payment.id))
    if existing:
        return existing
    reservation = db.get(Reservation, payment.reservation_id)
    room = db.get(Room, reservation.room_id) if reservation else None
    hotel = db.get(Hotel, room.hotel_id) if room else None
    if hotel is None:
        raise HTTPException(status_code=409, detail="Reservation hotel could not be found.")
    commission_rate = Decimal(os.getenv("PLATFORM_COMMISSION_RATE", "10"))
    tax_rate = Decimal(os.getenv("INVOICE_TAX_RATE", "0"))
    if not Decimal("0") <= commission_rate <= Decimal("100") or not Decimal("0") <= tax_rate <= Decimal("100"):
        raise HTTPException(status_code=500, detail="Commission and tax rates must be between 0 and 100.")
    gross = money(Decimal(str(payment.amount)))
    commission = money(gross * commission_rate / Decimal("100"))
    tax = money(gross * tax_rate / Decimal("100"))
    record = FinancialRecord(payment_id=payment.id, hotel_id=hotel.id, currency=payment.currency,
        gross_amount=gross, commission_rate=commission_rate, commission_amount=commission,
        tax_rate=tax_rate, tax_amount=tax, hotel_earnings=money(gross - commission))
    db.add(record)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        existing = db.scalar(select(FinancialRecord).where(FinancialRecord.payment_id == payment.id))
        if existing:
            return existing
        raise HTTPException(status_code=409, detail="Financial record could not be created.")
    db.refresh(record)
    return record


@router.get("/records", response_model=list[FinancialRecordResponse])
def list_financial_records(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    require_admin(user)
    return list(db.scalars(select(FinancialRecord).order_by(FinancialRecord.created_at.desc())).all())


@router.post("/settlements", response_model=SettlementResponse, status_code=201)
def create_settlement(payload: SettlementCreate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    require_admin(user)
    if db.get(Hotel, payload.hotel_id) is None:
        raise HTTPException(status_code=404, detail="Hotel not found.")
    settlement = Settlement(hotel_id=payload.hotel_id, amount=payload.amount, currency=payload.currency.lower(), notes=payload.notes)
    db.add(settlement)
    db.commit()
    db.refresh(settlement)
    return settlement


@router.get("/settlements", response_model=list[SettlementResponse])
def list_settlements(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    require_admin(user)
    return list(db.scalars(select(Settlement).order_by(Settlement.created_at.desc())).all())


@router.patch("/settlements/{settlement_id}", response_model=SettlementResponse)
def update_settlement(settlement_id: int, payload: SettlementStatusUpdate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    require_admin(user)
    settlement = db.get(Settlement, settlement_id)
    if settlement is None:
        raise HTTPException(status_code=404, detail="Settlement not found.")
    settlement.status = payload.status
    if payload.provider_payout_reference is not None:
        settlement.provider_payout_reference = payload.provider_payout_reference
    if payload.notes is not None:
        settlement.notes = payload.notes
    db.commit()
    db.refresh(settlement)
    return settlement


@router.post("/reconciliation", response_model=ReconciliationResponse, status_code=201)
def reconcile_payment(payload: ReconciliationCreate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    require_admin(user)
    existing = db.scalar(select(PaymentReconciliation).where(PaymentReconciliation.provider_transaction_id == payload.provider_transaction_id))
    if existing:
        raise HTTPException(status_code=409, detail="This provider transaction has already been reconciled.")
    payment = db.scalar(select(Payment).where(
        (Payment.stripe_payment_intent_id == payload.provider_transaction_id) |
        (Payment.stripe_checkout_session_id == payload.provider_transaction_id)
    ))
    local_amount = money(Decimal(str(payment.amount))) if payment else None
    provider_amount = money(payload.amount)
    provider_status = payload.status.strip().upper()
    local_status = payment.status.value if payment else None
    if payment is None:
        result_status = ReconciliationStatus.NOT_FOUND
        notes = "No local payment matched this provider transaction ID."
    elif local_amount != provider_amount or local_status != provider_status:
        result_status = ReconciliationStatus.MISMATCHED
        notes = "Provider amount or status differs from the local payment record."
    else:
        result_status = ReconciliationStatus.MATCHED
        notes = "Provider and local payment records match."
    record = PaymentReconciliation(provider_transaction_id=payload.provider_transaction_id,
        payment_id=payment.id if payment else None, provider_amount=provider_amount,
        local_amount=local_amount, provider_status=provider_status, local_status=local_status,
        status=result_status, notes=notes)
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


@router.get("/reconciliation", response_model=list[ReconciliationResponse])
def list_reconciliations(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    require_admin(user)
    return list(db.scalars(select(PaymentReconciliation).order_by(PaymentReconciliation.created_at.desc())).all())
