
from contextlib import asynccontextmanager

from apscheduler.schedulers.background import BackgroundScheduler
from fastapi import FastAPI

from app.api.v1.auth import router as auth_router
from app.api.v1.profile import router as profile_router
from app.api.v1.hotels import router as hotels_router
from app.api.v1.admin import router as admin_router
from app.api.v1.rooms import router as rooms_router
from app.api.v1.room_types import router as room_types_router
from app.api.v1.amenities import router as amenities_router
from app.api.v1.reservations import router as reservations_router
from app.api.v1.hotel_search import router as hotel_search_router
from app.api.v1.hotel_details import router as hotel_details_router
from app.api.v1.guests import router as guests_router
from app.api.v1.payments import router as payments_router
from app.api.v1.invoices import router as invoices_router
from app.api.v1.refunds import router as refunds_router
from app.api.v1.coupons import router as coupons_router
from app.api.v1.reviews import router as reviews_router
from app.api.v1.wishlist import router as wishlist_router
from app.api.v1.recommendations import router as recommendations_router
from app.api.v1.travel_assistant import router as travel_assistant_router
from app.api.v1.support_chatbot import router as support_chatbot_router
from app.api.v1.notifications import router as notifications_router
from app.api.v1.messaging import router as messaging_router
from app.api.v1.housekeeping import router as housekeeping_router
from app.api.v1.staff_management import router as staff_management_router
from app.api.v1.reservation_checkin import router as reservation_checkin_router
from app.api.v1.additional_services import (
    router as additional_services_router,
)
from app.api.v1.room_service import router as room_service_router
from app.services.reservation_reminder_service import (
    run_reservation_reminder_job,
)
from app.api.v1.revenue_analytics import router as revenue_analytics_router
from app.api.v1.occupancy_analytics import router as occupancy_analytics_router
from app.api.v1.customer_analytics import router as customer_analytics_router
from app.api.v1.hotel_owner_dashboard import (
    router as hotel_owner_dashboard_router,
)
from app.api.v1.customer_dashboard import router as customer_dashboard_router
from app.api.v1.admin_dashboard import router as admin_dashboard_router
from app.api.v1.hotel_moderation import router as hotel_moderation_router
from app.api.v1.reports import router as reports_router
from app.api.v1.audit_logs import router as audit_logs_router
from app.api.v1.hotel_subscriptions import (
    router as hotel_subscriptions_router,
)
from app.api.v1.subscription_webhooks import (
    router as subscription_webhooks_router,
)
from app.api.v1.subscription_payments import (
    router as subscription_payments_router,
)
from app.api.v1.subscription_checkout import (
    router as subscription_checkout_router,
)
from app.api.v1.dynamic_pricing import router as dynamic_pricing_router
from app.api.v1.loyalty import router as loyalty_router
from app.api.v1.locations import router as locations_router
from app.api.v1.financial_management import router as financial_management_router
from app.api.v1.business_intelligence import router as business_intelligence_router
from app.api.v1.security_monitoring import router as security_monitoring_router
from app.api.v1.system_settings import router as system_settings_router
from app.api.v1.system_administration import router as system_administration_router


scheduler = BackgroundScheduler(timezone="UTC")


@asynccontextmanager
async def lifespan(app: FastAPI):
    scheduler.add_job(
        run_reservation_reminder_job,
        trigger="interval",
        hours=1,
        id="reservation_reminders",
        replace_existing=True,
        max_instances=1,
    )

    scheduler.start()

    try:
        yield
    finally:
        if scheduler.running:
            scheduler.shutdown(wait=False)


app = FastAPI(
    title="StayNest Pro API",
    description="Backend API for hotel, resort, and room booking management.",
    version="1.0.0",
    lifespan=lifespan,
    openapi_tags=[
        {
            "name": "Reservations",
            "description": (
                "Reservation calendar, availability, and scheduling."
            ),
        },
        {"name": "Business Intelligence", "description": "Revenue, booking, customer, and destination summaries."},
        {"name": "Fraud Detection and Security", "description": "Suspicious activity alerts and review records."},
        {"name": "System Configuration", "description": "Platform settings and secure integration configuration status."},
        {"name": "Advanced Platform Administration", "description": "Operational overview and system health."},
    ],
)

app.include_router(auth_router)
app.include_router(profile_router)
app.include_router(hotel_search_router)
app.include_router(hotel_details_router)
app.include_router(admin_router)
app.include_router(rooms_router)
app.include_router(room_types_router)
app.include_router(amenities_router)

# Reservation router: register only once with the API prefix.
app.include_router(reservations_router, prefix="/api/v1")

app.include_router(hotels_router)
app.include_router(guests_router)
app.include_router(payments_router)

app.include_router(invoices_router, prefix="/api/v1")
app.include_router(refunds_router, prefix="/api/v1")
app.include_router(coupons_router, prefix="/api/v1")
app.include_router(reviews_router, prefix="/api/v1")
app.include_router(wishlist_router, prefix="/api/v1")
app.include_router(recommendations_router, prefix="/api/v1")
app.include_router(travel_assistant_router, prefix="/api/v1")
app.include_router(support_chatbot_router, prefix="/api/v1")
app.include_router(notifications_router, prefix="/api/v1")
app.include_router(messaging_router, prefix="/api/v1")
app.include_router(housekeeping_router, prefix="/api/v1")
app.include_router(staff_management_router, prefix="/api/v1")
app.include_router(reservation_checkin_router, prefix="/api/v1")
app.include_router(additional_services_router, prefix="/api/v1")
app.include_router(room_service_router, prefix="/api/v1")
app.include_router(revenue_analytics_router, prefix="/api/v1")
app.include_router(occupancy_analytics_router, prefix="/api/v1")
app.include_router(customer_analytics_router, prefix="/api/v1")
app.include_router(hotel_owner_dashboard_router, prefix="/api/v1")
app.include_router(customer_dashboard_router, prefix="/api/v1")
app.include_router(admin_dashboard_router, prefix="/api/v1")
app.include_router(hotel_moderation_router, prefix="/api/v1")
app.include_router(reports_router, prefix="/api/v1")
app.include_router(audit_logs_router, prefix="/api/v1")
app.include_router(hotel_subscriptions_router, prefix="/api/v1")
app.include_router(subscription_webhooks_router, prefix="/api/v1")
app.include_router(subscription_payments_router, prefix="/api/v1")
app.include_router(subscription_checkout_router, prefix="/api/v1")
app.include_router(dynamic_pricing_router, prefix="/api/v1")
app.include_router(loyalty_router, prefix="/api/v1")
app.include_router(locations_router, prefix="/api/v1")
app.include_router(financial_management_router, prefix="/api/v1")
app.include_router(business_intelligence_router, prefix="/api/v1")
app.include_router(security_monitoring_router, prefix="/api/v1")
app.include_router(system_settings_router, prefix="/api/v1")
app.include_router(system_administration_router, prefix="/api/v1")


@app.get("/", tags=["Health"])
def root():
    return {
        "success": True,
        "message": "Welcome to StayNest Pro API",
    }


@app.get("/health", tags=["Health"])
def health_check():
    return {
        "success": True,
        "message": "StayNest Pro API is running",
    }
