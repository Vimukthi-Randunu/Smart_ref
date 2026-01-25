import sqlite3

conn = sqlite3.connect("inventory.db")
cur = conn.cursor()

print("=== Checking Products Table ===")
cur.execute("PRAGMA table_info(products)")
columns = cur.fetchall()
print("Columns:", [col[1] for col in columns])

print("\n=== Checking Stock Movements Table ===")
cur.execute("PRAGMA table_info(stock_movements)")
columns = cur.fetchall()
print("Columns:", [col[1] for col in columns])

print("\n=== Checking Products Data ===")
cur.execute("SELECT id, user_id, name FROM products LIMIT 5")
products = cur.fetchall()
for p in products:
    print(f"Product ID: {p[0]}, User ID: {p[1]}, Name: {p[2]}")

print("\n=== Checking Users ===")
cur.execute("SELECT id, username FROM users")
users = cur.fetchall()
for u in users:
    print(f"User ID: {u[0]}, Username: {u[1]}")

conn.close()