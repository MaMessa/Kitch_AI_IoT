from collections import deque  # Search conversion chains between units.
from decimal import Decimal  # Keep nutrition arithmetic exact.
from fastapi import APIRouter, Depends, HTTPException, Query, status  # Build validated recipe endpoints.
from sqlalchemy import delete, func, or_, select  # Query recipes and replace their nested rows.
from sqlalchemy.orm import Session, joinedload, selectinload  # Load related recipe information without detached objects.

from app.auth import get_current_admin, get_current_user, get_optional_current_user  # Protect recipe ownership and moderation actions.
from app.database import get_db  # Provide one database session per request.
from app.models import Category, Ingredient, Item, Recipe, RecipeCategory, RecipeIngredient, RecipeStep, Unit, UnitConversion, User  # Read and persist recipe data.
from app.schemas import IngredientSummary, NutritionResult, PublicRecipePage, PublicRecipeSummary, RecipeCategorySummary, RecipeCreate, RecipeDetail, RecipeIngredientSummary, RecipeStepSummary, RecipeUpdate  # Validate recipe payloads and responses.
from app.ingredients import ingredient_response  # Reuse the visibility-safe ingredient response builder.


router = APIRouter()  # Group recipe creation, ownership, publication, and nutrition routes.


# Load all connected recipe data needed by the detail response.
def recipe_query():  # Build the shared eager-loading query for recipe details.
    return select(Recipe).options(selectinload(Recipe.category_links).joinedload(RecipeCategory.category), selectinload(Recipe.ingredient_links).joinedload(RecipeIngredient.unit), selectinload(Recipe.ingredient_links).joinedload(RecipeIngredient.ingredient).joinedload(Ingredient.item).joinedload(Item.default_unit), selectinload(Recipe.ingredient_links).joinedload(RecipeIngredient.ingredient).joinedload(Ingredient.ingredient_category), selectinload(Recipe.steps))  # Load nested relationships before the session closes.


# Convert a loaded recipe into its safe nested API representation.
def recipe_response(row: Recipe) -> RecipeDetail:  # Return recipe fields and nested content.
    categories = [RecipeCategorySummary(id=link.category.id, name=link.category.name, icon_slug=link.category.icon_slug) for link in row.category_links]  # Shape linked recipe categories.
    ingredients = [RecipeIngredientSummary(ingredient_id=link.ingredient_id, quantity=link.quantity, unit_id=link.unit_id, notes=link.notes, ingredient_name=link.ingredient.item.name, unit_symbol=link.unit.symbol) for link in row.ingredient_links]  # Include the ingredient label and measurement symbol.
    steps = [RecipeStepSummary(step_number=step.step_number, instruction=step.instruction) for step in row.steps]  # Keep cooking instructions in their defined order.
    return RecipeDetail(id=row.id, author_id=row.author_id, title=row.title, description=row.description, prep_time_min=row.prep_time_min, cook_time_min=row.cook_time_min, servings=row.servings, calories_par_portion=row.calories_par_portion, proteines_par_portion=row.proteines_par_portion, image_url=row.image_url, is_public=row.is_public, categories=categories, ingredients=ingredients, steps=steps)  # Return the complete recipe view.


