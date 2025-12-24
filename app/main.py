import os
from fastapi import Depends, FastAPI
from sqlalchemy import text
from sqlalchemy.orm import Session
from alembic.config import Config
from alembic import command
from dotenv import load_dotenv

from app.core.database import SessionLocal
from app.core.seed import seed_data

# Load environment variables từ .env file
load_dotenv()

app = FastAPI(title="Preschool Site API", version="0.1.0")


@app.on_event("startup")
async def startup_event():
    """Tự động chạy migrations và seed dữ liệu khi app khởi động."""
    try:
        # Đảm bảo DATABASE_URL được set
        database_url = os.getenv("DATABASE_URL")
        if not database_url:
            print("⚠️  Warning: DATABASE_URL not set, using default: postgresql+psycopg2://app:app@localhost:5432/preschool")
            database_url = "postgresql+psycopg2://app:app@localhost:5432/preschool"
        
        # Chạy migrations tự động
        alembic_cfg = Config("alembic.ini")
        # Set DATABASE_URL vào alembic config
        alembic_cfg.set_main_option("sqlalchemy.url", database_url)
        command.upgrade(alembic_cfg, "head")
        print("✅ Database migrations completed")
        
        # Seed dữ liệu ban đầu
        seed_data()
    except Exception as e:
        print(f"⚠️  Warning: Could not run migrations or seed data: {e}")
        print("   Make sure database is running and DATABASE_URL is set correctly")
        print(f"   Current DATABASE_URL: {os.getenv('DATABASE_URL', 'Not set (using default)')}")


def get_db() -> Session:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@app.get("/health")
def health(db: Session = Depends(get_db)) -> dict:
    # Basic DB connectivity check
    db.execute(text("SELECT 1"))
    return {"status": "ok"}
