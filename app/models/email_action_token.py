# Import timezone-aware timestamps for secure token expiry checks.
from datetime import datetime  # Represent token creation and use times.
# Import database types, constraints, and foreign-key support.
from sqlalchemy import BigInteger, CheckConstraint, DateTime, ForeignKey, String, UniqueConstraint, func  # Describe one-time email action tokens.
# Import SQLAlchemy's typed ORM helpers.
from sqlalchemy.orm import Mapped, mapped_column, relationship  # Map stored token data and its owning account.
# Import the shared declarative base.
from app.models.base import Base  # Register the table in project metadata.


# Store one-time email-verification and password-reset token digests.
class EmailActionToken(Base):  # Define a token that can be used for exactly one account action.
    __tablename__ = "email_action_token"  # Name the PostgreSQL table.

    __table_args__ = (CheckConstraint("purpose IN ('verify_email', 'reset_password')", name="ck_email_action_token_purpose"), UniqueConstraint("token_hash", name="uq_email_action_token_hash"))  # Restrict valid uses and keep token digests unique.

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)  # Store the token row identifier.
    user_id: Mapped[int] = mapped_column(ForeignKey("user.id", ondelete="CASCADE"), nullable=False, index=True)  # Link the token to the account it can affect.
    purpose: Mapped[str] = mapped_column(String(30), nullable=False)  # Separate email verification from password recovery.
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False)  # Store a digest instead of the usable link token.
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())  # Record when the token was created.
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)  # Set a finite lifetime for the token.
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)  # Mark a token after its one allowed use.

    user: Mapped["User"] = relationship(back_populates="email_action_tokens")  # Provide access to the token's account.
