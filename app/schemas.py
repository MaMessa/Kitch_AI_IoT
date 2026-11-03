from decimal import Decimal  # Preserve exact decimal values for quantities and nutrition.
from pydantic import BaseModel, ConfigDict, Field  # Validate request bodies and response objects.


# Return concise recipe-category data for labels and filters.
class RecipeCategorySummary(BaseModel):  # Describe one recipe category.
    id: int  # Identify the category.
    name: str  # Display the category label.
    icon_slug: str | None = None  # Allow an optional icon identifier.


# Return concise ingredient-category data for selection lists.
class IngredientCategorySummary(BaseModel):  # Describe one ingredient category.
    id: int  # Identify the category.
    name: str  # Display the category label.
    icon_slug: str | None = None  # Allow an optional icon identifier.


# Return unit information required by recipe and ingredient forms.
class UnitSummary(BaseModel):  # Describe one measurement unit.
    id: int  # Identify the unit.
    name: str  # Display the unit name.
    symbol: str  # Display the short unit symbol.
    unit_type: str  # Group compatible units for conversion.



# Validate the fields required to create a new unit.
class UnitCreate(BaseModel):  # Describe an administrator-created unit.
    name: str = Field(min_length=1, max_length=100)  # Require a unit display name.
    symbol: str = Field(min_length=1, max_length=20)  # Require a short, unique symbol.
    unit_type: str = Field(min_length=1, max_length=50)  # Group units that can be converted.
# Describe a conversion multiplier entered by an administrator.
class UnitConversionInput(BaseModel):  # Validate a conversion from one unit to another.
    from_unit_id: int = Field(gt=0)  # Require a valid source unit identifier.
    to_unit_id: int = Field(gt=0)  # Require a valid destination unit identifier.
    factor: Decimal = Field(gt=0)  # Require a positive multiplier.


# Return a saved unit conversion with its identifier.
class UnitConversionSummary(UnitConversionInput):  # Describe one stored conversion.
    id: int  # Identify the conversion row.


# Validate creation of a recipe or ingredient category.
class CategoryCreate(BaseModel):  # Describe a new category.
    name: str = Field(min_length=1, max_length=100)  # Require a short category name.
    icon_slug: str | None = Field(default=None, max_length=100)  # Accept an optional icon key.


# Validate partial category edits.
class CategoryUpdate(BaseModel):  # Describe editable category fields.
    name: str | None = Field(default=None, min_length=1, max_length=100)  # Allow a category name change.
    icon_slug: str | None = Field(default=None, max_length=100)  # Allow an icon change.


# Validate creation of a personal ingredient or brand variant.
class IngredientCreate(BaseModel):  # Describe a new private ingredient.
    name: str = Field(min_length=1, max_length=200)  # Require a display name stored on Item.
    default_unit_id: int = Field(gt=0)  # Require a default unit for the ingredient.
    ingredient_category_id: int = Field(gt=0)  # Require a category for the ingredient.
    base_ingredient_id: int | None = Field(default=None, gt=0)  # Optionally link a personal variant to a shared ingredient.
    image_url: str | None = Field(default=None, max_length=2048)  # Allow an optional product or ingredient image URL.
    brand: str | None = Field(default=None, max_length=200)  # Keep an optional brand separate from the generic name.
    barcode: str | None = Field(default=None, max_length=32)  # Keep an optional product barcode.
    calories: Decimal | None = Field(default=None, ge=0)  # Accept kcal per 100 g when known.
    proteins: Decimal | None = Field(default=None, ge=0)  # Accept protein grams per 100 g when known.
    carbs: Decimal | None = Field(default=None, ge=0)  # Accept carbohydrate grams per 100 g when known.
    fats: Decimal | None = Field(default=None, ge=0)  # Accept fat grams per 100 g when known.
    fiber: Decimal | None = Field(default=None, ge=0)  # Accept fiber grams per 100 g when known.


