from sqlalchemy.orm import DeclarativeBase

# Models inherit from this base so SQLAlchemy can collect their table definitions in Base.metadata.
class Base(DeclarativeBase):
    pass
