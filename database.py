# -*- coding: utf-8 -*-
import sqlite3 
from config import DB_PATH

# =========================
# CONNECTION
# =========================
def get_sql():
    return sqlite3.connect(DB_PATH, check_same_thread=False)

# =========================
# INIT DB
# =========================
def init_db():
    conn = get_sql()
    cursor = conn.cursor()

    # ===== TRACKS =====
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS tracks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            query TEXT UNIQUE,
            title TEXT,
            file_id TEXT,
            download_count INTEGER DEFAULT 0
        )
    """)

    # ===== USERS =====
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            daily_count INTEGER DEFAULT 0,
            last_reset TEXT,
            premium_until TEXT,
            total_downloads INTEGER DEFAULT 0,
            banned INTEGER DEFAULT 0
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS downloads_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            track_query TEXT,
            downloaded_at TEXT
        )
        """)

    conn.commit()
    conn.close()

# =========================
# TRACK FUNCTIONS
# =========================
def get_track(query):
    conn = get_sql()
    cur = conn.cursor()

    cur.execute("SELECT file_id FROM tracks WHERE query = ?", (query,))
    row = cur.fetchone()

    conn.close()
    return row[0] if row else None

def save_track(query, title, file_id):
    conn = get_sql()
    cur = conn.cursor()

    cur.execute("""
        INSERT OR IGNORE INTO tracks (query, title, file_id)
        VALUES (?, ?, ?)
    """, (query, title, file_id))

    conn.commit()
    conn.close()

def increase_download(query):
    conn = get_sql()
    cur = conn.cursor()

    cur.execute("""
        UPDATE tracks
        SET download_count = download_count + 1
        WHERE query = ?
    """, (query,))

    conn.commit()
    conn.close()

def get_all_tracks():
    conn = get_sql()
    cur = conn.cursor()

    cur.execute("SELECT query, file_id FROM tracks")
    rows = cur.fetchall()

    conn.close()
    return rows

# =========================
# USER FUNCTIONS
# =========================
def get_user(user_id):
    conn = get_sql()
    cur = conn.cursor()

    cur.execute("SELECT * FROM users WHERE user_id=?", (user_id,))
    row = cur.fetchone()

    conn.close()
    return row

def ensure_user(user_id):
    conn = get_sql()
    cur = conn.cursor()

    cur.execute("""
        INSERT OR IGNORE INTO users (user_id, daily_count, total_downloads)
        VALUES (?, 0, 0)
    """, (user_id,))

    conn.commit()
    conn.close()

def update_premium(user_id, premium_until):
    conn = get_sql()
    cur = conn.cursor()

    cur.execute("""
        INSERT INTO users (user_id, premium_until)
        VALUES (?, ?)
        ON CONFLICT(user_id)
        DO UPDATE SET premium_until=excluded.premium_until
    """, (user_id, premium_until))

    conn.commit()
    conn.close()

def increase_user_download(user_id):
    conn = get_sql()
    cur = conn.cursor()

    cur.execute("""
        UPDATE users
        SET daily_count = daily_count + 1,
            total_downloads = total_downloads + 1
        WHERE user_id = ?
    """, (user_id,))

    conn.commit()
    conn.close()

def reset_daily_if_needed(user_id, today):
    conn = get_sql()
    cur = conn.cursor()

    cur.execute("SELECT last_reset FROM users WHERE user_id=?", (user_id,))
    row = cur.fetchone()

    if row and row[0] != str(today):
        cur.execute("""
            UPDATE users
            SET daily_count=0, last_reset=?
            WHERE user_id=?
        """, (str(today), user_id))
        conn.commit()

    conn.close()

def ban_user(user_id):
    conn = get_sql()
    cur = conn.cursor()

    cur.execute("UPDATE users SET banned=1 WHERE user_id=?", (user_id,))
    conn.commit()
    conn.close()

def unban_user(user_id):
    conn = get_sql()
    cur = conn.cursor()

    cur.execute("UPDATE users SET banned=0 WHERE user_id=?", (user_id,))
    conn.commit()
    conn.close()

from datetime import datetime

def log_download(user_id, query):
    conn = get_sql()
    cur = conn.cursor()

    cur.execute("""
        INSERT INTO downloads_log (user_id, track_query, downloaded_at)
        VALUES (?, ?, ?)
    """, (user_id, query, datetime.now().isoformat()))

    conn.commit()
    conn.close()