from typing import Any
from app.core.db import connect
from app.core.utils import utc_now_iso

class SessionsRepo:
    def create_session(self, subject: str, planned_minutes: int) -> int:
        con = connect()
        cur = con.cursor()
        cur.execute(
            "INSERT INTO sessions(subject, planned_minutes, started_at) VALUES(?,?,?)",
            (subject, planned_minutes, utc_now_iso())
        )
        sid = cur.lastrowid
        con.commit()
        con.close()
        return int(sid)

    def ensure_checkpoints(self, session_id: int, planned_minutes: int) -> None:
        con = connect()
        cur = con.cursor()

        exists = cur.execute(
            "SELECT COUNT(*) AS c FROM checkpoints WHERE session_id = ?",
            (session_id,)
        ).fetchone()["c"]
        if int(exists) > 0:
            con.close()
            return

        total_seconds = planned_minutes * 60
        idx = 1
        due = 10 * 60
        now = utc_now_iso()
        while due < total_seconds + 1:
            cur.execute(
                "INSERT INTO checkpoints(session_id, idx, due_seconds, created_at) VALUES(?,?,?,?)",
                (session_id, idx, due, now)
            )
            idx += 1
            due += 10 * 60

        con.commit()
        con.close()

    def add_distraction(self, session_id: int, note: str | None) -> None:
        con = connect()
        cur = con.cursor()

        row = cur.execute("SELECT ended_at FROM sessions WHERE id = ?", (session_id,)).fetchone()
        if not row or row["ended_at"] is not None:
            con.close()
            raise ValueError("invalid session")

        cur.execute(
            "INSERT INTO distractions(session_id, noted_at, note) VALUES(?,?,?)",
            (session_id, utc_now_iso(), note)
        )
        con.commit()
        con.close()

    def get_open_session(self, session_id: int) -> dict[str, Any] | None:
        con = connect()
        cur = con.cursor()
        row = cur.execute(
            "SELECT * FROM sessions WHERE id = ? AND ended_at IS NULL",
            (session_id,)
        ).fetchone()
        con.close()
        return dict(row) if row else None

    def list_checkpoints(self, session_id: int) -> list[dict[str, Any]]:
        con = connect()
        cur = con.cursor()
        rows = cur.execute(
            "SELECT id, idx, due_seconds, completed_at, note FROM checkpoints WHERE session_id = ? ORDER BY idx",
            (session_id,)
        ).fetchall()
        con.close()
        return [dict(r) for r in rows]

    def complete_checkpoint(self, checkpoint_id: int, note: str | None) -> None:
        con = connect()
        cur = con.cursor()
        row = cur.execute("SELECT completed_at FROM checkpoints WHERE id = ?", (checkpoint_id,)).fetchone()
        if not row:
            con.close()
            raise ValueError("not found")
        if row["completed_at"] is not None:
            con.close()
            return

        cur.execute(
            "UPDATE checkpoints SET completed_at = ?, note = ? WHERE id = ?",
            (utc_now_iso(), note, checkpoint_id)
        )
        con.commit()
        con.close()

    def end_session(
        self,
        session_id: int,
        actual_seconds: int,
        altitude_end: int,
        turbulence_end: int,
        grade: str
    ) -> None:
        con = connect()
        cur = con.cursor()

        dcount = cur.execute(
            "SELECT COUNT(*) AS c FROM distractions WHERE session_id = ?",
            (session_id,)
        ).fetchone()["c"]

        cur.execute(
            """
            UPDATE sessions
            SET ended_at = ?, actual_seconds = ?,
                distractions_count = ?, altitude_end = ?, turbulence_end = ?, grade = ?
            WHERE id = ? AND ended_at IS NULL
            """,
            (utc_now_iso(), actual_seconds, int(dcount), altitude_end, turbulence_end, grade, session_id)
        )
        con.commit()
        con.close()

    def today_stats(self) -> dict[str, int]:
        from datetime import date
        today = date.today().isoformat()

        con = connect()
        cur = con.cursor()

        s = cur.execute(
            "SELECT COUNT(*) AS c, COALESCE(SUM(actual_seconds),0) AS sum_s "
            "FROM sessions WHERE started_at LIKE ? AND ended_at IS NOT NULL",
            (today + "%",)
        ).fetchone()

        d = cur.execute(
            "SELECT COUNT(*) AS c FROM distractions WHERE noted_at LIKE ?",
            (today + "%",)
        ).fetchone()

        con.close()

        focus_minutes = int(round(int(s["sum_s"]) / 60))
        return {
            "date": today,
            "sessions": int(s["c"]),
            "focus_minutes": focus_minutes,
            "distractions": int(d["c"]),
        }

    def recent_sessions(self, limit: int = 10) -> list[dict[str, Any]]:
        con = connect()
        cur = con.cursor()
        rows = cur.execute(
            """
            SELECT id, subject, planned_minutes, started_at, ended_at, actual_seconds,
                   distractions_count, altitude_end, turbulence_end, grade
            FROM sessions
            WHERE ended_at IS NOT NULL
            ORDER BY id DESC
            LIMIT ?
            """,
            (limit,)
        ).fetchall()
        con.close()
        return [dict(r) for r in rows]

    def list_sessions_for_export(self) -> list[dict[str, Any]]:
        con = connect()
        cur = con.cursor()
        rows = cur.execute(
            """
            SELECT id, subject, planned_minutes, started_at, ended_at, actual_seconds,
                   distractions_count, altitude_end, turbulence_end, grade
            FROM sessions
            WHERE ended_at IS NOT NULL
            ORDER BY id DESC
            """
        ).fetchall()
        con.close()
        return [dict(r) for r in rows]
