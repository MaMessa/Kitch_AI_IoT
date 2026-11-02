# Import the models so SQLAlchemy registers every table in Base.metadata.
from app.models.base import Base
from app.models.category import Category
from app.models.ingredient import Ingredient
from app.models.ingredient_category import IngredientCategory
from app.models.item import Item
from app.models.recipe import Recipe
from app.models.recipe_category import RecipeCategory
from app.models.recipe_ingredient import RecipeIngredient
from app.models.unit import Unit
from app.models.unit_conversion import UnitConversion
from app.models.user import User

__all__ = [
    "Base",
    "Category",
    "Ingredient",
    "IngredientCategory",
    "Item",
    "Recipe",
    "RecipeCategory",
    "RecipeIngredient",
    "Unit",
    "UnitConversion",
    "User",
]
