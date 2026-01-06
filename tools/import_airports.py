import argparse
import csv
import io
import sqlite3
import sys
import urllib.request
from datetime import datetime, timezone

OURAIRPORTS_AIRPORTS_CSV = "https://davidmegginson.github.io/ourairports-data/airports.csv"

KEEP_ISO = {"KZ", "RU", "US"}

def to_int01(v: str) -> int:
    v = (v or "").strip().lower()
    return 1 if v in {"yes", "y", "true", "1"} else 0

def download_csv(url: str) -> str:
    with urllib.request.urlopen(url, timeout=60) as resp:
        data = resp.read()
    return data.decode("utf-8", errors="replace")

def ensure_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS airports (
          code TEXT PRIMARY KEY,
          ident TEXT NOT NULL,
          iata_code TEXT,
          name TEXT NOT NULL,
          type TEXT,
          municipality TEXT,
          lat REAL NOT NULL,
          lon REAL NOT NULL,
          continent TEXT,
          iso_country TEXT,
          iso_region TEXT,
          scheduled_service INTEGER DEFAULT 0,
          home_link TEXT,
          wikipedia_link TEXT,
          keywords TEXT,
          source TEXT NOT NULL DEFAULT 'ourairports',
          updated_at TEXT
        );

        CREATE INDEX IF NOT EXISTS idx_airports_country ON airports(iso_country);
        CREATE INDEX IF NOT EXISTS idx_airports_continent ON airports(continent);
        CREATE INDEX IF NOT EXISTS idx_airports_name ON airports(name);
        CREATE INDEX IF NOT EXISTS idx_airports_muni ON airports(municipality);
        CREATE INDEX IF NOT EXISTS idx_airports_iata ON airports(iata_code);
        """
    )

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default="focusflight.db", help="Path to focusflight.db")
    ap.add_argument("--url", default=OURAIRPORTS_AIRPORTS_CSV, help="airports.csv URL")
    ap.add_argument("--truncate", action="store_true", help="Delete existing airports first")
    args = ap.parse_args()

    csv_text = download_csv(args.url)
    reader = csv.DictReader(io.StringIO(csv_text))

    conn = sqlite3.connect(args.db)
    conn.row_factory = sqlite3.Row
    ensure_schema(conn)

    if args.truncate:
        conn.execute("DELETE FROM airports")

    now = datetime.now(timezone.utc).isoformat()

    ins = 0
    skip = 0

    with conn:
        for row in reader:
            continent = (row.get("continent") or "").strip()
            iso_country = (row.get("iso_country") or "").strip().upper()

            keep = (continent == "EU") or (iso_country in KEEP_ISO)
            if not keep:
                skip += 1
                continue

            ident = (row.get("ident") or "").strip()
            iata = (row.get("iata_code") or "").strip().upper()
            name = (row.get("name") or "").strip()

            lat = (row.get("latitude_deg") or "").strip()
            lon = (row.get("longitude_deg") or "").strip()
            if not ident or not name or not lat or not lon:
                skip += 1
                continue

            try:
                lat_f = float(lat)
                lon_f = float(lon)
            except ValueError:
                skip += 1
                continue

            code = iata if iata else ident
            scheduled = to_int01(row.get("scheduled_service") or "")

            conn.execute(
                """
                INSERT INTO airports (
                  code, ident, iata_code, name, type, municipality,
                  lat, lon, continent, iso_country, iso_region,
                  scheduled_service, home_link, wikipedia_link, keywords,
                  source, updated_at
                ) VALUES (
                  ?, ?, ?, ?, ?, ?,
                  ?, ?, ?, ?, ?,
                  ?, ?, ?, ?,
                  'ourairports', ?
                )
                ON CONFLICT(code) DO UPDATE SET
                  ident=excluded.ident,
                  iata_code=excluded.iata_code,
                  name=excluded.name,
                  type=excluded.type,
                  municipality=excluded.municipality,
                  lat=excluded.lat,
                  lon=excluded.lon,
                  continent=excluded.continent,
                  iso_country=excluded.iso_country,
                  iso_region=excluded.iso_region,
                  scheduled_service=excluded.scheduled_service,
                  home_link=excluded.home_link,
                  wikipedia_link=excluded.wikipedia_link,
                  keywords=excluded.keywords,
                  updated_at=excluded.updated_at
                """,
                (
                    code,
                    ident,
                    iata or None,
                    name,
                    (row.get("type") or "").strip() or None,
                    (row.get("municipality") or "").strip() or None,
                    lat_f,
                    lon_f,
                    continent or None,
                    iso_country or None,
                    (row.get("iso_region") or "").strip() or None,
                    scheduled,
                    (row.get("home_link") or "").strip() or None,
                    (row.get("wikipedia_link") or "").strip() or None,
                    (row.get("keywords") or "").strip() or None,
                    now,
                ),
            )
            ins += 1

    conn.close()
    print(f"Imported: {ins}, skipped: {skip}, db: {args.db}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())