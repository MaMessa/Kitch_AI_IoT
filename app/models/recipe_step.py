from sqlalchemy import BigInteger, CheckConstraint, ForeignKey, Integer, Text, UniqueConstraint  # Define step fields and ordering rules.
from sqlalchemy.orm import Mapped, mapped_column, relationship  # Map the step and its parent recipe.

from app.models.base import Base  # Register this table with the shared model metadata.


# This model stores one ordered instruction belonging to a recipe.
class RecipeStep(Base):  # Define the ORM model for one recipe instruction.
    __tablename__ = "recipe_step"  # Use a dedicated table so devices can navigate steps.
    __table_args__ = (CheckConstraint("step_number > 0", name="ck_recipe_step_number_positive"), UniqueConstraint("recipe_id", "step_number", name="uq_recipe_step_order"))  # Require positive, unique step positions within each recipe.

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)  # Identify each recipe step.
    recipe_id: Mapped[int] = mapped_column(ForeignKey("recipe.id", ondelete="CASCADE"), nullable=False)  # Link the step to its recipe and delete it with its parent.
    step_number: Mapped[int] = mapped_column(Integer, nullable=False)  # Store the display order, starting at one.
    instruction: Mapped[str] = mapped_column(Text, nullable=False)  # Store the instruction text for this step.

    recipe: Mapped["Recipe"] = relationship(back_populates="steps")  # Provide access to the recipe that owns this step.
