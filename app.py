import os
import smtplib
import threading
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from flask import Flask, render_template, request, redirect, Response, flash, session, jsonify
from database import get_connection
from datetime import datetime, timedelta
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "smart_refill_dev_key_change_in_production")

# ─── AUTO MIGRATE: ensure new columns exist in any pre-existing DB ───
def _migrate_db():
    try:
        conn = get_connection()
        cur  = conn.cursor()
        existing = [r[1] for r in cur.execute("PRAGMA table_info(users)").fetchall()]
        if "email" not in existing:
            cur.execute("ALTER TABLE users ADD COLUMN email TEXT DEFAULT NULL")
        if "email_alerts" not in existing:
            cur.execute("ALTER TABLE users ADD COLUMN email_alerts INTEGER DEFAULT 1")
        if "smtp_email" not in existing:
            cur.execute("ALTER TABLE users ADD COLUMN smtp_email TEXT DEFAULT NULL")
        if "smtp_pass" not in existing:
            cur.execute("ALTER TABLE users ADD COLUMN smtp_pass TEXT DEFAULT NULL")
        if "last_alert_sent" not in existing:
            cur.execute("ALTER TABLE users ADD COLUMN last_alert_sent TIMESTAMP DEFAULT NULL")
        conn.commit()
        conn.close()
    except Exception as _e:
        print(f"[migrate] {_e}")

_migrate_db()   # runs once at import / startup

# ─── EMAIL CONFIG (set these as environment variables or fill in directly for testing) ───
MAIL_SERVER   = os.environ.get("MAIL_SERVER",   "smtp.gmail.com")
MAIL_PORT     = int(os.environ.get("MAIL_PORT",   "587"))
MAIL_USERNAME = os.environ.get("MAIL_USERNAME",  "")   # your Gmail address
MAIL_PASSWORD = os.environ.get("MAIL_PASSWORD",  "")   # Gmail App Password
MAIL_FROM     = os.environ.get("MAIL_FROM",      MAIL_USERNAME)

