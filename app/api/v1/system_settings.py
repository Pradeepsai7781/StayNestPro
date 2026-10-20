import os
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user
from app.db.session import get_db
from app.models import User, UserRole
from app.models.audit_log import AuditEventType
from app.models.system_configuration import SystemSetting
from app.services.audit_log_service import record_audit_event

router = APIRouter(prefix="/system-settings", tags=["System Configuration"])
ALLOWED_KEYS = {"financial", "currency", "platform_policy"}


class SystemSettingUpdate(BaseModel):
    value: dict
    description: str | None = Field(default=None, max_length=500)

    @field_validator("value")
    @classmethod
    def validate_setting_value(cls, value: dict) -> dict:
        forbidden = {"password", "secret", "token", "api_key", "private_key", "client_secret"}
        def walk(item):
            if isinstance(item, dict):
                for key, child in item.items():
                    normalized = str(key).lower().replace("-", "_")
                    if any(word in normalized for word in forbidden):
                        raise ValueError("Secrets must be configured through environment variables, not system settings.")
                    walk(child)
            elif isinstance(item, list):
                for child in item:
                    walk(child)
        walk(value)
        return value


def require_admin(user: User) -> None:
    if user.role != UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="Only administrators can manage system settings.")


def _validate_financial_settings(value: dict) -> None:
    for key in ("commission_rate", "tax_rate"):
        if key in value:
            try:
                rate = Decimal(str(value[key]))
            except (InvalidOperation, ValueError):
                raise HTTPException(status_code=422, detail=f"{key} must be a numeric percentage.")
            if rate < 0 or rate > 100:
                raise HTTPException(status_code=422, detail=f"{key} must be between 0 and 100.")
    if "currency" in value and (not isinstance(value["currency"], str) or len(value["currency"]) != 3 or not value["currency"].isalpha()):
        raise HTTPException(status_code=422, detail="currency must be a 3-letter currency code.")


@router.get("")
def list_system_settings(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    require_admin(current_user)
    return db.query(SystemSetting).order_by(SystemSetting.key).all()


@router.put("/{setting_key}")
def update_system_setting(
    setting_key: str,
    payload: SystemSettingUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_admin(current_user)
    if setting_key not in ALLOWED_KEYS:
        raise HTTPException(status_code=404, detail="Unsupported system setting key.")
    if setting_key == "financial":
        _validate_financial_settings(payload.value)
    if setting_key == "currency":
        _validate_financial_settings({"currency": payload.value.get("currency")})
    setting = db.query(SystemSetting).filter(SystemSetting.key == setting_key).first()
    now = datetime.now(timezone.utc)
    if setting is None:
        setting = SystemSetting(key=setting_key, value=payload.value, description=payload.description,
                                updated_by=current_user.id, created_at=now, updated_at=now)
        db.add(setting)
    else:
        setting.value = payload.value
        setting.description = payload.description
        setting.updated_by = current_user.id
        setting.updated_at = now
    db.flush()
    record_audit_event(db, AuditEventType.ADMIN_ACTION, "SYSTEM_SETTING_UPDATED", actor_id=current_user.id,
        description="Administrator updated a platform setting.", entity_type="SystemSetting",
        entity_id=setting_key, details={"setting_key": setting_key}, commit=False)
    db.commit()
    db.refresh(setting)
    return setting


@router.get("/integration-status")
def integration_configuration_status(current_user: User = Depends(get_current_user)):
    """Return presence flags only; secret values are never read back or returned."""
    require_admin(current_user)
    return {
        "email": {
            "smtp_host_configured": bool(os.getenv("SMTP_HOST")),
            "smtp_user_configured": bool(os.getenv("SMTP_USER")),
            "smtp_password_configured": bool(os.getenv("SMTP_PASSWORD")),
        },
        "payment_provider": {
            "stripe_secret_key_configured": bool(os.getenv("STRIPE_SECRET_KEY")),
            "stripe_webhook_secret_configured": bool(os.getenv("STRIPE_WEBHOOK_SECRET")),
        },
        "note": "Email and payment-provider secrets must be stored in environment variables, not in system settings.",
    }
