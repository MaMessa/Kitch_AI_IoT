from datetime import datetime
from decimal import Decimal

from sqlalchemy import BigInteger, CheckConstraint, DateTime, ForeignKey, Numeric, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


# This model stores a generic conversion between two units.
class UnitConversion(Base):
    __tablename__ = "unit_conversion"

    # Store one positive multiplier for converting from one unit to another.
    __table_args__ = (
        CheckConstraint("factor > 0", name="ck_unit_conversion_factor_positive"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    from_unit_id: Mapped[int] = mapped_column(ForeignKey("unit.id"), nullable=False)
    to_unit_id: Mapped[int] = mapped_column(ForeignKey("unit.id"), nullable=False)
    factor: Mapped[Decimal] = mapped_column(Numeric, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    from_unit: Mapped["Unit"] = relationship(
        back_populates="conversions_from",
        foreign_keys=[from_unit_id],
    )
    to_unit: Mapped["Unit"] = relationship(
        back_populates="conversions_to",
        foreign_keys=[to_unit_id],
    )
    # The conversion is generic and applies equally to every ingredient in V1.