# ─── EMAIL HELPER ───
def send_stock_alert_email(to_email: str, username: str, alert_products: list,
                           smtp_user: str = None, smtp_pass: str = None):
    """Send a rich HTML low-stock alert email. Runs in a background thread so it
    does not block the HTTP response.
    Uses per-user smtp_user/smtp_pass if provided, else falls back to env vars."""
    _smtp_user = smtp_user or MAIL_USERNAME
    _smtp_pass = smtp_pass or MAIL_PASSWORD
    if not _smtp_user or not _smtp_pass:
        print("[Email] SMTP credentials not configured — skipping alert.")
        return
    if not to_email:
        return

    now_str = datetime.now().strftime("%d %b %Y, %I:%M %p")
    critical = [p for p in alert_products if p['status'] == 'CRITICAL']
    low      = [p for p in alert_products if p['status'] == 'LOW']

    # ── Build HTML rows ──
    def row(p):
        badge_color = '#ef4444' if p['status'] == 'CRITICAL' else '#f59e0b'
        pct = round((p['quantity'] / max(p['reorder'], 1)) * 100)
        pct_bar_color = '#ef4444' if p['status'] == 'CRITICAL' else '#f59e0b'
        days = f"{p.get('days_remaining', '—')} days" if p.get('days_remaining') else 'N/A'
        return f"""
        <tr style="border-bottom:1px solid #2a2945">
          <td style="padding:12px 16px;font-weight:600;color:#f1f0ff">{p['name']}</td>
          <td style="padding:12px 16px;color:#a78bfa">{p.get('category','—')}</td>
          <td style="padding:12px 16px">
            <span style="background:rgba(255,255,255,.06);color:#f1f0ff;padding:3px 10px;border-radius:20px;font-weight:700">{p['quantity']}</span>
          </td>
          <td style="padding:12px 16px;color:#94a3b8">{p['reorder']}</td>
          <td style="padding:12px 16px">
            <span style="background:{badge_color}22;color:{badge_color};padding:3px 12px;border-radius:20px;font-size:11px;font-weight:800;border:1px solid {badge_color}44">{p['status']}</span>
          </td>
          <td style="padding:12px 16px">
            <div style="width:80px;height:6px;background:rgba(255,255,255,.08);border-radius:3px;overflow:hidden">
              <div style="width:{min(pct,100)}%;height:100%;background:{pct_bar_color};border-radius:3px"></div>
            </div>
            <span style="color:#94a3b8;font-size:11px">{pct}%</span>
          </td>
          <td style="padding:12px 16px;color:#94a3b8">{days}</td>
          <td style="padding:12px 16px;color:#34d399;font-weight:700">{p.get('suggested_qty','—')}</td>
        </tr>"""

    rows_html = "".join(row(p) for p in alert_products)
    n_critical = len(critical)
    n_low      = len(low)
    subject    = f"🚨 SmartRefill: {len(alert_products)} Stock Alert{'s' if len(alert_products)!=1 else ''} — Action Required"

    html = f"""
    <!DOCTYPE html><html><head><meta charset="UTF-8"></head>
    <body style="margin:0;padding:0;background:#0f0e17;font-family:'Segoe UI',Arial,sans-serif">
      <div style="max-width:700px;margin:30px auto;background:#16152a;border-radius:16px;overflow:hidden;border:1px solid rgba(255,255,255,.1)">

        <!-- Header -->
        <div style="background:linear-gradient(135deg,#6c63ff,#a78bfa);padding:32px 36px">
          <div style="display:flex;align-items:center;gap:14px">
            <div style="width:48px;height:48px;background:rgba(255,255,255,.2);border-radius:12px;display:flex;align-items:center;justify-content:center;font-size:22px">📦</div>
            <div>
              <div style="color:#fff;font-size:22px;font-weight:800;letter-spacing:-0.5px">SmartRefill Alert</div>
              <div style="color:rgba(255,255,255,.75);font-size:13px">Low Stock Notification — {now_str}</div>
            </div>
          </div>
        </div>

        <!-- Summary badges -->
        <div style="padding:24px 36px 0;display:flex;gap:16px;flex-wrap:wrap">
          <div style="background:rgba(248,113,113,.12);border:1px solid rgba(248,113,113,.25);border-radius:10px;padding:14px 22px;flex:1;min-width:140px">
            <div style="color:#f87171;font-size:28px;font-weight:900">{n_critical}</div>
            <div style="color:#fca5a5;font-size:12px;font-weight:700;margin-top:2px">CRITICAL Items</div>
          </div>
          <div style="background:rgba(251,191,36,.12);border:1px solid rgba(251,191,36,.25);border-radius:10px;padding:14px 22px;flex:1;min-width:140px">
            <div style="color:#fbbf24;font-size:28px;font-weight:900">{n_low}</div>
            <div style="color:#fcd34d;font-size:12px;font-weight:700;margin-top:2px">LOW Stock Items</div>
          </div>
          <div style="background:rgba(108,99,255,.12);border:1px solid rgba(108,99,255,.25);border-radius:10px;padding:14px 22px;flex:1;min-width:140px">
            <div style="color:#a78bfa;font-size:28px;font-weight:900">{len(alert_products)}</div>
            <div style="color:#c4b5fd;font-size:12px;font-weight:700;margin-top:2px">Total Alerts</div>
          </div>
        </div>

        <!-- Greeting -->
        <div style="padding:24px 36px">
          <p style="color:#f1f0ff;font-size:15px;margin:0 0 6px">Hello, <strong>{username}</strong> 👋</p>
          <p style="color:#94a3b8;font-size:13px;margin:0">The following products in your SmartRefill warehouse have dropped to or below their reorder levels and need your immediate attention.</p>
        </div>

        <!-- Table -->
        <div style="padding:0 36px 28px">
          <div style="border-radius:10px;overflow:hidden;border:1px solid rgba(255,255,255,.1)">
            <table style="width:100%;border-collapse:collapse">
              <thead>
                <tr style="background:rgba(108,99,255,.15)">
                  <th style="padding:11px 16px;text-align:left;color:#94a3b8;font-size:11px;letter-spacing:1px;text-transform:uppercase">Product</th>
                  <th style="padding:11px 16px;text-align:left;color:#94a3b8;font-size:11px;letter-spacing:1px;text-transform:uppercase">Category</th>
                  <th style="padding:11px 16px;text-align:left;color:#94a3b8;font-size:11px;letter-spacing:1px;text-transform:uppercase">In Stock</th>
                  <th style="padding:11px 16px;text-align:left;color:#94a3b8;font-size:11px;letter-spacing:1px;text-transform:uppercase">Reorder At</th>
                  <th style="padding:11px 16px;text-align:left;color:#94a3b8;font-size:11px;letter-spacing:1px;text-transform:uppercase">Status</th>
                  <th style="padding:11px 16px;text-align:left;color:#94a3b8;font-size:11px;letter-spacing:1px;text-transform:uppercase">Level</th>
                  <th style="padding:11px 16px;text-align:left;color:#94a3b8;font-size:11px;letter-spacing:1px;text-transform:uppercase">Days Left</th>
                  <th style="padding:11px 16px;text-align:left;color:#94a3b8;font-size:11px;letter-spacing:1px;text-transform:uppercase">Suggested Order</th>
                </tr>
              </thead>
              <tbody>{rows_html}</tbody>
            </table>
          </div>
        </div>

        <!-- CTA -->
        <div style="padding:0 36px 28px;text-align:center">
          <a href="http://127.0.0.1:5000/refill" style="display:inline-block;padding:13px 32px;background:linear-gradient(135deg,#6c63ff,#5a52e0);color:#fff;font-size:14px;font-weight:700;border-radius:10px;text-decoration:none;box-shadow:0 6px 20px rgba(108,99,255,.4)">View Refill Dashboard →</a>
        </div>

        <!-- Footer -->
        <div style="background:rgba(255,255,255,.04);border-top:1px solid rgba(255,255,255,.08);padding:18px 36px;text-align:center">
          <p style="color:#64748b;font-size:12px;margin:0">SmartRefill Warehouse System &nbsp;·&nbsp; You are receiving this because email alerts are enabled for your account.</p>
          <p style="color:#64748b;font-size:12px;margin:4px 0 0">To disable alerts, visit your <a href="http://127.0.0.1:5000/profile" style="color:#a78bfa">Profile Settings</a>.</p>
        </div>
      </div>
    </body></html>
    """

    def _send():
        try:
            msg = MIMEMultipart('alternative')
            msg['Subject'] = subject
            msg['From']    = f"SmartRefill <{_smtp_user}>"
            msg['To']      = to_email
            msg.attach(MIMEText(html, 'html'))
            with smtplib.SMTP(MAIL_SERVER, MAIL_PORT) as server:
                server.ehlo()
                server.starttls()
                server.login(_smtp_user, _smtp_pass)
                server.sendmail(_smtp_user, to_email, msg.as_string())
            print(f"[Email] ✅ Alert sent to {to_email} for {len(alert_products)} item(s).")
        except Exception as exc:
            print(f"[Email] ❌ Failed to send alert: {exc}")

    threading.Thread(target=_send, daemon=True).start()


