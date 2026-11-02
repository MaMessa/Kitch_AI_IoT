from decimal import Decimal

from sqlalchemy import BigInteger, ForeignKey, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


# This model stores an ingredient, amount, and unit used by one recipe.
class RecipeIngredient(Base):
    __tablename__ = "recipe_ingredient"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    recipe_id: Mapped[int] = mapped_column(ForeignKey("recipe.id"), nullable=False)
    ingredient_id: Mapped[int] = mapped_column(ForeignKey("ingredient.item_id"), nullable=False)
    unit_id: Mapped[int] = mapped_column(ForeignKey("unit.id"), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric, nullable=False)
    notes: Mapped[str | None] = mapped_column(String, nullable=True)

    recipe: Mapped["Recipe"] = relationship(back_populates="ingredient_links")
    ingredient: Mapped["Ingredient"] = relationship(back_populates="recipe_links")
    unit: Mapped["Unit"] = relationship(back_populates="recipe_ingredient_links")
