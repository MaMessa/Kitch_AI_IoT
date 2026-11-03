from alembic import op  # Apply reversible changes to the recipe table.
import sqlalchemy as sa  # Define exact PostgreSQL numeric columns.

revision = "b76e4c2901a5"  # Identify this nutrition cache migration.
down_revision = "a612f41c8e30"  # Follow the current ingredient archive revision.
branch_labels = None  # Keep the existing single migration branch.
depends_on = None  # Require no external migration branch.


# Store calculated values only when the recipe nutrition is complete.
def upgrade():  # Add nullable caches without inventing nutrition for older recipes.
    op.add_column("recipe", sa.Column("calories_par_portion", sa.Numeric(12, 2), nullable=True))  # Cache kcal per serving.
    op.add_column("recipe", sa.Column("proteines_par_portion", sa.Numeric(12, 2), nullable=True))  # Cache protein grams per serving.


# Restore the prior recipe schema if this migration is reversed.
def downgrade():  # Remove both cache columns.
    op.drop_column("recipe", "proteines_par_portion")  # Drop the protein cache first.
    op.drop_column("recipe", "calories_par_portion")  # Drop the calorie cache second.
