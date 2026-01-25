from flask import Flask, render_template, request, redirect, Response, flash, session
from database import get_connection
from datetime import datetime, timedelta
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps

app = Flask(__name__)
app.secret_key = "smart_refill_secret_key_2024"

# -------- AUTHENTICATION DECORATOR --------
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash("Please log in first!", "error")
            return redirect("/login")
        return f(*args, **kwargs)
    return decorated_function

# -------- LOGIN/SIGNUP ROUTES --------
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()
        
        if not username or not password:
            flash("Username and password are required!", "error")
            return redirect("/login")
        
        conn = get_connection()
        cur = conn.cursor()
        
        try:
            cur.execute("SELECT id, password FROM users WHERE username = ?", (username,))
            user = cur.fetchone()
            
            if user and check_password_hash(user[1], password):
                session['user_id'] = user[0]
                session['username'] = username
                flash(f"Welcome back, {username}!", "success")
                return redirect("/")
            else:
                flash("Invalid username or password!", "error")
        except Exception as e:
            flash(f"Login error: {str(e)}", "error")
        finally:
            conn.close()
        
        return redirect("/login")
    
    return render_template("login.html")

@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()
        confirm = request.form.get("confirm", "").strip()
        
        if not username or not password or not confirm:
            flash("All fields are required!", "error")
            return redirect("/signup")
        
        if len(username) < 3:
            flash("Username must be at least 3 characters!", "error")
            return redirect("/signup")
        
        if len(password) < 6:
            flash("Password must be at least 6 characters!", "error")
            return redirect("/signup")
        
        if " " in password:
            flash("Password cannot contain spaces!", "error")
            return redirect("/signup")
        
        if password != confirm:
            flash("Passwords do not match!", "error")
            return redirect("/signup")
        
        conn = get_connection()
        cur = conn.cursor()
        
        try:
            cur.execute("SELECT id FROM users WHERE username = ?", (username,))
            if cur.fetchone() is not None:
                conn.close()
                flash("Username already exists! Please choose a different one.", "error")
                return redirect("/signup")
            
            hashed_password = generate_password_hash(password)
            cur.execute("INSERT INTO users (username, password) VALUES (?, ?)", (username, hashed_password))
            conn.commit()
            conn.close()
            
            flash("Account created successfully! Please log in.", "success")
            return redirect("/login")
        except Exception as e:
            conn.close()
            flash(f"Error creating account: {str(e)}", "error")
            return redirect("/signup")
    
    return render_template("signup.html")

@app.route("/logout")
def logout():
    username = session.get('username', 'User')
    session.clear()
    flash(f"Goodbye, {username}!", "success")
    return redirect("/login")

# -------- BUSINESS LOGIC --------
def get_stock_status(quantity, reorder_level):
    if quantity <= reorder_level / 2:
        return "CRITICAL"
    elif quantity <= reorder_level:
        return "LOW"
    else:
        return "NORMAL"

def convert_to_ist(timestamp_str):
    try:
        utc_time = datetime.strptime(timestamp_str, "%Y-%m-%d %H:%M:%S")
        ist_time = utc_time + timedelta(hours=5, minutes=30)
        return ist_time.strftime("%Y-%m-%d %H:%M:%S")
    except:
        return timestamp_str

# ---------------- DASHBOARD ----------------
@app.route("/")
@login_required
def dashboard():
    user_id = session['user_id']
    conn = get_connection()
    cur = conn.cursor()
    
    cur.execute("SELECT COUNT(*) FROM products WHERE user_id = ?", (user_id,))
    total_skus = cur.fetchone()[0]
    
    cur.execute("SELECT quantity, reorder_level FROM products WHERE user_id = ?", (user_id,))
    rows = cur.fetchall()
    
    low = critical = 0
    for q, r in rows:
        if q <= r / 2:
            critical += 1
        elif q <= r:
            low += 1
    
    today = datetime.now().date()
    cur.execute(
        "SELECT SUM(quantity) FROM stock_movements WHERE user_id = ? AND movement_type='IN' AND DATE(timestamp)=?",
        (user_id, today)
    )
    inbound_today = cur.fetchone()[0] or 0
    
    cur.execute(
        "SELECT SUM(quantity) FROM stock_movements WHERE user_id = ? AND movement_type='OUT' AND DATE(timestamp)=?",
        (user_id, today)
    )
    outbound_today = cur.fetchone()[0] or 0
    
    conn.close()
    
    return render_template(
        "dashboard.html",
        total_skus=total_skus,
        low=low,
        critical=critical,
        inbound=inbound_today,
        outbound=outbound_today
    )

