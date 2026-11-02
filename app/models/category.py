from sqlalchemy import BigInteger, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


# This model maps the recipe category table to a Python class.
class Category(Base):
    __tablename__ = "category"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    name: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    icon_slug: Mapped[str | None] = mapped_column(String, nullable=True)

    # Each entry represents one recipe-to-category link.
    recipe_links: Mapped[list["RecipeCategory"]] = relationship(back_populates="category")
