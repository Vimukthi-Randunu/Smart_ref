import sqlite3

def add_cost_column():
    conn = sqlite3.connect("data/inventory.db")
    cur = conn.cursor()
    
    try:
        # Check if column exists
        cur.execute("PRAGMA table_info(products)")
        columns = [column[1] for column in cur.fetchall()]
        
        if 'cost_per_unit' not in columns:
            print("Adding cost_per_unit column...")
            cur.execute("ALTER TABLE products ADD COLUMN cost_per_unit REAL DEFAULT 0.0")
            print("✅ Column added successfully!")
        else:
            print("ℹ️ Column cost_per_unit already exists.")
            
        conn.commit()
    except Exception as e:
        print(f"❌ Error during migration: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    add_cost_column()
