
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user
from app.db.session import get_db
from app.models.loyalty import (
    LoyaltyAccount,
    LoyaltyEntryType,
    LoyaltyLedgerEntry,
)
from app.schemas.loyalty import (
    LoyaltyAccountResponse,
    LoyaltyLedgerResponse,
    LoyaltyRedemptionRequest,
    ReferralApplyRequest,
)
from app.services.loyalty_service import (
    get_or_create_loyalty_account,
    redeem_points,
    update_membership_tier,
)


router = APIRouter(
    prefix="/loyalty",
    tags=["Loyalty and Rewards"],
)


@router.get("/account", response_model=LoyaltyAccountResponse)
def get_loyalty_account(
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    try:
        account = get_or_create_loyalty_account(
            db,
            current_user.id,
        )
        db.commit()
        db.refresh(account)
        return account
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Loyalty account could not be created.",
        ) from exc


@router.get("/ledger", response_model=list[LoyaltyLedgerResponse])
def get_loyalty_ledger(
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    return db.scalars(
        select(LoyaltyLedgerEntry)
        .where(LoyaltyLedgerEntry.user_id == current_user.id)
        .order_by(LoyaltyLedgerEntry.created_at.desc())
    ).all()


@router.post("/redeem", response_model=LoyaltyLedgerResponse)
def redeem_loyalty_points(
    payload: LoyaltyRedemptionRequest,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    try:
        entry = redeem_points(
            db=db,
            user_id=current_user.id,
            payment_id=payload.payment_id,
            points=payload.points,
        )
        db.commit()
        db.refresh(entry)
        return entry

    except PermissionError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(exc),
        ) from exc

    except ValueError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc

    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Points redemption could not be completed.",
        ) from exc


@router.get("/benefits")
def get_membership_benefits(
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    try:
        account = get_or_create_loyalty_account(
            db,
            current_user.id,
        )

        benefits_by_tier = {
            "BRONZE": {
                "minimum_lifetime_points": 0,
                "description": "Earn points on eligible completed bookings.",
                "points_multiplier": 1.0,
            },
            "SILVER": {
                "minimum_lifetime_points": 2000,
                "description": "Silver membership benefits.",
                "points_multiplier": 1.25,
            },
            "GOLD": {
                "minimum_lifetime_points": 5000,
                "description": "Gold membership benefits.",
                "points_multiplier": 1.5,
            },
        }

        db.commit()

        return {
            "membership_tier": account.membership_tier,
            "points_balance": account.points_balance,
            "benefits": benefits_by_tier.get(
                account.membership_tier,
                benefits_by_tier["BRONZE"],
            ),
        }
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Membership benefits could not be retrieved.",
        ) from exc


@router.post("/referrals/apply")
def apply_referral(
    payload: ReferralApplyRequest,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    try:
        referred_account = get_or_create_loyalty_account(
            db,
            current_user.id,
        )

        referrer_account = db.scalar(
            select(LoyaltyAccount)
            .where(
                LoyaltyAccount.referral_code == payload.referral_code.strip().upper()
            )
            .with_for_update()
        )

        if referrer_account is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Referral code not found.",
            )

        if referrer_account.user_id == current_user.id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="You cannot use your own referral code.",
            )

        if referred_account.referred_by_user_id is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="A referral has already been applied.",
            )

        referral_key = f"referral:{current_user.id}"

        existing = db.scalar(
            select(LoyaltyLedgerEntry).where(
                LoyaltyLedgerEntry.idempotency_key.in_(
                    [
                        f"{referral_key}:referrer",
                        f"{referral_key}:referred",
                    ]
                )
            )
        )

        if existing is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="A referral reward has already been recorded.",
            )

        referred_account.referred_by_user_id = referrer_account.user_id

        referrer_account.points_balance += 100
        referred_account.points_balance += 100

        db.add_all(
            [
                LoyaltyLedgerEntry(
                    user_id=referrer_account.user_id,
                    entry_type=LoyaltyEntryType.REFERRAL_REWARD,
                    points=100,
                    idempotency_key=f"{referral_key}:referrer",
                    description=(
                        f"Referral reward for inviting user {current_user.id}"
                    ),
                ),
                LoyaltyLedgerEntry(
                    user_id=current_user.id,
                    entry_type=LoyaltyEntryType.REFERRAL_BONUS,
                    points=100,
                    idempotency_key=f"{referral_key}:referred",
                    description="Welcome reward for using a referral code",
                ),
            ]
        )

        db.flush()
        update_membership_tier(db, referrer_account)
        update_membership_tier(db, referred_account)
        db.commit()

        return {
            "message": "Referral applied successfully.",
            "referrer_points_awarded": 100,
            "your_points_awarded": 100,
        }

    except HTTPException:
        db.rollback()
        raise

    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Referral could not be applied.",
        ) from exc
