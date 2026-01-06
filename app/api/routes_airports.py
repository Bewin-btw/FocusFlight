from fastapi import APIRouter, Depends, Query
import sqlite3

from app.repositories.airports_repo import AirportsRepo
from app.db.db import get_db

router = APIRouter(prefix="/api/ife/airports", tags=["ife-airports"])

def repo(db: sqlite3.Connection = Depends(get_db)) -> AirportsRepo:
    return AirportsRepo(db)

@router.get("")
def list_airports(limit: int = Query(4000, ge=1, le=4000), r: AirportsRepo = Depends(repo)):
    return {"items": r.list_airports(limit=limit)}

@router.get("/search")
def search(
    q: str = Query("", max_length=80),
    limit: int = Query(20, ge=1, le=50),
    r: AirportsRepo = Depends(repo),
):
    return {"items": r.search(q=q, limit=limit)}

@router.get("/{code}")
def get_one(code: str, r: AirportsRepo = Depends(repo)):
    a = r.get_by_code(code)
    if not a:
        return {"error": "not_found"}
    return a