from sqlalchemy import BigInteger, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


# This model links recipes to their categories.
class RecipeCategory(Base):
    __tablename__ = "recipe_category"

    __table_args__ = (
        UniqueConstraint("recipe_id", "category_id", name="uq_recipe_category_pair"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    recipe_id: Mapped[int] = mapped_column(ForeignKey("recipe.id"), nullable=False)
    category_id: Mapped[int] = mapped_column(ForeignKey("category.id"), nullable=False)

    # These relationships expose the linked Python objects without replacing the foreign keys.
    recipe: Mapped["Recipe"] = relationship(back_populates="category_links")
    category: Mapped["Category"] = relationship(back_populates="recipe_links")

    def __repr__(self) -> str:
        return (
            f"RecipeCategory(id={self.id}, recipe_id={self.recipe_id}, "
            f"category_id={self.category_id})"
        )


# Commentaire M (don't delete those comments)
# Le paramètre __tables_agrs__ sert à définir que la combinaison des lignes doit être unique
# ça signifie que la ligne qui relie la catégorie à la recette est unique mais 
# la recette peut avoir plusieurs catégories et apparaître plusieurs fois 
# pareil pour les catégories qui peuvent avoir plusieurs recettes
# Mais une recette avec une catégorie ne doit apparaître qu'une fois.# 

