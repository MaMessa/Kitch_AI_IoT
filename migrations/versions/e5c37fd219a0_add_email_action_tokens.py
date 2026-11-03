"""Add single-use tokens for email verification and password recovery."""  # Describe this schema change.

# Import typing helpers used by Alembic's migration template.
from typing import Sequence, Union  # Type the revision links.
# Import Alembic operations and SQLAlchemy schema tools.
from alembic import op  # Provide database migration operations.
import sqlalchemy as sa  # Describe the token table and its constraints.


# Identify this migration and place it after revocable browser sessions.
revision: str = "e5c37fd219a0"  # Assign a stable Alembic revision identifier.
down_revision: Union[str, Sequence[str], None] = "d4b67e8201fa"  # Apply after UserSession was added.
branch_labels: Union[str, Sequence[str], None] = None  # Keep the change on the main migration branch.
depends_on: Union[str, Sequence[str], None] = None  # Declare no separate migration dependency.


# Create storage for hashed, expiring, one-time email action links.
def upgrade() -> None:  # Add verification and password recovery token storage.
    op.create_table(  # Create the new email_action_token table.
        "email_action_token",  # Name the PostgreSQL table.
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),  # Give every token row a generated identifier.
        sa.Column("user_id", sa.BigInteger(), nullable=False),  # Link the token to the account it can change.
        sa.Column("purpose", sa.String(length=30), nullable=False),  # Distinguish verification from password reset.
        sa.Column("token_hash", sa.String(length=64), nullable=False),  # Store only the token's SHA-256 digest.
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),  # Record when the token was issued.
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),  # Enforce a finite validity period.
        sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=True),  # Record one-time use or invalidation.
        sa.CheckConstraint("purpose IN ('verify_email', 'reset_password')", name="ck_email_action_token_purpose"),  # Reject unsupported token types.
        sa.ForeignKeyConstraint(["user_id"], ["user.id"], ondelete="CASCADE"),  # Delete tokens with their owning account.
        sa.PrimaryKeyConstraint("id"),  # Set the primary key.
        sa.UniqueConstraint("token_hash", name="uq_email_action_token_hash"),  # Prevent ambiguous token digests.
    )  # Finish creating the one-time token table.
    op.create_index("ix_email_action_token_user_id", "email_action_token", ["user_id"], unique=False)  # Find and invalidate an account's older links efficiently.


# Remove the email action token table if this migration is rolled back.
def downgrade() -> None:  # Reverse this schema change.
    op.drop_index("ix_email_action_token_user_id", table_name="email_action_token")  # Remove the account lookup index first.
    op.drop_table("email_action_token")  # Remove email action token storage.
