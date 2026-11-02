import os  # Read the Open Food Facts app identification setting.

from fastapi import Depends, FastAPI, HTTPException  # Imports API creation, dependency injection, and response errors.
from sqlalchemy import text  # Provides a small SQL statement for database readiness.
from sqlalchemy.orm import Session  # Types the SQLAlchemy session used by the endpoint.

from app.database import get_db  # Supplies a short-lived database session per request.
from app.integrations.open_food_facts import OpenFoodFactsUnavailable, get_product_by_barcode  # Connect to the external branded-food catalogue.

app = FastAPI(title="KitchAI API")  # Creates the FastAPI application instance.


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
