from sqlalchemy import BigInteger, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


# This model maps the Unit table to a Python class.
class Unit(Base):
    __tablename__ = "unit"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    name: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    symbol: Mapped[str] = mapped_column(String, unique=True,nullable=False)
    unit_type: Mapped[str] = mapped_column(String, nullable=False)

    default_for_items: Mapped[list["Item"]] = relationship(
        back_populates="default_unit"
    )
    recipe_ingredient_links: Mapped[list["RecipeIngredient"]] = relationship(
        back_populates="unit"
    )
    conversions_from: Mapped[list["UnitConversion"]] = relationship(
        back_populates="from_unit",
        foreign_keys="UnitConversion.from_unit_id",
    )
    conversions_to: Mapped[list["UnitConversion"]] = relationship(
        back_populates="to_unit",
        foreign_keys="UnitConversion.to_unit_id",
    )
