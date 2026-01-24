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

        # Validation
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
            # Check if username already exists
            cur.execute("SELECT id FROM users WHERE username = ?", (username,))
            if cur.fetchone() is not None:
                conn.close()
                flash("Username already exists! Please choose a different one.", "error")
                return redirect("/signup")

            # Create new user
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
    """Convert UTC timestamp to IST (UTC+5:30)"""
    try:
        # Parse the timestamp string
        utc_time = datetime.strptime(timestamp_str, "%Y-%m-%d %H:%M:%S")
        # Add 5 hours 30 minutes to convert to IST
        ist_time = utc_time + timedelta(hours=5, minutes=30)
        return ist_time.strftime("%Y-%m-%d %H:%M:%S")
    except:
        return timestamp_str

# ---------------- DASHBOARD ----------------
@app.route("/")
@login_required
def dashboard():
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("SELECT COUNT(*) FROM products")
    total_skus = cur.fetchone()[0]

    cur.execute("SELECT quantity, reorder_level FROM products")
    rows = cur.fetchall()

    low = critical = 0
    for q, r in rows:
        if q <= r / 2:
            critical += 1
        elif q <= r:
            low += 1

    today = datetime.now().date()

    cur.execute(
        "SELECT SUM(quantity) FROM stock_movements WHERE movement_type='IN' AND DATE(timestamp)=?",
        (today,)
    )
    inbound_today = cur.fetchone()[0] or 0

    cur.execute(
        "SELECT SUM(quantity) FROM stock_movements WHERE movement_type='OUT' AND DATE(timestamp)=?",
        (today,)
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
    if request.method == "POST":
        conn = get_connection()
        cur = conn.cursor()

        name = request.form.get("name", "").strip()
        category = request.form.get("category", "").strip()
        quantity_str = request.form.get("quantity", "0")
        reorder_str = request.form.get("reorder", "0")

        # Validation
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

        # Check for duplicate SKU
        cur.execute("SELECT id FROM products WHERE name = ?", (name,))
        if cur.fetchone() is not None:
            conn.close()
            flash(f"SKU '{name}' already exists! Please use a different name.", "error")
            return redirect("/add")

        try:
            cur.execute(
                "INSERT INTO products VALUES (NULL,?,?,?,?,?)",
                (name, category, quantity, reorder, 0)
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
    conn = get_connection()
    cur = conn.cursor()

    if request.method == "POST":
        new_name = request.form.get("name", "").strip()
        category = request.form.get("category", "").strip()
        reorder_str = request.form.get("reorder", "0")

        # Validation
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

        # Check if new name already exists (and it's different from current)
        if new_name != product_name:
            cur.execute("SELECT id FROM products WHERE name = ?", (new_name,))
            if cur.fetchone() is not None:
                conn.close()
                flash(f"SKU '{new_name}' already exists! Please use a different name.", "error")
                return redirect(f"/edit/{product_name}")

        try:
            # Update product details (don't change quantity)
            cur.execute(
                "UPDATE products SET name = ?, category = ?, reorder_level = ? WHERE name = ?",
                (new_name, category, reorder, product_name)
            )
            # Also update product_name in stock movements if name changed
            if new_name != product_name:
                cur.execute("UPDATE stock_movements SET product_name = ? WHERE product_name = ?", (new_name, product_name))
            
            conn.commit()
            flash(f"SKU updated successfully!", "success")
        except Exception as e:
            flash(f"Error updating SKU: {str(e)}", "error")
        finally:
            conn.close()

        return redirect("/products")

    # GET request - show edit form
    cur.execute("SELECT name, category, quantity, reorder_level, sales_count FROM products WHERE name = ?", (product_name,))
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
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("SELECT name, category, quantity, reorder_level, sales_count FROM products")
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
    conn = get_connection()
    cur = conn.cursor()

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        quantity_str = request.form.get("quantity", "0")

        # Validation
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
            cur.execute("UPDATE products SET quantity = quantity + ? WHERE name = ?", (qty, name))
            cur.execute(
                "INSERT INTO stock_movements VALUES (NULL, ?, ?, ?, CURRENT_TIMESTAMP)",
                (name, "IN", qty)
            )
            conn.commit()
            flash(f"Successfully recorded inbound: {qty} units of '{name}'", "success")
        except Exception as e:
            flash(f"Error recording inbound: {str(e)}", "error")
        finally:
            conn.close()

        return redirect("/products")

    cur.execute("SELECT name FROM products")
    products = cur.fetchall()
    conn.close()

    return render_template("inbound.html", products=products)

# ---------------- OUTBOUND ----------------
@app.route("/outbound", methods=["GET", "POST"])
@login_required
def outbound():
    conn = get_connection()
    cur = conn.cursor()

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        quantity_str = request.form.get("quantity", "0")

        # Validation
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

        # Check current quantity
        cur.execute("SELECT quantity FROM products WHERE name = ?", (name,))
        result = cur.fetchone()
        
        if result is None:
            conn.close()
            flash(f"Product '{name}' not found!", "error")
            return redirect("/outbound")
        
        current_qty = result[0]
        
        # Prevent outbound if quantity exceeds available stock
        if qty > current_qty:
            conn.close()
            flash(f"Insufficient stock! Only {current_qty} units available for '{name}'. Cannot dispatch {qty} units.", "error")
            return redirect("/outbound")

        try:
            cur.execute(
                "UPDATE products SET quantity = quantity - ?, sales_count = sales_count + ? WHERE name = ?",
                (qty, qty, name)
            )

            cur.execute(
                "INSERT INTO stock_movements VALUES (NULL, ?, ?, ?, CURRENT_TIMESTAMP)",
                (name, "OUT", qty)
            )

            conn.commit()
            flash(f"Successfully recorded outbound: {qty} units of '{name}'", "success")
        except Exception as e:
            flash(f"Error recording outbound: {str(e)}", "error")
        finally:
            conn.close()

        return redirect("/products")

    cur.execute("SELECT name FROM products")
    products = cur.fetchall()
    conn.close()

    return render_template("outbound.html", products=products)

# ---------------- HISTORY ----------------
@app.route("/history")
@login_required
def history():
    days = request.args.get("days")

    conn = get_connection()
    cur = conn.cursor()

    if days:
        since = datetime.now() - timedelta(days=int(days))
        cur.execute(
            "SELECT * FROM stock_movements WHERE timestamp >= ? ORDER BY timestamp DESC",
            (since,)
        )
    else:
        cur.execute("SELECT * FROM stock_movements ORDER BY timestamp DESC")

    movements = cur.fetchall()
    conn.close()

    # Convert timestamps to IST
    converted_movements = []
    for m in movements:
        converted_m = list(m)
        converted_m[4] = convert_to_ist(m[4])
        converted_movements.append(tuple(converted_m))

    return render_template("history.html", movements=converted_movements)

# ---------------- REFILL DASHBOARD (FIXED) ----------------
@app.route("/refill")
@login_required
def refill():
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("SELECT name, quantity, reorder_level, sales_count FROM products")
    products = list(cur.fetchall())
    conn.close()

    products.sort(key=lambda x: x[3], reverse=True)
    refill_list = [p for p in products if p[1] <= p[2]]

    return render_template("refill.html", products=refill_list)

# ---------------- DELETE SKU ----------------
@app.route("/delete/<product_name>", methods=["POST"])
@login_required
def delete_sku(product_name):
    try:
        conn = get_connection()
        cur = conn.cursor()
        
        # Check if product exists
        cur.execute("SELECT id FROM products WHERE name = ?", (product_name,))
        if cur.fetchone() is None:
            conn.close()
            flash(f"SKU '{product_name}' not found!", "error")
            return redirect("/products")
        
        # Delete the product
        cur.execute("DELETE FROM products WHERE name = ?", (product_name,))
        
        # Also delete associated stock movements (optional - keeps history)
        cur.execute("DELETE FROM stock_movements WHERE product_name = ?", (product_name,))
        
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
    try:
        conn = get_connection()
        cur = conn.cursor()

        cur.execute("SELECT * FROM stock_movements")
        rows = cur.fetchall()
        conn.close()

        if not rows:
            flash("No movement records to export!", "warning")
            return redirect("/history")

        def generate():
            yield "Product,Type,Quantity,Timestamp\n"
            for r in rows:
                # Convert timestamp to IST
                timestamp = convert_to_ist(r[4]) if len(r) > 4 else r[4]
                yield f"{r[1]},{r[2]},{r[3]},{timestamp}\n"

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
