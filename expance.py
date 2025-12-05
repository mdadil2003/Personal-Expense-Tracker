"""
final_expense_tracker_part1.py
Part 1 of final application:
- Database wrapper (SQLite) with schema for multi-currency
- Migration helper for older schema
- Default currency rates (fallback)
- Live currency fetcher (open.er-api.com) with safe fallback
- Theme detection helper (Windows)
- Comments for viva/exam explanation
"""

import os
import sqlite3
import platform
from datetime import datetime, date, timedelta

# Optional libs (handled in main app)
try:
    import requests
    REQUESTS_AVAILABLE = True
except Exception:
    REQUESTS_AVAILABLE = False

# ---------------------------
# Constants
# ---------------------------
DB_NAME = "expenses.db"

# Default fallback currency rates (1 unit of currency -> INR)
# Use these if live fetch fails.
DEFAULT_RATES = {
    "INR": 1.0, "USD": 83.0, "EUR": 90.0, "GBP": 104.0, "AED": 22.6,
    "SAR": 22.15, "QAR": 22.8, "KWD": 270.0, "BHD": 220.0,
    "CAD": 61.0, "AUD": 55.0, "SGD": 62.0, "JPY": 0.56, "CNY": 11.5,
    "CHF": 95.5, "NZD": 50.0, "HKD": 10.7, "SEK": 7.9, "NOK": 8.0,
    "DKK": 12.1, "ZAR": 4.3, "PKR": 0.30, "BDT": 0.75, "LKR": 0.28,
    "IDR": 0.0053
}

# Currency list mapping for UI (Country – Currency code)
CURRENCY_LIST = {
    "India – INR": "INR",
    "United States – USD": "USD",
    "European Union – EUR": "EUR",
    "United Kingdom – GBP": "GBP",
    "United Arab Emirates – AED": "AED",
    "Saudi Arabia – SAR": "SAR",
    "Qatar – QAR": "QAR",
    "Kuwait – KWD": "KWD",
    "Bahrain – BHD": "BHD",
    "Canada – CAD": "CAD",
    "Australia – AUD": "AUD",
    "Singapore – SGD": "SGD",
    "Japan – JPY": "JPY",
    "China – CNY": "CNY",
    "Switzerland – CHF": "CHF",
    "New Zealand – NZD": "NZD",
    "Hong Kong – HKD": "HKD",
    "Sweden – SEK": "SEK",
    "Norway – NOK": "NOK",
    "Denmark – DKK": "DKK",
    "South Africa – ZAR": "ZAR",
    "Pakistan – PKR": "PKR",
    "Bangladesh – BDT": "BDT",
    "Sri Lanka – LKR": "LKR",
    "Indonesia – IDR": "IDR"
}

