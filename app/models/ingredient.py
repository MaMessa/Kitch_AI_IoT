from decimal import Decimal

from sqlalchemy import BigInteger, ForeignKey, Numeric, String, UniqueConstraint  # Define database columns and the provider identity rule.
from sqlalchemy.orm import Mapped, mapped_column, relationship  # Map typed Python attributes to SQL columns and relations.

from app.models.base import Base


# This model adds food-specific data to a shared Item record.
class Ingredient(Base):
    __tablename__ = "ingredient"  # Keep the existing PostgreSQL table name.
    __table_args__ = (UniqueConstraint("data_source", "source_id", name="uq_ingredient_source_id"),)  # Prevent importing one external record twice.

    # The item id is also this table's primary key, creating a one-to-one extension.
    item_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("item.id"), primary_key=True
    )
    ingredient_category_id: Mapped[int] = mapped_column(
        ForeignKey("ingredient_category.id"), nullable=False
    )
    calories: Mapped[Decimal | None] = mapped_column(Numeric, nullable=True)
    proteins: Mapped[Decimal | None] = mapped_column(Numeric, nullable=True)
    carbs: Mapped[Decimal | None] = mapped_column(Numeric, nullable=True)
    fats: Mapped[Decimal | None] = mapped_column(Numeric, nullable=True)
    fiber: Mapped[Decimal | None] = mapped_column(Numeric, nullable=True)
    data_source: Mapped[str] = mapped_column(String, nullable=False, default="manual", server_default="manual")  # Distinguish manual, Ciqual, and Open Food Facts records.
    source_id: Mapped[str | None] = mapped_column(String, nullable=True)  # Store Ciqual's food code or another provider's stable identifier.
    source_version: Mapped[str | None] = mapped_column(String, nullable=True)  # Record which dataset revision supplied the values.
    source_url: Mapped[str | None] = mapped_column(String, nullable=True)  # Keep a link to the source and its attribution.
    brand: Mapped[str | None] = mapped_column(String, nullable=True)  # Keep a product brand separate from the generic food name.
    barcode: Mapped[str | None] = mapped_column(String, nullable=True)  # Reserve the GTIN field for branded products.

    item: Mapped["Item"] = relationship(back_populates="ingredient")
    ingredient_category: Mapped["IngredientCategory"] = relationship(
        back_populates="ingredients"
    )
    recipe_links: Mapped[list["RecipeIngredient"]] = relationship(
        back_populates="ingredient"
    )

    # Nutrient columns store values per 100 g; unavailable data stays NULL rather than becoming zero.