# ─── HELPER: get all low/critical stock products for a user ───
def get_low_stock_products(user_id, conn):
    """Returns a list of dicts for all products at or below reorder level."""
    cur = conn.cursor()
    thirty_days_ago = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d %H:%M:%S')
    cur.execute("""
        SELECT p.name, p.category, p.quantity, p.reorder_level, p.cost_per_unit,
               COALESCE(SUM(CASE WHEN s.movement_type='OUT' AND s.timestamp > ? THEN s.quantity ELSE 0 END), 0) as out_30
        FROM products p
        LEFT JOIN stock_movements s ON p.name = s.product_name AND s.user_id = p.user_id
        WHERE p.user_id = ? AND p.quantity <= p.reorder_level
        GROUP BY p.name
    """, (thirty_days_ago, user_id))

    products = []
    for row in cur.fetchall():
        name, category, qty, reorder, cost, out_30 = row
        avg_daily  = round(out_30 / 30, 2) if out_30 > 0 else 0
        days_rem   = round(qty / avg_daily, 1) if avg_daily > 0 else None
        status     = get_stock_status(qty, reorder)
        suggested  = max(1, int(avg_daily * 14) - qty) if avg_daily > 0 else reorder * 2
        products.append({
            'name': name, 'category': category,
            'quantity': qty, 'reorder': reorder,
            'status': status, 'days_remaining': days_rem,
            'suggested_qty': suggested
        })
    # CRITICAL first, then LOW
    products.sort(key=lambda x: 0 if x['status'] == 'CRITICAL' else 1)
    return products


