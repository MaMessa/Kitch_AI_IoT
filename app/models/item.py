from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


# This model stores fields shared by food items and other item types.
class Item(Base):
    __tablename__ = "item"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    image_url: Mapped[str | None] = mapped_column(String, nullable=True)
    default_unit_id: Mapped[int] = mapped_column(ForeignKey("unit.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    default_unit: Mapped["Unit"] = relationship(back_populates="default_for_items")
    ingredient: Mapped["Ingredient | None"] = relationship(back_populates="item")
