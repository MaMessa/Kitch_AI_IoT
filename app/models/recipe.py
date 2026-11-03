from datetime import datetime
from decimal import Decimal  # Represent calculated nutrition without binary rounding.

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Integer, Numeric, String, Text, false, func  # Define recipe columns and their safe database defaults.
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


# This model stores the main information about a recipe.
class Recipe(Base):
    __tablename__ = "recipe"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    author_id: Mapped[int] = mapped_column(ForeignKey("user.id"), nullable=False)
    title: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    prep_time_min: Mapped[int | None] = mapped_column(Integer, nullable=True)
    cook_time_min: Mapped[int | None] = mapped_column(Integer, nullable=True)
    servings: Mapped[int] = mapped_column(Integer, nullable=False, default=4)
    calories_par_portion: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)  # Cache calculated kcal per serving when all inputs are known.
    proteines_par_portion: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)  # Cache calculated protein grams per serving when all inputs are known.
    image_url: Mapped[str | None] = mapped_column(String, nullable=True)
    is_public: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default=false())  # Keep a newly created recipe private until its author publishes it.
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    # Each entry represents one recipe-to-category link.
    category_links: Mapped[list["RecipeCategory"]] = relationship(back_populates="recipe")
    author: Mapped["User"] = relationship(back_populates="recipes")
    ingredient_links: Mapped[list["RecipeIngredient"]] = relationship(
        back_populates="recipe"
    )
    steps: Mapped[list["RecipeStep"]] = relationship(back_populates="recipe", cascade="all, delete-orphan", order_by="RecipeStep.step_number")  # Keep instructions ordered and owned by the recipe.

    # TODO: household_id is deferred because Household is outside the selected V1 scope.