# ─── HELPER: auto-send alert for a user (with 2-hour cooldown) ───
def try_send_auto_alert(user_id):
    """Checks if the user has low/critical stock and sends a comprehensive
    alert email. Respects a 2-hour cooldown to avoid spamming."""
    try:
        conn = get_connection()
        cur  = conn.cursor()
        cur.execute(
            "SELECT email, email_alerts, username, smtp_email, smtp_pass, last_alert_sent FROM users WHERE id = ?",
            (user_id,)
        )
        u = cur.fetchone()
        if not u:
            conn.close()
            return

        to_email, alerts_on, username, smtp_email, smtp_pass, last_sent = u

        # Must have alerts enabled, a recipient email, and SMTP credentials
        if not alerts_on or not to_email or not smtp_email or not smtp_pass:
            conn.close()
            return

        # 2-hour cooldown: don't flood the inbox
        if last_sent:
            try:
                last_dt = datetime.strptime(last_sent[:19], '%Y-%m-%d %H:%M:%S')
                if (datetime.now() - last_dt).total_seconds() < 7200:
                    conn.close()
                    return
            except Exception:
                pass

        alert_products = get_low_stock_products(user_id, conn)
        if not alert_products:
            conn.close()
            return

        # Record send time BEFORE dispatching so parallel triggers don't double-send
        cur.execute(
            "UPDATE users SET last_alert_sent = ? WHERE id = ?",
            (datetime.now().strftime('%Y-%m-%d %H:%M:%S'), user_id)
        )
        conn.commit()
        conn.close()

        send_stock_alert_email(to_email, username, alert_products, smtp_email, smtp_pass)
        print(f"[auto-alert] Sent to user {user_id} ({username}) — {len(alert_products)} item(s) low.")

    except Exception as exc:
        print(f"[auto-alert] Error for user {user_id}: {exc}")


# ─── BACKGROUND PERIODIC ALERT CHECK (every 6 hours) ───
def _background_alert_check():
    """Runs every 6 hours. Sends auto-alerts to any user with unconfigured
    low stock who has SMTP credentials set up."""
    print("[bg-alert] Running periodic stock alert check...")
    try:
        conn = get_connection()
        cur  = conn.cursor()
        cur.execute(
            "SELECT id FROM users WHERE email_alerts = 1 AND email IS NOT NULL "
            "AND smtp_email IS NOT NULL AND smtp_pass IS NOT NULL"
        )
        user_ids = [row[0] for row in cur.fetchall()]
        conn.close()
        for uid in user_ids:
            try_send_auto_alert(uid)
    except Exception as exc:
        print(f"[bg-alert] Error: {exc}")
    finally:
        # Schedule next run in 6 hours
        threading.Timer(6 * 3600, _background_alert_check).start()

# Kick off the first background check 60 seconds after startup
threading.Timer(60, _background_alert_check).start()


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
        # Honour the hidden `next` field carried through the form
        next_url  = request.form.get("next", "").strip()

        if not username or not password:
            flash("Username and password are required!", "error")
            return redirect("/login" + (f"?next={next_url}" if next_url else ""))

        conn = get_connection()
        cur = conn.cursor()

        try:
            cur.execute("SELECT id, password FROM users WHERE username = ?", (username,))
            user = cur.fetchone()

            if user and check_password_hash(user[1], password):
                session['user_id'] = user[0]
                session['username'] = username
                flash(f"Welcome back, {username}!", "success")
                # Safe redirect: only allow internal paths starting with /
                if next_url and next_url.startswith("/") and not next_url.startswith("//"):
                    return redirect(next_url)
                return redirect("/dashboard")
            else:
                flash("Invalid username or password!", "error")
        except Exception as e:
            flash(f"Login error: {str(e)}", "error")
        finally:
            conn.close()

        return redirect("/login" + (f"?next={next_url}" if next_url else ""))

    # GET — pass `next` so template can embed it in a hidden field
    next_url = request.args.get("next", "")
    return render_template("login.html", next_url=next_url)

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

# ---------------- PUBLIC LANDING PAGE ----------------
@app.route("/")
def index():
    """Public landing page - redirects to dashboard if authenticated"""
    if 'user_id' in session:
        return redirect("/dashboard")
    return render_template("index.html")

# ---------------- DASHBOARD ----------------
@app.route("/dashboard")
@login_required
def dashboard():
    user_id = session['user_id']
    conn = get_connection()
    cur = conn.cursor()
    
    cur.execute("SELECT COUNT(*) FROM products WHERE user_id = ?", (user_id,))
    total_skus = cur.fetchone()[0]
    
    cur.execute("SELECT quantity, reorder_level, cost_per_unit FROM products WHERE user_id = ?", (user_id,))
    rows = cur.fetchall()
    
    low = critical = 0
    total_value = 0
    for q, r, c in rows:
        total_value += q * c
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
        outbound=outbound_today,
        total_value=total_value
    )

