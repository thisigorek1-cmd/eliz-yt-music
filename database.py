import sqlite3
from config import DB_PATH

def init_db():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS tracks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            query TEXT,
            file_path TEXT
        )
    """)

    conn.commit()
    conn.close()

def get_track(query):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    cur.execute("SELECT file_path FROM tracks WHERE query = ?", (query,))
    row = cur.fetchone()

    conn.close()
    return row[0] if row else None

def save_track(query, file_path):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    cur.execute("INSERT INTO tracks (query, file_path) VALUES (?, ?)", (query, file_path))

    conn.commit()
    conn.close()