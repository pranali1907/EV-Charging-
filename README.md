# ChargeLive - Smart EV Charging Station Platform

ChargeLive is a production-ready, feature-rich web application built on Flask, PostgreSQL, and Bootstrap for EV Charging Station Discovery, Charger Reservation, and Transaction Settlement. It features an interactive, geocoded map search interface, dynamic booking slot generation with overlap checks, real-time energy/cost calculators, a demo payment checkout gateway, printable invoice receipts, booking history portals for users, and a secure administration panel.

---

## Features

### 🔍 Interactive Discovery & Search
- **Leaflet & OpenStreetMap Integration**: Displays charging stations on an interactive map.
- **Intelligent Search Engine**:
  - Automatically identifies cities (Pune, Sangli, Kolhapur, Mumbai) and returns precise results.
  - Supports natural query strings (e.g. `"charging station in Pune"`, `"EV near Mumbai"`, `"LECCS near Sangli"`).
  - Prioritizes exact city matches and filters markers, counts, and lists immediately.
  - Auto-selects input text on click to allow frictionless searching.

### 📅 Smart Charger Booking Engine
- **Manual Start Time Inputs**: Replaces generic time slot dropdowns with a manual text field (`hh:mm AM/PM` format).
- **Auto End Time Math**: Automatically computes and locks the read-only End Time using Javascript Date baseline arithmetic on duration changes.
- **Dynamic Cost & Energy Calculators**: Live-renders calculations:
  - **Estimated Energy (kWh)** = `Charger Power (kW) * (Duration / 60)`
  - **Estimated Cost (Rs)** = `Estimated Energy * Price per kWh`
- **Past-Time & Overlaps Rejection**: Blocks past hours for today's date client-side and backend, and prevents conflicting reservations on the same charger.

### 💳 Transactional Settlement & Invoices
- **Demo Checkout Portal**: Supports UPI QR validation, Card credentials validation, Net Banking dropdowns, linked ChargeLive Wallet payments, and Cash holds.
- **Transactional Animations**: Integrates faked checkout spinners and success checkmarks.
- **Printable Invoice Receipts**: Auto-generates unique invoices (`INV-YYYY-bookingID`), Transaction IDs, brand metadata, and mobile validation QR codes with specific `@media print` layout formatting.
- **Booking History**: Allows users to check their historical reservations sorted by **Upcoming**, **Completed**, and **Cancelled** states.

### 🛡️ Administration Dashboard
- **Financial Analytics**: Tracks Total Revenue, Upcoming Reservations, Completed Sessions, and Cancelled Sessions.
- **Station & Charger CRUD**: Facilitates management of operating hours, geocoding details, power ratings, connector types, and IoT-mapping.
- **Transactions Ledger**: Displays detailed logs of all payments, transaction IDs, amounts, and dates.

---

## Folder Structure

```text
ChargeLive/
|-- app.py                   # Application factory initialization
|-- config.py                # Environment configurations (supports DATABASE_URL)
|-- requirements.txt         # Production Python packages
|-- Procfile                 # Production WSGI server runner
|-- runtime.txt              # Specifies active python engine version
|-- README.md                # System documentation
|-- .env.example             # Template for variables setup
|-- admin/                   # Administration blueprint routes & helpers
|-- database/                # Database engine setup
|-- models/                  # SQLAlchemy models (Station, Charger, Booking, Payment, etc.)
|-- routes/                  # Client-facing routing blueprints (Home, Book)
|-- services/                # Database service layer abstractions
|-- static/                  # Static styles, javascript, and images
`-- templates/               # Jinja2 template components & views
```

---

## Technical Stack

- **Backend**: Python, Flask, Flask-SQLAlchemy, Flask-Migrate
- **Database**: PostgreSQL (psycopg2)
- **Frontend**: Bootstrap 5, Vanilla JavaScript, Leaflet Map Library, Font Awesome, Bootstrap Icons
- **Production Server**: Gunicorn

---

## Installation & Setup

### 1. Clone & Set Up Environment
```powershell
python -m venv myenv
.\myenv\Scripts\activate
pip install -r requirements.txt
```

### 2. Configure Environment Variables
Copy `.env.example` to `.env` and fill in your postgres credentials or database URL:
```env
FLASK_ENV=production
SECRET_KEY=generate-a-secure-random-secret-key
PORT=5000
DATABASE_URL=postgresql://postgres:password@localhost:5432/chargelive_db
ADMIN_USERNAME=admin
ADMIN_PASSWORD=pbkdf2:sha256:your-generated-password-hash
```

### 3. Initialize Database
Ensure your PostgreSQL database `chargelive_db` exists, then run migrations:
```powershell
flask db upgrade
```

### 4. Run Locally
```powershell
python app.py
```
Open [http://127.0.0.1:5000](http://127.0.0.1:5000) to view the homepage.

---

## Deployment Steps

This project is fully ready for zero-downtime deployment on platforms like Render, Railway, or PythonAnywhere:

1. **Database Set Up**: Provision a managed PostgreSQL instance and retrieve the Connection URI.
2. **Environment Setup**: Add `DATABASE_URL`, `SECRET_KEY`, `ADMIN_USERNAME`, and `ADMIN_PASSWORD` to your platform's environment variables.
3. **Execution Command**: The `Procfile` is pre-configured to run Gunicorn. The platform will automatically spin up the server:
   ```bash
   gunicorn app:app
   ```
4. **Python Version**: Platforms reading `runtime.txt` will automatically use Python 3.10.12.
