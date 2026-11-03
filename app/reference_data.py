from fastapi import APIRouter, Depends, HTTPException, status  # Build public reads and administrator-only writes.
from sqlalchemy import func, select  # Query reference data and count existing references.
from sqlalchemy.exc import IntegrityError  # Translate database uniqueness and reference conflicts.
from sqlalchemy.orm import Session  # Type the request database dependency.

from app.auth import get_current_admin  # Restrict mutations to administrator accounts.
from app.database import get_db  # Provide a request-scoped database session.
from app.models import Category, Ingredient, IngredientCategory, Item, Recipe, RecipeCategory, RecipeIngredient, Unit, UnitConversion, User  # Read shared references and their dependent rows.
from app.schemas import CategoryCreate, CategoryUpdate, IngredientCategorySummary, RecipeCategorySummary, UnitConversionInput, UnitConversionSummary, UnitCreate, UnitSummary  # Validate reference-data payloads.


router = APIRouter()  # Group reference-data routes for mounting under the API version prefix.


# Keep cached recipe portions aligned when a generic conversion changes.
def refresh_all_recipe_nutrition(db: Session) -> None:  # Recalculate the small V1 recipe catalogue after unit changes.
    from app.recipes import refresh_recipe_nutrition_cache  # Import locally to avoid an API-router import cycle.
    try:  # Translate constraints raised before the final commit.
        db.flush()  # Apply the changed conversion before reading its graph.
    except IntegrityError as error:  # Handle concurrent duplicate reference data.
        db.rollback()  # Restore the session after the failed flush.
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Cette unité ou conversion existe déjà ou est encore utilisée.") from error  # Keep database internals out of the API response.
    for recipe in db.scalars(select(Recipe)).all():  # Visit every recipe that may depend on this conversion.
        refresh_recipe_nutrition_cache(recipe, db, db.get(User, recipe.author_id))  # Store complete values or clear incomplete ones.


# Convert database uniqueness conflicts into a predictable client response.
def commit_or_conflict(db: Session) -> None:  # Commit one reference-data mutation.
    try:  # Handle concurrent duplicate names or unit pairs safely.
        db.commit()  # Persist the administrator's change.
    except IntegrityError as error:  # Catch database constraints without returning SQL internals.
        db.rollback()  # Restore the session after the failed transaction.
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Une donnée de référence identique existe déjà ou est encore utilisée.") from error  # Explain the conflict in product language.


# Return all recipe categories so visitors can filter public recipes.
@router.get("/categories/recipes", response_model=list[RecipeCategorySummary])  # Expose recipe categories to every visitor.
def list_recipe_categories(db: Session = Depends(get_db)) -> list[RecipeCategorySummary]:  # Read the recipe category catalogue.
    rows = db.scalars(select(Category).order_by(Category.name)).all()  # Sort categories for predictable select controls.
    return [RecipeCategorySummary(id=row.id, name=row.name, icon_slug=row.icon_slug) for row in rows]  # Return only fields needed by the interface.


# Return all ingredient categories for ingredient creation forms.
@router.get("/categories/ingredients", response_model=list[IngredientCategorySummary])  # Expose ingredient categories to every visitor.
def list_ingredient_categories(db: Session = Depends(get_db)) -> list[IngredientCategorySummary]:  # Read the ingredient category catalogue.
    rows = db.scalars(select(IngredientCategory).order_by(IngredientCategory.name)).all()  # Sort categories for predictable select controls.
    return [IngredientCategorySummary(id=row.id, name=row.name, icon_slug=row.icon_slug) for row in rows]  # Return only fields needed by the interface.


# Return measurement units for ingredients and recipe amounts.
@router.get("/units", response_model=list[UnitSummary])  # Expose configured units to every visitor.
def list_units(db: Session = Depends(get_db)) -> list[UnitSummary]:  # Read the unit catalogue.
    rows = db.scalars(select(Unit).order_by(Unit.unit_type, Unit.name)).all()  # Group units by type and name for easy selection.
    return [UnitSummary(id=row.id, name=row.name, symbol=row.symbol, unit_type=row.unit_type) for row in rows]  # Return safe display fields.


