# Import datetime for the identity-link creation timestamp.
from datetime import datetime  # Represent the timestamp with a Python datetime object.
# Import SQL constraints, types, and foreign-key support.
from sqlalchemy import BigInteger, CheckConstraint, DateTime, ForeignKey, String, UniqueConstraint, func  # Define identity columns and integrity rules.
# Import SQLAlchemy's typed mapping and relationship helpers.
from sqlalchemy.orm import Mapped, mapped_column, relationship  # Map fields and the parent user relationship.
# Import the shared declarative base for all ORM models.
from app.models.base import Base  # Register this model in the project's metadata.


# This model links one KitchAI account to an external sign-in identity.
class AuthIdentity(Base):  # Define the ORM class for linked provider identities.
    __tablename__ = "auth_identity"  # Set the PostgreSQL table name.

    # Keep provider identities unique and limit V1 to the selected login providers.
    __table_args__ = (  # Declare rules that apply across columns in this table.
        UniqueConstraint("provider", "provider_user_id", name="uq_auth_identity_provider_subject"),  # Prevent one provider identity from belonging to multiple users.
        UniqueConstraint("user_id", "provider", name="uq_auth_identity_user_provider"),  # Allow at most one account per provider on each user.
        CheckConstraint("provider IN ('google', 'facebook', 'apple')", name="ck_auth_identity_provider"),  # Restrict provider names to the supported V1 options.
    )  # Finish the table-level constraints.

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)  # Store the identity link's primary key.
    user_id: Mapped[int] = mapped_column(ForeignKey("user.id"), nullable=False)  # Link the provider identity to a KitchAI user.
    provider: Mapped[str] = mapped_column(String, nullable=False)  # Store google, facebook, or apple.
    provider_user_id: Mapped[str] = mapped_column(String, nullable=False)  # Store the stable user identifier issued by that provider.
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())  # Let PostgreSQL record when the identity was linked.

    user: Mapped["User"] = relationship(back_populates="auth_identities")  # Allow navigation back to the KitchAI account.
