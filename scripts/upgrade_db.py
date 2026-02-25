import sqlite3

def upgrade_database():
    """
    Upgrades the database to support multi-tenant architecture.
    Adds user_id column to products and stock_movements tables.
    """
    conn = sqlite3.connect("inventory.db")
    cur = conn.cursor()
    
    print("Starting database upgrade for multi-tenant support...")
    
    try:
        # Check if user_id column exists in products table
        cur.execute("PRAGMA table_info(products)")
        columns = [column[1] for column in cur.fetchall()]
        
        if 'user_id' not in columns:
            print("Adding user_id to products table...")
            
            # Step 1: Create new products table with user_id
            cur.execute("""
                CREATE TABLE products_new (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL DEFAULT 1,
                    name TEXT NOT NULL,
                    category TEXT NOT NULL,
                    quantity INTEGER DEFAULT 0,
                    reorder_level INTEGER DEFAULT 10,
                    sales_count INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
                    UNIQUE(user_id, name)
                )
            """)
            
            # Step 2: Copy data from old table (assign to user_id = 1 by default)
            cur.execute("""
                INSERT INTO products_new (id, user_id, name, category, quantity, reorder_level, sales_count)
                SELECT id, 1, name, category, quantity, reorder_level, sales_count FROM products
            """)
            
            # Step 3: Drop old table and rename new one
            cur.execute("DROP TABLE products")
            cur.execute("ALTER TABLE products_new RENAME TO products")
            
            print("✅ Products table upgraded successfully!")
        else:
            print("✅ Products table already has user_id column")
        
        # Check if user_id column exists in stock_movements table
        cur.execute("PRAGMA table_info(stock_movements)")
        columns = [column[1] for column in cur.fetchall()]
        
        if 'user_id' not in columns:
            print("Adding user_id to stock_movements table...")
            
            # Step 1: Create new stock_movements table with user_id
            cur.execute("""
                CREATE TABLE stock_movements_new (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL DEFAULT 1,
                    product_name TEXT NOT NULL,
                    movement_type TEXT NOT NULL,
                    quantity INTEGER NOT NULL,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
                )
            """)
            
            # Step 2: Copy data from old table
            cur.execute("""
                INSERT INTO stock_movements_new (id, user_id, product_name, movement_type, quantity, timestamp)
                SELECT id, 1, product_name, movement_type, quantity, timestamp FROM stock_movements
            """)
            
            # Step 3: Drop old table and rename new one
            cur.execute("DROP TABLE stock_movements")
            cur.execute("ALTER TABLE stock_movements_new RENAME TO stock_movements")
            
            print("✅ Stock movements table upgraded successfully!")
        else:
            print("✅ Stock movements table already has user_id column")
        
        conn.commit()
        print("\n🎉 Database upgrade completed successfully!")
        print("📊 All existing data has been preserved and assigned to the first user.")
        print("🔒 New users will now have completely isolated data!")
        
    except Exception as e:
        conn.rollback()
        print(f"❌ Error during upgrade: {str(e)}")
    finally:
        conn.close()

if __name__ == "__main__":
    upgrade_database()