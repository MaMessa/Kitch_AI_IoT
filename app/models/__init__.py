# Import the models so SQLAlchemy registers every table in Base.metadata.
from app.models.base import Base
from app.models.auth_identity import AuthIdentity
from app.models.category import Category
from app.models.email_action_token import EmailActionToken  # Register one-time email tokens in the shared metadata.
from app.models.ingredient import Ingredient
from app.models.ingredient_category import IngredientCategory
from app.models.item import Item
from app.models.recipe import Recipe
from app.models.recipe_category import RecipeCategory
from app.models.recipe_ingredient import RecipeIngredient
from app.models.recipe_step import RecipeStep  # Register the ordered recipe-step table.
from app.models.unit import Unit
from app.models.unit_conversion import UnitConversion
from app.models.user import User
from app.models.user_session import UserSession  # Register revocable browser sessions in the shared metadata.

__all__ = [
    "AuthIdentity",
    "Base",
    "Category",
    "EmailActionToken",  # Export email verification and recovery tokens.
    "Ingredient",
    "IngredientCategory",
    "Item",
    "Recipe",
    "RecipeCategory",
    "RecipeIngredient",
    "RecipeStep",  # Export RecipeStep for the rest of the application.
    "Unit",
    "UnitConversion",
    "User",
    "UserSession",  # Export the browser-session model for the API and migrations.
]
