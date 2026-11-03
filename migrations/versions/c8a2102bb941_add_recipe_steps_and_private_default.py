"""Add ordered recipe steps and default recipes to private."""

from typing import Sequence, Union  # Type Alembic revision links consistently.

from alembic import op  # Access Alembic's schema migration operations.
import sqlalchemy as sa  # Define schema types and execute the data-preserving backfill.


revision: str = "c8a2102bb941"  # Identify this migration in Alembic's history.
down_revision: Union[str, Sequence[str], None] = "a31d9c4ef702"  # Apply after nutrition-source provenance fields.
branch_labels: Union[str, Sequence[str], None] = None  # Keep this migration in the main revision chain.
depends_on: Union[str, Sequence[str], None] = None  # No separate migration branch is required.


def upgrade() -> None:  # Replace the single instructions field with ordered step rows.
    op.create_table(  # Create the table that stores one row per recipe step.
        "recipe_step",  # Name the new PostgreSQL table.
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),  # Give every step its own generated identifier.
        sa.Column("recipe_id", sa.BigInteger(), nullable=False),  # Link the step to its parent recipe.
        sa.Column("step_number", sa.Integer(), nullable=False),  # Store the one-based display order.
        sa.Column("instruction", sa.Text(), nullable=False),  # Store this step's instruction text.
        sa.CheckConstraint("step_number > 0", name="ck_recipe_step_number_positive"),  # Reject zero or negative step positions.
        sa.ForeignKeyConstraint(["recipe_id"], ["recipe.id"], ondelete="CASCADE"),  # Remove steps automatically when their recipe is deleted.
        sa.PrimaryKeyConstraint("id"),  # Set the primary key for recipe steps.
        sa.UniqueConstraint("recipe_id", "step_number", name="uq_recipe_step_order"),  # Prevent duplicate step numbers within one recipe.
    )  # Finish creating the ordered step table.
    op.execute(sa.text("INSERT INTO recipe_step (recipe_id, step_number, instruction) SELECT id, 1, instructions FROM recipe"))  # Preserve existing instructions as step one before removing the old column.
    op.drop_column("recipe", "instructions")  # Remove the former single-text instruction field after the backfill.
    op.alter_column("recipe", "is_public", existing_type=sa.Boolean(), server_default=sa.text("false"), existing_server_default=sa.text("true"), nullable=False)  # Make future database-created recipes private by default.


def downgrade() -> None:  # Restore the old single-instructions representation if rolled back.
    op.add_column("recipe", sa.Column("instructions", sa.Text(), nullable=True))  # Add a temporary nullable destination for combined steps.
    op.execute(sa.text("UPDATE recipe SET instructions = COALESCE((SELECT string_agg(instruction, E'\\n\\n' ORDER BY step_number) FROM recipe_step WHERE recipe_step.recipe_id = recipe.id), '')"))  # Join each recipe's ordered steps into the former text field.
    op.alter_column("recipe", "instructions", existing_type=sa.Text(), nullable=False)  # Restore the original required-column rule.
    op.drop_table("recipe_step")  # Remove the ordered step table after its content has been copied.
    op.alter_column("recipe", "is_public", existing_type=sa.Boolean(), server_default=sa.text("true"), existing_server_default=sa.text("false"), nullable=False)  # Restore the previous database default.
