 docker compose up -d 
 alembic upgrade head
 .\.venv\Scripts\activate.bat
 uvicorn app.main:app --reload --access-log --log-level info