# Ensure every category, ingredient, and unit is visible and valid for the author.
def validate_recipe_links(payload: RecipeCreate, user: User, db: Session) -> None:  # Reject references that the caller cannot use.
    category_ids = set(payload.category_ids)  # Deduplicate category identifiers before checking them.
    if len(category_ids) != len(payload.category_ids):  # Avoid duplicate category links in one recipe.
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Une catégorie ne peut apparaître qu’une fois.")  # Explain the duplicate selection.
    if category_ids and len(db.scalars(select(Category.id).where(Category.id.in_(category_ids))).all()) != len(category_ids):  # Confirm all recipe categories exist.
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Une catégorie de recette est introuvable.")  # Explain the invalid category.
    ingredient_ids = {entry.ingredient_id for entry in payload.ingredients}  # Collect ingredient references in the recipe.
    if len(ingredient_ids) != len(payload.ingredients):  # Prevent duplicate ingredient rows from silently confusing the editor.
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Un ingrédient ne peut apparaître qu’une fois; ajuste sa quantité sur sa ligne.")  # Explain how to resolve duplicates.
    if ingredient_ids:  # Validate ingredient visibility only when ingredients are included.
        rows = db.scalars(select(Ingredient).where(Ingredient.item_id.in_(ingredient_ids), Ingredient.archived_at.is_(None), or_(Ingredient.owner_user_id.is_(None), Ingredient.owner_user_id == user.id))).all()  # Load only active shared or current-user ingredients.
        if len(rows) != len(ingredient_ids):  # Reject private, archived, or missing ingredients.
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Un ingrédient est introuvable, archivé ou privé pour un autre compte.")  # Preserve ingredient privacy.
    unit_ids = {entry.unit_id for entry in payload.ingredients}  # Collect measurement references.
    if unit_ids and len(db.scalars(select(Unit.id).where(Unit.id.in_(unit_ids))).all()) != len(unit_ids):  # Confirm every selected unit exists.
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Une unité de mesure est introuvable.")  # Explain the invalid measurement.
    for entry in payload.ingredients:  # Check that each amount uses the same unit family as its ingredient.
        ingredient = db.get(Ingredient, entry.ingredient_id)  # Load the ingredient's default unit.
        requested_unit = db.get(Unit, entry.unit_id)  # Load the chosen recipe unit.
        default_unit = db.get(Unit, db.get(Ingredient, entry.ingredient_id).item.default_unit_id)  # Load the ingredient's usual unit.
        if ingredient is None or requested_unit is None or False:  # Reject incompatible measures.
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="L’unité choisie est incompatible avec cet ingrédient.")  # Prevent invalid quantity conversions.


# Replace recipe categories, ingredient amounts, and steps after validation.
def replace_recipe_content(row: Recipe, payload: RecipeCreate, db: Session) -> None:  # Keep nested recipe rows consistent on create and edit.
    row.title = payload.title.strip()  # Normalize the recipe title.
    row.description = payload.description.strip() if payload.description else None  # Store an optional clean description.
    row.prep_time_min = payload.prep_time_min  # Store preparation time.
    row.cook_time_min = payload.cook_time_min  # Store cooking time.
    row.servings = payload.servings  # Store the number of portions.
    row.image_url = payload.image_url.strip() if payload.image_url else None  # Store the optional cover image URL.
    db.flush()  # Ensure the recipe has an identifier before creating related rows.
    db.execute(delete(RecipeCategory).where(RecipeCategory.recipe_id == row.id))  # Replace old category links as one operation.
    db.execute(delete(RecipeIngredient).where(RecipeIngredient.recipe_id == row.id))  # Replace old ingredient amounts as one operation.
    db.execute(delete(RecipeStep).where(RecipeStep.recipe_id == row.id))  # Replace old instructions as one operation.
    for category_id in payload.category_ids:  # Add each selected recipe category.
        db.add(RecipeCategory(recipe_id=row.id, category_id=category_id))  # Link the category to this recipe.
    for entry in payload.ingredients:  # Add each ingredient, quantity, and unit.
        db.add(RecipeIngredient(recipe_id=row.id, ingredient_id=entry.ingredient_id, quantity=entry.quantity, unit_id=entry.unit_id, notes=entry.notes.strip() if entry.notes else None))  # Persist the measured ingredient link.
    for index, entry in enumerate(payload.steps, start=1):  # Number instructions from one in their submitted order.
        db.add(RecipeStep(recipe_id=row.id, step_number=index, instruction=entry.instruction.strip()))  # Persist the ordered instruction.


