PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS airports (
  code TEXT PRIMARY KEY,                 -- IATA if exists, else ident
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

  scheduled_service INTEGER DEFAULT 0,    -- 0 or 1
  home_link TEXT,
  wikipedia_link TEXT,
  keywords TEXT,

  source TEXT NOT NULL DEFAULT 'ourairports',
  updated_at TEXT
);

CREATE INDEX IF NOT EXISTS idx_airports_country ON airports(iso_country);
CREATE INDEX IF NOT EXISTS idx_airports_continent ON airports(continent);

-- Для быстрого поиска
CREATE INDEX IF NOT EXISTS idx_airports_name ON airports(name);
CREATE INDEX IF NOT EXISTS idx_airports_muni ON airports(municipality);
CREATE INDEX IF NOT EXISTS idx_airports_iata ON airports(iata_code);