# Validate partial edits to an ingredient owned by the current user.
class IngredientUpdate(BaseModel):  # Describe editable personal-ingredient fields.
    name: str | None = Field(default=None, min_length=1, max_length=200)  # Allow renaming the linked Item.
    default_unit_id: int | None = Field(default=None, gt=0)  # Allow changing the default measurement unit.
    ingredient_category_id: int | None = Field(default=None, gt=0)  # Allow changing the ingredient category.
    image_url: str | None = Field(default=None, max_length=2048)  # Allow replacing the optional image URL.
    brand: str | None = Field(default=None, max_length=200)  # Allow editing the product brand.
    barcode: str | None = Field(default=None, max_length=32)  # Allow editing the product barcode.
    calories: Decimal | None = Field(default=None, ge=0)  # Allow replacing kcal per 100 g.
    proteins: Decimal | None = Field(default=None, ge=0)  # Allow replacing protein grams per 100 g.
    carbs: Decimal | None = Field(default=None, ge=0)  # Allow replacing carbohydrate grams per 100 g.
    fats: Decimal | None = Field(default=None, ge=0)  # Allow replacing fat grams per 100 g.
    fiber: Decimal | None = Field(default=None, ge=0)  # Allow replacing fiber grams per 100 g.


# Return the effective ingredient information visible to one user.
class IngredientSummary(BaseModel):  # Describe an ingredient for search and recipe forms.
    model_config = ConfigDict(from_attributes=True)  # Allow safe conversion from ORM objects.
    id: int  # Identify the ingredient through its Item primary key.
    name: str  # Display the ingredient name.
    image_url: str | None  # Display an optional image.
    default_unit_id: int  # Preselect the ingredient's usual measurement unit.
    default_unit_name: str  # Display the default unit's name.
    default_unit_symbol: str  # Display the default unit's symbol.
    ingredient_category_id: int  # Identify the ingredient category.
    ingredient_category_name: str  # Display the ingredient category.
    owner_user_id: int | None  # Distinguish shared ingredients from private ones.
    base_ingredient_id: int | None  # Identify a shared base when this is a personal variant.
    brand: str | None  # Display an optional brand.
    barcode: str | None  # Display an optional barcode.
    calories: Decimal | None  # Return effective kcal per 100 g.
    proteins: Decimal | None  # Return effective protein grams per 100 g.
    carbs: Decimal | None  # Return effective carbohydrate grams per 100 g.
    fats: Decimal | None  # Return effective fat grams per 100 g.
    fiber: Decimal | None  # Return effective fiber grams per 100 g.
    nutrition_inherited: bool  # Tell the interface whether values come from the base ingredient.
    is_archived: bool  # Keep archived ingredients hidden from new recipe choices.


# Validate one ingredient and amount in a recipe.
class RecipeIngredientInput(BaseModel):  # Describe one recipe ingredient link.
    ingredient_id: int = Field(gt=0)  # Require a valid ingredient.
    quantity: Decimal = Field(gt=0)  # Require a positive recipe quantity.
    unit_id: int = Field(gt=0)  # Require a valid unit.
    notes: str | None = Field(default=None, max_length=500)  # Allow a short preparation or brand note.


# Return one ingredient link attached to a recipe.
class RecipeIngredientSummary(RecipeIngredientInput):  # Describe one saved recipe ingredient.
    ingredient_name: str  # Display the ingredient label.
    unit_symbol: str  # Display the selected measurement symbol.


# Validate one ordered instruction in a recipe.
class RecipeStepInput(BaseModel):  # Describe one recipe instruction.
    instruction: str = Field(min_length=1, max_length=4000)  # Require readable, bounded instruction text.


# Return one saved instruction with its order.
class RecipeStepSummary(BaseModel):  # Describe one ordered recipe step.
    step_number: int  # Identify its position in the recipe.
    instruction: str  # Display the instruction text.


