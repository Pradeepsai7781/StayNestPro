from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user
from app.db.session import get_db
from app.models import Reservation, ReservationStatus, User, UserRole
from app.models.audit_log import AuditEventType, AuditLog
from app.models.payment import Payment, PaymentStatus
from app.models.security_alert import SecurityAlert, SecurityAlertStatus
from app.services.audit_log_service import record_audit_event

router = APIRouter(prefix="/security", tags=["Fraud Detection and Security"])


class SecurityAlertReview(BaseModel):
    status: SecurityAlertStatus = SecurityAlertStatus.REVIEWED
    review_note: str | None = Field(default=None, max_length=1000)


def require_admin(user: User) -> None:
    if user.role != UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="Only administrators can access security monitoring.")


def _create_alert(db: Session, *, alert_type: str, severity: str, description: str,
                  user_id: int | None = None, ip_address: str | None = None,
                  details: dict | None = None, now: datetime) -> bool:
    duplicate = db.query(SecurityAlert).filter(
        SecurityAlert.alert_type == alert_type,
        SecurityAlert.user_id == user_id,
        SecurityAlert.ip_address == ip_address,
        SecurityAlert.status == SecurityAlertStatus.OPEN,
        SecurityAlert.created_at >= now - timedelta(hours=24),
    ).first()
    if duplicate:
        return False
    db.add(SecurityAlert(alert_type=alert_type, severity=severity, description=description,
                         user_id=user_id, ip_address=ip_address, details=details,
                         status=SecurityAlertStatus.OPEN, created_at=now))
    return True


@router.post("/scan")
def scan_suspicious_activity(
    failed_payment_threshold: int = Query(default=3, ge=2, le=20),
    failed_login_threshold: int = Query(default=5, ge=3, le=50),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Scan recent audit/payment/booking data and persist security alerts for review."""
    require_admin(current_user)
    now = datetime.now(timezone.utc)
    since = now - timedelta(hours=1)
    created = 0

    failed_payments = (
        db.query(Payment.customer_id, func.count(Payment.id).label("attempts"))
        .filter(Payment.status == PaymentStatus.FAILED, Payment.created_at >= since)
        .group_by(Payment.customer_id).having(func.count(Payment.id) >= failed_payment_threshold).all()
    )
    for user_id, attempts in failed_payments:
        created += _create_alert(db, alert_type="REPEATED_FAILED_PAYMENTS", severity="HIGH",
            description=f"Customer has {attempts} failed payment attempts within one hour.",
            user_id=user_id, details={"attempt_count": attempts, "window_hours": 1}, now=now)

    failed_logins = (
        db.query(AuditLog.ip_address, func.count(AuditLog.id).label("attempts"))
        .filter(AuditLog.event_type == AuditEventType.LOGIN_FAILED,
                AuditLog.created_at >= since, AuditLog.ip_address.isnot(None))
        .group_by(AuditLog.ip_address).having(func.count(AuditLog.id) >= failed_login_threshold).all()
    )
    for ip_address, attempts in failed_logins:
        created += _create_alert(db, alert_type="REPEATED_FAILED_LOGINS", severity="HIGH",
            description=f"IP address has {attempts} failed login events within one hour.",
            ip_address=ip_address, details={"attempt_count": attempts, "window_hours": 1}, now=now)

    # Flag multiple active bookings by the same customer for the same room and overlapping dates.
    recent_bookings = db.query(Reservation).filter(
        Reservation.created_at >= now - timedelta(days=7),
        Reservation.status == ReservationStatus.CONFIRMED,
    ).order_by(Reservation.customer_id, Reservation.room_id, Reservation.check_in).all()
    seen = {}
    for booking in recent_bookings:
        key = (booking.customer_id, booking.room_id)
        previous = seen.setdefault(key, [])
        for other in previous:
            if booking.check_in < other.check_out and other.check_in < booking.check_out:
                created += _create_alert(db, alert_type="OVERLAPPING_BOOKING_PATTERN", severity="MEDIUM",
                    description="The same customer has overlapping confirmed bookings for one room.",
                    user_id=booking.customer_id,
                    details={"reservation_ids": [other.id, booking.id], "room_id": booking.room_id}, now=now)
                break
        previous.append(booking)

    # Repeated booking creations by one customer in a short window are also surfaced for review.
    rapid_bookings = (
        db.query(Reservation.customer_id, func.count(Reservation.id).label("attempts"))
        .filter(Reservation.created_at >= since)
        .group_by(Reservation.customer_id).having(func.count(Reservation.id) >= 5).all()
    )
    for user_id, attempts in rapid_bookings:
        created += _create_alert(db, alert_type="RAPID_BOOKING_PATTERN", severity="MEDIUM",
            description=f"Customer created {attempts} reservations within one hour.", user_id=user_id,
            details={"booking_count": attempts, "window_hours": 1}, now=now)

    db.commit()
    record_audit_event(db, AuditEventType.ADMIN_ACTION, "SECURITY_SCAN_COMPLETED",
        actor_id=current_user.id, description="Administrator ran a suspicious activity scan.",
        entity_type="SecurityAlert", details={"alerts_created": created})
    return {"scan_time": now, "alerts_created": created}


@router.get("/alerts")
def list_security_alerts(
    status: SecurityAlertStatus | None = Query(default=None),
    severity: str | None = Query(default=None, pattern="^(LOW|MEDIUM|HIGH|CRITICAL)$"),
    limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_admin(current_user)
    query = db.query(SecurityAlert)
    if status is not None:
        query = query.filter(SecurityAlert.status == status)
    if severity is not None:
        query = query.filter(SecurityAlert.severity == severity)
    return query.order_by(SecurityAlert.created_at.desc(), SecurityAlert.id.desc()).limit(limit).all()


@router.patch("/alerts/{alert_id}/review")
def review_security_alert(
    alert_id: int,
    payload: SecurityAlertReview,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_admin(current_user)
    alert = db.query(SecurityAlert).filter(SecurityAlert.id == alert_id).first()
    if alert is None:
        raise HTTPException(status_code=404, detail="Security alert not found.")
    alert.status = payload.status
    alert.reviewed_by = current_user.id
    alert.reviewed_at = datetime.now(timezone.utc)
    if payload.review_note:
        alert.details = {**(alert.details or {}), "review_note": payload.review_note}
    db.flush()
    record_audit_event(db, AuditEventType.ADMIN_ACTION, "SECURITY_ALERT_REVIEWED",
        actor_id=current_user.id, description="Administrator updated a security alert review status.",
        entity_type="SecurityAlert", entity_id=alert.id,
        details={"status": alert.status.value}, commit=False)
    db.commit()
    db.refresh(alert)
    return alert
