"""Read a single branded food product from the Open Food Facts API."""

import json  # Decode the JSON payload returned by the provider.
from decimal import Decimal, InvalidOperation  # Preserve nutrition values without binary floating-point rounding.
from urllib.error import HTTPError, URLError  # Convert network failures into a provider-specific error.
from urllib.request import Request, urlopen  # Make a lightweight standard-library HTTP request.


OPEN_FOOD_FACTS_BASE_URL = "https://world.openfoodfacts.org/api/v3.6/product"  # Use the current documented product API.
OPEN_FOOD_FACTS_SOURCE_URL = "https://world.openfoodfacts.org/"  # Provide the attribution link required for reused data.


class OpenFoodFactsUnavailable(Exception):  # Represent timeouts, HTTP failures, and invalid provider responses.
    pass  # Keep API error translation in the FastAPI route.


def _decimal_or_none(value: object) -> Decimal | None:  # Convert a provider number only when it is present and valid.
    if value is None or isinstance(value, bool):  # Treat missing and boolean values as unavailable nutrition.
        return None  # Do not invent a numeric value for missing information.
    try:  # Handle numeric strings and JSON numbers through Decimal.
        return Decimal(str(value))  # Keep the original decimal precision as closely as possible.
    except (InvalidOperation, ValueError):  # Ignore malformed community-entered values safely.
        return None  # Report malformed data as unavailable rather than as zero.


def get_product_by_barcode(barcode: str, user_agent: str) -> dict[str, object] | None:  # Fetch one product and return a compact KitchAI-shaped result.
    url = f"{OPEN_FOOD_FACTS_BASE_URL}/{barcode}.json?fields=code,product_name,brands,nutriments,last_modified_t"  # Request only fields this integration uses.
    request = Request(url, headers={"User-Agent": user_agent, "Accept": "application/json"})  # Identify KitchAI as required by the API provider.
    try:  # Bound the network operation and normalize expected transport failures.
        with urlopen(request, timeout=8) as response:  # Open the remote response with a short timeout.
            payload = json.loads(response.read().decode("utf-8"))  # Parse the provider's JSON document.
    except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as error:  # Catch HTTP, connection, timeout, and malformed-JSON errors.
        raise OpenFoodFactsUnavailable("Open Food Facts could not be reached.") from error  # Avoid exposing upstream details to clients.
    if payload.get("status") != 1:  # The API uses status 0 when a barcode is not in its catalogue.
        return None  # Let the route return a clean not-found response.
    product = payload.get("product") or {}  # Tolerate a successful response with an empty product object.
    nutrients = product.get("nutriments") or {}  # The community data may have no nutrition section.
    return {  # Return only the product fields used by ingredient creation.
        "barcode": str(product.get("code") or barcode),  # Preserve the provider's normalized product code.
        "name": product.get("product_name") or None,  # Product names can be blank in contributed records.
        "brand": product.get("brands") or None,  # Preserve brands as supplied without parsing multi-brand strings.
        "nutrition_per_100g": {  # Match the units already used by KitchAI's Ingredient model.
            "calories_kcal": _decimal_or_none(nutrients.get("energy-kcal_100g")),  # Read kcal instead of converting kJ without a source rule.
            "proteins_g": _decimal_or_none(nutrients.get("proteins_100g")),  # Read protein grams per 100 g.
            "carbohydrates_g": _decimal_or_none(nutrients.get("carbohydrates_100g")),  # Read carbohydrate grams per 100 g.
            "fats_g": _decimal_or_none(nutrients.get("fat_100g")),  # Read fat grams per 100 g.
            "fiber_g": _decimal_or_none(nutrients.get("fiber_100g")),  # Read fibre grams per 100 g when reported.
        },  # Close the normalized nutrition section.
        "source": "Open Food Facts",  # Identify the database supplying this record.
        "source_url": f"{OPEN_FOOD_FACTS_SOURCE_URL}product/{barcode}",  # Link users to the source product record.
        "source_last_modified": product.get("last_modified_t"),  # Let clients see the source record's update time.
        "attribution": "Données : Open Food Facts, sous licence ODbL.",  # Display the required data attribution.
        "notice": "Les données sont contributives et peuvent être incomplètes ou inexactes.",  # Communicate the provider's published quality limitation.
    }  # Finish the compact result.
