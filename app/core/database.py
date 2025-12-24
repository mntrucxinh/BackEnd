import os

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv

from app.models import Base


# Load environment variables early so DATABASE_URL từ .env luôn được dùng
load_dotenv()

DATABASE_URL = os.getenv(
    "DATABASE_URL", "postgresql+psycopg2://app:app@localhost:5433/preschool"
)

engine = create_engine(DATABASE_URL, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


def init_db() -> None:
    """Create tables based on SQLAlchemy models (mainly for local quickstart)."""
    Base.metadata.create_all(bind=engine)