# ---------------- ADD SKU ----------------
@app.route("/add", methods=["GET", "POST"])
@login_required
def add_product():
    user_id = session['user_id']
    
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        category = request.form.get("category", "").strip()
        quantity_str = request.form.get("quantity", "0")
        reorder_str = request.form.get("reorder", "0")
        cost = float(request.form.get("cost", "0"))
        supplier_id = request.form.get("supplier_id")
        if not supplier_id:
            supplier_id = None
        
        # Validation
        if not name or not category:
            flash("Name and Category are required!", "error")
            return redirect("/add")
            
        try:
            qty = int(quantity_str)
            reorder = int(reorder_str)
        except ValueError:
            flash("Quantity and Reorder Level must be numbers!", "error")
            return redirect("/add")
        
        if qty < 0 or reorder < 0 or cost < 0:
            flash("Quantity, Reorder Level, and Cost cannot be negative!", "error")
            return redirect("/add")
            
        conn = get_connection()
        cur = conn.cursor()
        
        try:
            # Check if product exists
            cur.execute("SELECT id FROM products WHERE user_id = ? AND name = ?", (user_id, name))
            if cur.fetchone():
                flash("Product with this name already exists!", "error")
                return redirect("/add")
            
            cur.execute(
                "INSERT INTO products (user_id, name, category, quantity, reorder_level, cost_per_unit, supplier_id) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (user_id, name, category, qty, reorder, cost, supplier_id)
            )
            conn.commit()
            
            # Log initial stock...
            flash(f"Product '{name}' added successfully!", "success")
        except Exception as e:
            flash(f"Error adding product: {str(e)}", "error")
        finally:
            conn.close()
        
        return redirect("/products")
    
    # GET method
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT id, name FROM suppliers WHERE user_id = ? ORDER BY name", (user_id,))
    suppliers = cur.fetchall()
    conn.close()
    
    return render_template("add_product.html", suppliers=suppliers)

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
        cost = float(request.form.get("cost", "0"))
        supplier_id = request.form.get("supplier_id")
        if not supplier_id:
            supplier_id = None
        
        if not new_name or not category:
            flash("SKU Name and Category are required!", "error")
            return redirect(f"/edit/{product_name}")
        
        try:
            reorder = int(reorder_str)
        except ValueError:
            flash("Reorder Level must be a number!", "error")
            return redirect(f"/edit/{product_name}")
        
        if reorder < 0 or cost < 0:
            flash("Reorder Level and Cost cannot be negative!", "error")
            return redirect(f"/edit/{product_name}")
        
        if new_name != product_name:
            cur.execute("SELECT id FROM products WHERE user_id = ? AND name = ?", (user_id, new_name))
            if cur.fetchone() is not None:
                flash(f"SKU '{new_name}' already exists in your inventory!", "error")
                return redirect(f"/edit/{product_name}")
        
        try:
            # Update product
            cur.execute(
                "UPDATE products SET name = ?, category = ?, reorder_level = ?, cost_per_unit = ?, supplier_id = ? WHERE user_id = ? AND name = ?",
                (new_name, category, reorder, cost, supplier_id, user_id, product_name)
            )
            if new_name != product_name:
                cur.execute(
                    "UPDATE stock_movements SET product_name = ? WHERE user_id = ? AND product_name = ?",
                    (new_name, user_id, product_name)
                )
            conn.commit()
            flash(f"SKU updated successfully!", "success")
            return redirect("/products")
        except Exception as e:
            flash(f"Error updating SKU: {str(e)}", "error")
            return redirect(f"/edit/{product_name}")
        finally:
            conn.close()
    
    # GET request - show form
    cur.execute(
        "SELECT name, category, quantity, reorder_level, sales_count, cost_per_unit, supplier_id FROM products WHERE user_id = ? AND name = ?",
        (user_id, product_name)
    )
    product = cur.fetchone()
    
    cur.execute("SELECT id, name FROM suppliers WHERE user_id = ? ORDER BY name", (user_id,))
    suppliers = cur.fetchall()
    
    conn.close()
    
    if product is None:
        flash(f"SKU '{product_name}' not found!", "error")
        return redirect("/products")
    
    product_data = {
        "name": product[0],
        "category": product[1],
        "quantity": product[2],
        "reorder": product[3],
        "sales": product[4],
        "cost": product[5],
        "supplier_id": product[6]
    }
    
    return render_template("edit_product.html", product=product_data, suppliers=suppliers)

