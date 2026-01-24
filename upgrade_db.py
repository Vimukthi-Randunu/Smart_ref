import sqlite3

conn = sqlite3.connect("inventory.db")
cur = conn.cursor()

cur.execute("""
CREATE TABLE IF NOT EXISTS stock_movements (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    product_name TEXT,
    movement_type TEXT,   -- IN or OUT
    quantity INTEGER,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
)
""")

conn.commit()
conn.close()

print("Stock movement table created")
