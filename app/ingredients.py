from datetime import datetime, timezone  # Record archive actions in UTC.
from fastapi import APIRouter, Depends, HTTPException, Query, status  # Build validated ingredient endpoints.
from sqlalchemy import case, func, or_, select  # Filter and rank matching ingredient names.
from sqlalchemy.exc import IntegrityError  # Translate delete conflicts into stable responses.
from sqlalchemy.orm import Session, joinedload, selectinload  # Load connected item, unit, category, and base data safely.

from app.auth import get_current_admin, get_current_user, get_optional_current_user  # Enforce account ownership and administrator roles.
from app.database import get_db  # Provide a request-scoped database session.
from app.models import Ingredient, IngredientCategory, Item, Recipe, RecipeIngredient, Unit, User  # Read ingredients and dependent recipes.
from app.schemas import IngredientCreate, IngredientSummary, IngredientUpdate  # Validate ingredient input and output.


router = APIRouter()  # Group ingredient catalogue routes.


# Recalculate portions when an ingredient's nutrition or unit changes.
def refresh_dependent_recipe_nutrition(db: Session, ingredient_id: int) -> None:  # Keep saved recipes aligned with catalogue corrections.
    from app.recipes import refresh_recipe_nutrition_cache  # Import locally because recipe routes also use ingredient helpers.
    db.flush()  # Make the edited ingredient values visible to recipe queries.
    variants = select(Ingredient.item_id).where(Ingredient.base_ingredient_id == ingredient_id)  # Include personal variants that inherit this ingredient.
    recipe_ids = db.scalars(select(RecipeIngredient.recipe_id).where(or_(RecipeIngredient.ingredient_id == ingredient_id, RecipeIngredient.ingredient_id.in_(variants)))).all()  # Find recipes using the ingredient or its variants.
    for recipe_id in set(recipe_ids):  # Recalculate each affected recipe once.
        recipe = db.get(Recipe, recipe_id)  # Load the recipe with its author identifier.
        refresh_recipe_nutrition_cache(recipe, db, db.get(User, recipe.author_id))  # Save complete values or clear incomplete ones.


# Load ingredient relationships needed for safe API responses.
def ingredient_query():  # Build the common eager-loading query.
    return select(Ingredient).options(joinedload(Ingredient.item).joinedload(Item.default_unit), joinedload(Ingredient.ingredient_category), joinedload(Ingredient.base_ingredient).joinedload(Ingredient.item))  # Avoid querying each ingredient's item and category separately.


# Build the visible nutrition values, inheriting fields from a base when empty.
def ingredient_response(row: Ingredient) -> IngredientSummary:  # Shape one ingredient for the current user.
    base = row.base_ingredient  # Read the optional generic ingredient behind a variant.
    nutrition_fields = ("calories", "proteins", "carbs", "fats", "fiber")  # List the nutrition fields shared by base and variant records.
    effective = {field: getattr(row, field) if getattr(row, field) is not None else getattr(base, field, None) for field in nutrition_fields}  # Prefer variant values and otherwise inherit from the base.
    inherited = any(getattr(row, field) is None and getattr(base, field, None) is not None for field in nutrition_fields)  # Explain whether any returned value came from the base.
    return IngredientSummary(id=row.item_id, name=row.item.name, image_url=row.item.image_url, default_unit_id=row.item.default_unit_id, default_unit_name=row.item.default_unit.name, default_unit_symbol=row.item.default_unit.symbol, ingredient_category_id=row.ingredient_category_id, ingredient_category_name=row.ingredient_category.name, owner_user_id=row.owner_user_id, base_ingredient_id=row.base_ingredient_id, brand=row.brand, barcode=row.barcode, calories=effective["calories"], proteins=effective["proteins"], carbs=effective["carbs"], fats=effective["fats"], fiber=effective["fiber"], nutrition_inherited=inherited, is_archived=row.archived_at is not None)  # Return no credentials or private data from other records.


