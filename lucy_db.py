# -*- coding: utf-8 -*-
"""
SQLite 기반 데이터베이스 및 MD 파일 자동 동기화 (lucy_db.py)
"""
import os
import sqlite3
import datetime

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MEMORY_DIR = os.path.join(BASE_DIR, "memory")
DB_PATH = os.path.join(MEMORY_DIR, "lucy.db")


def get_db(db_path=None):
    path = db_path or DB_PATH
    os.makedirs(os.path.dirname(path), exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    _init_schema(conn)
    return conn


def _init_schema(conn):
    with conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS notes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                content TEXT NOT NULL,
                date TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS lessons (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                content TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS todos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                task TEXT NOT NULL,
                done INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)


def add_note(content, date=None, db_path=None):
    if not date:
        date = datetime.date.today().isoformat()
    conn = get_db(db_path)
    with conn:
        conn.execute("INSERT INTO notes (content, date) VALUES (?, ?)", (content, date))
    conn.close()


def get_notes(db_path=None):
    conn = get_db(db_path)
    cur = conn.execute("SELECT content, date FROM notes ORDER BY id ASC")
    rows = cur.fetchall()
    conn.close()
    return [{"content": r["content"], "date": r["date"]} for r in rows]


def sync_notes_md(md_path=None, db_path=None):
    """DB에 저장된 notes를 notes.md 파일에 동기화 백업합니다."""
    path = md_path or os.path.join(MEMORY_DIR, "notes.md")
    notes = get_notes(db_path)
    lines = [f"- {n['content']}  ({n['date']})\n" for n in notes]
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.writelines(lines)
    return len(notes)


def add_lesson(content, db_path=None):
    conn = get_db(db_path)
    with conn:
        conn.execute("INSERT INTO lessons (content) VALUES (?)", (content,))
    conn.close()


def get_lessons(db_path=None):
    conn = get_db(db_path)
    cur = conn.execute("SELECT content FROM lessons ORDER BY id ASC")
    rows = cur.fetchall()
    conn.close()
    return [r["content"] for r in rows]


def add_todo(task, done=0, db_path=None):
    conn = get_db(db_path)
    with conn:
        conn.execute("INSERT INTO todos (task, done) VALUES (?, ?)", (task, done))
    conn.close()


def get_todos(db_path=None):
    conn = get_db(db_path)
    cur = conn.execute("SELECT task, done FROM todos ORDER BY id ASC")
    rows = cur.fetchall()
    conn.close()
    return [{"task": r["task"], "done": r["done"]} for r in rows]
