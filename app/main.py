from fastapi import Depends, FastAPI
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.database import SessionLocal

app = FastAPI(title="Preschool Site API", version="0.1.0")


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
