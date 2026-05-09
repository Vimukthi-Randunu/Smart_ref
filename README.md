# SmartRefill — DevOps Case Study

> This README is divided into two parts:
> **Part 1 — DevOps Case Study**: Documents the deployment infrastructure added to this codebase — Dockerfile, CI/CD pipeline, staging and production environments, health checks, and rollback.
> **Part 2 — Application Documentation**: The original developer's documentation covering application features, routes, database schema, and local setup instructions.

## Live Environments
# 🔗 Live Demo
https://smart-ref.onrender.com

| Environment | Status |
|---|---|
| Staging | Deployed via GitHub Actions on every push to main |
| Production | Deployed via manual approval gate |

> **Note**: Live URLs are available on request. 
> Environments are spun up on demand to demonstrate the full pipeline.

## Overview

SmartRefill is a full-featured, multi-tenant warehouse inventory management system built with Python Flask and SQLite. It allows teams to track stock levels, manage suppliers, record inbound and outbound movements, generate reports, and receive low-stock alerts — all through a clean web interface.

This repository is a DevOps case study. The original application was built by [Kan-06](https://github.com/Kan-06/Smart_ref) with working application code but zero DevOps infrastructure. I was brought in to add the complete deployment layer — simulating exactly what a DevOps engineer does when a client hands over an existing codebase.

---

## The Problem

When I received this codebase it had no deployment infrastructure whatsoever:

- No Dockerfile — the app could only run on a developer's local machine
- No Docker Compose — no way to manage the app and its configuration consistently
- No CI/CD pipeline — every deployment would require manual SSH and manual commands
- No staging environment — any change would go directly to production with no safety net
- No automated tests in the pipeline — broken code could be deployed without detection
- No health check — a failed deployment would go unnoticed until a user reported it
- No rollback mechanism — a bad deploy had no automatic recovery path
- Incomplete database initialization — the `database.py` script was missing the suppliers table and several columns added through undocumented migration scripts

The developer had deployed manually to Render by clicking buttons in a UI. This approach does not scale, is not repeatable, and offers no protection against bad deployments.

---

## What I Built

### Dockerfile

Containerized the Flask application using Python 3.11-slim as the base image. Production startup uses Gunicorn as the WSGI server instead of Flask's built-in development server, which is single-threaded and not safe for production traffic.

```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
EXPOSE 5000
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "2", "app:app"]
```

### Docker Compose

Wrote a `docker-compose.yml` for local development with a bind mount volume so the SQLite database persists outside the container across restarts. Environment variables are injected at runtime — never hardcoded.

### SQLite Volume Strategy

This app uses SQLite — a file-based database. Without a Docker volume, the database file lives inside the container and gets wiped on every deployment. I solved this by mounting `./data` on the host machine into `/app/data` inside the container. The database file lives on the server's disk and survives every container replacement.

### GitHub Actions CI/CD Pipeline

Four-job pipeline triggered on every push to main:

**test** — installs dependencies and runs pytest smoke tests on a fresh GitHub runner. If tests fail, nothing deploys.

**build-and-push** — builds the Docker image, tags it with the Git commit SHA and `latest`, pushes both tags to Docker Hub. One image built once, deployed identically everywhere.

**deploy-staging** — SSHes into the staging EC2 instance, writes a production Docker Compose file with the correct image tag, pulls the new image, starts the container, initializes the database, and runs a health check.

**deploy-production** — identical to staging but requires manual approval in GitHub before running. Production is never touched without a human decision.

### Staging and Production Environments

Two isolated EC2 instances on AWS:

- Staging: automatic deployment on every push to main
- Production: manual approval gate via GitHub Environments

Each environment has completely isolated secrets — separate EC2 hosts, separate SSH keys, separate secret keys. A broken staging deployment never affects production users.

### Health Check and Automatic Rollback

After every deployment the pipeline hits the live URL with curl. If the app does not respond, the pipeline automatically rolls back to the previous image and marks the deployment as failed. Production users experience at most a few seconds of downtime during a bad deploy before automatic recovery kicks in.

### Automated Database Initialization

The deploy script automatically runs `python database.py` inside the container after every deployment. This ensures all required tables exist on fresh servers without manual intervention.

---

## Key Findings From the Codebase

Working on someone else's code always surfaces undocumented assumptions. Here is what I found:

**Missing dependency** — `requests` was imported in `app.py` but not listed in `requirements.txt`. The app crashed immediately on a fresh install. Added to requirements.txt.

**Incomplete database initialization** — `database.py` was missing the `suppliers` table and four `emailjs` columns in the `users` table. These had been added through one-off migration scripts that were never merged back into the main initialization script. Fixed by updating `database.py` to create all tables and columns correctly.

**SQLite migration script bug** — `scripts/add_suppliers_table.py` had a missing comma in an `os.path.join` call, producing the path `datainventory.db` instead of `data/inventory.db`. Documented for the client.

**Development server in production** — the app used `app.run(debug=True)` with no production server configured. Gunicorn was already in `requirements.txt` suggesting the developer intended production deployment but never completed the setup. Resolved by the Dockerfile.

---

## Architecture

```
Developer pushes to main
        ↓
GitHub Actions Runner
        ↓
┌─────────────────────────────────────┐
│  test → build-and-push              │
│         ↓                           │
│  deploy-staging (automatic)         │
│         ↓                           │
│  deploy-production (manual approve) │
└─────────────────────────────────────┘
        ↓                    ↓
  Staging EC2          Production EC2
  Port 5000            Port 5000
  Docker + Volume      Docker + Volume
  SQLite DB            SQLite DB
        ↓                    ↓
   Health Check         Health Check
        ↓                    ↓
  Rollback if fail     Rollback if fail
```

---

## Tech Stack

| Layer | Technology |
|---|---|
| Application | Python 3.11, Flask 3.0, Gunicorn |
| Database | SQLite with Docker bind mount volume |
| Containerization | Docker, Docker Compose |
| CI/CD | GitHub Actions |
| Registry | Docker Hub |
| Infrastructure | AWS EC2 (Ubuntu 24.04) |
| Environments | GitHub Environments with approval gates |

---

## Future Improvements

**Nginx reverse proxy** — currently the app is exposed directly on port 5000. Adding Nginx on port 80 would remove the port number from the URL, enable HTTPS via Let's Encrypt, and add a proper production-grade HTTP layer in front of Gunicorn.

**PostgreSQL migration** — SQLite works for a single-server deployment but cannot scale horizontally. Migrating to PostgreSQL as a separate container would allow multiple app servers to share one database, enabling load balancing and true horizontal scaling.

**HTTPS** — production applications should never run on plain HTTP. SSL termination via Nginx and Let's Encrypt certificates would secure all traffic.

**Secrets scanning** — adding a secrets scanning step to the pipeline would prevent accidental credential commits.

---

## What This Project Demonstrates

This project simulates exactly what a DevOps engineer does in a real client engagement — receiving an existing codebase with no deployment infrastructure and building the complete DevOps layer from scratch. Every decision made here — from the volume strategy to the approval gate to the rollback mechanism — was driven by a specific problem identified in the codebase, not by copying a template.

---

*DevOps layer added by [Vimukthi Randunu](https://github.com/Vimukthi-Randunu) — radianceitsolution.com*



## Application Documentation
# 🔗 Live Demo
https://smart-ref.onrender.com
 
# 📦 SmartRefill — Warehouse Inventory Management System

A full-featured, multi-tenant warehouse management web application built with **Python Flask** and **SQLite**. SmartRefill helps teams track stock levels, manage inbound/outbound movements, monitor suppliers, generate reports, and receive low-stock email alerts — all through a clean, modern dark-themed UI.

---
## 🚀 Features

### 🔐 Authentication & User Management

- Secure signup and login with **hashed passwords** (`werkzeug.security`)
- Per-user data isolation (multi-tenant — each user sees only their own inventory)
- Session-based authentication with `login_required` decorator
- Password change from Profile Settings

### 📊 Dashboard

- At-a-glance KPIs: Total SKUs, Inventory Value, Critical & Low stock counts
- Today's inbound and outbound units
- Direct navigation to all major sections

### 📦 Warehouse Stock (Products)

- Add, edit, and delete SKUs (Stock Keeping Units)
- Fields: Name, Category, Quantity, Reorder Level, Cost per Unit, Supplier
- Real-time stock status badges: `NORMAL` / `LOW` / `CRITICAL`
- Search and filter products by name or category
- Export stock movement history to **CSV**

### 🟢 Inbound / 🔴 Outbound Movements

- Record incoming stock (Inbound)
- Record outgoing/sold stock (Outbound) with stock-level validation
- Automatic **email alert** triggered when outbound causes stock to drop below reorder level

### 🔔 Refill Dashboard

- Lists all products currently at or below reorder level
- Smart urgency sorting (most critical items first)
- Shows: Current Qty, Reorder Level, Average Daily Usage, Estimated Days Remaining, Suggested Order Qty
- **Manual "Send Alert Email"** button to trigger an immediate low-stock report

### 📧 Email Alerts

- Rich HTML email with product-level details (status, stock %, days remaining, suggested order)
- Auto-triggered on outbound when stock becomes CRITICAL or LOW
- Manually triggered from the Refill page
- Configurable via environment variables (Gmail/SMTP)
- Toggle alerts on/off from Profile Settings

### 🏢 Suppliers

- Add, edit, and delete supplier records (Name, Contact, Phone, Email, Address)
- Link suppliers to products
- Safe-delete: prevents deletion if supplier is linked to active products

### 📈 Reports

- **Top Movers**: Top 10 most-sold products
- **ABC Analysis**: Classifies products into A (top 70%), B (next 20%), C (bottom 10%) by sales volume
- **Dead Stock Detection**: Products with stock > 0 but no outbound movement in the last 30 days
- Summary stats: Total SKUs, Total Items in Stock, Total Inventory Value

### 📋 History & CSV Export

- Full stock movement log (Inbound/Outbound) with timestamps in **IST**
- Filter by time period (last 7 / 30 / 90 days)
- One-click **Export CSV** download

### 👤 Profile Settings

- Update email address for alert notifications
- Toggle email alerts on/off
- Change password securely

### 🎨 UI & Design

- Dark-themed, responsive interface
- Light/Dark theme toggle (`dark-theme.css`)
- Smooth animations via `enhancements.js`
- Mobile-friendly layout

---

## 🗂️ Project Structure

```
SMART_REFILL/
├── app.py                    # Main Flask application (all routes & logic)
├── database.py               # DB connection & schema initialization
├── inventory.db              # SQLite database (auto-created)
├── requirements.txt          # Python dependencies
├── .gitignore
│
├── templates/                # Jinja2 HTML templates
│   ├── index.html            # Public landing page
│   ├── login.html            # Login page
│   ├── signup.html           # Signup page
│   ├── dashboard.html        # Main dashboard
│   ├── view_products.html    # Warehouse stock list
│   ├── add_product.html      # Add new SKU
│   ├── edit_product.html     # Edit existing SKU
│   ├── inbound.html          # Record inbound stock
│   ├── outbound.html         # Record outbound stock
│   ├── refill.html           # Refill / low-stock dashboard
│   ├── reports.html          # Analytics & reports
│   ├── suppliers.html        # Supplier management
│   ├── history.html          # Movement history
│   └── profile.html          # User profile & settings
│
├── static/
│   ├── style.css             # Main stylesheet
│   ├── dark-theme.css        # Dark theme overrides
│   ├── enhancements.js       # UI animations & interactivity
│   └── dashboard.js          # Dashboard chart logic
│
└── scripts/                  # One-time DB migration scripts
    ├── upgrade_db.py         # General DB upgrade script
    ├── add_cost_column.py    # Adds cost_per_unit column
    ├── add_suppliers_table.py# Creates suppliers table
    └── README.md             # Scripts usage guide
```

---

## 🗄️ Database Schema

**`users`**
| Column | Type | Description |
|---|---|---|
| id | INTEGER PK | Auto-increment |
| username | TEXT UNIQUE | Login username |
| password | TEXT | Hashed password |
| email | TEXT | Email for alerts |
| email_alerts | INTEGER | 1 = enabled, 0 = disabled |
| created_at | TIMESTAMP | Account creation time |

**`products`**
| Column | Type | Description |
|---|---|---|
| id | INTEGER PK | Auto-increment |
| user_id | INTEGER FK | Owner user |
| name | TEXT | SKU name (unique per user) |
| category | TEXT | Product category |
| quantity | INTEGER | Current stock |
| reorder_level | INTEGER | Alert threshold |
| cost_per_unit | REAL | Unit cost |
| sales_count | INTEGER | Total units sold |
| supplier_id | INTEGER FK | Linked supplier |
| created_at | TIMESTAMP | Creation time |

**`stock_movements`**
| Column | Type | Description |
|---|---|---|
| id | INTEGER PK | Auto-increment |
| user_id | INTEGER FK | Owner user |
| product_name | TEXT | SKU name |
| movement_type | TEXT | `IN` or `OUT` |
| quantity | INTEGER | Units moved |
| timestamp | TIMESTAMP | Movement time |

**`suppliers`**
| Column | Type | Description |
|---|---|---|
| id | INTEGER PK | Auto-increment |
| user_id | INTEGER FK | Owner user |
| name | TEXT | Supplier name |
| contact_name | TEXT | Contact person |
| phone | TEXT | Phone number |
| email | TEXT | Email address |
| address | TEXT | Physical address |

---

## ⚙️ Setup & Installation

### 1. Clone the Repository

```bash
git clone https://github.com/Kan-06/Smart_ref.git
cd Smart_ref
```

### 2. Create a Virtual Environment

```bash
python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS/Linux
source .venv/bin/activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Initialize the Database

```bash
python database.py
```

### 5. (Optional) Configure Email Alerts

Set the following environment variables to enable email alerts:

```bash
# Windows (PowerShell)
$env:MAIL_USERNAME = "your_gmail@gmail.com"
$env:MAIL_PASSWORD = "your_gmail_app_password"
$env:MAIL_FROM     = "your_gmail@gmail.com"

# macOS/Linux
export MAIL_USERNAME="your_gmail@gmail.com"
export MAIL_PASSWORD="your_gmail_app_password"
export MAIL_FROM="your_gmail@gmail.com"
```

> **Note:** For Gmail, use an [App Password](https://myaccount.google.com/apppasswords), not your account password. 2-Step Verification must be enabled.

### 6. Run the Application

```bash
python app.py
```

Open your browser at: **http://localhost:5000**

---

## 🌐 Application Routes

| Method   | Route                    | Description                  |
| -------- | ------------------------ | ---------------------------- |
| GET      | `/`                      | Public landing page          |
| GET/POST | `/login`                 | User login                   |
| GET/POST | `/signup`                | New user registration        |
| GET      | `/logout`                | Logout & clear session       |
| GET      | `/dashboard`             | Main dashboard               |
| GET      | `/products`              | View all stock / SKUs        |
| GET/POST | `/add`                   | Add new SKU                  |
| GET/POST | `/edit/<name>`           | Edit existing SKU            |
| POST     | `/delete/<name>`         | Delete SKU                   |
| GET/POST | `/inbound`               | Record inbound stock         |
| GET/POST | `/outbound`              | Record outbound stock        |
| GET      | `/refill`                | Refill / low-stock dashboard |
| POST     | `/send-alert`            | Send low-stock email alert   |
| GET      | `/reports`               | Analytics reports            |
| GET/POST | `/suppliers`             | Supplier list & add          |
| GET/POST | `/suppliers/edit/<id>`   | Edit supplier                |
| POST     | `/suppliers/delete/<id>` | Delete supplier              |
| GET      | `/history`               | Stock movement history       |
| GET      | `/export`                | Download CSV export          |
| GET/POST | `/profile`               | User profile & settings      |

---

## 🔧 Tech Stack

| Layer      | Technology                    |
| ---------- | ----------------------------- |
| Backend    | Python 3, Flask 3.0           |
| Database   | SQLite (via `sqlite3`)        |
| Auth       | Werkzeug password hashing     |
| Email      | Python `smtplib` + Gmail SMTP |
| Frontend   | HTML5, CSS3, Vanilla JS       |
| Deployment | Gunicorn (Render / Linux)     |

---

## 🚢 Deployment (Render)

1. Push your code to GitHub
2. Create a new **Web Service** on [Render](https://render.com)
3. Set **Build Command**: `pip install -r requirements.txt`
4. Set **Start Command**: `gunicorn app:app`
5. Add environment variables: `SECRET_KEY`, `MAIL_USERNAME`, `MAIL_PASSWORD`, `MAIL_FROM`

---

## 📌 Stock Status Logic

| Status      | Condition                       |
| ----------- | ------------------------------- |
| 🟢 NORMAL   | `quantity > reorder_level`      |
| 🟡 LOW      | `quantity <= reorder_level`     |
| 🔴 CRITICAL | `quantity <= reorder_level / 2` |

---

## 🛡️ Security Notes

- All passwords are stored as **bcrypt hashes** (via Werkzeug)
- Session secrets are set via environment variables in production
- User data is fully isolated — no cross-user data leakage
- Only internal redirect paths are allowed after login (open-redirect prevention)

---

## 📄 License

This project is developed for academic and educational purposes.

---

_SmartRefill — Built with Flask & SQLite | February 2026_
