from fastapi import APIRouter, Query, Depends
import sqlite3
import math
from timezonefinder import TimezoneFinder

from app.core.airports import AIRPORTS
from app.db.db import get_db  # твоя функция подключения sqlite

_tf = TimezoneFinder()
router = APIRouter(prefix="/api/ife", tags=["ife"])


def haversine_km(lat1, lon1, lat2, lon2) -> float:
    r = 6371.0
    p1 = math.radians(lat1)
    p2 = math.radians(lat2)
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (math.sin(dlat / 2) ** 2) + math.cos(p1) * math.cos(p2) * (math.sin(dlon / 2) ** 2)
    return 2 * r * math.asin(math.sqrt(a))


def lerp(a: float, b: float, t: float) -> float:
    return a + (b - a) * t


def estimate_duration_minutes(distance_km: float) -> int:
    cruise_kmh = 820.0
    overhead_min = 22.0
    mins = (distance_km / cruise_kmh) * 60.0 + overhead_min
    return max(5, int(round(mins)))


def _airport_code_col(conn: sqlite3.Connection) -> str | None:
    cols = {r["name"] for r in conn.execute("PRAGMA table_info(airports)").fetchall()}
    # твоя схема: iata
    if "iata" in cols:
        return "iata"
    # схема ourairports: iata_code
    if "iata_code" in cols:
        return "iata_code"
    # схема ourairports: code (если iata отсутствует)
    if "code" in cols:
        return "code"
    return None


def _db_get_airport(conn: sqlite3.Connection, code: str) -> dict | None:
    c = code.upper().strip()
    code_col = _airport_code_col(conn)
    if not code_col:
        return None

    row = conn.execute(
        f"""
        SELECT
          {code_col} AS code,
          name,
          lat,
          lon
        FROM airports
        WHERE {code_col} IS NOT NULL
          AND TRIM({code_col}) != ''
          AND UPPER({code_col}) = UPPER(?)
        LIMIT 1
        """,
        (c,),
    ).fetchone()

    if not row:
        return None

    return {
        "code": (row["code"] or "").upper().strip(),
        "name": row["name"],
        "lat": float(row["lat"]),
        "lon": float(row["lon"]),
    }


def get_airport(code: str, conn: sqlite3.Connection | None = None) -> dict | None:
    c = code.upper().strip()

    if c in AIRPORTS:
        a = AIRPORTS[c]
        return {"code": c, "name": a["name"], "lat": a["lat"], "lon": a["lon"]}

    if conn is None:
        conn2 = get_db()
        try:
            return _db_get_airport(conn2, c)
        finally:
            conn2.close()

    return _db_get_airport(conn, c)


@router.get("/tz")
def tz(lat: float, lon: float):
    name = _tf.timezone_at(lat=lat, lng=lon) or "UTC"
    return {"tz": name}


# удобный поиск (можно дергать из фронта)
@router.get("/airports/search")
def airports_search(
    q: str = Query("", max_length=80),
    limit: int = Query(20, ge=1, le=50),
    db: sqlite3.Connection = Depends(get_db),
):
    query = (q or "").strip()
    if not query:
        return {"items": []}

    q_up = query.upper()
    q_lo = query.lower()

    code_col = _airport_code_col(db)

    def score_item(code: str, name: str) -> int:
        code_u = (code or "").upper()
        name_s = (name or "")
        name_l = name_s.lower()

        s = 0
        if code_u == q_up:
            s += 1000
        elif code_u.startswith(q_up):
            s += 700
        elif q_up in code_u:
            s += 350

        if name_l.startswith(q_lo):
            s += 320
        elif q_lo in name_l:
            s += 160

        parts = [p for p in q_lo.split() if p]
        if parts and all(p in name_l for p in parts):
            s += 140

        return s

    items = []

    if code_col:
        like = f"%{query}%"
        rows = db.execute(
            f"""
            SELECT {code_col} AS code, name, lat, lon
            FROM airports
            WHERE ({code_col} IS NOT NULL AND TRIM({code_col}) != '')
              AND (
                UPPER({code_col}) LIKE UPPER(?)
                OR name LIKE ?
              )
            LIMIT 220
            """,
            (like, like),
        ).fetchall()

        for r in rows:
            code = (r["code"] or "").upper().strip()
            if not code:
                continue
            items.append({
                "code": code,
                "name": r["name"],
                "lat": float(r["lat"]),
                "lon": float(r["lon"]),
            })
    else:
        for code, a in AIRPORTS.items():
            if q_up in code or q_lo in a["name"].lower():
                items.append({"code": code, "name": a["name"], "lat": a["lat"], "lon": a["lon"]})
            if len(items) >= 220:
                break

    items.sort(key=lambda a: (-score_item(a["code"], a["name"]), a["code"]))
    return {"items": items[:limit]}

@router.get("/pick")
def pick(
    minutes: int = Query(50, ge=5, le=240),
    origin: str = Query("BER"),
    db: sqlite3.Connection = Depends(get_db),
):
    o = get_airport(origin, db)
    if not o:
        return {"error": "bad origin"}

    candidates: list[tuple[float, str, float, int]] = []

    code_col = _airport_code_col(db)
    if code_col:
        rows = db.execute(
            f"""
            SELECT {code_col} AS code, name, lat, lon
            FROM airports
            WHERE {code_col} IS NOT NULL AND TRIM({code_col}) != ''
            LIMIT 4000
            """
        ).fetchall()

        for r in rows:
            code = (r["code"] or "").upper().strip()
            if not code or code == o["code"]:
                continue
            lat = float(r["lat"])
            lon = float(r["lon"])
            km = haversine_km(o["lat"], o["lon"], lat, lon)
            est_min = estimate_duration_minutes(km)
            candidates.append((abs(est_min - minutes), code, km, est_min))

    # если база пустая или не подошла, fallback на AIRPORTS
    if not candidates:
        for code, d in AIRPORTS.items():
            if code == o["code"]:
                continue
            km = haversine_km(o["lat"], o["lon"], d["lat"], d["lon"])
            est_min = estimate_duration_minutes(km)
            candidates.append((abs(est_min - minutes), code, km, est_min))

    candidates.sort(key=lambda x: x[0])
    best_code = candidates[0][1]
    return plan(origin=o["code"], dest=best_code, planned_minutes=minutes, db=db)


@router.get("/plan")
def plan(
    origin: str = Query("BER"),
    dest: str = Query("IST"),
    planned_minutes: int | None = Query(None, ge=5, le=240),
    db: sqlite3.Connection = Depends(get_db),
):
    o = get_airport(origin, db)
    d = get_airport(dest, db)
    if not o or not d or o["code"] == d["code"]:
        return {"error": "bad route"}

    total_km = haversine_km(o["lat"], o["lon"], d["lat"], d["lon"])

    if planned_minutes is None:
        planned_minutes = estimate_duration_minutes(total_km)

    duration_s = planned_minutes * 60

    n = 160
    path = []
    for i in range(n):
        t = i / (n - 1)
        path.append([lerp(o["lon"], d["lon"], t), lerp(o["lat"], d["lat"], t)])

    speed_kmh = (total_km / duration_s) * 3600.0 if duration_s > 0 else 0.0

    return {
        "origin": o,
        "dest": d,
        "path": path,
        "total_km": round(total_km, 1),
        "duration_s": duration_s,
        "planned_minutes": planned_minutes,
        "speed_kmh": round(speed_kmh, 0),
    }