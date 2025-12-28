import os

from alembic import command
from alembic.config import Config
from dotenv import load_dotenv
from fastapi import Depends, FastAPI
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.routes.admin import assets as admin_assets, news as admin_news
from app.core.database import get_db
from app.core.errors import register_exception_handlers
from app.core.seed import seed_data

# Load environment variables từ .env file
load_dotenv()

app = FastAPI(title="Preschool Site API", version="0.1.0")
register_exception_handlers(app)


@app.on_event("startup")
async def startup_event():
    """Tự động chạy migrations và seed dữ liệu khi app khởi động."""
    try:
        # Đảm bảo DATABASE_URL được set
        database_url = os.getenv("DATABASE_URL")
        if not database_url:
            print(
                "⚠️  Warning: DATABASE_URL not set, using default: "
                "postgresql+psycopg2://app:app@localhost:5432/preschool"
            )
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
        print(
            f"   Current DATABASE_URL: "
            f"{os.getenv('DATABASE_URL', 'Not set (using default)')}"
        )


@app.get("/health")
def health(db: Session = Depends(get_db)) -> dict:
    # Basic DB connectivity check
    db.execute(text("SELECT 1"))
    return {"status": "ok"}


# Admin API routes
app.include_router(admin_news.router)
app.include_router(admin_assets.router)