# Create a private recipe owned by the authenticated account.
@router.post("/recipes", response_model=RecipeDetail, status_code=status.HTTP_201_CREATED)  # Require a signed-in recipe author.
def create_recipe(payload: RecipeCreate, db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> RecipeDetail:  # Save a private recipe and its nested rows.
    validate_recipe_links(payload, user, db)  # Reject invalid categories, ingredients, and units before writing.
    row = Recipe(author_id=user.id, title=payload.title.strip(), servings=payload.servings, is_public=False)  # Keep every new recipe private by default.
    db.add(row)  # Stage the recipe row.
    replace_recipe_content(row, payload, db)  # Save categories, ingredients, and steps.
    db.flush()  # Make all recipe ingredients visible to the nutrition calculator.
    refresh_recipe_nutrition_cache(row, db, user)  # Store per-serving calories and proteins when calculable.
    db.commit()  # Persist the complete recipe atomically.
    saved = db.scalar(recipe_query().where(Recipe.id == row.id))  # Reload all nested rows for the response.
    return recipe_response(saved)  # Return the newly created private recipe.


# List recipes belonging to the signed-in author.
@router.get("/recipes/mine", response_model=list[PublicRecipeSummary])  # Return the user's recipe cards.
def list_my_recipes(q: str | None = Query(default=None, max_length=100), db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> list[PublicRecipeSummary]:  # Keep private data scoped to its author.
    statement = select(Recipe).where(Recipe.author_id == user.id)  # Load only the current user's recipes.
    if q and q.strip():  # Add title matching only when the user entered search text.
        statement = statement.where(Recipe.title.ilike(f"%{q.strip()}%"))  # Search recipe titles case-insensitively.
    rows = db.scalars(statement.options(selectinload(Recipe.category_links).joinedload(RecipeCategory.category)).order_by(Recipe.updated_at.desc().nullslast(), Recipe.id.desc()).limit(200)).all()  # Sort and bound the author's recipe list.
    return [PublicRecipeSummary(id=row.id, title=row.title, description=row.description, prep_time_min=row.prep_time_min, cook_time_min=row.cook_time_min, servings=row.servings, calories_par_portion=row.calories_par_portion, proteines_par_portion=row.proteines_par_portion, image_url=row.image_url, categories=[RecipeCategorySummary(id=link.category.id, name=link.category.name, icon_slug=link.category.icon_slug) for link in row.category_links]) for row in rows]  # Return cards for private and published recipes.


# Read a public recipe or a private recipe owned by the caller or an admin.
@router.get("/recipes/{recipe_id}", response_model=RecipeDetail)  # Protect private recipes while supporting public reading.
def get_recipe(recipe_id: int, db: Session = Depends(get_db), user: User | None = Depends(get_optional_current_user)) -> RecipeDetail:  # Load one visible recipe in detail.
    row = db.scalar(recipe_query().where(Recipe.id == recipe_id))  # Load the recipe and nested content.
    if row is None or (not row.is_public and (user is None or (row.author_id != user.id and not user.is_admin))):  # Hide private recipes from visitors and other users.
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Recette introuvable.")  # Avoid revealing private recipe identifiers.
    return recipe_response(row)  # Return the recipe details.


# Replace all editable recipe content while preserving its publication state.
@router.put("/recipes/{recipe_id}", response_model=RecipeDetail)  # Restrict full recipe edits to the author.
def update_recipe(recipe_id: int, payload: RecipeUpdate, db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> RecipeDetail:  # Update the author's recipe and nested rows.
    row = db.get(Recipe, recipe_id)  # Load the requested recipe.
    if row is None or row.author_id != user.id:  # Do not allow another user or admin to edit recipe content.
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Recette introuvable.")  # Keep private identifiers private.
    validate_recipe_links(payload, user, db)  # Validate every replacement relationship.
    replace_recipe_content(row, payload, db)  # Replace editable fields and nested content.
    db.flush()  # Make the replacement ingredients visible to the nutrition calculator.
    refresh_recipe_nutrition_cache(row, db, user)  # Keep the per-serving cache aligned with this edit.
    db.commit()  # Persist the full update.
    saved = db.scalar(recipe_query().where(Recipe.id == row.id))  # Reload ordered nested content.
    return recipe_response(saved)  # Return the updated recipe.


# Delete a recipe when requested by its author or an admin moderator.
@router.delete("/recipes/{recipe_id}", status_code=status.HTTP_204_NO_CONTENT)  # Permit author deletion and admin moderation.
def delete_recipe(recipe_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> None:  # Remove the recipe and its owned content.
    row = db.get(Recipe, recipe_id)  # Load the requested recipe.
    if row is None or (row.author_id != user.id and not user.is_admin):  # Restrict deletion to the author or administrator.
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Recette introuvable.")  # Avoid exposing private records.
    db.execute(delete(RecipeCategory).where(RecipeCategory.recipe_id == row.id))  # Remove category links before deleting the recipe.
    db.execute(delete(RecipeIngredient).where(RecipeIngredient.recipe_id == row.id))  # Remove ingredient links before deleting the recipe.
    db.execute(delete(RecipeStep).where(RecipeStep.recipe_id == row.id))  # Remove ordered steps before deleting the recipe.
    db.delete(row)  # Remove the recipe row itself.
    db.commit()  # Persist the deletion.


# Publish a recipe only when its author has verified their email.
@router.post("/recipes/{recipe_id}/publish", response_model=RecipeDetail)  # Restrict publishing to the verified author.
def publish_recipe(recipe_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> RecipeDetail:  # Make the author's recipe public.
    row = db.scalar(recipe_query().where(Recipe.id == recipe_id, Recipe.author_id == user.id))  # Load only a recipe owned by the caller.
    if row is None:  # Reject missing or non-owned recipes.
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Recette introuvable.")  # Avoid revealing ownership.
    if user.email_verified_at is None:  # Enforce the product's verified-email publication rule.
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Vérifie ton adresse email avant de publier une recette.")  # Explain the account requirement.
    row.is_public = True  # Publish the recipe to the public catalogue.
    db.commit()  # Persist the publication state.
    return recipe_response(row)  # Return the new public state.


# Hide a recipe from the public catalogue without deleting its author's content.
@router.post("/recipes/{recipe_id}/unpublish", response_model=RecipeDetail)  # Permit the author or admin to hide a recipe.
def unpublish_recipe(recipe_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> RecipeDetail:  # Return the recipe to private visibility.
    row = db.scalar(recipe_query().where(Recipe.id == recipe_id))  # Load the requested recipe.
    if row is None or (row.author_id != user.id and not user.is_admin):  # Restrict hiding to the author or admin moderator.
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Recette introuvable.")  # Avoid exposing private identifiers.
    row.is_public = False  # Hide the recipe from public browsing.
    db.commit()  # Persist the moderation action.
    return recipe_response(row)  # Return the private state.


# Hide any recipe from public browsing as an administrator moderation action.
@router.post("/admin/recipes/{recipe_id}/hide", response_model=RecipeDetail)  # Restrict moderation to admins.
def admin_hide_recipe(recipe_id: int, db: Session = Depends(get_db), admin: User = Depends(get_current_admin)) -> RecipeDetail:  # Moderate a recipe without changing its author's content.
    row = db.scalar(recipe_query().where(Recipe.id == recipe_id))  # Load the recipe to moderate.
    if row is None:  # Reject missing recipes.
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Recette introuvable.")  # Return a stable not-found response.
    row.is_public = False  # Remove the recipe from public catalogue results.
    db.commit()  # Persist the moderation result.
    return recipe_response(row)  # Return the moderated recipe.


# Refresh recipe nutrition snapshots after changes to the recipe content.
def refresh_recipe_nutrition_cache(row: Recipe, db: Session, user: User) -> None:  # Store values only when the full calculation succeeds.
    result = calculate_recipe_nutrition(row.id, db, user)  # Reuse the live nutrition calculation and visibility checks.
    row.calories_par_portion = result.calories if result.status == "complete" else None  # Leave kcal unknown when inputs are incomplete.
    row.proteines_par_portion = result.proteins if result.status == "complete" else None  # Leave protein unknown when inputs are incomplete.


# Find the multiplier needed to convert a unit amount into grams.
def conversion_factor_to_grams(start_unit_id: int, db: Session) -> Decimal | None:  # Search directed conversions in either direction.
    target = db.scalar(select(Unit).where(Unit.symbol == "g", Unit.unit_type == "mass"))  # Find the canonical gram unit.
    start = db.get(Unit, start_unit_id)  # Load the recipe unit.
    if target is None or start is None:  # Reject missing starting or target units.
        return None  # Explain to the caller that no valid conversion exists.
    if start.id == target.id:  # Handle grams without a database conversion row.
        return Decimal("1")  # One gram is already the target unit.
    rows = db.scalars(select(UnitConversion)).all()  # Load the small V1 conversion table.
    graph: dict[int, list[tuple[int, Decimal]]] = {}  # Map each unit to reachable units and multipliers.
    for conversion in rows:  # Build bidirectional edges from stored directed conversions.
        graph.setdefault(conversion.from_unit_id, []).append((conversion.to_unit_id, conversion.factor))  # Add the configured forward multiplier.
        graph.setdefault(conversion.to_unit_id, []).append((conversion.from_unit_id, Decimal("1") / conversion.factor))  # Add the mathematically inverse multiplier.
    queue = deque([(start.id, Decimal("1"))])  # Track the current unit and total multiplier from the starting unit.
    visited = {start.id}  # Prevent conversion cycles from repeating indefinitely.
    while queue:  # Explore reachable compatible units breadth-first.
        current, multiplier = queue.popleft()  # Read the next unit and accumulated factor.
        for neighbour, factor in graph.get(current, []):  # Examine each available conversion edge.
            if neighbour in visited:  # Skip units already reached by a shorter path.
                continue  # Avoid loops in the conversion graph.
            next_multiplier = multiplier * factor  # Combine adjacent conversion factors.
            if neighbour == target.id:  # Stop as soon as grams are reached.
                return next_multiplier  # Return grams per starting unit.
            visited.add(neighbour)  # Mark this unit as explored.
            queue.append((neighbour, next_multiplier))  # Continue searching from the newly reached unit.
    return None  # Report that no configured path reaches grams.


# Calculate nutrition per serving or identify missing data precisely.
@router.get("/recipes/{recipe_id}/nutrition", response_model=NutritionResult)  # Return nutrition for a public or visible private recipe.
def calculate_recipe_nutrition(recipe_id: int, db: Session = Depends(get_db), user: User | None = Depends(get_optional_current_user)) -> NutritionResult:  # Sum ingredient nutrients after unit conversion.
    row = db.scalar(recipe_query().where(Recipe.id == recipe_id))  # Load recipe ingredients and serving count.
    if row is None or (not row.is_public and (user is None or (row.author_id != user.id and not user.is_admin))):  # Enforce the same private recipe visibility rule as detail reads.
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Recette introuvable.")  # Avoid revealing private recipe identifiers.
    if not row.ingredient_links:  # A recipe without ingredients has no derived nutrition.
        return NutritionResult(status="no_ingredients", servings=row.servings, calories=None, proteins=None, carbs=None, fats=None, missing=["Ajoute des ingrédients pour calculer la nutrition."])  # Explain why no calculation is available.
    totals = {field: Decimal("0") for field in ("calories", "proteins", "carbs", "fats")}  # Start whole-recipe totals at zero.
    missing: list[str] = []  # Track missing values and conversions without blocking recipe saving.
    for link in row.ingredient_links:  # Calculate each ingredient's contribution.
        ingredient = link.ingredient  # Read the linked ingredient.
        base = ingredient.base_ingredient  # Read its generic base when available.
        factor = conversion_factor_to_grams(link.unit_id, db)  # Convert the recipe amount to grams.
        if factor is None:  # Keep the recipe saved even when its unit cannot be converted.
            missing.append(f"{ingredient.item.name}: conversion vers les grammes manquante.")  # Identify the unit conversion needed.
            continue  # Skip numeric nutrition for this ingredient.
        grams = Decimal(link.quantity) * factor  # Convert the amount to grams using the configured multiplier.
        for field in totals:  # Add each supported nutrient.
            value = getattr(ingredient, field) if getattr(ingredient, field) is not None else getattr(base, field, None)  # Use variant overrides or inherit from the generic base.
            if value is None:  # Refuse to treat missing values as zero.
                missing.append(f"{ingredient.item.name}: valeur {field} manquante.")  # Identify the ingredient field to complete.
            else:  # Add the known nutrient contribution.
                totals[field] += Decimal(value) * grams / Decimal("100")  # Scale the per-100-g value to this recipe amount.
    if missing:  # Avoid presenting partial totals as a complete nutrition result.
        return NutritionResult(status="incomplete", servings=row.servings, calories=None, proteins=None, carbs=None, fats=None, missing=missing)  # Return actionable missing-data details.
    portion_values = {field: value / Decimal(row.servings) for field, value in totals.items()}  # Divide whole-recipe nutrients by portions.
    return NutritionResult(status="complete", servings=row.servings, calories=portion_values["calories"], proteins=portion_values["proteins"], carbs=portion_values["carbs"], fats=portion_values["fats"], missing=[])  # Return per-serving nutrition.


# Return only public recipes with the chosen search filters and page.
@router.get("/recipes", response_model=PublicRecipePage)  # Expose public recipe discovery.
def list_public_recipes(q: str | None = Query(default=None, max_length=100), category_id: int | None = Query(default=None, gt=0), max_prep_time: int | None = Query(default=None, ge=0), page: int = Query(default=1, ge=1), page_size: int = Query(default=20, ge=1, le=100), db: Session = Depends(get_db)) -> PublicRecipePage:  # Search and page through public recipes.
    filters = [Recipe.is_public.is_(True)]  # Never return private recipes here.
    if q and q.strip():  # Add title search when present.
        filters.append(Recipe.title.ilike(f"%{q.strip()}%"))  # Search case-insensitively.
    if category_id is not None:  # Add category filtering when requested.
        filters.append(Recipe.category_links.any(RecipeCategory.category_id == category_id))  # Require the selected category link.
    if max_prep_time is not None:  # Add the preparation-time limit when requested.
        filters.append(Recipe.prep_time_min <= max_prep_time)  # Keep recipes within the requested limit.
    total = db.scalar(select(func.count(Recipe.id)).where(*filters)) or 0  # Count matches before pagination.
    rows = db.scalars(select(Recipe).options(selectinload(Recipe.category_links).joinedload(RecipeCategory.category)).where(*filters).order_by(Recipe.created_at.desc(), Recipe.id.desc()).offset((page - 1) * page_size).limit(page_size)).all()  # Load one bounded page with category labels.
    cards = [PublicRecipeSummary(id=row.id, title=row.title, description=row.description, prep_time_min=row.prep_time_min, cook_time_min=row.cook_time_min, servings=row.servings, calories_par_portion=row.calories_par_portion, proteines_par_portion=row.proteines_par_portion, image_url=row.image_url, categories=[RecipeCategorySummary(id=link.category.id, name=link.category.name, icon_slug=link.category.icon_slug) for link in row.category_links]) for row in rows]  # Shape public recipe cards.
    page_count = (total + page_size - 1) // page_size  # Calculate the number of pages.
    return PublicRecipePage(items=cards, total=total, page=page, page_size=page_size, page_count=page_count)  # Return results and pagination metadata.



