from sqlalchemy import BigInteger, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


# This model groups ingredients into categories such as vegetables or dairy.
class IngredientCategory(Base):
    __tablename__ = "ingredient_category"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    name: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    icon_slug: Mapped[str | None] = mapped_column(String, nullable=True)

    ingredients: Mapped[list["Ingredient"]] = relationship(
        back_populates="ingredient_category"
    )