# ---------------- ADD SKU ----------------
@app.route("/add", methods=["GET", "POST"])
@login_required
def add_product():
    user_id = session['user_id']
    
    if request.method == "POST":
        conn = get_connection()
        cur = conn.cursor()
        
        name = request.form.get("name", "").strip()
        category = request.form.get("category", "").strip()
        quantity_str = request.form.get("quantity", "0")
        reorder_str = request.form.get("reorder", "0")
        
        if not name or not category:
            conn.close()
            flash("SKU Name and Category are required!", "error")
            return redirect("/add")
        
        try:
            quantity = int(quantity_str)
            reorder = int(reorder_str)
        except ValueError:
            conn.close()
            flash("Quantity and Reorder Level must be valid numbers!", "error")
            return redirect("/add")
        
        if quantity < 0 or reorder < 0:
            conn.close()
            flash("Quantity and Reorder Level cannot be negative!", "error")
            return redirect("/add")
        
        cur.execute("SELECT id FROM products WHERE user_id = ? AND name = ?", (user_id, name))
        if cur.fetchone() is not None:
            conn.close()
            flash(f"SKU '{name}' already exists in your inventory!", "error")
            return redirect("/add")
        
        try:
            cur.execute(
                "INSERT INTO products (user_id, name, category, quantity, reorder_level, sales_count) VALUES (?,?,?,?,?,?)",
                (user_id, name, category, quantity, reorder, 0)
            )
            conn.commit()
            flash(f"SKU '{name}' added successfully!", "success")
        except Exception as e:
            flash(f"Error adding SKU: {str(e)}", "error")
        finally:
            conn.close()
        
        return redirect("/products")
    
    return render_template("add_product.html")

# ---------------- EDIT SKU ----------------
@app.route("/edit/<product_name>", methods=["GET", "POST"])
@login_required
def edit_product(product_name):
    user_id = session['user_id']
    conn = get_connection()
    cur = conn.cursor()
    
    if request.method == "POST":
        new_name = request.form.get("name", "").strip()
        category = request.form.get("category", "").strip()
        reorder_str = request.form.get("reorder", "0")
        
        if not new_name or not category:
            conn.close()
            flash("SKU Name and Category are required!", "error")
            return redirect(f"/edit/{product_name}")
        
        try:
            reorder = int(reorder_str)
        except ValueError:
            conn.close()
            flash("Reorder Level must be a valid number!", "error")
            return redirect(f"/edit/{product_name}")
        
        if reorder < 0:
            conn.close()
            flash("Reorder Level cannot be negative!", "error")
            return redirect(f"/edit/{product_name}")
        
        if new_name != product_name:
            cur.execute("SELECT id FROM products WHERE user_id = ? AND name = ?", (user_id, new_name))
            if cur.fetchone() is not None:
                conn.close()
                flash(f"SKU '{new_name}' already exists in your inventory!", "error")
                return redirect(f"/edit/{product_name}")
        
        try:
            cur.execute(
                "UPDATE products SET name = ?, category = ?, reorder_level = ? WHERE user_id = ? AND name = ?",
                (new_name, category, reorder, user_id, product_name)
            )
            if new_name != product_name:
                cur.execute(
                    "UPDATE stock_movements SET product_name = ? WHERE user_id = ? AND product_name = ?",
                    (new_name, user_id, product_name)
                )
            conn.commit()
            flash(f"SKU updated successfully!", "success")
        except Exception as e:
            flash(f"Error updating SKU: {str(e)}", "error")
        finally:
            conn.close()
        
        return redirect("/products")
    
    cur.execute(
        "SELECT name, category, quantity, reorder_level, sales_count FROM products WHERE user_id = ? AND name = ?",
        (user_id, product_name)
    )
    product = cur.fetchone()
    conn.close()
    
    if product is None:
        flash(f"SKU '{product_name}' not found!", "error")
        return redirect("/products")
    
    product_data = {
        "name": product[0],
        "category": product[1],
        "quantity": product[2],
        "reorder": product[3],
        "sales": product[4]
    }
    
    return render_template("edit_product.html", product=product_data)

