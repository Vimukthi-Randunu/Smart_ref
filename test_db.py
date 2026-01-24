import sqlite3

conn = sqlite3.connect("inventory.db")
print("SQLite connected successfully")
conn.close()
