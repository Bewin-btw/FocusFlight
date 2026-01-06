from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.core.config import settings
from app.core.db import init_db

from app.api.routes_pages import router as pages_router
from app.api.routes_sessions import router as sessions_router
from app.api.routes_stats import router as stats_router
from app.api.routes_export import router as export_router
from app.api.routes_ife import router as ife_router
from app.api.routes_airports import router as airports_router

app = FastAPI(title=settings.app_title)

@app.on_event("startup")
def on_startup():
    init_db()

app.mount("/static", StaticFiles(directory="app/static"), name="static")

app.include_router(pages_router)
app.include_router(sessions_router)
app.include_router(stats_router)
app.include_router(export_router)
app.include_router(ife_router)
app.include_router(airports_router)