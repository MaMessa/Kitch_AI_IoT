# Import datetime for account creation, updates, and email verification timestamps.
from datetime import datetime  # Represent timestamp values with Python datetime objects.
# Import SQL types and database defaults used by the User table.
from sqlalchemy import BigInteger, Boolean, DateTime, String, false, func  # Define the user's columns and defaults.
# Import SQLAlchemy's typed mapping and relationship helpers.
from sqlalchemy.orm import Mapped, mapped_column, relationship  # Map fields and related model collections.
# Import the shared declarative base for all ORM models.
from app.models.base import Base  # Register this model in the project's metadata.


# This model stores a KitchAI account that may use a password or social login.
class User(Base):  # Define the ORM class for the user table.
    __tablename__ = "user"  # Set the PostgreSQL table name.

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)  # Store the account's primary key.
    email: Mapped[str] = mapped_column(String, unique=True, nullable=False)  # Keep one required email per account.
    password_hash: Mapped[str | None] = mapped_column(String, nullable=True)  # Allow accounts that sign in only with a provider.
    email_verified_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)  # Record when the email was verified.
    is_admin: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default=false())  # Default accounts to non-admin.
    first_name: Mapped[str] = mapped_column(String, nullable=False)  # Store the account holder's required first name.
    last_name: Mapped[str | None] = mapped_column(String, nullable=True)  # Store an optional last name.
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())  # Let PostgreSQL record account creation time.
    updated_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)  # Store an optional account update time.

    recipes: Mapped[list["Recipe"]] = relationship(back_populates="author")  # Expose recipes written by this user.
    auth_identities: Mapped[list["AuthIdentity"]] = relationship(back_populates="user")  # Expose linked Google, Facebook, or Apple identities.