# ---------------------------
# Database wrapper class
# ---------------------------
class ExpenseDB:
    """
    Lightweight SQLite wrapper for transactions and budgets.
    - transactions stores original amount + currency + converted INR amount
    - budgets table stores monthly budgets (year, month unique)
    """

    def __init__(self, filename=DB_NAME):
        self.filename = filename
        # connect (will create file if not present)
        self.conn = sqlite3.connect(self.filename)
        self.cur = self.conn.cursor()
        self._create_tables()

    def _create_tables(self):
        """Create required tables if they don't exist (idempotent)."""
        # transactions: id, date, category, amount_original, currency, amount_in_inr, description, created_at
        self.cur.execute('''
            CREATE TABLE IF NOT EXISTS transactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT NOT NULL,
                category TEXT NOT NULL,
                amount_original REAL,
                currency TEXT,
                amount_in_inr REAL,
                description TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        # budgets table: unique per (year, month)
        self.cur.execute('''
            CREATE TABLE IF NOT EXISTS budgets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                year INTEGER NOT NULL,
                month INTEGER NOT NULL,
                amount REAL NOT NULL,
                UNIQUE(year, month)
            )
        ''')
        self.conn.commit()

    # --- CRUD for transactions ---
    def add_transaction(self, date_str, category, amount_original, currency, amount_in_inr, description=""):
        """Insert a transaction and return its id."""
        self.cur.execute('''
            INSERT INTO transactions (date, category, amount_original, currency, amount_in_inr, description)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (date_str, category, amount_original, currency, amount_in_inr, description))
        self.conn.commit()
        return self.cur.lastrowid

    def update_transaction(self, trans_id, date_str, category, amount_original, currency, amount_in_inr, description=""):
        """Update an existing transaction by id."""
        self.cur.execute('''
            UPDATE transactions
            SET date=?, category=?, amount_original=?, currency=?, amount_in_inr=?, description=?
            WHERE id=?
        ''', (date_str, category, amount_original, currency, amount_in_inr, description, trans_id))
        self.conn.commit()
        return self.cur.rowcount

    def delete_transaction(self, trans_id):
        """Delete by id."""
        self.cur.execute('DELETE FROM transactions WHERE id=?', (trans_id,))
        self.conn.commit()
        return self.cur.rowcount

    def get_all_transactions(self):
        """Return all transactions ordered by date desc."""
        self.cur.execute('''
            SELECT id, date, category, amount_original, currency, amount_in_inr, description
            FROM transactions
            ORDER BY date DESC
        ''')
        return self.cur.fetchall()

    def get_transactions_by_month(self, year, month):
        """Return transactions for given year/month (month is 1..12)."""
        start = f"{year}-{month:02d}-01"
        if month == 12:
            end = f"{year+1}-01-01"
        else:
            end = f"{year}-{month+1:02d}-01"
        self.cur.execute('''
            SELECT id, date, category, amount_original, currency, amount_in_inr, description
            FROM transactions
            WHERE date >= ? AND date < ?
            ORDER BY date DESC
        ''', (start, end))
        return self.cur.fetchall()

    def get_category_summary(self, year=None, month=None):
        """
        Return (category, SUM(amount_in_inr)) either for a given month or all time.
        Useful for reports and charts.
        """
        if year and month:
            start = f"{year}-{month:02d}-01"
            if month == 12:
                end = f"{year+1}-01-01"
            else:
                end = f"{year}-{month+1:02d}-01"
            self.cur.execute('''
                SELECT category, SUM(amount_in_inr) as total
                FROM transactions
                WHERE date >= ? AND date < ?
                GROUP BY category
                ORDER BY total DESC
            ''', (start, end))
        else:
            self.cur.execute('''
                SELECT category, SUM(amount_in_inr) as total
                FROM transactions
                GROUP BY category
                ORDER BY total DESC
            ''')
        return self.cur.fetchall()

    def get_totals_for_range(self, start_date_str, end_date_str):
        """Return sum(amount_in_inr) for date range [start_date, end_date)."""
        self.cur.execute('''
            SELECT SUM(amount_in_inr) FROM transactions WHERE date >= ? AND date < ?
        ''', (start_date_str, end_date_str))
        row = self.cur.fetchone()
        return float(row[0]) if row and row[0] else 0.0

    # --- Budget table helpers ---
    def get_budget(self, year, month):
        self.cur.execute('SELECT amount FROM budgets WHERE year=? AND month=?', (year, month))
        r = self.cur.fetchone()
        return r[0] if r else None

    def set_budget(self, year, month, amount):
        if self.get_budget(year, month) is None:
            self.cur.execute('INSERT INTO budgets (year, month, amount) VALUES (?, ?, ?)', (year, month, amount))
        else:
            self.cur.execute('UPDATE budgets SET amount=? WHERE year=? AND month=?', (amount, year, month))
        self.conn.commit()

    def close(self):
        self.conn.close()