# Return conversion factors for the nutrition calculator.
@router.get("/unit-conversions", response_model=list[UnitConversionSummary])  # Expose configured conversions to every visitor.
def list_unit_conversions(db: Session = Depends(get_db)) -> list[UnitConversionSummary]:  # Read the unit conversion catalogue.
    rows = db.scalars(select(UnitConversion).order_by(UnitConversion.from_unit_id, UnitConversion.to_unit_id)).all()  # Return conversions in a stable order.
    return [UnitConversionSummary(id=row.id, from_unit_id=row.from_unit_id, to_unit_id=row.to_unit_id, factor=row.factor) for row in rows]  # Return factors without internal ORM objects.


# Create a recipe category through the admin interface.
@router.post("/admin/categories/recipes", response_model=RecipeCategorySummary, status_code=status.HTTP_201_CREATED)  # Restrict recipe category creation to admins.
def create_recipe_category(payload: CategoryCreate, db: Session = Depends(get_db), admin=Depends(get_current_admin)) -> RecipeCategorySummary:  # Save a shared recipe category.
    row = Category(name=payload.name.strip(), icon_slug=payload.icon_slug)  # Normalize the display name before storage.
    db.add(row)  # Stage the new category.
    commit_or_conflict(db)  # Save it or return a readable duplicate error.
    db.refresh(row)  # Load its generated identifier.
    return RecipeCategorySummary(id=row.id, name=row.name, icon_slug=row.icon_slug)  # Return the new category.


# Rename a recipe category through the admin interface.
@router.patch("/admin/categories/recipes/{category_id}", response_model=RecipeCategorySummary)  # Restrict recipe category edits to admins.
def update_recipe_category(category_id: int, payload: CategoryUpdate, db: Session = Depends(get_db), admin=Depends(get_current_admin)) -> RecipeCategorySummary:  # Update selected recipe category fields.
    row = db.get(Category, category_id)  # Find the category to edit.
    if row is None:  # Reject identifiers that do not exist.
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Catégorie introuvable.")  # Return a stable not-found response.
    for field, value in payload.model_dump(exclude_unset=True).items():  # Apply only fields sent by the administrator.
        setattr(row, field, value.strip() if field == "name" and value is not None else value)  # Normalize names while preserving explicit nullable values.
    commit_or_conflict(db)  # Save the edit or return a readable conflict.
    return RecipeCategorySummary(id=row.id, name=row.name, icon_slug=row.icon_slug)  # Return the updated category.


# Delete a recipe category only when no recipe uses it.
@router.delete("/admin/categories/recipes/{category_id}", status_code=status.HTTP_204_NO_CONTENT)  # Restrict recipe category deletion to admins.
def delete_recipe_category(category_id: int, db: Session = Depends(get_db), admin=Depends(get_current_admin)) -> None:  # Remove an unused recipe category.
    row = db.get(Category, category_id)  # Find the requested recipe category.
    if row is None:  # Reject identifiers that do not exist.
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Catégorie de recette introuvable.")  # Return a stable not-found response.
    usage_count = db.scalar(select(func.count()).select_from(RecipeCategory).where(RecipeCategory.category_id == category_id))  # Count recipes that still use this category.
    if usage_count:  # Protect recipe classifications from being removed accidentally.
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"Cette catégorie est utilisée par {usage_count} recette(s). Retire-la d’abord de ces recettes.")  # Explain the dependency that blocks deletion.
    db.delete(row)  # Stage the unused category for deletion.
    commit_or_conflict(db)  # Persist deletion or translate a concurrent reference conflict.


# Create an ingredient category through the admin interface.
@router.post("/admin/categories/ingredients", response_model=IngredientCategorySummary, status_code=status.HTTP_201_CREATED)  # Restrict ingredient category creation to admins.
def create_ingredient_category(payload: CategoryCreate, db: Session = Depends(get_db), admin=Depends(get_current_admin)) -> IngredientCategorySummary:  # Save a shared ingredient category.
    row = IngredientCategory(name=payload.name.strip(), icon_slug=payload.icon_slug)  # Normalize the display name before storage.
    db.add(row)  # Stage the new category.
    commit_or_conflict(db)  # Save it or return a readable duplicate error.
    db.refresh(row)  # Load its generated identifier.
    return IngredientCategorySummary(id=row.id, name=row.name, icon_slug=row.icon_slug)  # Return the new category.


