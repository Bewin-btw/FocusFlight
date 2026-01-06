from fastapi import APIRouter
from app.repositories.sessions_repo import SessionsRepo

router = APIRouter(prefix="/api", tags=["stats"])
repo = SessionsRepo()

@router.get("/stats/today")
def stats_today():
    return repo.today_stats()
