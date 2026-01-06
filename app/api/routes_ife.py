from fastapi import APIRouter, Query
from app.core.airports import AIRPORTS
import math

router = APIRouter(prefix="/api/ife", tags=["ife"])

def haversine_km(lat1, lon1, lat2, lon2) -> float:
    r = 6371.0
    p1 = math.radians(lat1)
    p2 = math.radians(lat2)
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2) ** 2 + math.cos(p1) * math.cos(p2) * (math.sin(dlon / 2) ** 2)
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return r * c

def lerp(a: float, b: float, t: float) -> float:
    return a + (b - a) * t

@router.get("/airports")
def airports():
    items = []
    for code, a in AIRPORTS.items():
        items.append({"code": code, "name": a["name"], "lat": a["lat"], "lon": a["lon"]})
    items.sort(key=lambda x: x["code"])
    return {"items": items}

@router.get("/plan")
def plan(
    origin: str = Query("BER"),
    dest: str = Query("IST"),
    planned_minutes: int = Query(50, ge=5, le=240),
):
    origin = origin.upper().strip()
    dest = dest.upper().strip()

    if origin not in AIRPORTS or dest not in AIRPORTS or origin == dest:
        return {"error": "bad route"}

    o = AIRPORTS[origin]
    d = AIRPORTS[dest]

    total_km = haversine_km(o["lat"], o["lon"], d["lat"], d["lon"])
    duration_s = planned_minutes * 60

    # Для плавной анимации линии
    n = 160
    path = []
    for i in range(n):
        t = i / (n - 1)
        path.append([lerp(o["lon"], d["lon"], t), lerp(o["lat"], d["lat"], t)])  # GeoJSON lon,lat

    # Средняя скорость по плану сессии
    speed_kmh = (total_km / duration_s) * 3600.0 if duration_s > 0 else 0.0

    return {
        "origin": {"code": origin, "name": o["name"], "lat": o["lat"], "lon": o["lon"]},
        "dest": {"code": dest, "name": d["name"], "lat": d["lat"], "lon": d["lon"]},
        "path": path,
        "total_km": round(total_km, 1),
        "duration_s": duration_s,
        "speed_kmh": round(speed_kmh, 0),
    }
