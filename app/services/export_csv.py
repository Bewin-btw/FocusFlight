import csv
import io
from app.repositories.sessions_repo import SessionsRepo

def export_sessions_csv(repo: SessionsRepo) -> str:
    rows = repo.list_sessions_for_export()

    out = io.StringIO()
    w = csv.writer(out)

    w.writerow([
        "id", "subject", "planned_minutes",
        "started_at", "ended_at", "actual_seconds",
        "distractions_count", "altitude_end", "turbulence_end", "grade"
    ])

    for r in rows:
        w.writerow([
            r["id"], r["subject"], r["planned_minutes"],
            r["started_at"], r["ended_at"], r["actual_seconds"],
            r["distractions_count"], r["altitude_end"], r["turbulence_end"], r["grade"]
        ])

    return out.getvalue()
