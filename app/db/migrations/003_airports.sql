CREATE TABLE IF NOT EXISTS airports (
  id INTEGER PRIMARY KEY,
  iata TEXT NOT NULL UNIQUE,
  name TEXT NOT NULL,
  iso_country TEXT,
  continent TEXT,
  lat REAL NOT NULL,
  lon REAL NOT NULL,
  municipality TEXT
);

CREATE INDEX IF NOT EXISTS idx_airports_iata ON airports(iata);
CREATE INDEX IF NOT EXISTS idx_airports_name ON airports(name);
CREATE INDEX IF NOT EXISTS idx_airports_country ON airports(iso_country);