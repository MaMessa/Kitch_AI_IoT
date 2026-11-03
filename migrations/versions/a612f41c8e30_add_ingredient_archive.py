from alembic import op  # Provide Alembic operations for schema changes.
import sqlalchemy as sa  # Define the SQL types used by this migration.

revision = "a612f41c8e30"  # Identify this schema revision.
down_revision = "f73a9bc2d104"  # Apply this migration after ingredient ownership.
branch_labels = None  # Keep this migration on the main revision branch.
depends_on = None  # Declare no separate migration dependency.


# Add a reversible archive marker while preserving recipe history.
def upgrade():  # Apply the ingredient archive field.
    op.add_column("ingredient", sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True))  # Leave active ingredients unarchived by default.


# Remove the archive marker if this migration is rolled back.
def downgrade():  # Revert the ingredient archive field.
    op.drop_column("ingredient", "archived_at")  # Remove only the newly added column.
