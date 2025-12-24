import os

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models import Base


DATABASE_URL = os.getenv(
    "DATABASE_URL", "postgresql+psycopg2://app:app@localhost:5432/preschool"
)

engine = create_engine(DATABASE_URL, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


def init_db() -> None:
    """Create tables based on SQLAlchemy models (mainly for local quickstart)."""
    Base.metadata.create_all(bind=engine)
