import os
import sqlite3
import datetime
from .database import DB_PATH

def create_backup():
    """
    Creates a safe backup of the main SQLite database using the sqlite3 backup API.
    Backups are stored indefinitely in the 'backups' directory with a timestamp.
    """
    if not os.path.exists(DB_PATH):
        print(f"[BackupManager] Source database not found at {DB_PATH}. Skipping backup.")
        return None

    base_dir = os.path.dirname(DB_PATH)
    backup_dir = os.path.join(base_dir, "backups")
    os.makedirs(backup_dir, exist_ok=True)

    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_filename = f"soccer_oracle_{timestamp}.sqlite"
    backup_path = os.path.join(backup_dir, backup_filename)

    print(f"[BackupManager] Starting database backup to {backup_path}...")

    try:
        source_conn = sqlite3.connect(DB_PATH)
        backup_conn = sqlite3.connect(backup_path)
        with source_conn:
            source_conn.backup(backup_conn)
        backup_conn.close()
        source_conn.close()
        print(f"[BackupManager] Backup completed successfully: {backup_filename}")
        return backup_path
    except Exception as e:
        print(f"[BackupManager] Backup failed: {e}")
        if os.path.exists(backup_path):
            try:
                os.remove(backup_path)
            except Exception:
                pass
        return None