# Validate references and save an ingredient for either a user or administrator.
def create_ingredient(payload: IngredientCreate, db: Session, owner_user_id: int | None) -> IngredientSummary:  # Share creation rules between personal and shared ingredients.
    unit = db.get(Unit, payload.default_unit_id)  # Find the required default unit.
    category = db.get(IngredientCategory, payload.ingredient_category_id)  # Find the required ingredient category.
    if unit is None or category is None:  # Reject invalid reference identifiers.
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Choisis une unité et une catégorie existantes.")  # Explain the invalid form selection.
    base = None  # Start without an inherited base ingredient.
    if payload.base_ingredient_id is not None:  # Validate an optional shared base ingredient.
        base = db.get(Ingredient, payload.base_ingredient_id)  # Load the selected base record.
        if base is None or base.owner_user_id is not None or base.archived_at is not None:  # Permit only active shared ingredients as bases.
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="L’ingrédient de base doit appartenir au catalogue partagé.")  # Keep personal catalogues isolated.
    item = Item(name=payload.name.strip(), image_url=payload.image_url, default_unit_id=unit.id)  # Store shared display fields in the Item table.
    db.add(item)  # Stage the shared Item row.
    db.flush()  # Allocate its identifier before creating the Ingredient row.
    row = Ingredient(item_id=item.id, ingredient_category_id=category.id, owner_user_id=owner_user_id, base_ingredient_id=base.item_id if base else None, brand=payload.brand, barcode=payload.barcode, calories=payload.calories, proteins=payload.proteins, carbs=payload.carbs, fats=payload.fats, fiber=payload.fiber, data_source="manual")  # Keep ownership server-controlled and nutrition nullable.
    db.add(row)  # Stage the food-specific record.
    try:  # Save the linked Item and Ingredient atomically.
        db.commit()  # Persist both records together.
    except IntegrityError as error:  # Handle duplicate data and concurrently invalid references.
        db.rollback()  # Restore the session after a failed transaction.
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Un ingrédient identique ou une référence invalide empêche l’enregistrement.") from error  # Return a stable conflict message.
    loaded = db.scalar(ingredient_query().where(Ingredient.item_id == row.item_id))  # Reload relationships for the response.
    return ingredient_response(loaded)  # Return the saved visible ingredient.


# List active shared ingredients and active ingredients owned by the current user.
@router.get("/ingredients", response_model=list[IngredientSummary])  # Expose shared ingredients publicly and add the current user's private records.
def list_ingredients(q: str | None = Query(default=None, max_length=100), category_id: int | None = Query(default=None, gt=0), include_archived: bool = False, offset: int = Query(default=0, ge=0), limit: int = Query(default=200, ge=1, le=200), db: Session = Depends(get_db), user: User | None = Depends(get_optional_current_user)) -> list[IngredientSummary]:  # Search only records visible to this visitor.
    visibility = Ingredient.owner_user_id.is_(None) if user is None else or_(Ingredient.owner_user_id.is_(None), Ingredient.owner_user_id == user.id)  # Keep private ingredients scoped to their owner.
    statement = ingredient_query().join(Item, Ingredient.item_id == Item.id).where(visibility)  # Build the shared-or-owned query.
    if not include_archived or user is None:  # Never expose archived records to anonymous visitors.
        statement = statement.where(Ingredient.archived_at.is_(None))  # Hide inactive ingredients from normal searches.
    if q and q.strip():  # Add name search only when a non-empty query is present.
        statement = statement.where(Item.name.ilike(f"%{q.strip()}%"))  # Search ingredient names case-insensitively.
    if category_id is not None:  # Add optional category filtering.
        statement = statement.where(Ingredient.ingredient_category_id == category_id)  # Restrict results to the requested category.
    search_term = q.strip().lower() if q else ""  # Normalize the search for exact and prefix ranking.
    priority = case((func.lower(Item.name) == search_term, 0), (func.lower(Item.name).like(search_term + "%"), 1), else_=2)  # Prefer exact names, then names starting with the query.
    rows = db.scalars(statement.order_by(priority, Item.name).offset(offset).limit(limit)).unique().all()  # Page through the full catalogue with best matches first.
    return [ingredient_response(row) for row in rows]  # Return visible ingredients with effective nutrition values.


