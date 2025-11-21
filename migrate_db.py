import sqlite3
import os

DB_FILE = "shouldibuy.db"

def migrate():
    if not os.path.exists(DB_FILE):
        print(f"Database {DB_FILE} not found. Skipping migration.")
        return

    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    try:
        # Check if column exists
        cursor.execute("PRAGMA table_info(analysis_jobs)")
        columns = [info[1] for info in cursor.fetchall()]
        
        if 'short_id' not in columns:
            print("Adding short_id column to analysis_jobs...")
            cursor.execute("ALTER TABLE analysis_jobs ADD COLUMN short_id TEXT")
            cursor.execute("CREATE UNIQUE INDEX ix_analysis_jobs_short_id ON analysis_jobs (short_id)")
            conn.commit()
            print("Migration successful.")
        else:
            print("Column short_id already exists.")
            
    except Exception as e:
        print(f"Migration failed: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    migrate()
