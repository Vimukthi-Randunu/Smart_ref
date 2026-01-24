import sqlite3
from werkzeug.security import generate_password_hash

conn = sqlite3.connect("inventory.db")
cur = conn.cursor()

# Create users table
cur.execute("""
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    password TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
""")

cur.execute("""
CREATE TABLE IF NOT EXISTS products (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT,
    category TEXT,
    quantity INTEGER,
    reorder_level INTEGER,
    sales_count INTEGER
)
""")

# Create stock_movements table if it doesn't exist
cur.execute("""
CREATE TABLE IF NOT EXISTS stock_movements (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    product_id INTEGER,
    movement_type TEXT,
    quantity INTEGER,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(product_id) REFERENCES products(id)
)
""")

# Add a default admin user if no users exist
cur.execute("SELECT COUNT(*) FROM users")
if cur.fetchone()[0] == 0:
    default_password = generate_password_hash("admin123")
    cur.execute("INSERT INTO users (username, password) VALUES (?, ?)", ("admin", default_password))
    print("✅ Default admin user created: username='admin', password='admin123'")

conn.commit()
conn.close()

print("✅ Database tables created successfully")
