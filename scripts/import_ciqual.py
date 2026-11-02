"""Import the Ciqual 2025 Excel food table into KitchAI's ingredient catalogue."""

import argparse  # Read paths and database catalogue IDs from the command line.
from decimal import Decimal, InvalidOperation  # Store imported nutrition values precisely.
from pathlib import Path  # Validate the path to the downloaded workbook.
import sys  # Return a clear non-zero exit status for invalid input.
import re  # Normalize multi-line Excel headers into comparable text.
import unicodedata  # Ignore accents when matching French header names.

from openpyxl import load_workbook  # Read the official .xlsx workbook without pandas.
from sqlalchemy import select  # Find existing provider records for idempotent imports.

from app.database import SessionLocal  # Reuse the application's configured PostgreSQL connection.
from app.models import Ingredient, IngredientCategory, Item, Unit  # Import into the existing catalogue models.


CIQUAL_VERSION = "2025"  # Record the edition used to load the catalogue.
CIQUAL_SOURCE_URL = "https://ciqual.anses.fr/"  # Keep the official source URL for attribution.
CIQUAL_COLUMN_PATTERNS = {  # Match semantic header parts despite line breaks and punctuation in Excel.
    "alim_code": "alim code",  # Use the stable food code as the import identity.
    "alim_nom_fr": "alim nom fr",  # Use the French food label for the Item name.
    "calories": "energie reglement ue n 1169 2011 kcal 100 g",  # Select energy in kcal using the EU regulation method.
    "proteins": "proteines n x 6 25 g 100 g",  # Select the label protein value with the 6.25 conversion factor.
    "carbs": "glucides g 100 g",  # Select available carbohydrates, excluding fibre.
    "fats": "lipides g 100 g",  # Select total fat per 100 g.
    "fiber": "fibres alimentaires g 100 g",  # Keep fibre in its own nutrition field.
}  # Finish the source-header matching rules.


def normalize_header(value: object) -> str:  # Make headers comparable across line wrapping, accents, and punctuation.
    plain_text = "".join(character for character in unicodedata.normalize("NFKD", str(value)) if not unicodedata.combining(character))  # Strip accents while preserving readable letters.
    return " ".join(re.findall(r"[a-z0-9]+", plain_text.casefold()))  # Keep lowercase words and numbers separated by one space.


def parse_nutrient(value: object) -> Decimal | None:  # Convert only exact numeric values and leave censored or missing values unknown.
    if value is None or isinstance(value, bool):  # Missing cells must not become zero.
        return None  # Preserve missing data as SQL NULL.
    text = str(value).strip().replace(",", ".")  # Accept French decimal separators as well as numeric Excel cells.
    if not text or text.casefold() in {"-", "traces"} or text.startswith("<"):  # Censored or trace values are not exact numbers.
        return None  # Avoid treating a detection limit or trace as an exact value.
    try:  # Parse ordinary decimal strings.
        return Decimal(text)  # Return a precise numeric value for PostgreSQL Numeric.
    except InvalidOperation:  # Handle unexpected labels without stopping the full import.
        return None  # Preserve unparseable data as unavailable.


