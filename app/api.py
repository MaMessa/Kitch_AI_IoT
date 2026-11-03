import os  # Read the Open Food Facts app identification setting.

from fastapi import Depends, FastAPI, HTTPException, Query  # Import route creation, validation, and response errors.
from fastapi.staticfiles import StaticFiles  # Serve uploaded development cover images.
from fastapi.middleware.cors import CORSMiddleware  # Let the separate Vite frontend call the API from its local origin.
from sqlalchemy import func, select, text  # Build safe database queries and count filtered rows.
from sqlalchemy.orm import Session, selectinload  # Type request sessions and load related categories efficiently.

from app.database import get_db  # Supplies a short-lived database session per request.
from app.integrations.open_food_facts import OpenFoodFactsUnavailable, get_product_by_barcode  # Connect to the external branded-food catalogue.
from app.models import Recipe, RecipeCategory  # Query public recipes and their category links.
from app.schemas import PublicRecipePage, PublicRecipeSummary, RecipeCategorySummary  # Validate the public recipe response format.
from app.auth import router as auth_router  # Register email/password authentication routes.
from app.reference_data import router as reference_router  # Register public reference reads and admin edits.
from app.ingredients import router as ingredients_router  # Register shared and personal ingredient routes.
from app.recipes import router as recipes_router  # Register recipe management and nutrition routes.
from app.media import MEDIA_DIR, router as media_router  # Register private uploads and their public image files.

DEFAULT_CORS_ORIGINS = "http://localhost:5173,http://127.0.0.1:5173"  # Allow the local Vite development origins by default.
cors_origins = [origin.strip() for origin in os.getenv("CORS_ORIGINS", DEFAULT_CORS_ORIGINS).split(",") if origin.strip()]  # Allow deployment origins to be configured without code changes.
app = FastAPI(title="KitchAI API", version="0.1.0")  # Create the versioned application metadata shown in OpenAPI docs.
app.add_middleware(CORSMiddleware, allow_origins=cors_origins, allow_credentials=True, allow_methods=["*"], allow_headers=["*"])  # Enable browser requests from the configured web frontend.
app.include_router(auth_router, prefix="/api/v1/auth", tags=["authentication"])  # Mount account routes under the versioned API.
app.include_router(reference_router, prefix="/api/v1", tags=["reference-data"])  # Mount category, unit, and conversion routes.
app.include_router(ingredients_router, prefix="/api/v1", tags=["ingredients"])  # Mount shared and personal ingredient routes.
app.include_router(recipes_router, prefix="/api/v1", tags=["recipes"])  # Mount recipe management and nutrition routes.
app.include_router(media_router, prefix="/api/v1", tags=["media"])  # Mount authenticated recipe cover uploads.
app.mount("/api/v1/media/files", StaticFiles(directory=MEDIA_DIR), name="recipe-covers")  # Serve uploaded image bytes from the same API origin.


@app.get("/health")  # Registers a route that checks whether the API process responds.
def health_check() -> dict[str, str]:  # Defines the response returned by the process check.
    return {"status": "ok"}  # Confirms that the API process is responding.


@app.get("/health/db")  # Registers a route that also checks PostgreSQL connectivity.
def database_health_check(db: Session = Depends(get_db)) -> dict[str, str]:  # Requests a session that FastAPI closes after the response.
    db.execute(text("SELECT 1"))  # Sends a harmless query to verify the database connection.
    return {"status": "ok", "database": "connected"}  # Reports success without exposing connection details.


@app.get("/api/v1/external/open-food-facts/{barcode}")  # Exposes a single-product lookup for ingredient entry.
def open_food_facts_lookup(barcode: str) -> dict[str, object]:  # Return a normalized product for the user to review before saving.
    if not barcode.isdigit() or not 8 <= len(barcode) <= 14:  # Reject malformed GTIN-like values before making a network call.
        raise HTTPException(status_code=422, detail="Le code-barres doit contenir de 8 à 14 chiffres.")  # Explain the expected input format.
    user_agent = os.getenv("OPENFOODFACTS_USER_AGENT", "KitchAI/0.1 (maxime.messaoui@gmail.com)")  # Identify KitchAI as requested by the provider.
    try:  # Translate provider-level outcomes into clear HTTP responses.
        product = get_product_by_barcode(barcode, user_agent)  # Query only the product needed for this ingredient form.
    except OpenFoodFactsUnavailable as error:  # Handle a provider timeout or service error.
        raise HTTPException(status_code=503, detail="Open Food Facts est temporairement indisponible.") from error  # Keep upstream internals out of the public response.
    if product is None:  # Handle a barcode that has no matching Open Food Facts record.
        raise HTTPException(status_code=404, detail="Aucun produit trouvé pour ce code-barres.")  # Let the user continue with manual entry.
    return product  # Return the source data for user review, without writing it to the database automatically.



