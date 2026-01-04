import os

from alembic import command
from alembic.config import Config
from dotenv import load_dotenv
from pathlib import Path

from fastapi import Depends, FastAPI
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text
from sqlalchemy.orm import Session

from fastapi.middleware.cors import CORSMiddleware

from app.core.ratelimit import RATE_LIMIT_RULES, RateLimiter
from app.api.routes.admin import assets as admin_assets, news as admin_news
from app.api.routes import auth
from app.api.routes.user import announcements as user_announcements, news as user_news
from app.core.database import get_db
from app.core.errors import register_exception_handlers
from app.core.seed import seed_data

# Load environment variables từ .env file
load_dotenv()

app = FastAPI(title="Preschool Site API", version="0.1.0")
register_exception_handlers(app)
rate_limiter = RateLimiter(RATE_LIMIT_RULES)

frontend_origins = os.getenv("FRONTEND_ORIGINS", "*")
allow_origins = ["*"]
if frontend_origins and frontend_origins.strip() != "*":
    allow_origins = [o.strip() for o in frontend_origins.split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allow_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def log_requests(request, call_next):
    # Rate limit đầu vào theo rule
    rate_limit_response = rate_limiter.check(request)
    if rate_limit_response:
        return rate_limit_response

    response = await call_next(request)
    print(f"{request.method} {request.url.path} -> {response.status_code}")
    return response


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
        print("✅ Application startup complete")
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
# Auth routes
app.include_router(auth.router)
# Public/User API routes
app.include_router(user_news.router)
app.include_router(user_announcements.router)

# Mount static files để serve uploads
# Dùng cùng UPLOAD_DIR với asset_service
from app.services.asset_service import UPLOAD_DIR
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=str(UPLOAD_DIR)), name="uploads")
