"""Database setup and management using dataset."""
import os
from pathlib import Path
from typing import Optional

import dataset

# Database file path
DB_PATH = Path(__file__).parent.parent.parent / "laser_tag.db"
DB_URL = f"sqlite:///{DB_PATH}"

# Global database connection
_db: Optional[dataset.Database] = None


def get_db() -> dataset.Database:
    """Get or create the database connection."""
    global _db
    if _db is None:
        _db = dataset.connect(DB_URL)
    return _db


def init_db(wipe_on_startup: bool = False) -> None:
    """Initialize the database and create tables if needed.
    
    Args:
        wipe_on_startup: If True, wipe the database on startup.
    """
    db = get_db()
    
    if wipe_on_startup and DB_PATH.exists():
        DB_PATH.unlink()
        # Reconnect to create fresh database
        global _db
        _db = None
        db = get_db()
    
    # Create tables if they don't exist
    # Players table: id, username, score
    players_table = db["players"]
    
    # Hits table: id, hitter_id, target_id, timestamp
    hits_table = db["hits"]
    
    # Ensure tables exist (dataset creates them automatically on first insert)
    # But we can verify they're accessible
    _ = players_table
    _ = hits_table


def close_db() -> None:
    """Close the database connection."""
    global _db
    if _db is not None:
        _db.close()
        _db = None