# ---------------- VIEW STOCK ----------------
@app.route("/products")
@login_required
def view_products():
    user_id = session['user_id']
    conn = get_connection()
    cur = conn.cursor()
    
    cur.execute(
        "SELECT name, category, quantity, reorder_level, sales_count FROM products WHERE user_id = ?",
        (user_id,)
    )
    rows = cur.fetchall()
    conn.close()
    
    products = []
    for r in rows:
        products.append({
            "name": r[0],
            "category": r[1],
            "quantity": r[2],
            "reorder": r[3],
            "sales": r[4],
            "status": get_stock_status(r[2], r[3])
        })
    
    return render_template("view_products.html", products=products)

# ---------------- INBOUND ----------------
@app.route("/inbound", methods=["GET", "POST"])
@login_required
def inbound():
    user_id = session['user_id']
    conn = get_connection()
    cur = conn.cursor()
    
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        quantity_str = request.form.get("quantity", "0")
        
        if not name:
            conn.close()
            flash("Please select a SKU!", "error")
            return redirect("/inbound")
        
        try:
            qty = int(quantity_str)
        except ValueError:
            conn.close()
            flash("Quantity must be a valid number!", "error")
            return redirect("/inbound")
        
        if qty <= 0:
            conn.close()
            flash("Quantity must be greater than 0!", "error")
            return redirect("/inbound")
        
        try:
            cur.execute(
                "UPDATE products SET quantity = quantity + ? WHERE user_id = ? AND name = ?",
                (qty, user_id, name)
            )
            cur.execute(
                "INSERT INTO stock_movements (user_id, product_name, movement_type, quantity) VALUES (?, ?, ?, ?)",
                (user_id, name, "IN", qty)
            )
            conn.commit()
            flash(f"Successfully recorded inbound: {qty} units of '{name}'", "success")
        except Exception as e:
            flash(f"Error recording inbound: {str(e)}", "error")
        finally:
            conn.close()
        
        return redirect("/products")
    
    cur.execute("SELECT name FROM products WHERE user_id = ?", (user_id,))
    products = cur.fetchall()
    conn.close()
    
    return render_template("inbound.html", products=products)

# ---------------- OUTBOUND ----------------
@app.route("/outbound", methods=["GET", "POST"])
@login_required
def outbound():
    user_id = session['user_id']
    conn = get_connection()
    cur = conn.cursor()
    
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        quantity_str = request.form.get("quantity", "0")
        
        if not name:
            conn.close()
            flash("Please select a SKU!", "error")
            return redirect("/outbound")
        
        try:
            qty = int(quantity_str)
        except ValueError:
            conn.close()
            flash("Quantity must be a valid number!", "error")
            return redirect("/outbound")
        
        if qty <= 0:
            conn.close()
            flash("Quantity must be greater than 0!", "error")
            return redirect("/outbound")
        
        cur.execute("SELECT quantity FROM products WHERE user_id = ? AND name = ?", (user_id, name))
        result = cur.fetchone()
        
        if result is None:
            conn.close()
            flash(f"Product '{name}' not found!", "error")
            return redirect("/outbound")
        
        current_qty = result[0]
        
        if qty > current_qty:
            conn.close()
            flash(f"Insufficient stock! Only {current_qty} units available.", "error")
            return redirect("/outbound")
        
        try:
            cur.execute(
                "UPDATE products SET quantity = quantity - ?, sales_count = sales_count + ? WHERE user_id = ? AND name = ?",
                (qty, qty, user_id, name)
            )
            cur.execute(
                "INSERT INTO stock_movements (user_id, product_name, movement_type, quantity) VALUES (?, ?, ?, ?)",
                (user_id, name, "OUT", qty)
            )
            conn.commit()
            flash(f"Successfully recorded outbound: {qty} units of '{name}'", "success")
        except Exception as e:
            flash(f"Error recording outbound: {str(e)}", "error")
        finally:
            conn.close()
        
        return redirect("/products")
    
    cur.execute("SELECT name FROM products WHERE user_id = ?", (user_id,))
    products = cur.fetchall()
    conn.close()
    
    return render_template("outbound.html", products=products)