# ---------------- VIEW STOCK ----------------
@app.route("/products")
@login_required
def view_products():
    user_id = session['user_id']
    conn = get_connection()
    cur = conn.cursor()
    
    cur.execute(
        "SELECT name, category, quantity, reorder_level, sales_count, cost_per_unit FROM products WHERE user_id = ?",
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
            "cost": r[5],
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

            # ── Auto email alert: comprehensive check for ALL low stock items ──
            # Runs in background thread — never blocks the HTTP response
            threading.Thread(target=try_send_auto_alert, args=(user_id,), daemon=True).start()

            flash(f"Successfully recorded outbound: {qty} units of '{name}'", "success")
        except Exception as e:
            flash(f"Error recording outbound: {str(e)}", "error")
        finally:
            conn.close()
        
        return redirect("/products")
    
    cur.execute("SELECT name, quantity FROM products WHERE user_id = ?", (user_id,))
    products = cur.fetchall()
    
    conn.close()
    return render_template("outbound.html", products=products)

# ---------------- REPORTS ----------------
@app.route("/reports")
@login_required
def reports():
    user_id = session['user_id']
    conn = get_connection()
    cur = conn.cursor()
    
    # Top Movers (by sales_count)
    cur.execute("""
        SELECT name, category, sales_count 
        FROM products 
        WHERE user_id = ? 
        ORDER BY sales_count DESC 
        LIMIT 10
    """, (user_id,))
    top_movers_rows = cur.fetchall()
    
    top_movers = []
    for r in top_movers_rows:
        top_movers.append({
            "name": r[0],
            "category": r[1],
            "sales_count": r[2]
        })
        
    # Summary Stats
    cur.execute("SELECT COUNT(*) FROM products WHERE user_id = ?", (user_id,))
    total_skus = cur.fetchone()[0]
    
    cur.execute("SELECT SUM(quantity) FROM products WHERE user_id = ?", (user_id,))
    total_items = cur.fetchone()[0] or 0
    
    cur.execute("SELECT SUM(quantity * cost_per_unit) FROM products WHERE user_id = ?", (user_id,))
    total_value = cur.fetchone()[0] or 0.0

    # -------- ABC ANALYSIS --------
    # Classify products by cumulative sales contribution:
    # A = top 70% of sales volume, B = next 20%, C = remaining 10%
    cur.execute("""
        SELECT name, category, sales_count, quantity, cost_per_unit
        FROM products
        WHERE user_id = ?
        ORDER BY sales_count DESC
    """, (user_id,))
    all_rows = cur.fetchall()

    total_sales_vol = sum(r[2] for r in all_rows) or 1
    cumulative = 0
    abc_data = []
    for r in all_rows:
        cumulative += r[2]
        pct = (cumulative / total_sales_vol) * 100
        if pct <= 70:
            grade = 'A'
        elif pct <= 90:
            grade = 'B'
        else:
            grade = 'C'
        abc_data.append({
            'name': r[0],
            'category': r[1],
            'sales_count': r[2],
            'quantity': r[3],
            'value': round(r[3] * r[4], 2),
            'grade': grade
        })

    # -------- DEAD STOCK DETECTION --------
    # Products with stock > 0 but no OUT movement in last 30 days
    thirty_days_ago = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d %H:%M:%S')
    cur.execute("""
        SELECT p.name, p.category, p.quantity, p.cost_per_unit,
               MAX(CASE WHEN s.movement_type='OUT' THEN s.timestamp ELSE NULL END) as last_out
        FROM products p
        LEFT JOIN stock_movements s ON p.name = s.product_name AND s.user_id = p.user_id
        WHERE p.user_id = ? AND p.quantity > 0
        GROUP BY p.name
        HAVING last_out IS NULL OR last_out < ?
        ORDER BY p.quantity * p.cost_per_unit DESC
    """, (user_id, thirty_days_ago))

    dead_stock = []
    for r in cur.fetchall():
        if r[4]:
            try:
                last_dt = datetime.strptime(r[4][:19], '%Y-%m-%d %H:%M:%S')
                days_idle = (datetime.now() - last_dt).days
            except Exception:
                days_idle = None
        else:
            days_idle = None  # never sold at all
        dead_stock.append({
            'name': r[0],
            'category': r[1],
            'quantity': r[2],
            'value': round(r[2] * r[3], 2),
            'days_idle': days_idle
        })

    conn.close()
    
    return render_template(
        "reports.html",
        top_movers=top_movers,
        total_skus=total_skus,
        total_items=total_items,
        total_value=total_value,
        abc_data=abc_data,
        dead_stock=dead_stock
    )

# ---------------- SUPPLIERS ----------------
@app.route("/suppliers", methods=["GET", "POST"])
@login_required
def suppliers():
    user_id = session['user_id']
    conn = get_connection()
    cur = conn.cursor()
    
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        contact = request.form.get("contact", "").strip()
        phone = request.form.get("phone", "").strip()
        email = request.form.get("email", "").strip()
        address = request.form.get("address", "").strip()
        
        if not name:
            conn.close()
            flash("Supplier Name is required!", "error")
            return redirect("/suppliers")
            
        try:
            cur.execute(
                "INSERT INTO suppliers (user_id, name, contact_name, phone, email, address) VALUES (?, ?, ?, ?, ?, ?)",
                (user_id, name, contact, phone, email, address)
            )
            conn.commit()
            flash(f"Supplier '{name}' added successfully!", "success")
        except Exception as e:
            flash(f"Error adding supplier: {str(e)}", "error")
        finally:
            conn.close()
        
        return redirect("/suppliers")
    
    cur.execute("SELECT id, name, contact_name, phone, email, address FROM suppliers WHERE user_id = ? ORDER BY name", (user_id,))
    suppliers_list = cur.fetchall()
    conn.close()
    
    return render_template("suppliers.html", suppliers=suppliers_list)

@app.route("/suppliers/edit/<int:supplier_id>", methods=["GET", "POST"])
@login_required
def edit_supplier(supplier_id):
    user_id = session['user_id']
    conn = get_connection()
    cur = conn.cursor()
    
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        contact = request.form.get("contact", "").strip()
        phone = request.form.get("phone", "").strip()
        email = request.form.get("email", "").strip()
        address = request.form.get("address", "").strip()
        
        if not name:
            conn.close()
            flash("Supplier Name is required!", "error")
            return redirect(f"/suppliers/edit/{supplier_id}")
            
        try:
            cur.execute(
                "UPDATE suppliers SET name = ?, contact_name = ?, phone = ?, email = ?, address = ? WHERE id = ? AND user_id = ?",
                (name, contact, phone, email, address, supplier_id, user_id)
            )
            conn.commit()
            flash(f"Supplier details updated!", "success")
            return redirect("/suppliers")
        except Exception as e:
            flash(f"Error updating supplier: {str(e)}", "error")
            return redirect(f"/suppliers/edit/{supplier_id}")
        finally:
            conn.close()
            
    cur.execute("SELECT id, name, contact_name, phone, email, address FROM suppliers WHERE id = ? AND user_id = ?", (supplier_id, user_id))
    supplier = cur.fetchone()
    conn.close()
    
    if not supplier:
        flash("Supplier not found!", "error")
        return redirect("/suppliers")
        
    return render_template("suppliers.html", edit_supplier=supplier, suppliers=[]) # Re-use template for edit mode

@app.route("/suppliers/delete/<int:supplier_id>", methods=["POST"])
@login_required
def delete_supplier(supplier_id):
    user_id = session['user_id']
    conn = get_connection()
    cur = conn.cursor()
    
    try:
        # Check if used in products
        cur.execute("SELECT COUNT(*) FROM products WHERE supplier_id = ? AND user_id = ?", (supplier_id, user_id))
        count = cur.fetchone()[0]
        
        if count > 0:
            flash(f"Cannot delete supplier! They are linked to {count} products.", "error")
        else:
            cur.execute("DELETE FROM suppliers WHERE id = ? AND user_id = ?", (supplier_id, user_id))
            conn.commit()
            flash("Supplier deleted successfully!", "success")
    except Exception as e:
        flash(f"Error deleting supplier: {str(e)}", "error")
    finally:
        conn.close()
        
    return redirect("/suppliers")

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

    thirty_days_ago = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d %H:%M:%S')

    # Get all products below reorder level, along with 30-day outbound quantity
    cur.execute("""
        SELECT p.name, p.quantity, p.reorder_level, p.sales_count,
               COALESCE(SUM(CASE WHEN s.movement_type='OUT' AND s.timestamp > ? THEN s.quantity ELSE 0 END), 0) as out_30
        FROM products p
        LEFT JOIN stock_movements s ON p.name = s.product_name AND s.user_id = p.user_id
        WHERE p.user_id = ? AND p.quantity <= p.reorder_level
        GROUP BY p.name
    """, (thirty_days_ago, user_id))

    refill_list = []
    for row in cur.fetchall():
        name, qty, reorder, sales, out_30 = row
        avg_daily = round(out_30 / 30, 2) if out_30 > 0 else 0

        if avg_daily > 0:
            days_remaining = round(qty / avg_daily, 1)
            # Suggest enough stock for 14 days
            suggested_qty = max(1, int(avg_daily * 14) - qty)
        else:
            days_remaining = None
            # Fallback: suggest double the reorder level
            suggested_qty = reorder * 2

        refill_list.append({
            'name': name,
            'quantity': qty,
            'reorder': reorder,
            'sales': sales,
            'avg_daily': avg_daily,
            'days_remaining': days_remaining,
            'suggested_qty': suggested_qty
        })

    conn.close()

    # Sort by urgency: items closest to 0 days first; None (no history) at the end
    refill_list.sort(key=lambda x: (
        x['days_remaining'] is None,
        x['days_remaining'] if x['days_remaining'] is not None else float('inf')
    ))

    return render_template("refill.html", products=refill_list)

# ─── MANUAL TEST EMAIL ALERT (from Refill page) ───
@app.route("/send-alert", methods=["POST"])
@login_required
def send_alert():
    user_id = session['user_id']
    conn = get_connection()
    cur = conn.cursor()

    cur.execute(
        "SELECT email, email_alerts, username, smtp_email, smtp_pass FROM users WHERE id = ?",
        (user_id,)
    )
    u = cur.fetchone()
    conn.close()

    if not u or not u[0]:
        flash("⚠️ No recipient email set. Go to Profile Settings and add your email address.", "error")
        return redirect("/refill")

    to_email, alerts_on, username, smtp_email, smtp_pass = u

    if not smtp_email or not smtp_pass:
        flash("⚠️ SMTP credentials not configured. Go to Profile Settings → Email & SMTP Setup.", "error")
        return redirect("/profile")

    conn2 = get_connection()
    alert_products = get_low_stock_products(user_id, conn2)
    conn2.close()

    if not alert_products:
        flash("✅ All stock levels are healthy right now — no alert needed!", "success")
        return redirect("/refill")

    # Bypass cooldown for manual test — always send
    send_stock_alert_email(to_email, username, alert_products, smtp_email, smtp_pass)

    # Update last_alert_sent so the auto system respects the cooldown
    conn3 = get_connection()
    conn3.execute(
        "UPDATE users SET last_alert_sent = ? WHERE id = ?",
        (datetime.now().strftime('%Y-%m-%d %H:%M:%S'), user_id)
    )
    conn3.commit()
    conn3.close()

    flash(f"📧 Test alert email sent to {to_email} with {len(alert_products)} low-stock item(s)!", "success")
    return redirect("/refill")

# ─── PROFILE / SETTINGS ───
@app.route("/profile", methods=["GET", "POST"])
@login_required
def profile():
    user_id = session['user_id']
    conn = get_connection()
    cur = conn.cursor()

    if request.method == "POST":
        action = request.form.get("action", "")

        if action == "update_email":
            new_email    = request.form.get("email", "").strip()
            email_alerts = 1 if request.form.get("email_alerts") else 0
            new_smtp_email = request.form.get("smtp_email", "").strip()
            new_smtp_pass  = request.form.get("smtp_pass", "").strip()

            if new_email and "@" not in new_email:
                flash("Please enter a valid recipient email address.", "error")
            elif new_smtp_email and "@" not in new_smtp_email:
                flash("Please enter a valid Gmail address for SMTP.", "error")
            else:
                cur.execute(
                    "UPDATE users SET email = ?, email_alerts = ?, smtp_email = ?, smtp_pass = ? WHERE id = ?",
                    (
                        new_email or None,
                        email_alerts,
                        new_smtp_email or None,
                        new_smtp_pass or None,
                        user_id
                    )
                )
                conn.commit()
                flash("✅ Email & SMTP settings saved! Automatic alerts are now active.", "success")

        elif action == "change_password":
            current_pw  = request.form.get("current_password", "")
            new_pw      = request.form.get("new_password", "")
            confirm_pw  = request.form.get("confirm_password", "")
            cur.execute("SELECT password FROM users WHERE id = ?", (user_id,))
            row = cur.fetchone()
            if not row or not check_password_hash(row[0], current_pw):
                flash("Current password is incorrect.", "error")
            elif len(new_pw) < 6:
                flash("New password must be at least 6 characters.", "error")
            elif new_pw != confirm_pw:
                flash("Passwords do not match.", "error")
            else:
                cur.execute(
                    "UPDATE users SET password = ? WHERE id = ?",
                    (generate_password_hash(new_pw), user_id)
                )
                conn.commit()
                flash("✅ Password changed successfully!", "success")

        conn.close()
        return redirect("/profile")

    cur.execute("SELECT username, email, email_alerts, smtp_email, smtp_pass FROM users WHERE id = ?", (user_id,))
    row = cur.fetchone()
    conn.close()
    user_data = {
        'username':     row[0] if row else session.get('username', ''),
        'email':        row[1] if row else '',
        'email_alerts': row[2] if row else 1,
        'smtp_email':   row[3] if row else '',
        'smtp_pass':    row[4] if row else '',
    }
    return render_template("profile.html", user=user_data)

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
