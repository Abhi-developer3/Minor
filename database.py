# database.py
import sqlite3
from typing import List, Dict
import hashlib
import os

DB_PATH = "chatbot1.db"

# Create connection (thread-safe for Flask/FastAPI)
conn = sqlite3.connect(DB_PATH, check_same_thread=False)
conn.row_factory = sqlite3.Row

# ----------------------------------------------------------------------
# Helper: Add column if not exists
# ----------------------------------------------------------------------
def add_column_if_not_exists(table: str, column: str, definition: str):
    """Safely add a column if it doesn't already exist."""
    try:
        with conn:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")
        print(f"[Migration] Added column: {column} to {table}")
    except sqlite3.OperationalError as e:
        if "duplicate column name" in str(e).lower():
            pass  # Already exists
        else:
            print(f"[Migration Warning] Could not add {column}: {e}")

# ----------------------------------------------------------------------
# Schema Definition
# ----------------------------------------------------------------------
INIT_SQL = """
-- Users table
CREATE TABLE IF NOT EXISTS users (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    username      TEXT UNIQUE NOT NULL,
    email         TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL DEFAULT '',
    first_name    TEXT,
    last_name     TEXT,
    created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create unique indexes (idempotent)
CREATE UNIQUE INDEX IF NOT EXISTS idx_users_username ON users(username);
CREATE UNIQUE INDEX IF NOT EXISTS idx_users_email ON users(email);

-- Threads belong to users
CREATE TABLE IF NOT EXISTS threads (
    thread_id     TEXT PRIMARY KEY,
    user_id       INTEGER NOT NULL,
    title         TEXT DEFAULT 'New Chat',
    created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

-- Messages in threads
CREATE TABLE IF NOT EXISTS thread_messages (
    thread_id     TEXT,
    idx           INTEGER,
    role          TEXT CHECK(role IN ('user','assistant')),
    content       TEXT,
    media_b64     TEXT,
    PRIMARY KEY (thread_id, idx),
    FOREIGN KEY (thread_id) REFERENCES threads(thread_id) ON DELETE CASCADE
);
"""

# ----------------------------------------------------------------------
# Initialize / Migrate Database
# ----------------------------------------------------------------------
with conn:
    conn.executescript(INIT_SQL)

# --- Migration 1: Ensure critical columns exist in users table ---
with conn:
    cur = conn.execute("PRAGMA table_info(users)")
    existing_columns = {row["name"] for row in cur.fetchall()}

    if "password_hash" not in existing_columns:
        add_column_if_not_exists("users", "password_hash", "TEXT NOT NULL DEFAULT ''")
    if "first_name" not in existing_columns:
        add_column_if_not_exists("users", "first_name", "TEXT")
    if "last_name" not in existing_columns:
        add_column_if_not_exists("users", "last_name", "TEXT")
    if "created_at" not in existing_columns:
        add_column_if_not_exists("users", "created_at", "TIMESTAMP DEFAULT CURRENT_TIMESTAMP")

# --- Migration 2: Add media_b64 if missing ---
add_column_if_not_exists("thread_messages", "media_b64", "TEXT")

# --- Migration 3: Ensure default title on threads ---
with conn:
    try:
        conn.execute("ALTER TABLE threads ADD COLUMN title TEXT DEFAULT 'New Chat'")
    except sqlite3.OperationalError:
        pass  # Already has title or default


# ----------------------------------------------------------------------
# User Authentication Helpers
# ----------------------------------------------------------------------
def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()

def verify_password(stored_hash: str, provided_password: str) -> bool:
    return stored_hash == hash_password(provided_password)

def create_user(username: str, email: str, password: str, first_name: str = None, last_name: str = None) -> int:
    """Create a new user and return user ID."""
    password_hash = hash_password(password)
    try:
        with conn:
            cur = conn.execute(
                """INSERT INTO users (username, email, password_hash, first_name, last_name)
                   VALUES (?, ?, ?, ?, ?)""",
                (username.lower(), email.lower(), password_hash, first_name, last_name)
            )
            return cur.lastrowid
    except sqlite3.IntegrityError as e:
        if "username" in str(e):
            raise ValueError("Username already taken")
        if "email" in str(e):
            raise ValueError("Email already registered")
        raise

def get_user_by_username(username: str):
    cur = conn.execute("SELECT * FROM users WHERE username = ?", (username.lower(),))
    row = cur.fetchone()
    if row:
        return dict(row)  # Convert SQLite Row → dict with 'id', 'username', etc.
    return None

def get_user_by_email(email: str):
    cur = conn.execute("SELECT * FROM users WHERE email = ?", (email.lower(),))
    row = cur.fetchone()
    if row:
        return dict(row)
    return None

def get_user_by_id(user_id: int):
    cur = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,))
    return cur.fetchone()

# ----------------------------------------------------------------------
# Thread & Message Helpers (user-scoped)
# ----------------------------------------------------------------------
def get_thread_list(user_id: int) -> List[Dict]:
    cur = conn.execute(
        "SELECT thread_id, title, created_at FROM threads WHERE user_id = ? ORDER BY created_at DESC",
        (user_id,)
    )
    rows = cur.fetchall()
    return [
        {
            "thread_id": r["thread_id"],
            "title": r["title"] or "New Conversation",
            "created_at": r["created_at"]
        }
        for r in rows
    ]

def create_thread(thread_id, user_id, title="New Chat"):
    try:
        conn.execute(
            "INSERT INTO threads (thread_id, user_id, title, created_at) VALUES (?, ?, ?, datetime('now'))",
            (thread_id, user_id, title)
        )
        conn.commit()
    except sqlite3.IntegrityError:
        # Thread already exists – just update title
        conn.execute(
            "UPDATE threads SET title = ? WHERE thread_id = ?",
            (title, thread_id)
        )
        conn.commit()

def set_thread_title(thread_id: str, title: str):
    with conn:
        conn.execute("UPDATE threads SET title = ? WHERE thread_id = ?", (title, thread_id))

def load_messages(thread_id: str) -> List[Dict]:
    cur = conn.execute(
        "SELECT role, content, media_b64 FROM thread_messages WHERE thread_id = ? ORDER BY idx",
        (thread_id,)
    )
    return [
        {"role": r["role"], "content": r["content"], "media_b64": r["media_b64"]}
        for r in cur.fetchall()
    ]

def append_message(thread_id: str, role: str, content: str, media_b64: str | None = None):
    cur = conn.execute(
        "SELECT COALESCE(MAX(idx), -1) FROM thread_messages WHERE thread_id = ?",
        (thread_id,)
    )
    next_idx = cur.fetchone()[0] + 1
    with conn:
        conn.execute(
            """INSERT INTO thread_messages (thread_id, idx, role, content, media_b64)
               VALUES (?, ?, ?, ?, ?)""",
            (thread_id, next_idx, role, content, media_b64)
        )

def delete_thread(thread_id: str):
    with conn:
        conn.execute("DELETE FROM threads WHERE thread_id = ?", (thread_id,))

def thread_belongs_to_user(thread_id: str, user_id: int) -> bool:
    cur = conn.execute(
        "SELECT 1 FROM threads WHERE thread_id = ? AND user_id = ?",
        (thread_id, user_id)
    )
    return cur.fetchone() is not None