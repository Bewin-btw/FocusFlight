from fastapi import APIRouter
from fastapi.responses import Response
from app.repositories.sessions_repo import SessionsRepo
from app.services.export_csv import export_sessions_csv

router = APIRouter(prefix="/api", tags=["export"])
repo = SessionsRepo()

@router.get("/export/sessions.csv")
def export_csv():
    csv_text = export_sessions_csv(repo)
    return Response(
        content=csv_text,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="focusflight_sessions.csv"'}
    )