def main() -> int:  # Run the explicit, repeatable Ciqual import command.
    parser = argparse.ArgumentParser(description="Import the official Ciqual 2025 .xlsx table.")  # Explain the command's purpose.
    parser.add_argument("--file", required=True, type=Path, help="Path to the downloaded Ciqual 2025 French .xlsx file.")  # Require the user to download the file from ANSES.
    parser.add_argument("--ingredient-category-id", required=True, type=int, help="Existing KitchAI ingredient category ID for imported foods.")  # Respect the admin-managed category catalogue.
    parser.add_argument("--gram-unit-id", required=True, type=int, help="Existing KitchAI unit ID whose symbol is g.")  # Require the admin to configure gram as an ingredient's default unit.
    args = parser.parse_args()  # Read command-line arguments.
    if not args.file.is_file():  # Validate the workbook path before connecting to PostgreSQL.
        parser.error(f"Workbook not found: {args.file}")  # Explain the missing file with a standard CLI error.
    workbook = load_workbook(args.file, read_only=True, data_only=True)  # Read cached cell values without modifying the source workbook.
    sheet = next((workbook[name] for name in workbook.sheetnames if "composition" in name.casefold()), workbook[workbook.sheetnames[0]])  # Find the composition worksheet by name.
    rows = sheet.iter_rows(values_only=True)  # Stream workbook rows without loading the full sheet into memory.
    headers = [str(value).strip() if value is not None else "" for value in next(rows)]  # Use the first sheet row as field names.
    normalized_headers = [normalize_header(header) for header in headers]  # Normalize the wrapped and accented column titles.
    positions = {}  # Store the source position selected for each KitchAI field.
    for field, pattern in CIQUAL_COLUMN_PATTERNS.items():  # Match every required source column by its normalized meaning.
        matches = [index for index, header in enumerate(normalized_headers) if pattern in header]  # Find source headers containing this pattern.
        if len(matches) != 1:  # Stop if a column is missing or matches multiple source fields.
            parser.error(f"Expected exactly one Ciqual column matching '{pattern}', found {len(matches)}.")  # Report the mismatched field clearly.
        positions[field] = matches[0]  # Save the unique matching source index.
    imported = 0  # Count rows inserted or updated.
    skipped = 0  # Count blank rows that were ignored.
    with SessionLocal.begin() as session:  # Commit all rows together or roll back the entire import on failure.
        category = session.get(IngredientCategory, args.ingredient_category_id)  # Load the category selected by the administrator.
        gram_unit = session.get(Unit, args.gram_unit_id)  # Load the default gram unit selected by the administrator.
        if category is None:  # Avoid attaching records to a nonexistent category.
            parser.error("The ingredient category ID does not exist.")  # Ask the admin to create or select a real category.
        if gram_unit is None or gram_unit.symbol.casefold() != "g":  # Ensure all imported food quantities use mass in grams.
            parser.error("The unit ID must exist and have the symbol 'g'.")  # Reject volume units because Ciqual values are per 100 g.
        for row in rows:  # Process each food record once.
            code = row[positions["alim_code"]] if positions["alim_code"] < len(row) else None  # Read the stable Ciqual food identifier.
            name = row[positions["alim_nom_fr"]] if positions["alim_nom_fr"] < len(row) else None  # Read the French food label.
            if code is None or not name:  # Ignore formatting rows and empty spreadsheet rows.
                skipped += 1  # Track ignored rows for the final report.
                continue  # Move to the next spreadsheet row.
            source_id = str(int(code)) if isinstance(code, (int, float)) else str(code).strip()  # Normalize Excel numeric IDs without a trailing decimal.
            ingredient = session.scalar(select(Ingredient).where(Ingredient.data_source == "ciqual", Ingredient.source_id == source_id))  # Make the import safe to repeat.
            values = {  # Map the five current KitchAI nutrition fields to documented Ciqual columns.
                "calories": parse_nutrient(row[positions["calories"]]),  # Store kcal per 100 g.
                "proteins": parse_nutrient(row[positions["proteins"]]),  # Store protein grams per 100 g.
                "carbs": parse_nutrient(row[positions["carbs"]]),  # Store carbohydrate grams per 100 g.
                "fats": parse_nutrient(row[positions["fats"]]),  # Store fat grams per 100 g.
                "fiber": parse_nutrient(row[positions["fiber"]]),  # Store fibre grams per 100 g.
            }  # Finish mapping this food's nutrition fields.
            if ingredient is None:  # Create the shared Item and Ingredient extension for a new Ciqual food.
                item = Item(name=str(name).strip(), default_unit_id=gram_unit.id)  # Give the food a gram default for nutrition calculations.
                session.add(item)  # Add the base item first.
                session.flush()  # Obtain the generated Item ID before creating its Ingredient extension.
                ingredient = Ingredient(item_id=item.id, ingredient_category_id=category.id, data_source="ciqual", source_id=source_id)  # Create the source-linked food record.
                item.ingredient = ingredient  # Connect the one-to-one ORM relationship.
                session.add(ingredient)  # Add the nutrition row to the transaction.
            else:  # Refresh values for a Ciqual record loaded in an earlier import.
                item = ingredient.item  # Reuse the base Item row and preserve its stable ID.
                item.name = str(name).strip()  # Update the display label from this edition.
                item.default_unit_id = gram_unit.id  # Keep the imported food's mass unit explicit.
                ingredient.ingredient_category_id = category.id  # Apply the administrator-selected catalogue category.
            for field, value in values.items():  # Apply each mapped nutrient value.
                setattr(ingredient, field, value)  # NULL stays NULL when Ciqual has no exact value.
            ingredient.source_version = CIQUAL_VERSION  # Store the dataset edition alongside its values.
            ingredient.source_url = CIQUAL_SOURCE_URL  # Preserve the source attribution link.
            imported += 1  # Count this successfully processed Ciqual record.
    workbook.close()  # Release the source workbook file handle.
    print(f"Ciqual {CIQUAL_VERSION}: {imported} foods imported or updated; {skipped} empty rows skipped.")  # Summarize the completed transaction.
    return 0  # Signal successful completion to the shell.


if __name__ == "__main__":  # Run the importer only when invoked as a command-line script.
    sys.exit(main())  # Return the import result as the process exit code.
