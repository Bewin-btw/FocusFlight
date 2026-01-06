from fastapi import APIRouter, Body
from fastapi.responses import JSONResponse
from app.repositories.sessions_repo import SessionsRepo
from app.services.grading import grade_from_altitude

router = APIRouter(prefix="/api", tags=["sessions"])
repo = SessionsRepo()

@router.post("/session/start")
def session_start(payload: dict = Body(...)):
    subject = (payload.get("subject") or "Study").strip()
    planned_minutes = int(payload.get("planned_minutes") or 50)
    planned_minutes = max(5, min(240, planned_minutes))

    sid = repo.create_session(subject, planned_minutes)
    repo.ensure_checkpoints(sid, planned_minutes)

    return {"session_id": sid, "planned_minutes": planned_minutes}

@router.post("/distraction")
def distraction(payload: dict = Body(...)):
    try:
        session_id = int(payload.get("session_id"))
        note = (payload.get("note") or "").strip() or None
        repo.add_distraction(session_id, note)
        return {"ok": True}
    except Exception:
        return JSONResponse({"error": "invalid session"}, status_code=400)

@router.get("/session/{session_id}/checkpoints")
def checkpoints(session_id: int):
    s = repo.get_open_session(session_id)
    if not s:
        return JSONResponse({"error": "invalid session"}, status_code=400)
    return {"items": repo.list_checkpoints(session_id)}

@router.post("/checkpoint/complete")
def checkpoint_complete(payload: dict = Body(...)):
    try:
        checkpoint_id = int(payload.get("checkpoint_id"))
        note = (payload.get("note") or "").strip() or None
        repo.complete_checkpoint(checkpoint_id, note)
        return {"ok": True}
    except Exception:
        return JSONResponse({"error": "not found"}, status_code=404)

@router.post("/session/end")
def session_end(payload: dict = Body(...)):
    try:
        session_id = int(payload.get("session_id"))
        actual_seconds = int(payload.get("actual_seconds") or 0)
        altitude_end = int(payload.get("altitude_end") or 100)
        turbulence_end = int(payload.get("turbulence_end") or 0)

        actual_seconds = max(0, actual_seconds)
        altitude_end = max(0, min(100, altitude_end))
        turbulence_end = max(0, turbulence_end)

        grade = grade_from_altitude(altitude_end)
        repo.end_session(session_id, actual_seconds, altitude_end, turbulence_end, grade)
        return {"ok": True, "grade": grade}
    except Exception:
        return JSONResponse({"error": "bad request"}, status_code=400)

@router.get("/sessions/recent")
def sessions_recent(limit: int = 10):
    limit = max(1, min(50, int(limit)))
    return {"items": repo.recent_sessions(limit)}
