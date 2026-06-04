import sqlite3
import os
import json
import logging
from datetime import datetime
from config import LOG_DIR, MAX_HISTORY_PAIRS

logger = logging.getLogger(__name__)
DB_PATH = os.path.join(LOG_DIR, "bot_database.db")

def get_connection():
    return sqlite3.connect(DB_PATH)

def init_db():
    try:
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    user_id INTEGER PRIMARY KEY,
                    username TEXT,
                    first_name TEXT,
                    last_seen TIMESTAMP
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    role TEXT,
                    content TEXT,
                    timestamp TIMESTAMP,
                    FOREIGN KEY(user_id) REFERENCES users(user_id)
                )
            """)
            conn.commit()
    except Exception as e:
        logger.error(f"Error initializing DB: {e}")

def update_user(user_id: int, username: str, first_name: str):
    try:
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO users (user_id, username, first_name, last_seen)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(user_id) DO UPDATE SET
                    username=excluded.username,
                    first_name=excluded.first_name,
                    last_seen=excluded.last_seen
            """, (user_id, username, first_name, datetime.now()))
            conn.commit()
    except Exception as e:
        logger.error(f"Error updating user: {e}")

def add_message(user_id: int, role: str, content: str):
    try:
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO messages (user_id, role, content, timestamp)
                VALUES (?, ?, ?, ?)
            """, (user_id, role, content, datetime.now()))
            conn.commit()
    except Exception as e:
        logger.error(f"Error adding message: {e}")

def get_history(user_id: int, max_pairs: int = MAX_HISTORY_PAIRS) -> list[dict]:
    try:
        limit = max_pairs * 2
        with get_connection() as conn:
            cursor = conn.cursor()
            # Fetch last N messages ordered by timestamp DESC
            cursor.execute("""
                SELECT role, content FROM messages
                WHERE user_id = ?
                ORDER BY timestamp DESC
                LIMIT ?
            """, (user_id, limit))
            rows = cursor.fetchall()
            
            # They are ordered DESC, so we reverse them
            history = [{"role": row[0], "content": row[1]} for row in reversed(rows)]
            return history
    except Exception as e:
        logger.error(f"Error getting history: {e}")
        return []

def clear_history(user_id: int):
    try:
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM messages WHERE user_id = ?", (user_id,))
            conn.commit()
    except Exception as e:
        logger.error(f"Error clearing history: {e}")

def get_stats() -> str:
    try:
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM users")
            total_users = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(*) FROM messages WHERE role='user'")
            total_requests = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(*) FROM users WHERE date(last_seen) = date('now')")
            active_today = cursor.fetchone()[0]

            return (
                f"📊 Статистика бота:\n\n"
                f"👥 Всего пользователей: {total_users}\n"
                f"🔥 Активных сегодня: {active_today}\n"
                f"💬 Всего запросов: {total_requests}"
            )
    except Exception as e:
        logger.error(f"Error getting stats: {e}")
        return "Ошибка получения статистики"
