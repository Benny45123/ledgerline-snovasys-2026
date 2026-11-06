"""
How this works / why it is safe:
This module establishes the SQLAlchemy Declarative Base.
It standardizes table naming and metadata configuration across all models.
No database connections or business logic are executed at import time.
"""

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass
