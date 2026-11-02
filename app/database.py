import os

from collections.abc import Generator  # Types the database-session dependency.

from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker  # Provides request-scoped ORM sessions.

# Load environment variables from the .env file
load_dotenv()

# récupère la valeur de DATABASE_URL, 
# chargée depuis le fichier .env par load_dotenv(). 
# SQLAlchemy utilise ensuite cette adresse 
# pour se connecter à PostgreSQL.
DATABASE_URL = os.environ["DATABASE_URL"]

# Create the SQLAlchemy engine (connection manager)
engine = create_engine(DATABASE_URL, pool_pre_ping=True)



SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)  # Creates independent sessions for API requests.


def get_db() -> Generator[Session, None, None]:  # Supplies one session to a request and then closes it.
    db = SessionLocal()  # Opens a new database session.
    try:  # Ensures cleanup runs even when a request fails.
        yield db  # Makes the session available to the route.
    finally:  # Runs after the route finishes or raises an error.
        db.close()  # Releases the connection back to the connection pool.


def check_database_connection() -> None:
    """Check that PostgreSQL accepts SQL queries."""

    # Open a connection and release it automatically afterward
    with engine.connect() as connection:
        result = connection.execute(text("SELECT 1"))
        print(f"Database connection OK: {result.scalar_one()}")