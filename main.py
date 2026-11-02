from app.database import engine  # Reuse the configured SQLAlchemy engine.
from app.models import Base, Category  # Import Base and the model to insert.
from sqlalchemy.orm import Session  # Import the unit-of-work used for database changes.

def main():
    
    Base.metadata.create_all(engine) # Create any tables that do not exist yet

    # Build a Python object;  line alone does not write to PostgreSQL.
    category = Category(name="Desserts", icon_slug=None)

    # Open a session and close it automatically when this block ends.
    with Session(engine) as session:
        # Add the category to the session so SQLAlchemy tracks it for insertion.
        session.add(category)

        # Send the pending INSERT to PostgreSQL and commit the transaction.
        session.commit()

    # Confirm that the example transaction completed.
    print("Category added successfully.")


if __name__ == "__main__":
    # Run main() only when this file is launched directly.
    main()
    