# Rename an ingredient category through the admin interface.
@router.patch("/admin/categories/ingredients/{category_id}", response_model=IngredientCategorySummary)  # Restrict ingredient category edits to admins.
def update_ingredient_category(category_id: int, payload: CategoryUpdate, db: Session = Depends(get_db), admin=Depends(get_current_admin)) -> IngredientCategorySummary:  # Update selected ingredient category fields.
    row = db.get(IngredientCategory, category_id)  # Find the category to edit.
    if row is None:  # Reject identifiers that do not exist.
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Catégorie introuvable.")  # Return a stable not-found response.
    for field, value in payload.model_dump(exclude_unset=True).items():  # Apply only fields sent by the administrator.
        setattr(row, field, value.strip() if field == "name" and value is not None else value)  # Normalize names while preserving explicit nullable values.
    commit_or_conflict(db)  # Save the edit or return a readable conflict.
    return IngredientCategorySummary(id=row.id, name=row.name, icon_slug=row.icon_slug)  # Return the updated category.


# Delete an ingredient category only when no ingredient belongs to it.
@router.delete("/admin/categories/ingredients/{category_id}", status_code=status.HTTP_204_NO_CONTENT)  # Restrict ingredient category deletion to admins.
def delete_ingredient_category(category_id: int, db: Session = Depends(get_db), admin=Depends(get_current_admin)) -> None:  # Remove an unused ingredient category.
    row = db.get(IngredientCategory, category_id)  # Find the requested ingredient category.
    if row is None:  # Reject identifiers that do not exist.
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Catégorie d’ingrédients introuvable.")  # Return a stable not-found response.
    usage_count = db.scalar(select(func.count()).select_from(Ingredient).where(Ingredient.ingredient_category_id == category_id))  # Count ingredients that still use this category.
    if usage_count:  # Protect ingredient classifications from being removed accidentally.
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"Cette catégorie est utilisée par {usage_count} ingrédient(s). Modifie d’abord ces ingrédients.")  # Explain the dependency that blocks deletion.
    db.delete(row)  # Stage the unused category for deletion.
    commit_or_conflict(db)  # Persist deletion or translate a concurrent reference conflict.


# Create a measurement unit through the admin interface.
@router.post("/admin/units", response_model=UnitSummary, status_code=status.HTTP_201_CREATED)  # Restrict unit creation to admins.
def create_unit(payload: UnitCreate, db: Session = Depends(get_db), admin=Depends(get_current_admin)) -> UnitSummary:  # Save a shared measurement unit.
    row = Unit(name=payload.name.strip(), symbol=payload.symbol.strip(), unit_type=payload.unit_type.strip().lower())  # Normalize unit text before storage.
    db.add(row)  # Stage the new unit.
    commit_or_conflict(db)  # Save it or return a readable duplicate error.
    db.refresh(row)  # Load its generated identifier.
    return UnitSummary(id=row.id, name=row.name, symbol=row.symbol, unit_type=row.unit_type)  # Return the new unit.


# Update a measurement unit through the admin interface.
@router.patch("/admin/units/{unit_id}", response_model=UnitSummary)  # Restrict unit edits to admins.
def update_unit(unit_id: int, payload: UnitSummary, db: Session = Depends(get_db), admin=Depends(get_current_admin)) -> UnitSummary:  # Update one configured measurement unit.
    row = db.get(Unit, unit_id)  # Find the unit to edit.
    if row is None:  # Reject identifiers that do not exist.
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Unité introuvable.")  # Return a stable not-found response.
    row.name = payload.name.strip()  # Normalize the updated unit name.
    row.symbol = payload.symbol.strip()  # Normalize the updated unit symbol.
    row.unit_type = payload.unit_type.strip().lower()  # Keep unit types normalized for compatibility checks.
    refresh_all_recipe_nutrition(db)  # Recheck the gram target if its symbol or type changed.
    commit_or_conflict(db)  # Save the edit or return a readable conflict.
    return UnitSummary(id=row.id, name=row.name, symbol=row.symbol, unit_type=row.unit_type)  # Return the updated unit.


