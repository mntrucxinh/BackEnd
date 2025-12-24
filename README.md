docker compose up -d db adminer
alembic upgrade head
uvicorn app.main:app --reload