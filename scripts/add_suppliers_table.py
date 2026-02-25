import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'inventory.db')

def migrate():
    if not os.path.exists(DB_PATH):
        print(f"Database not found at {DB_PATH}")
        return

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    try:
        # 1. Create suppliers table
        print("Creating suppliers table...")
        cur.execute("""
            CREATE TABLE IF NOT EXISTS suppliers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                contact_name TEXT,
                phone TEXT,
                email TEXT,
                address TEXT,
                FOREIGN KEY(user_id) REFERENCES users(id)
            )
        """)
        
        # 2. Add supplier_id to products table
        print("Checking for supplier_id column in products...")
        cur.execute("PRAGMA table_info(products)")
        columns = [info[1] for info in cur.fetchall()]
        
        if 'supplier_id' not in columns:
            print("Adding supplier_id column to products table...")
            cur.execute("ALTER TABLE products ADD COLUMN supplier_id INTEGER REFERENCES suppliers(id)")
        else:
            print("supplier_id column already exists.")

        conn.commit()
        print("Migration completed successfully.")

    except Exception as e:
        print(f"An error occurred: {e}")
        conn.rollback()
    finally:
        conn.close()

if __name__ == "__main__":
    migrate()
