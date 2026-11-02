from decimal import Decimal

from sqlalchemy import BigInteger, ForeignKey, Numeric
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


# This model adds food-specific data to a shared Item record.
class Ingredient(Base):
    __tablename__ = "ingredient"

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

    item: Mapped["Item"] = relationship(back_populates="ingredient")
    ingredient_category: Mapped["IngredientCategory"] = relationship(
        back_populates="ingredients"
    )
    recipe_links: Mapped[list["RecipeIngredient"]] = relationship(
        back_populates="ingredient"
    )

    # TODO: Confirm that nutrition values are measured per 100 g or ml.
