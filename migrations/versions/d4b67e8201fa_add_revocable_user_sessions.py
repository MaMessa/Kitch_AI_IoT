"""Add revocable server-side browser sessions."""  # Describe this schema change.

# Import typing helpers used by Alembic's revision template.
from typing import Sequence, Union  # Type this migration's revision links.
# Import Alembic operations and SQLAlchemy types.
from alembic import op  # Provide database schema operations.
import sqlalchemy as sa  # Describe the new table and its columns.


# Identify the new migration and place it after the current schema head.
revision: str = "d4b67e8201fa"  # Give this change a stable migration identifier.
down_revision: Union[str, Sequence[str], None] = "c8a2102bb941"  # Apply after recipe-step support.
branch_labels: Union[str, Sequence[str], None] = None  # Keep this migration on the main history branch.
depends_on: Union[str, Sequence[str], None] = None  # Declare no independent migration dependency.


# Create the table needed to invalidate browser sessions from the server.
def upgrade() -> None:  # Add storage for hashed, expiring, revocable sessions.
    op.create_table(  # Create the new user_session table.
        "user_session",  # Name the PostgreSQL table.
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),  # Give every session a generated identifier.
        sa.Column("user_id", sa.BigInteger(), nullable=False),  # Store which account owns this session.
        sa.Column("token_hash", sa.String(length=64), nullable=False),  # Store the SHA-256 digest instead of the raw cookie.
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),  # Record when the server created the session.
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),  # Record when the session must stop working.
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),  # Record explicit logout or future account-wide revocation.
        sa.ForeignKeyConstraint(["user_id"], ["user.id"], ondelete="CASCADE"),  # Remove sessions automatically when an account is deleted.
        sa.PrimaryKeyConstraint("id"),  # Set the table's primary key.
        sa.UniqueConstraint("token_hash", name="uq_user_session_token_hash"),  # Prevent token digest collisions from creating ambiguous sessions.
    )  # Finish defining the session table.
    op.create_index("ix_user_session_user_id", "user_session", ["user_id"], unique=False)  # Find and revoke an account's sessions efficiently.


# Remove the session table if this migration is intentionally rolled back.
def downgrade() -> None:  # Reverse the session-table schema change.
    op.drop_index("ix_user_session_user_id", table_name="user_session")  # Remove the account lookup index first.
    op.drop_table("user_session")  # Remove stored sessions when rolling back.
