import sqlite3
from flask import g
from datetime import datetime

DATABASE = 'sports_day.db'


def get_db():
    if 'db' not in g:
        g.db = sqlite3.connect(DATABASE)
        g.db.row_factory = sqlite3.Row
    return g.db


def close_db(e=None):
    db = g.pop('db', None)

    if db is not None:
        db.close()


def init_db():
    db = sqlite3.connect(DATABASE)

    db.executescript('''
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        email TEXT NOT NULL UNIQUE,
        phone TEXT NOT NULL,
        password TEXT NOT NULL,
        role TEXT DEFAULT 'student',
        created_at TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS sports (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL UNIQUE,
        description TEXT,
        rules TEXT,
        fee REAL NOT NULL DEFAULT 0,
        max_players INTEGER DEFAULT 20,
        venue TEXT,
        event_date TEXT,
        is_active INTEGER DEFAULT 1,
        created_at TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS registrations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        sport_id INTEGER,
        payment_ref TEXT,
        payment_status TEXT DEFAULT 'pending',
        registered_at TEXT NOT NULL,
        UNIQUE(user_id, sport_id),
        FOREIGN KEY(user_id) REFERENCES users(id),
        FOREIGN KEY(sport_id) REFERENCES sports(id)
    );
    ''')

    admin = db.execute(
        "SELECT * FROM users WHERE email = ?",
        ('admin@sportsday.edu',)
    ).fetchone()

    if not admin:
        from werkzeug.security import generate_password_hash
        db.execute('''
        INSERT INTO users(name, email, phone, password, role, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
        ''', (
            'Admin',
            'admin@sportsday.edu',
            '03000000000',
            generate_password_hash('admin123'),
            'admin',
            datetime.now().isoformat()
        ))

    sports = db.execute('SELECT COUNT(*) FROM sports').fetchone()[0]

    if sports == 0:
        sample_sports = [
            (
                'Cricket',
                '10 over cricket tournament',
                '11 players required. Umpire decision final.',
                500,
                22,
                'Main Ground Block A',
                '2026-05-20'
            ),
            (
                'Basketball',
                '5v5 basketball event',
                'Proper sports shoes required.',
                350,
                10,
                'Basketball Court',
                '2026-05-22'
            ),
            (
                'Badminton',
                'Singles competition',
                'Knockout format.',
                300,
                8,
                'Indoor Court',
                '2026-05-23'
            ),
            (
                'Table Tennis',
                'Singles event',
                'Best of 3 games.',
                200,
                8,
                'Indoor Hall',
                '2026-05-24'
            ),
            (
                'Football',
                '7v7 football event',
                'No rough play allowed.',
                600,
                14,
                'Football Ground',
                '2026-05-25'
            )
        ]

        for sport in sample_sports:
            db.execute('''
            INSERT INTO sports(
                name, description, rules, fee,
                max_players, venue, event_date, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                sport[0], sport[1], sport[2], sport[3],
                sport[4], sport[5], sport[6],
                datetime.now().isoformat()
            ))

    db.commit()
    db.close()