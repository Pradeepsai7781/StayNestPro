
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models.audit_log import AuditEventType, AuditLog


def record_audit_event(
    db: Session,
    event_type: AuditEventType,
    action: str,
    actor_id: int | None = None,
    description: str | None = None,
    entity_type: str | None = None,
    entity_id: str | int | None = None,
    ip_address: str | None = None,
    details: dict | None = None,
    commit: bool = True,
) -> AuditLog:
    """Record an audit event.

    Use commit=False when the caller manages the transaction.
    Never store passwords, access tokens, or refresh tokens in details.
    """

    audit_log = AuditLog(
        actor_id=actor_id,
        event_type=event_type,
        action=action,
        description=description,
        entity_type=entity_type,
        entity_id=(
            str(entity_id) if entity_id is not None else None
        ),
        ip_address=ip_address,
        details=details,
        created_at=datetime.now(timezone.utc),
    )

    db.add(audit_log)

    try:
        if commit:
            db.commit()
            db.refresh(audit_log)
        else:
            db.flush()
    except Exception:
        if commit:
            db.rollback()
        raise

    return audit_log
