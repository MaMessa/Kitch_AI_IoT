from datetime import datetime  # Represent the optional archive timestamp.
from decimal import Decimal  # Use Decimal so nutrition values keep exact decimal precision.

from sqlalchemy import BigInteger, CheckConstraint, DateTime, ForeignKey, Numeric, String, UniqueConstraint  # Define ingredient columns and database integrity rules.
from sqlalchemy.orm import Mapped, mapped_column, relationship  # Map typed columns and related model objects.

from app.models.base import Base  # Register the ingredient table in shared model metadata.


# Add food-specific nutrition and ownership fields to a shared Item record.
class Ingredient(Base):  # Define the SQLAlchemy model for one food ingredient.
    __tablename__ = "ingredient"  # Keep the established PostgreSQL table name.
    __table_args__ = (  # Group database rules that apply to the whole ingredient table.
        CheckConstraint("base_ingredient_id IS NULL OR base_ingredient_id <> item_id", name="ck_ingredient_not_own_base"),  # Prevent an ingredient from being its own base.
        UniqueConstraint("data_source", "source_id", name="uq_ingredient_source_id"),  # Prevent importing one external record twice.
    )  # Finish the table-level constraints.

    # The item id is also this table's primary key, creating a one-to-one extension.
    item_id: Mapped[int] = mapped_column(  # Map the key shared with the general Item record.
        BigInteger, ForeignKey("item.id"), primary_key=True  # Require each ingredient to belong to exactly one item.
    )  # Finish the primary-key mapping.
    ingredient_category_id: Mapped[int] = mapped_column(  # Map the ingredient's required category.
        ForeignKey("ingredient_category.id"), nullable=False  # Require a valid ingredient category.
    )  # Finish the category mapping.
    calories: Mapped[Decimal | None] = mapped_column(Numeric, nullable=True)  # Store kcal per 100 g when known.
    proteins: Mapped[Decimal | None] = mapped_column(Numeric, nullable=True)  # Store protein grams per 100 g when known.
    carbs: Mapped[Decimal | None] = mapped_column(Numeric, nullable=True)  # Store carbohydrate grams per 100 g when known.
    fats: Mapped[Decimal | None] = mapped_column(Numeric, nullable=True)  # Store fat grams per 100 g when known.
    fiber: Mapped[Decimal | None] = mapped_column(Numeric, nullable=True)  # Store fiber grams per 100 g when known.
    data_source: Mapped[str] = mapped_column(String, nullable=False, default="manual", server_default="manual")  # Distinguish manual, Ciqual, and Open Food Facts records.
    source_id: Mapped[str | None] = mapped_column(String, nullable=True)  # Store a stable food code from the source.
    source_version: Mapped[str | None] = mapped_column(String, nullable=True)  # Record the source dataset revision.
    source_url: Mapped[str | None] = mapped_column(String, nullable=True)  # Keep the source attribution link.
    brand: Mapped[str | None] = mapped_column(String, nullable=True)  # Keep a product brand separate from its generic name.
    barcode: Mapped[str | None] = mapped_column(String, nullable=True)  # Reserve the product's GTIN barcode.
    owner_user_id: Mapped[int | None] = mapped_column(ForeignKey("user.id"), nullable=True)  # NULL means shared catalogue; a user id means private ownership.
    base_ingredient_id: Mapped[int | None] = mapped_column(ForeignKey("ingredient.item_id"), nullable=True)  # Link a personal brand variant to its generic ingredient.
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)  # Hide an ingredient from new recipes without deleting its history.

    item: Mapped["Item"] = relationship(back_populates="ingredient")  # Reach the ingredient's name, image, and default unit.
    ingredient_category: Mapped["IngredientCategory"] = relationship(back_populates="ingredients")  # Reach the ingredient's category.
    recipe_links: Mapped[list["RecipeIngredient"]] = relationship(back_populates="ingredient")  # Reach the recipes that use this ingredient.
    owner_user: Mapped["User | None"] = relationship(back_populates="personal_ingredients")  # Identify the account that owns this private ingredient.
    base_ingredient: Mapped["Ingredient | None"] = relationship("Ingredient", remote_side="Ingredient.item_id", back_populates="personal_variants")  # Reach the generic ingredient behind this variant.
    personal_variants: Mapped[list["Ingredient"]] = relationship("Ingredient", back_populates="base_ingredient")  # Reach private variants based on this ingredient.

    # Nutrition values are per 100 g; missing values remain NULL rather than becoming zero.

