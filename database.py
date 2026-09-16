import sqlite3


SCHEMA = """
CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY, name TEXT NOT NULL, email TEXT UNIQUE NOT NULL, password_hash TEXT NOT NULL, role TEXT NOT NULL DEFAULT 'customer', verified INTEGER NOT NULL DEFAULT 0, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS auth_sessions (id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE, token TEXT UNIQUE NOT NULL, expires_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS verification_tokens (id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE, token TEXT UNIQUE NOT NULL, expires_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS password_reset_tokens (id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE, token TEXT UNIQUE NOT NULL, expires_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS shows (id INTEGER PRIMARY KEY, cinema_name TEXT NOT NULL, show_name TEXT NOT NULL, starts_at TEXT NOT NULL, festival_discount NUMERIC NOT NULL DEFAULT 0, member_percent NUMERIC NOT NULL DEFAULT 0, member_discount_cap NUMERIC NOT NULL DEFAULT 0, convenience_fee NUMERIC NOT NULL DEFAULT 0, gst_percent NUMERIC NOT NULL DEFAULT 18, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS ticket_tiers (id INTEGER PRIMARY KEY, show_id INTEGER NOT NULL REFERENCES shows(id) ON DELETE CASCADE, name TEXT NOT NULL, price NUMERIC NOT NULL CHECK(price >= 0), UNIQUE(show_id, name));
CREATE TABLE IF NOT EXISTS seats (id INTEGER PRIMARY KEY, show_id INTEGER NOT NULL REFERENCES shows(id) ON DELETE CASCADE, tier_id INTEGER NOT NULL REFERENCES ticket_tiers(id) ON DELETE CASCADE, seat_number TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'available', UNIQUE(show_id, seat_number));
CREATE TABLE IF NOT EXISTS bookings (id INTEGER PRIMARY KEY, reference TEXT UNIQUE NOT NULL, user_id INTEGER NOT NULL REFERENCES users(id), show_id INTEGER NOT NULL REFERENCES shows(id), tier_id INTEGER NOT NULL REFERENCES ticket_tiers(id), quantity INTEGER NOT NULL CHECK(quantity > 0), status TEXT NOT NULL, total_amount NUMERIC NOT NULL, hold_expires_at TEXT, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS booking_items (id INTEGER PRIMARY KEY, booking_id INTEGER NOT NULL REFERENCES bookings(id) ON DELETE CASCADE, seat_id INTEGER NOT NULL REFERENCES seats(id), price NUMERIC NOT NULL, UNIQUE(booking_id, seat_id));
CREATE TABLE IF NOT EXISTS passengers (id INTEGER PRIMARY KEY, booking_id INTEGER UNIQUE NOT NULL REFERENCES bookings(id) ON DELETE CASCADE, name TEXT NOT NULL, email TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS payments (id INTEGER PRIMARY KEY, booking_id INTEGER UNIQUE NOT NULL REFERENCES bookings(id), provider TEXT NOT NULL, provider_reference TEXT, status TEXT NOT NULL, amount NUMERIC NOT NULL, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS refunds (id INTEGER PRIMARY KEY, booking_id INTEGER NOT NULL REFERENCES bookings(id), status TEXT NOT NULL, amount NUMERIC NOT NULL, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS coupons (id INTEGER PRIMARY KEY, code TEXT UNIQUE NOT NULL, discount_percent NUMERIC NOT NULL, active INTEGER NOT NULL DEFAULT 1, expires_at TEXT);
CREATE TABLE IF NOT EXISTS notifications (id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE, kind TEXT NOT NULL, message TEXT NOT NULL, read_at TEXT, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
CREATE INDEX IF NOT EXISTS idx_shows_starts_at ON shows(starts_at);
CREATE INDEX IF NOT EXISTS idx_bookings_user ON bookings(user_id, status);
"""


def get_db():
    from flask import current_app, g

    if "db" not in g:
        g.db = sqlite3.connect(current_app.config["DATABASE"])
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


def close_db(_error=None):
    from flask import g

    db = g.pop("db", None)
    if db:
        db.close()


def init_db(path):
    connection = sqlite3.connect(path)
    connection.executescript(SCHEMA)
    connection.commit()
    connection.close()


def seed_db(db):
    if db.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 0:
        from werkzeug.security import generate_password_hash

        db.execute("INSERT INTO users (name, email, password_hash, role, verified) VALUES (?, ?, ?, 'admin', 1)", ("Administrator", "admin@example.com", generate_password_hash("Admin123!")))
    if db.execute("SELECT COUNT(*) FROM shows").fetchone()[0] == 0:
        show = db.execute("INSERT INTO shows (cinema_name, show_name, starts_at, festival_discount, member_percent, member_discount_cap, convenience_fee, gst_percent) VALUES ('City Cinema', 'Evening Premiere', '2026-12-20T18:30:00+00:00', 20, 10, 50, 12.50, 18)").lastrowid
        for name, price, count in (("Silver", 100, 12), ("Gold", 150, 8), ("Recliner", 250, 4)):
            tier = db.execute("INSERT INTO ticket_tiers (show_id, name, price) VALUES (?, ?, ?)", (show, name, price)).lastrowid
            for number in range(1, count + 1):
                db.execute("INSERT INTO seats (show_id, tier_id, seat_number) VALUES (?, ?, ?)", (show, tier, f"{name[0]}{number}"))
    db.commit()