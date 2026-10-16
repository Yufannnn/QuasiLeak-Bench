-- Only daily aggregates are stored; no raw request or person-level identifiers.
CREATE TABLE IF NOT EXISTS daily_page_views (
  day TEXT NOT NULL,
  path TEXT NOT NULL,
  country TEXT NOT NULL,
  views INTEGER NOT NULL DEFAULT 0,
  PRIMARY KEY (day, path, country)
);
