-- Схема базы данных веб-приложения «Афиша мероприятий»
-- СУБД: SQLite 3
PRAGMA foreign_keys = ON;

DROP TABLE IF EXISTS visits;
DROP TABLE IF EXISTS favorites;
DROP TABLE IF EXISTS events;
DROP TABLE IF EXISTS users;
DROP TABLE IF EXISTS categories;
DROP TABLE IF EXISTS cities;

CREATE TABLE cities (
    id      INTEGER PRIMARY KEY AUTOINCREMENT,
    name    TEXT NOT NULL UNIQUE,
    slug    TEXT NOT NULL UNIQUE
);

CREATE TABLE categories (
    id      INTEGER PRIMARY KEY AUTOINCREMENT,
    name    TEXT NOT NULL UNIQUE,
    slug    TEXT NOT NULL UNIQUE,
    accent  TEXT NOT NULL DEFAULT '#4f46e5'
);

CREATE TABLE users (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    full_name     TEXT NOT NULL,
    email         TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    role          TEXT NOT NULL DEFAULT 'user'
                  CHECK (role IN ('user', 'organizer', 'admin')),
    city_id       INTEGER REFERENCES cities(id) ON DELETE SET NULL,
    created_at    TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE events (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    title         TEXT NOT NULL,
    summary       TEXT NOT NULL DEFAULT '',
    description   TEXT NOT NULL DEFAULT '',
    category_id   INTEGER NOT NULL REFERENCES categories(id) ON DELETE RESTRICT,
    city_id       INTEGER NOT NULL REFERENCES cities(id)      ON DELETE RESTRICT,
    venue         TEXT NOT NULL,
    address       TEXT NOT NULL DEFAULT '',
    starts_at     TEXT NOT NULL,
    ends_at       TEXT,
    price_min     INTEGER NOT NULL DEFAULT 0,
    is_free       INTEGER NOT NULL DEFAULT 0 CHECK (is_free IN (0, 1)),
    age_limit     INTEGER NOT NULL DEFAULT 0,
    status        TEXT NOT NULL DEFAULT 'pending'
                  CHECK (status IN ('pending', 'published', 'rejected')),
    reject_reason TEXT,
    created_by    INTEGER REFERENCES users(id) ON DELETE SET NULL,
    created_at    TEXT NOT NULL DEFAULT (datetime('now')),
    moderated_by  INTEGER REFERENCES users(id) ON DELETE SET NULL,
    moderated_at  TEXT
);

CREATE TABLE favorites (
    user_id    INTEGER NOT NULL REFERENCES users(id)  ON DELETE CASCADE,
    event_id   INTEGER NOT NULL REFERENCES events(id) ON DELETE CASCADE,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (user_id, event_id)
);

CREATE TABLE visits (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id    INTEGER NOT NULL REFERENCES users(id)  ON DELETE CASCADE,
    event_id   INTEGER NOT NULL REFERENCES events(id) ON DELETE CASCADE,
    visited_at TEXT NOT NULL DEFAULT (datetime('now')),
    rating     INTEGER CHECK (rating BETWEEN 1 AND 5),
    comment    TEXT NOT NULL DEFAULT '',
    UNIQUE (user_id, event_id)
);

CREATE INDEX idx_events_starts_at ON events (starts_at);
CREATE INDEX idx_events_filter    ON events (status, city_id, category_id, starts_at);
CREATE INDEX idx_favorites_user   ON favorites (user_id);
CREATE INDEX idx_visits_user      ON visits (user_id, visited_at);
