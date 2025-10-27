import sqlite3
from pathlib import Path

from src.config import config

def init_db():
    db_path = Path(config.DATABASE_FILE)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path), check_same_thread=False)
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY,
            telegram_id TEXT UNIQUE,
            encrypted_wallet TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS trades (
            id INTEGER PRIMARY KEY,
            user_id INTEGER,
            tx_hash TEXT,
            token_address TEXT,
            amount_in_native TEXT,
            amount_token TEXT,
            buy_price_native_per_token REAL,
            profit_target_percent INTEGER,
            side TEXT,
            status TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    return conn

# single global connection
conn = init_db()