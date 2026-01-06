import sqlite3
from typing import Any

class AirportsRepo:
    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    def list_airports(self, limit: int = 4000) -> list[dict[str, Any]]:
        rows = self.conn.execute(
            """
            SELECT iata_code, name, lat, lon
            FROM airports
            WHERE iata_code IS NOT NULL
              AND length(iata_code) = 3
              AND (scheduled_service = 1 OR scheduled_service IS NULL)
            ORDER BY iata_code ASC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()

        return [
            {"code": r["iata_code"], "name": r["name"], "lat": r["lat"], "lon": r["lon"]}
            for r in rows
        ]

    def search(self, q: str, limit: int = 20) -> list[dict[str, Any]]:
        q = (q or "").strip().upper()
        like = f"%{q}%"
        rows = self.conn.execute(
            """
            SELECT iata_code, name, lat, lon
            FROM airports
            WHERE iata_code IS NOT NULL
              AND length(iata_code) = 3
              AND (
                upper(iata_code) LIKE ?
                OR upper(name) LIKE ?
                OR upper(coalesce(municipality, '')) LIKE ?
              )
            ORDER BY iata_code ASC
            LIMIT ?
            """,
            (like, like, like, limit),
        ).fetchall()

        return [
            {"code": r["iata_code"], "name": r["name"], "lat": r["lat"], "lon": r["lon"]}
            for r in rows
        ]

    def get_by_code(self, code: str) -> dict[str, Any] | None:
        code = (code or "").strip().upper()
        row = self.conn.execute(
            """
            SELECT iata_code, name, lat, lon
            FROM airports
            WHERE iata_code = ?
            LIMIT 1
            """,
            (code,),
        ).fetchone()
        if not row:
            return None
        return {"code": row["iata_code"], "name": row["name"], "lat": row["lat"], "lon": row["lon"]}