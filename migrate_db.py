import sqlite3
import os
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.environ.get("DATA_DIR", BASE_DIR)
DB_PATH = os.path.join(DATA_DIR, 'documents.db')

def migrate():
    print(f"Migrating database at {DB_PATH}...")
    if not os.path.exists(DB_PATH):
        print("Database does not exist yet. No migration needed.")
        return
        
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    try:
        cursor.execute("ALTER TABLE documents ADD COLUMN username VARCHAR(100)")
        print("Added 'username' column.")
    except sqlite3.OperationalError as e:
        print(f"'username' column might already exist: {e}")
        
    try:
        cursor.execute("ALTER TABLE documents ADD COLUMN email VARCHAR(100)")
        print("Added 'email' column.")
    except sqlite3.OperationalError as e:
        print(f"'email' column might already exist: {e}")

    try:
        cursor.execute("ALTER TABLE documents ADD COLUMN file_title VARCHAR(255)")
        print("Added 'file_title' column.")
    except sqlite3.OperationalError as e:
        print(f"'file_title' column might already exist: {e}")

    try:
        cursor.execute("ALTER TABLE documents ADD COLUMN status VARCHAR(50) DEFAULT 'pending'")
        print("Added 'status' column.")
    except sqlite3.OperationalError as e:
        print(f"'status' column might already exist: {e}")

    try:
        cursor.execute("ALTER TABLE users ADD COLUMN role VARCHAR(20) DEFAULT 'user'")
        print("Added 'role' column.")
    except sqlite3.OperationalError as e:
        print(f"'role' column might already exist: {e}")
        
    conn.commit()
    conn.close()
    print("Migration complete.")

if __name__ == "__main__":
    migrate()
