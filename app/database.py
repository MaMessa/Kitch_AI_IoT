import os

from dotenv import load_dotenv
from sqlalchemy import create_engine, text

# Load environment variables from the .env file
load_dotenv()

# Retrieve the database connection URL
DATABASE_URL = os.environ["DATABASE_URL"]

# Create the SQLAlchemy engine (connection manager)
engine = create_engine(DATABASE_URL, pool_pre_ping=True)


def check_database_connection() -> None:
    """Check that PostgreSQL accepts SQL queries."""

    # Open a connection and release it automatically afterward
    with engine.connect() as connection:
        result = connection.execute(text("SELECT 1"))
        print(f"Database connection OK: {result.scalar_one()}")