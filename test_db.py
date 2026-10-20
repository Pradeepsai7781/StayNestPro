
from sqlalchemy import text
from app.db.session import engine

try:
    with engine.connect() as connection:
        result = connection.execute(text("SELECT DATABASE(), VERSION()"))
        database, version = result.fetchone()

        print("Database connection successful!")
        print("Database:", database)
        print("MySQL version:", version)

except Exception as error:
    print("Database connection failed.")
    print("Error type:", type(error).__name__)
    print("Check your local .env configuration and MySQL service.")