# ---------------- HISTORY ----------------
@app.route("/history")
@login_required
def history():
    user_id = session.get("user_id")
    if user_id is None:
        return redirect("/login")
    
    days = request.args.get("days")
    conn = get_connection()
    cur = conn.cursor()
    
    if days:
        since = datetime.now() - timedelta(days=int(days))
        cur.execute(
            """
            SELECT 
                p.id,
                p.name,
                p.category,
                s.movement_type,
                s.quantity,
                s.timestamp
            FROM stock_movements s
            LEFT JOIN products p ON s.product_name = p.name AND s.user_id = p.user_id
            WHERE s.user_id = ? AND s.timestamp >= ?
            ORDER BY s.timestamp DESC
            """,
            (user_id, since),
        )
    else:
        cur.execute(
            """
            SELECT 
                p.id,
                p.name,
                p.category,
                s.movement_type,
                s.quantity,
                s.timestamp
            FROM stock_movements s
            LEFT JOIN products p ON s.product_name = p.name AND s.user_id = p.user_id
            WHERE s.user_id = ?
            ORDER BY s.timestamp DESC
            """,
            (user_id,),
        )
    
    movements = cur.fetchall()
    conn.close()
    
    # Convert timestamps to IST
    converted_movements = []
    for m in movements:
        converted_m = list(m)
        converted_m[5] = convert_to_ist(m[5])
        converted_movements.append(tuple(converted_m))
    
    return render_template("history.html", movements=converted_movements)

# ---------------- REFILL DASHBOARD ----------------
@app.route("/refill")
@login_required
def refill():
    user_id = session['user_id']
    conn = get_connection()
    cur = conn.cursor()
    
    cur.execute(
        "SELECT name, quantity, reorder_level, sales_count FROM products WHERE user_id = ?",
        (user_id,)
    )
    products = list(cur.fetchall())
    conn.close()
    
    products.sort(key=lambda x: x[3], reverse=True)
    refill_list = [p for p in products if p[1] <= p[2]]
    
    return render_template("refill.html", products=refill_list)

# ---------------- DELETE SKU ----------------
@app.route("/delete/<product_name>", methods=["POST"])
@login_required
def delete_sku(product_name):
    user_id = session['user_id']
    
    try:
        conn = get_connection()
        cur = conn.cursor()
        
        cur.execute("SELECT id FROM products WHERE user_id = ? AND name = ?", (user_id, product_name))
        if cur.fetchone() is None:
            conn.close()
            flash(f"SKU '{product_name}' not found!", "error")
            return redirect("/products")
        
        cur.execute("DELETE FROM products WHERE user_id = ? AND name = ?", (user_id, product_name))
        cur.execute("DELETE FROM stock_movements WHERE user_id = ? AND product_name = ?", (user_id, product_name))
        
        conn.commit()
        conn.close()
        
        flash(f"SKU '{product_name}' has been successfully deleted!", "success")
    except Exception as e:
        flash(f"Error deleting SKU: {str(e)}", "error")
    
    return redirect("/products")

# ---------------- CSV EXPORT ----------------
@app.route("/export")
@login_required
def export_csv():
    user_id = session.get("user_id")
    if user_id is None:
        return redirect("/login")
    
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute(
            """
            SELECT 
                p.id,
                p.name,
                p.category,
                s.movement_type,
                s.quantity,
                s.timestamp
            FROM stock_movements s
            LEFT JOIN products p ON s.product_name = p.name AND s.user_id = p.user_id
            WHERE s.user_id = ?
            ORDER BY s.timestamp DESC
            """,
            (user_id,),
        )
        rows = cur.fetchall()
        conn.close()
        
        if not rows:
            flash("No movement records to export!", "warning")
            return redirect("/history")
        
        def generate():
            yield "SKU,SKU Name,Category,Movement,Quantity,Date & Time\n"
            for r in rows:
                sku_id = r[0] if r[0] else "N/A"
                sku_name = r[1] if r[1] else "Unknown"
                category = r[2] if r[2] else "Uncategorized"
                movement = r[3]
                quantity = r[4]
                timestamp = convert_to_ist(r[5])
                yield f"{sku_id},{sku_name},{category},{movement},{quantity},{timestamp}\n"
        
        return Response(
            generate(),
            mimetype="text/csv",
            headers={"Content-Disposition": "attachment; filename=movement_report.csv"}
        )
    except Exception as e:
        flash(f"Error exporting CSV: {str(e)}", "error")
        return redirect("/history")

# ---------------- RUN ----------------
if __name__ == "__main__":
    app.run(debug=True)