# Delete a unit only after all items, recipe amounts, and conversions stop using it.
@router.delete("/admin/units/{unit_id}", status_code=status.HTTP_204_NO_CONTENT)  # Restrict unit deletion to admins.
def delete_unit(unit_id: int, db: Session = Depends(get_db), admin=Depends(get_current_admin)) -> None:  # Remove an unused measurement unit.
    row = db.get(Unit, unit_id)  # Find the requested unit.
    if row is None:  # Reject identifiers that do not exist.
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Unité introuvable.")  # Return a stable not-found response.
    item_count = db.scalar(select(func.count()).select_from(Item).where(Item.default_unit_id == unit_id))  # Count items that use the unit by default.
    recipe_count = db.scalar(select(func.count()).select_from(RecipeIngredient).where(RecipeIngredient.unit_id == unit_id))  # Count recipe ingredient amounts using the unit.
    conversion_count = db.scalar(select(func.count()).select_from(UnitConversion).where((UnitConversion.from_unit_id == unit_id) | (UnitConversion.to_unit_id == unit_id)))  # Count conversions that depend on the unit.
    if item_count or recipe_count or conversion_count:  # Keep every persisted quantity interpretable.
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"Cette unité est encore utilisée : {item_count} aliment(s), {recipe_count} quantité(s) de recette et {conversion_count} conversion(s).")  # Show what must be reassigned or removed first.
    db.delete(row)  # Stage the unused unit for deletion.
    commit_or_conflict(db)  # Persist deletion or translate a concurrent reference conflict.


# Add a generic multiplier for converting one unit to another.
@router.post("/admin/unit-conversions", response_model=UnitConversionSummary, status_code=status.HTTP_201_CREATED)  # Restrict conversion creation to admins.
def create_unit_conversion(payload: UnitConversionInput, db: Session = Depends(get_db), admin=Depends(get_current_admin)) -> UnitConversionSummary:  # Save a generic conversion rule.
    source = db.get(Unit, payload.from_unit_id)  # Find the source unit.
    target = db.get(Unit, payload.to_unit_id)  # Find the destination unit.
    if source is None or target is None:  # Reject missing unit references.
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Les deux unités doivent exister.")  # Explain the invalid unit selection.
    if source.id == target.id:  # Reject identity conversions; configured equivalencies may cross unit types.
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Choisis deux unités différentes du même type.")  # Explain the conversion rule.
    duplicate = db.scalar(select(UnitConversion).where(UnitConversion.from_unit_id == source.id, UnitConversion.to_unit_id == target.id))  # Check for a duplicate directed pair.
    if duplicate is not None:  # Avoid duplicate conversions between the same units.
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Cette conversion existe déjà.")  # Return a stable duplicate response.
    row = UnitConversion(from_unit_id=source.id, to_unit_id=target.id, factor=payload.factor)  # Create the requested multiplier.
    db.add(row)  # Stage the conversion.
    refresh_all_recipe_nutrition(db)  # Recalculate portions that can now use this conversion.
    commit_or_conflict(db)  # Save it or translate any database conflict.
    db.refresh(row)  # Load the generated identifier.
    return UnitConversionSummary(id=row.id, from_unit_id=row.from_unit_id, to_unit_id=row.to_unit_id, factor=row.factor)  # Return the stored rule.


# Delete one selected conversion rule without affecting its units.
@router.delete("/admin/unit-conversions/{conversion_id}", status_code=status.HTTP_204_NO_CONTENT)  # Restrict conversion deletion to admins.
def delete_unit_conversion(conversion_id: int, db: Session = Depends(get_db), admin=Depends(get_current_admin)) -> None:  # Remove a conversion multiplier.
    row = db.get(UnitConversion, conversion_id)  # Find the requested conversion.
    if row is None:  # Reject identifiers that do not exist.
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversion introuvable.")  # Return a stable not-found response.
    db.delete(row)  # Stage the selected conversion for deletion.
    refresh_all_recipe_nutrition(db)  # Clear or update portions that depended on the removed conversion.
    commit_or_conflict(db)  # Persist the deletion.


