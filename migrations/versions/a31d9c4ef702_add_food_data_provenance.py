"""Add food-data provenance fields to ingredients."""

from typing import Sequence, Union  # Type Alembic revision links consistently.

from alembic import op  # Access Alembic's schema migration operations.
import sqlalchemy as sa  # Define portable SQL column types.


revision: str = "a31d9c4ef702"  # Identify this migration in Alembic's history.
down_revision: Union[str, Sequence[str], None] = "52f922d0ce0d"  # Apply after the authentication schema migration.
branch_labels: Union[str, Sequence[str], None] = None  # This migration is part of the main revision chain.
depends_on: Union[str, Sequence[str], None] = None  # No separate migration branch is required.


def upgrade() -> None:  # Add nullable provenance fields while keeping existing ingredients valid.
    op.add_column("ingredient", sa.Column("data_source", sa.String(), server_default="manual", nullable=False))  # Mark existing rows and manual entries with their source.
    op.add_column("ingredient", sa.Column("source_id", sa.String(), nullable=True))  # Store the stable identifier assigned by Ciqual or another provider.
    op.add_column("ingredient", sa.Column("source_version", sa.String(), nullable=True))  # Record the imported dataset edition.
    op.add_column("ingredient", sa.Column("source_url", sa.String(), nullable=True))  # Preserve provenance and attribution links.
    op.add_column("ingredient", sa.Column("brand", sa.String(), nullable=True))  # Keep branded products distinguishable from generic foods.
    op.add_column("ingredient", sa.Column("barcode", sa.String(), nullable=True))  # Store a product's barcode when it is saved.
    op.create_unique_constraint("uq_ingredient_source_id", "ingredient", ["data_source", "source_id"])  # Prevent duplicate copies of one provider record.


def downgrade() -> None:  # Remove the new provenance fields if this migration is reverted.
    op.drop_constraint("uq_ingredient_source_id", "ingredient", type_="unique")  # Drop the provider identity rule before its columns.
    op.drop_column("ingredient", "barcode")  # Remove the saved product barcode.
    op.drop_column("ingredient", "brand")  # Remove the product brand.
    op.drop_column("ingredient", "source_url")  # Remove the attribution URL.
    op.drop_column("ingredient", "source_version")  # Remove the dataset edition.
    op.drop_column("ingredient", "source_id")  # Remove the external provider identifier.
    op.drop_column("ingredient", "data_source")  # Remove the provider name.
