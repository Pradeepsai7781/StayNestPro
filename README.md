StayNest Pro - Hotel, Resort & Room Booking Management Platform
A comprehensive hotel, resort, and room booking management backend built using FastAPI, MySQL, SQLAlchemy ORM, JWT Authentication, and Alembic.

The platform provides secure APIs for authentication, hotel management, room management, reservations, payments, analytics, administration, AI-powered services, loyalty systems, subscriptions, and operational workflows.

1. Technologies Used
Backend Framework: FastAPI
Programming Language: Python
Database: MySQL
ORM: SQLAlchemy
Authentication: JWT Access & Refresh Tokens
Database Migration: Alembic
Validation: Pydantic
API Documentation: Swagger UI / OpenAPI
API Testing: Postman
Automated Testing: Pytest
Payment Gateway: Stripe (Test Mode)
Configuration: Environment Variables (.env)
2. Features
Authentication & RBAC
User Registration
Login & Logout
JWT Authentication
Refresh Tokens
Password Reset
Role-Based Access Control
Supported Roles:

CUSTOMER
HOTEL_OWNER
HOTEL_STAFF
ADMIN
Customer Management
Customer Profiles
Travel Preferences
Profile Updates
Profile Image Support
Hotel Management
Hotel Registration
Hotel Verification
Hotel Moderation
Hotel Profiles
Hotel Amenities
Hotel Gallery Management
Hotel Search & Filters
Room Management
Room CRUD Operations
Room Types Management
Room Availability
Capacity & Pricing Validation
Dynamic Pricing
Reservation Management
Room Booking
Reservation Calendar
Booking History
Guest Management
Check-In Management
Check-Out Management
Payment Management
Stripe Checkout Integration
Payment Records
Invoice Generation
Refund Management
Settlement Management
Financial Reconciliation
Customer Features
Reviews & Ratings
Hotel Wishlist
Notifications
Messaging
Loyalty & Rewards
AI Services
Hotel Recommendations
AI Travel Assistant
AI Customer Support Chatbot
Analytics & Reporting
Revenue Analytics
Occupancy Analytics
Customer Analytics
Business Intelligence
Dashboard APIs
Export Reports
Security
Audit Logs
Security Monitoring
Fraud Detection
Protected Endpoints
JWT-Based Authorization
3. Project Structure
StayNestPro/
│
├── app/
│   ├── api/
│   ├── core/
│   ├── db/
│   ├── models/
│   ├── schemas/
│   ├── services/
│   └── main.py
│
├── alembic/
│   └── versions/
│
├── tests/
│
├── media/
│
├── Postman/
│
├── Screenshots/
│
├── README.md
├── requirements.txt
├── alembic.ini
├── TEST_RESULTS.txt
├── .env.example
└── .gitignore
4. Requirements
Python 3.8+
MySQL Server
Git
Virtual Environment
5. Setup Instructions
Clone Repository
git clone https://github.com/Pradeepsai7781/StayNestPro.git
cd StayNestPro
Create Virtual Environment
Windows:

python -m venv venv
venv\Scripts\activate
Linux/Mac:

python -m venv venv
source venv/bin/activate
Install Dependencies
pip install -r requirements.txt
6. Configure Environment Variables
Create a .env file from .env.example.

Example:

DATABASE_URL=mysql+pymysql://username:password@localhost/staynest_db

SECRET_KEY=your_secret_key

ALGORITHM=HS256

ACCESS_TOKEN_EXPIRE_MINUTES=30

REFRESH_TOKEN_EXPIRE_DAYS=7

STRIPE_SECRET_KEY=your_stripe_key

STRIPE_WEBHOOK_SECRET=your_webhook_secret
Never upload real secrets to GitHub.

7. Database Setup
Create Database:

CREATE DATABASE staynest_db;
Apply Migrations:

alembic upgrade head
Verify Migration Status:

alembic current
8. Running the Application
Start FastAPI:

uvicorn app.main:app --reload
Application:

http://127.0.0.1:8000
9. API Documentation
Swagger UI:

http://127.0.0.1:8000/docs
ReDoc:

http://127.0.0.1:8000/redoc
OpenAPI Schema:

http://127.0.0.1:8000/openapi.json
10. Main API Modules
Implemented Modules:

Authentication & RBAC
Customer Profile Management
Hotel Registration & Verification
Hotel Profile Management
Room Management
Room Types
Hotel Amenities
Hotel Availability
Hotel Search
Advanced Filters
Hotel Details
Room Booking
Guest Management
Booking Management
Payment Management
Invoice Management
Refund Management
Coupons & Discounts
Reviews & Ratings
Wishlist Management
AI Recommendations
AI Travel Assistant
AI Support Chatbot
Notifications
Messaging
Housekeeping
Staff Management
Check-In / Check-Out
Additional Services
Room Service
Analytics
Reports
Security Monitoring
Loyalty & Rewards
Location Services
Dynamic Pricing
Business Intelligence
Platform Administration
Total Modules Implemented: 50

11. Testing
Swagger Testing
All APIs tested using FastAPI Swagger UI.

Tested:

Authentication
CRUD Operations
Role Validation
Booking Workflows
Payment Workflows
Refund Workflows
Dashboard APIs
Analytics APIs
Postman Testing
Collection Included:

Postman/StayNest Pro Backend API Tests.postman_collection.json
Environment Included:

Postman/StayNest Pro Local.postman_environment.json
Automated Testing
Run tests:

pytest
Result:

38 Passed
0 Failed
12. Screenshots
Project includes Swagger and Testing Screenshots:

Examples:

Authentication Login
Customer Dashboard
Room Management
Booking Availability
Reservation Calendar
Payment Checkout
Refund Records
Business Intelligence
Security Monitoring
AI Customer Support
AI Travel Assistant
Hotel Moderation
Pytest Results
Location:

Screenshots/
13. Security Features
JWT Authentication
Password Hashing
RBAC Authorization
Protected Routes
Validation Using Pydantic
Audit Logging
Security Monitoring
Fraud Detection
Environment-Based Secrets
14. Test Results
Pytest Results

38 Passed
0 Failed
0 Errors

Swagger Testing Completed
Postman Testing Completed
Additional details available in:

TEST_RESULTS.txt
15. Known Limitations
Stripe runs in test mode.
AI responses depend on configured providers.
Production deployment requires secure credentials and infrastructure configuration.
16. Author
Ediga Venkata Sai Pradeep

GitHub:

https://github.com/Pradeepsai7781

17. License
This project was developed for educational, training, and backend development demonstration purposes.