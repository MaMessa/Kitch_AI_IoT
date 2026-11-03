from alembic import op  # Provide Alembic operations for schema changes.
import sqlalchemy as sa  # Define the SQL types used by this migration.

revision = "f73a9bc2d104"  # Identify this schema revision.
down_revision = "e5c37fd219a0"  # Apply this migration after email-action tokens.
branch_labels = None  # Keep this migration on the main revision branch.
depends_on = None  # Declare no separate migration dependency.


# Add ownership and base-ingredient links without changing existing Ciqual rows.
def upgrade():  # Apply the ingredient ownership schema.
    op.add_column("ingredient", sa.Column("owner_user_id", sa.BigInteger(), nullable=True))  # Let null represent the shared catalogue.
    op.add_column("ingredient", sa.Column("base_ingredient_id", sa.BigInteger(), nullable=True))  # Allow personal variants to link to a shared ingredient.
    op.create_foreign_key("fk_ingredient_owner_user_id_user", "ingredient", "user", ["owner_user_id"], ["id"])  # Require any owner to be a real account.
    op.create_foreign_key("fk_ingredient_base_ingredient_id_ingredient", "ingredient", "ingredient", ["base_ingredient_id"], ["item_id"])  # Require each base link to identify a real ingredient.
    op.create_check_constraint("ck_ingredient_not_own_base", "ingredient", "base_ingredient_id IS NULL OR base_ingredient_id <> item_id")  # Reject a self-referencing base link.


# Remove the added relationships and columns if the migration is rolled back.
def downgrade():  # Revert the ingredient ownership schema.
    op.drop_constraint("ck_ingredient_not_own_base", "ingredient", type_="check")  # Remove the self-reference rule first.
    op.drop_constraint("fk_ingredient_base_ingredient_id_ingredient", "ingredient", type_="foreignkey")  # Remove the base-ingredient foreign key.
    op.drop_constraint("fk_ingredient_owner_user_id_user", "ingredient", type_="foreignkey")  # Remove the owner foreign key.
    op.drop_column("ingredient", "base_ingredient_id")  # Remove the personal-variant link.
    op.drop_column("ingredient", "owner_user_id")  # Remove the ownership field.