# ---------------------------
# Migration helper for older DBs
# ---------------------------
def migrate_old_schema(db_name=DB_NAME):
    """
    Attempt to migrate older databases that only had 'amount' column.
    This helper:
    - Adds amount_original, currency, amount_in_inr columns if missing.
    - Copies legacy 'amount' column to amount_original/amount_in_inr if present.
    This helps users keep old data when switching to new version.
    """
    if not os.path.exists(db_name):
        return "no_db"

    conn = sqlite3.connect(db_name)
    cur = conn.cursor()
    cur.execute("PRAGMA table_info(transactions)")
    cols = [c[1] for c in cur.fetchall()]

    changed = False
    # Add new columns if missing
    if "amount_original" not in cols:
        cur.execute("ALTER TABLE transactions ADD COLUMN amount_original REAL")
        changed = True
    if "currency" not in cols:
        cur.execute("ALTER TABLE transactions ADD COLUMN currency TEXT DEFAULT 'INR'")
        changed = True
    if "amount_in_inr" not in cols:
        cur.execute("ALTER TABLE transactions ADD COLUMN amount_in_inr REAL")
        changed = True

    # If previous schema had 'amount', copy into new columns
    if "amount" in cols:
        cur.execute("SELECT id, amount FROM transactions")
        rows = cur.fetchall()
        for r in rows:
            tid, old_amount = r
            cur.execute("""
                UPDATE transactions
                SET amount_original=?, currency=?, amount_in_inr=?
                WHERE id=?
            """, (old_amount, "INR", old_amount, tid))
        changed = True

    conn.commit()
    conn.close()
    return "migrated" if changed else "ok"

# ---------------------------
# Currency fetcher
# ---------------------------
def fetch_live_rates(base_currency="INR"):
    """
    Fetch live rates from open.er-api.com for the given base currency.
    Returns dict: currency_code -> rate (1 unit of currency -> INR), or None on failure.
    Note: API may provide rates as 1 base_currency = X target_currency.
    For base=INR, API returns 1 INR = rates[CUR] units of CUR.
    To get 1 CUR -> INR, we invert: 1/CUR_rate.
    """
    if not REQUESTS_AVAILABLE:
        return None
    url = f"https://open.er-api.com/v6/latest/{base_currency}"
    try:
        resp = requests.get(url, timeout=8)
        data = resp.json()
        if isinstance(data, dict) and data.get("result") == "success":
            rates = data.get("rates", {})
            # Construct mapping: currency -> 1 unit currency expressed in base_currency (INR)
            converted = {}
            for cur_code, val in rates.items():
                # val: how many units of cur_code in 1 base (i.e., 1 INR = val CUR).
                # So 1 CUR = 1 / val INR
                try:
                    if val and float(val) != 0:
                        converted[cur_code] = 1.0 / float(val)
                except Exception:
                    continue
            return converted
        else:
            return None
    except Exception:
        return None

# ---------------------------
# Theme detection (Windows)
# ---------------------------
def detect_windows_theme():
    """
    Try to detect Windows system theme for apps (light/dark).
    Returns: "light", "dark", or None (if unsupported).
    """
    if platform.system() != "Windows":
        return None
    try:
        import winreg
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                             r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize")
        value, _ = winreg.QueryValueEx(key, "AppsUseLightTheme")
        winreg.CloseKey(key)
        return "light" if value == 1 else "dark"
    except Exception:
        return None

# ---------------------------
# Quick demo / self-test when run directly
# ---------------------------
if __name__ == "__main__":
    print("Part 1 check: Running DB creation and migration test.")
    mig = migrate_old_schema(DB_NAME)
    print("Migration result:", mig)
    db = ExpenseDB(DB_NAME)
    print("DB tables created. Sample counts:")
    print("Transactions:", len(db.get_all_transactions()))
    print("Fetching live rates (if requests available)...")
    rates = fetch_live_rates() if REQUESTS_AVAILABLE else None
    print("Live rates fetched:", bool(rates))
    db.close()
    print("Part 1 OK. Save this file and await Part 2 (UI & main app).")