# Validate a new recipe while keeping it private by default.
class RecipeCreate(BaseModel):  # Describe a recipe submitted by its author.
    title: str = Field(min_length=1, max_length=200)  # Require a display title.
    description: str | None = Field(default=None, max_length=5000)  # Allow an optional description.
    prep_time_min: int | None = Field(default=None, ge=0, le=1440)  # Bound preparation time to one day.
    cook_time_min: int | None = Field(default=None, ge=0, le=1440)  # Bound cooking time to one day.
    servings: int = Field(default=4, ge=1, le=100)  # Require a sensible serving count.
    image_url: str | None = Field(default=None, max_length=2048)  # Accept an optional cover image URL.
    category_ids: list[int] = Field(default_factory=list, max_length=20)  # Allow a bounded set of recipe categories.
    ingredients: list[RecipeIngredientInput] = Field(default_factory=list, max_length=100)  # Allow a bounded list of ingredient amounts.
    steps: list[RecipeStepInput] = Field(default_factory=list, max_length=100)  # Allow a bounded list of ordered instructions.


# Validate a partial recipe edit.
class RecipeUpdate(RecipeCreate):  # Reuse creation rules for recipe edits.
    pass  # Keep the same validation for complete edit forms.


# Return a public recipe card for catalogue browsing.
class PublicRecipeSummary(BaseModel):  # Expose fields needed by the public recipe grid.
    id: int  # Identify the recipe.
    title: str  # Display the recipe title.
    description: str | None  # Display an optional recipe summary.
    prep_time_min: int | None  # Display preparation time.
    cook_time_min: int | None  # Support the maximum-time filter.
    servings: int  # Display the portion count.
    calories_par_portion: Decimal | None  # Show calculated kcal per serving when available.
    proteines_par_portion: Decimal | None  # Show calculated protein grams per serving when available.
    image_url: str | None  # Display the optional cover image.
    categories: list[RecipeCategorySummary]  # Display recipe category labels.


# Wrap public recipe cards with pagination information.
class PublicRecipePage(BaseModel):  # Describe one page of the public catalogue.
    items: list[PublicRecipeSummary]  # Return matching recipe cards.
    total: int  # Report the number of matching recipes.
    page: int  # Echo the requested page.
    page_size: int  # Echo the maximum page size.
    page_count: int  # Report the number of result pages.


# Return a full recipe including its ordered ingredients and steps.
class RecipeDetail(BaseModel):  # Describe a recipe in owner and public detail screens.
    id: int  # Identify the recipe.
    author_id: int  # Identify the author for ownership controls.
    title: str  # Display the recipe title.
    description: str | None  # Display an optional description.
    prep_time_min: int | None  # Display preparation time.
    cook_time_min: int | None  # Display cooking time.
    servings: int  # Display the number of portions.
    calories_par_portion: Decimal | None  # Return the stored kcal per serving.
    proteines_par_portion: Decimal | None  # Return the stored protein grams per serving.
    image_url: str | None  # Display an optional cover image.
    is_public: bool  # Show whether the recipe is public.
    categories: list[RecipeCategorySummary]  # Return linked categories.
    ingredients: list[RecipeIngredientSummary]  # Return measured ingredients.
    steps: list[RecipeStepSummary]  # Return cooking instructions in order.


# Return calculated or incomplete nutrition information.
class NutritionResult(BaseModel):  # Describe nutrition per portion.
    status: str  # Report complete or incomplete calculation.
    servings: int  # Explain the divisor used for per-portion values.
    calories: Decimal | None  # Return kcal per portion when calculable.
    proteins: Decimal | None  # Return protein grams per portion when calculable.
    carbs: Decimal | None  # Return carbohydrate grams per portion when calculable.
    fats: Decimal | None  # Return fat grams per portion when calculable.
    missing: list[str]  # Explain which values or conversions prevent calculation.

