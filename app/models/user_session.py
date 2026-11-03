# Import timezone-aware timestamps for safe session expiry comparisons.
from datetime import datetime  # Represent session timestamps in Python.
# Import database column types, foreign keys, and timestamp defaults.
from sqlalchemy import BigInteger, DateTime, ForeignKey, String, UniqueConstraint, func  # Describe persisted session fields and token uniqueness.
# Import SQLAlchemy's typed mapping helpers.
from sqlalchemy.orm import Mapped, mapped_column, relationship  # Map columns and the owning user.
# Import the shared declarative base.
from app.models.base import Base  # Register this table with project metadata.


# Store revocable browser sessions without storing the raw cookie token.
class UserSession(Base):  # Define one logged-in browser session.
    __tablename__ = "user_session"  # Name the PostgreSQL table.

    __table_args__ = (UniqueConstraint("token_hash", name="uq_user_session_token_hash"),)  # Name the token uniqueness rule to match the migration.

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)  # Identify this session row.
    user_id: Mapped[int] = mapped_column(ForeignKey("user.id", ondelete="CASCADE"), nullable=False, index=True)  # Connect the session to its account.
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False)  # Store only the SHA-256 token digest.
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())  # Record when the session was created.
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)  # Stop accepting the session after this time.
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)  # Mark sessions that were explicitly signed out.

    user: Mapped["User"] = relationship(back_populates="sessions")  # Allow the owning account to be accessed through the ORM.