# List visible ingredients for an optional signed-in account without exposing another user's private rows.
@router.get("/ingredients/search", response_model=list[IngredientSummary])  # Expose the current ingredient catalogue.
def search_ingredients(q: str | None = Query(default=None, max_length=100), category_id: int | None = Query(default=None, gt=0), offset: int = Query(default=0, ge=0), limit: int = Query(default=200, ge=1, le=200), db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> list[IngredientSummary]:  # Search shared and owned ingredients.
    statement = ingredient_query().join(Item, Ingredient.item_id == Item.id).where(or_(Ingredient.owner_user_id.is_(None), Ingredient.owner_user_id == user.id), Ingredient.archived_at.is_(None))  # Restrict results to shared and current-user ingredients.
    if q and q.strip():  # Add text matching only for non-empty search input.
        statement = statement.where(Item.name.ilike(f"%{q.strip()}%"))  # Search ingredient names case-insensitively.
    if category_id is not None:  # Add category filtering only when requested.
        statement = statement.where(Ingredient.ingredient_category_id == category_id)  # Restrict results to the selected category.
    search_term = q.strip().lower() if q else ""  # Normalize the search for exact and prefix ranking.
    priority = case((func.lower(Item.name) == search_term, 0), (func.lower(Item.name).like(search_term + "%"), 1), else_=2)  # Prefer exact names, then names starting with the query.
    rows = db.scalars(statement.order_by(priority, Item.name).offset(offset).limit(limit)).unique().all()  # Return best matching results before broader contains matches.
    return [ingredient_response(row) for row in rows]  # Return only the caller's visible ingredients.


# Read one shared ingredient or an ingredient owned by the current user.
@router.get("/ingredients/{ingredient_id}", response_model=IngredientSummary)  # Protect other users' private ingredients.
def get_ingredient(ingredient_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> IngredientSummary:  # Load one visible ingredient.
    row = db.scalar(ingredient_query().where(Ingredient.item_id == ingredient_id, or_(Ingredient.owner_user_id.is_(None), Ingredient.owner_user_id == user.id)))  # Apply the same shared-or-owned visibility rule.
    if row is None:  # Hide private records from other accounts.
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ingrédient introuvable.")  # Return a consistent not-found response.
    return ingredient_response(row)  # Return the effective nutrition values.


# Create a private ingredient owned by the signed-in account.
@router.post("/ingredients", response_model=IngredientSummary, status_code=status.HTTP_201_CREATED)  # Require a valid user session.
def add_personal_ingredient(payload: IngredientCreate, db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> IngredientSummary:  # Save a private ingredient or brand variant.
    return create_ingredient(payload, db, user.id)  # Derive ownership from the session, never from request data.


# Edit a personal ingredient owned by the signed-in account.
@router.patch("/ingredients/{ingredient_id}", response_model=IngredientSummary)  # Restrict changes to the owner.
def update_personal_ingredient(ingredient_id: int, payload: IngredientUpdate, db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> IngredientSummary:  # Apply only submitted fields.
    row = db.scalar(ingredient_query().where(Ingredient.item_id == ingredient_id, Ingredient.owner_user_id == user.id))  # Find an ingredient owned by this account.
    if row is None:  # Reject shared ingredients and another user's records.
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ingrédient personnel introuvable.")  # Avoid revealing ownership details.
    values = payload.model_dump(exclude_unset=True)  # Keep omitted fields unchanged.
    for field, value in values.items():  # Apply only editable user-provided fields.
        if field == "name":  # Store display names on the parent Item row.
            row.item.name = value.strip()  # Normalize the updated ingredient name.
        elif field == "default_unit_id":  # Validate a newly selected default unit.
            if db.get(Unit, value) is None:  # Reject invalid units before assigning a foreign key.
                raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Unité introuvable.")  # Explain the invalid unit.
            row.item.default_unit_id = value  # Save the selected unit.
        elif field == "ingredient_category_id":  # Validate a newly selected ingredient category.
            if db.get(IngredientCategory, value) is None:  # Reject invalid categories before assignment.
                raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Catégorie introuvable.")  # Explain the invalid category.
            setattr(row, field, value)  # Save the selected category.
        else:  # Apply brand, image, barcode, or nutrition fields.
            setattr(row, field, value)  # Update the selected ingredient property.
    refresh_dependent_recipe_nutrition(db, ingredient_id)  # Recalculate recipes that use this personal ingredient.
    db.commit()  # Persist the personal edit.
    refreshed = db.scalar(ingredient_query().where(Ingredient.item_id == row.item_id))  # Reload effective nutrition and display relations.
    return ingredient_response(refreshed)  # Return the updated ingredient.


# Archive an ingredient without breaking recipes that already reference it.
@router.post("/ingredients/{ingredient_id}/archive", response_model=IngredientSummary)  # Restrict archiving to the owner.
def archive_personal_ingredient(ingredient_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> IngredientSummary:  # Hide the ingredient from future recipe forms.
    row = db.scalar(ingredient_query().where(Ingredient.item_id == ingredient_id, Ingredient.owner_user_id == user.id))  # Find an ingredient owned by this account.
    if row is None:  # Reject shared and other-user ingredients.
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ingrédient personnel introuvable.")  # Avoid revealing ownership details.
    row.archived_at = datetime.now(timezone.utc)  # Mark the ingredient inactive while preserving history.
    db.commit()  # Persist the archive timestamp.
    return ingredient_response(row)  # Return the archived state.


# Delete an unused personal ingredient and its linked Item.
@router.delete("/ingredients/{ingredient_id}", status_code=status.HTTP_204_NO_CONTENT)  # Restrict deletion to the owner.
def delete_personal_ingredient(ingredient_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> None:  # Preserve ingredients that remain in recipes.
    row = db.scalar(ingredient_query().where(Ingredient.item_id == ingredient_id, Ingredient.owner_user_id == user.id))  # Find an ingredient owned by this account.
    if row is None:  # Reject shared and other-user ingredients.
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ingrédient personnel introuvable.")  # Avoid revealing ownership details.
    used = db.scalar(select(RecipeIngredient.id).where(RecipeIngredient.ingredient_id == row.item_id).limit(1))  # Check for recipe references before deletion.
    if used is not None:  # Keep recipe history stable.
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Cet ingrédient est utilisé dans une recette. Archive-le plutôt.")  # Offer the safe archive action.
    item_id = row.item_id  # Save the parent key before deleting the ingredient extension.
    db.delete(row)  # Remove the ingredient-specific row first.
    db.flush()  # Ensure the foreign-key dependency is removed before its Item.
    item = db.get(Item, item_id)  # Load the general Item row.
    if item is not None:  # Protect against incomplete legacy data.
        db.delete(item)  # Remove the unused general item record.
    try:  # Persist deletion while handling variants or other references.
        db.commit()  # Apply both deletions atomically.
    except IntegrityError as error:  # A base ingredient may still have personal variants.
        db.rollback()  # Restore the session after a blocked deletion.
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Cet ingrédient sert de base à une variante ou est encore utilisé; archive-le.") from error  # Keep referenced data intact.


# Create an admin-managed shared ingredient in the public base catalogue.
@router.post("/admin/ingredients", response_model=IngredientSummary, status_code=status.HTTP_201_CREATED)  # Restrict shared catalogue changes to admins.
def add_shared_ingredient(payload: IngredientCreate, db: Session = Depends(get_db), admin: User = Depends(get_current_admin)) -> IngredientSummary:  # Save a shared ingredient for all users.
    if payload.base_ingredient_id is not None:  # Keep shared base records independent from personal variants.
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Un ingrédient partagé ne peut pas être une variante.")  # Preserve the one-way catalogue structure.
    return create_ingredient(payload, db, None)  # Leave owner_user_id empty for shared catalogue visibility.


# Let administrators correct names, units, categories, and nutrition in the shared catalogue.
@router.patch("/admin/ingredients/{ingredient_id}", response_model=IngredientSummary)  # Restrict shared ingredient edits to administrators.
def update_shared_ingredient(ingredient_id: int, payload: IngredientUpdate, db: Session = Depends(get_db), admin: User = Depends(get_current_admin)) -> IngredientSummary:  # Apply the supplied shared ingredient fields.
    row = db.scalar(ingredient_query().where(Ingredient.item_id == ingredient_id, Ingredient.owner_user_id.is_(None)))  # Load only a shared ingredient.
    if row is None:  # Reject private or unknown ingredient identifiers.
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ingrédient partagé introuvable.")  # Keep personal records protected.
    for field, value in payload.model_dump(exclude_unset=True).items():  # Update only fields the admin changed.
        if field in {"name", "default_unit_id", "ingredient_category_id"} and value is None:  # Keep required fields non-null.
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Le nom, la catégorie et l’unité sont obligatoires.")  # Explain the required data.
        if field == "name":  # Store names on the linked general item.
            row.item.name = value.strip()  # Save a clean display name.
        elif field == "image_url":  # Store images on the linked general item.
            row.item.image_url = value  # Save the optional image URL.
        elif field == "default_unit_id":  # Validate the selected default measurement unit.
            if db.get(Unit, value) is None:  # Reject a missing unit before assigning it.
                raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Unité introuvable.")  # Explain the invalid reference.
            row.item.default_unit_id = value  # Save the valid unit on Item.
        elif field == "ingredient_category_id":  # Validate the selected food category.
            if db.get(IngredientCategory, value) is None:  # Reject a missing category before assigning it.
                raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Catégorie introuvable.")  # Explain the invalid reference.
            row.ingredient_category_id = value  # Save the valid category on Ingredient.
        else:  # Save nutrition and optional branded-food metadata.
            setattr(row, field, value)  # Apply the validated field value.
    refresh_dependent_recipe_nutrition(db, ingredient_id)  # Recalculate recipes that use this shared ingredient or its variants.
    db.commit()  # Persist the administrator's corrections.
    refreshed = db.scalar(ingredient_query().where(Ingredient.item_id == ingredient_id))  # Reload linked labels and effective nutrition.
    return ingredient_response(refreshed)  # Return the updated shared ingredient.


