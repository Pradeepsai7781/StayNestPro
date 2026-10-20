StayNest Pro Backend
Project Overview
StayNest Pro is a hotel, resort, and room booking management platform built using FastAPI and MySQL. The system provides secure REST APIs for customer management, hotel onboarding, room management, bookings, payments, analytics, subscriptions, administration, and hotel operations.

This project is a backend-only implementation and exposes APIs through Swagger UI and OpenAPI documentation.

Technology Stack
FastAPI
Python 3.8+
MySQL
SQLAlchemy ORM
Alembic
Pydantic
JWT Authentication
bcrypt / Argon2 Password Hashing
Stripe Payment Integration
Swagger UI
Postman
Pytest
Features
Authentication & Authorization
User Registration
Login
JWT Access Tokens
JWT Refresh Tokens
Role-Based Access Control (RBAC)
Password Reset
Email Verification
User Roles
CUSTOMER
HOTEL_OWNER
HOTEL_STAFF
ADMIN
Hotel Management
Hotel Registration
Hotel Verification
Hotel Profile Management
Hotel Amenities
Hotel Gallery
Hotel Moderation
Room Management
Room CRUD Operations
Room Types
Room Availability
Dynamic Pricing
Booking System
Room Booking
Guest Management
Booking Management
Check-In / Check-Out
Booking History
Payments
Stripe Integration
Payment Tracking
Invoices
Refund Processing
Subscription Billing
Customer Features
Wishlist
Reviews & Ratings
Loyalty & Rewards
Notifications
Messaging
Analytics
Revenue Analytics
Occupancy Analytics
Customer Analytics
Business Intelligence
Dashboard APIs
Security
Audit Logs
Security Logs
Fraud Detection
Role-Based Restrictions
Project Structure
staynest-pro/
|
├── app/
│   ├── api/
│   ├── core/
│   ├── database/
│   ├── models/
│   ├── schemas/
│   ├── services/
│   ├── utils/
│   └── main.py
|
├── alembic/
│   └── versions/
|
├── tests/
|
├── uploads/
|
├── docs/
|
├── .env.example
├── requirements.txt
├── alembic.ini
├── pytest.ini
├── README.md
├── postman_collection.json
└── postman_environment.json
Installation
1. Clone Repository
git clone <repository-url>
cd staynest-pro
2. Create Virtual Environment
python -m venv venv
Activate Environment
Windows

venv\Scripts\activate
Linux/Mac

source venv/bin/activate
3. Install Dependencies
pip install -r requirements.txt
Environment Configuration
Create a .env file using .env.example.

Example:

DATABASE_URL=mysql+pymysql://username:password@localhost:3306/staynest_db

SECRET_KEY=your_secret_key

ALGORITHM=HS256

ACCESS_TOKEN_EXPIRE_MINUTES=30

REFRESH_TOKEN_EXPIRE_DAYS=7

STRIPE_SECRET_KEY=your_stripe_secret

STRIPE_WEBHOOK_SECRET=your_webhook_secret

UPLOAD_DIR=uploads

OPENAI_API_KEY=your_ai_provider_key
Database Setup
Create Database
CREATE DATABASE staynest_db;
Run Migrations
alembic upgrade head
Check Migration History
alembic history
Running The Application
uvicorn app.main:app --reload
Application URL:

http://localhost:8000
Swagger Documentation
Swagger UI

http://localhost:8000/docs
ReDoc

http://localhost:8000/redoc
OpenAPI Schema

http://localhost:8000/openapi.json
Authentication
All protected APIs require JWT Bearer Token.

Example Header:

Authorization: Bearer <access_token>
Use the Swagger "Authorize" button to test protected endpoints.

API Testing
Swagger UI
Validated for:

Authentication
CRUD Operations
Role-Based Access Control
Validation Errors
Booking Workflows
Payment Workflows
Refund Processing
Filters & Pagination
Postman
Collection Included:

StayNest Pro Backend API Tests
Environment Variables:

base_url
access_token
refresh_token
customer_id
hotel_id
room_id
booking_id
payment_id
Running Tests
Execute test suite:

pytest -v
Example Result:

===================================
38 passed, 0 failed
===================================
Health Check
Endpoint:

GET /health
Response:

{
  "success": true,
  "message": "Service healthy"
}
Role Permissions
CUSTOMER
Manage Profile
Search Hotels
Book Rooms
Payments
Reviews
Wishlist
HOTEL_OWNER
Manage Hotels
Manage Rooms
View Revenue
Manage Staff
HOTEL_STAFF
Housekeeping
Check-In
Check-Out
Service Operations
ADMIN
User Management
Hotel Approval
Dashboard Access
Security Monitoring
Platform Configuration
Automated Testing Coverage
Covered Areas:

Authentication
Authorization
Customer CRUD
Hotel CRUD
Room CRUD
Booking Logic
Availability Validation
Payment Flow
Refund Flow
Report Generation
Role-Based Access Control
Input Validation
Security Measures
JWT Authentication
Password Hashing
Input Validation
Rate Limiting
RBAC Authorization
Audit Logging
Secure Environment Variables
Stripe Webhook Verification
Deliverables Included
Complete FastAPI Source Code
SQLAlchemy Models
Alembic Migrations
Swagger Documentation
Postman Collection
Postman Environment
Pytest Test Suite
Test Results
Setup Documentation
API Inventory
.env.example
Database Migration Instructions
Known Limitations
External AI service behavior depends on provider availability.
Stripe operates in test mode for development/testing.
Some third-party integrations may require provider credentials before production deployment.
Author
Developer: Ediga Venkata Sai Pradeep

Project: StayNest Pro Backend Version: 1.0.0