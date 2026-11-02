# Import nutrition data

## Ciqual

Download the French Ciqual 2025 Excel workbook from the [ANSES Ciqual page](https://ciqual.anses.fr/cms/fr/node/19). The workbook itself is not committed to the repository.

Before importing, create an ingredient category for the shared reference foods and a unit whose symbol is g in the admin configuration. Then note their database IDs and run:

    REM Import or refresh the Ciqual records using the selected category and gram unit.
    uv run --locked python -m scripts.import_ciqual --file "C:\path\to\Table Ciqual 2025_FR_2025_11_03.xlsx" --ingredient-category-id 1 --gram-unit-id 1

The import updates existing Ciqual records by source code, so rerunning it does not create duplicates. Unknown, trace, and below-detection-limit nutrition values remain empty.

## Open Food Facts

The API route GET /api/v1/external/open-food-facts/{barcode} looks up one branded product. It returns the product name, brand, available nutrient values per 100 g, source link, attribution, and a data-quality notice. The result is not saved automatically; the user should review it before creating a personal ingredient.

Set OPENFOODFACTS_USER_AGENT in .env to a descriptive value such as KitchAI/0.1 (contact@example.com). Use the correct contact address before calling the external API.
