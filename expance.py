"""
Personal Expense Tracker – Multi-Currency (INR-focused)

Features:
- Python desktop app using Tkinter
- SQLite database backend
- Multi-currency: store original amount + currency + INR equivalent
- Live currency rates via open.er-api.com (optional, with safe fallback)
- Add / Edit / Delete transactions
- Filter by month/year
- Search by text
- Dashboard: Today / This Week / This Month + Top Categories
- Monthly Budget (with progress info)
- CSV & PDF export
- Matplotlib charts (Pie, Bar, Daily Line, Stats)
- Scrollable left panel and table
- Light/Dark theme (follows system, with toggle)
"""

import os
import csv
import sqlite3
import platform
from datetime import datetime, timedelta, date
from collections import defaultdict

# --- GUI imports ---
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from tkcalendar import DateEntry

# --- Charts ---
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

# --- Optional libraries ---
try:
    import requests
    REQUESTS_AVAILABLE = True
except Exception:
    REQUESTS_AVAILABLE = False

try:
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.styles import getSampleStyleSheet
    REPORTLAB_AVAILABLE = True
except Exception:
    REPORTLAB_AVAILABLE = False


# =========================
#  CONSTANTS / CURRENCY DATA
# =========================

DB_NAME = "expenses.db"

# Fallback currency rates (approx) – 1 unit currency => INR
DEFAULT_RATES = {
    "INR": 1.0, "USD": 83.0, "EUR": 90.0, "GBP": 104.0, "AED": 22.6,
    "SAR": 22.15, "QAR": 22.8, "KWD": 270.0, "BHD": 220.0,
    "CAD": 61.0, "AUD": 55.0, "SGD": 62.0, "JPY": 0.56, "CNY": 11.5,
    "CHF": 95.5, "NZD": 50.0, "HKD": 10.7, "SEK": 7.9, "NOK": 8.0,
    "DKK": 12.1, "ZAR": 4.3, "PKR": 0.30, "BDT": 0.75, "LKR": 0.28,
    "IDR": 0.0053
}

# Country – CurrencyCode labels for dropdown
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


# =========================
#  DATABASE LAYER
# =========================

class ExpenseDB:
    """
    SQLite wrapper for expense tracker.
    Stores:
      - original amount
      - currency code
      - amount_in_inr
    Also stores monthly budgets.
    """

    def __init__(self, filename=DB_NAME):
        self.filename = filename
        self.conn = sqlite3.connect(self.filename)
        self.cur = self.conn.cursor()
        self._create_tables()

    def _create_tables(self):
        """Create tables if not already present."""
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

    # --- Transactions ---

    def add_transaction(self, date_str, category, amount_original, currency, amount_in_inr, description=""):
        """Insert new transaction and return new ID."""
        self.cur.execute('''
            INSERT INTO transactions (date, category, amount_original, currency, amount_in_inr, description)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (date_str, category, amount_original, currency, amount_in_inr, description))
        self.conn.commit()
        return self.cur.lastrowid

    def update_transaction(self, trans_id, date_str, category, amount_original, currency, amount_in_inr, description=""):
        """Update an existing transaction."""
        self.cur.execute('''
            UPDATE transactions
            SET date=?, category=?, amount_original=?, currency=?, amount_in_inr=?, description=?
            WHERE id=?
        ''', (date_str, category, amount_original, currency, amount_in_inr, description, trans_id))
        self.conn.commit()
        return self.cur.rowcount

    def delete_transaction(self, trans_id):
        """Delete by ID."""
        self.cur.execute('DELETE FROM transactions WHERE id=?', (trans_id,))
        self.conn.commit()
        return self.cur.rowcount

    def get_all_transactions(self):
        """Return all transactions sorted by date desc."""
        self.cur.execute('''
            SELECT id, date, category, amount_original, currency, amount_in_inr, description
            FROM transactions
            ORDER BY date DESC
        ''')
        return self.cur.fetchall()

    def get_transactions_by_month(self, year, month):
        """Return monthly transactions."""
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
        """Return category-wise sum of amount_in_inr."""
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
        """Return sum of amount_in_inr for [start, end)."""
        self.cur.execute('''
            SELECT SUM(amount_in_inr) FROM transactions
            WHERE date >= ? AND date < ?
        ''', (start_date_str, end_date_str))
        row = self.cur.fetchone()
        return float(row[0]) if row and row[0] else 0.0

    # --- Budget ---

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


# =========================
#  MIGRATION HELPER
# =========================

def migrate_old_schema(db_name=DB_NAME):
    """
    If an older DB schema exists (with only 'amount' column),
    this will:
      - Add amount_original, currency, amount_in_inr columns.
      - Copy legacy 'amount' => amount_original & amount_in_inr.
    Ensures older data is not lost.
    """
    if not os.path.exists(db_name):
        return "no_db"

    conn = sqlite3.connect(db_name)
    cur = conn.cursor()
    cur.execute("PRAGMA table_info(transactions)")
    cols = [c[1] for c in cur.fetchall()]

    changed = False
    if "amount_original" not in cols:
        cur.execute("ALTER TABLE transactions ADD COLUMN amount_original REAL")
        changed = True
    if "currency" not in cols:
        cur.execute("ALTER TABLE transactions ADD COLUMN currency TEXT DEFAULT 'INR'")
        changed = True
    if "amount_in_inr" not in cols:
        cur.execute("ALTER TABLE transactions ADD COLUMN amount_in_inr REAL")
        changed = True

    if "amount" in cols:
        cur.execute("SELECT id, amount FROM transactions")
        rows = cur.fetchall()
        for tid, old_amount in rows:
            cur.execute('''
                UPDATE transactions
                SET amount_original=?, currency=?, amount_in_inr=?
                WHERE id=?
            ''', (old_amount, "INR", old_amount, tid))
        changed = True

    conn.commit()
    conn.close()
    return "migrated" if changed else "ok"


# =========================
#  CURRENCY RATES (LIVE)
# =========================

def fetch_live_rates(base="INR"):
    """
    Fetch live rates from open.er-api.com.
    It returns mapping:
        currency_code -> (1 currency unit => INR)
    When base=INR, API returns:
        1 INR = X units of CUR
    So 1 CUR = 1 / X INR
    """
    if not REQUESTS_AVAILABLE:
        return None

    url = f"https://open.er-api.com/v6/latest/{base}"
    try:
        resp = requests.get(url, timeout=8)
        data = resp.json()
        if data.get("result") != "success":
            return None
        rates = data.get("rates", {})
        converted = {}
        for cur_code, val in rates.items():
            try:
                val = float(val)
                if val != 0:
                    converted[cur_code] = 1.0 / val
            except Exception:
                continue
        return converted
    except Exception:
        return None


# =========================
#  THEME DETECTION (WINDOWS)
# =========================

def detect_windows_theme():
    """Detect Windows app theme: returns 'light' or 'dark' or None."""
    if platform.system() != "Windows":
        return None
    try:
        import winreg
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize"
        )
        value, _ = winreg.QueryValueEx(key, "AppsUseLightTheme")
        winreg.CloseKey(key)
        return "light" if value == 1 else "dark"
    except Exception:
        return None


# =========================
#  MAIN APPLICATION CLASS
# =========================

class ExpenseTrackerApp:
    """
    Tkinter GUI application.
    - Left panel: dashboard, add/edit form, budget, filters
    - Right panel: transaction table
    """

    def __init__(self, root):
        self.root = root
        self.root.title("Personal Expense Tracker — Multi-Currency (INR)")
        self.root.geometry("1200x720")
        self.root.minsize(1000, 600)

        # migrate old schema first
        migrate_old_schema(DB_NAME)

        # DB + currency setup
        self.db = ExpenseDB(DB_NAME)
        self.currency_list = CURRENCY_LIST.copy()
        self.currency_rates = DEFAULT_RATES.copy()

        # edit mode state
        self.editing_id = None

        # theme config
        sys_theme = detect_windows_theme()
        self.theme_light = {
            "root_bg": "#f0f0f0",
            "panel_bg": "white",
            "title_bg": "#1155CC",
            "title_fg": "white",
            "accent": "#2E379A",
            "success": "#06A77D",
            "danger": "#D90368",
            "text": "#222"
        }
        self.theme_dark = {
            "root_bg": "#1e1e1e",
            "panel_bg": "#2b2b2b",
            "title_bg": "#0b3a66",
            "title_fg": "white",
            "accent": "#4C5CEB",
            "success": "#13C48B",
            "danger": "#F2557A",
            "text": "#ddd"
        }
        self.current_theme = self.theme_light if sys_theme != "dark" else self.theme_dark

        # build UI
        self.build_ui()
        self.apply_theme()

        # fetch live currency rates (if possible)
        live = fetch_live_rates("INR")
        if live:
            self.currency_rates.update(live)

        # initial refresh
        self.refresh_all()

    # -----------------
    #  UI CONSTRUCTION
    # -----------------

    def build_ui(self):
        # Title bar
        self.title_frame = tk.Frame(self.root, bg=self.current_theme["title_bg"], height=60)
        self.title_frame.pack(fill="x")
        self.title_frame.pack_propagate(False)

        tk.Label(
            self.title_frame,
            text="  Personal Expense Tracker (Multi-Currency, INR)",
            bg=self.current_theme["title_bg"],
            fg=self.current_theme["title_fg"],
            font=("Arial", 18, "bold")
        ).pack(side="left", padx=10)

        # Right side of title: theme toggle, export, search
        self.theme_btn = tk.Button(self.title_frame, text="Toggle Theme", command=self.toggle_theme)
        self.theme_btn.pack(side="right", padx=6, pady=10)

        export_frame = tk.Frame(self.title_frame, bg=self.current_theme["title_bg"])
        export_frame.pack(side="right", padx=6)
        tk.Button(export_frame, text="Export CSV", command=self.export_csv).pack(side="left", padx=4)
        tk.Button(export_frame, text="Export PDF", command=self.export_pdf).pack(side="left", padx=4)

        search_frame = tk.Frame(self.title_frame, bg=self.current_theme["title_bg"])
        search_frame.pack(side="right", padx=8)
        tk.Label(search_frame, text="Search:", bg=self.current_theme["title_bg"], fg="white").pack(side="left")
        self.search_var = tk.StringVar()
        self.search_entry = tk.Entry(search_frame, textvariable=self.search_var, width=22)
        self.search_entry.pack(side="left", padx=4)
        tk.Button(search_frame, text="Search", command=self.search).pack(side="left", padx=4)
        tk.Button(search_frame, text="Clear", command=self.clear_search).pack(side="left", padx=2)

        # Main area
        self.main_frame = tk.Frame(self.root, bg=self.current_theme["root_bg"])
        self.main_frame.pack(fill="both", expand=True, padx=8, pady=8)

        # LEFT PANEL (scrollable)
        left_outer = tk.Frame(self.main_frame, width=360, bg=self.current_theme["panel_bg"])
        left_outer.pack(side="left", fill="y", padx=(0, 8))
        left_outer.pack_propagate(False)

        left_canvas = tk.Canvas(left_outer, bg=self.current_theme["panel_bg"], highlightthickness=0)
        left_canvas.pack(side="left", fill="both", expand=True)
        left_scroll = ttk.Scrollbar(left_outer, orient="vertical", command=left_canvas.yview)
        left_scroll.pack(side="right", fill="y")
        left_canvas.configure(yscrollcommand=left_scroll.set)

        self.left_frame = tk.Frame(left_canvas, bg=self.current_theme["panel_bg"])
        left_canvas.create_window((0, 0), window=self.left_frame, anchor="nw")

        def _on_left_config(event):
            left_canvas.configure(scrollregion=left_canvas.bbox("all"))

        self.left_frame.bind("<Configure>", _on_left_config)

        # mouse wheel for left panel
        def _on_mousewheel(event):
            left_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

        self.left_frame.bind("<Enter>", lambda e: self.left_frame.bind_all("<MouseWheel>", _on_mousewheel))
        self.left_frame.bind("<Leave>", lambda e: self.left_frame.unbind_all("<MouseWheel>"))

        # Dashboard box
        dash_box = ttk.LabelFrame(self.left_frame, text="Dashboard", padding=(10, 8))
        dash_box.pack(fill="x", padx=8, pady=8)

        self.dash_today = tk.Label(dash_box, text="Today: ₹0.00", anchor="w")
        self.dash_today.pack(fill="x")
        self.dash_week = tk.Label(dash_box, text="This Week: ₹0.00", anchor="w")
        self.dash_week.pack(fill="x")
        self.dash_month = tk.Label(dash_box, text="This Month: ₹0.00", anchor="w")
        self.dash_month.pack(fill="x")

        tk.Label(dash_box, text="Top Categories:", anchor="w").pack(fill="x", pady=(6, 0))
        self.dash_top = tk.Label(dash_box, text="-", anchor="w", justify="left")
        self.dash_top.pack(fill="x")

        # Add/Edit form
        form_box = ttk.LabelFrame(self.left_frame, text="Add / Edit Transaction", padding=(10, 10))
        form_box.pack(fill="x", padx=8, pady=8)

        tk.Label(form_box, text="Date:").grid(row=0, column=0, sticky="w", pady=4)
        self.date_entry = DateEntry(form_box, width=18, date_pattern="yyyy-mm-dd")
        self.date_entry.grid(row=0, column=1, sticky="e", pady=4)

        tk.Label(form_box, text="Category:").grid(row=1, column=0, sticky="w", pady=4)
        self.category_var = tk.StringVar()
        categories = ["Food", "Transport", "Entertainment", "Shopping", "Bills",
                      "Healthcare", "Education", "Other"]
        self.category_combo = ttk.Combobox(
            form_box,
            values=categories,
            textvariable=self.category_var,
            width=16,
            state="readonly"
        )
        self.category_combo.grid(row=1, column=1, sticky="e", pady=4)
        self.category_combo.set("Food")

        tk.Label(form_box, text="Amount:").grid(row=2, column=0, sticky="w", pady=4)
        self.amount_entry = tk.Entry(form_box, width=18)
        self.amount_entry.grid(row=2, column=1, sticky="e", pady=4)

        tk.Label(form_box, text="Currency:").grid(row=3, column=0, sticky="w", pady=4)
        self.currency_var = tk.StringVar()
        self.currency_combo = ttk.Combobox(
            form_box,
            values=list(self.currency_list.keys()),
            textvariable=self.currency_var,
            width=18,
            state="readonly"
        )
        self.currency_combo.grid(row=3, column=1, sticky="e", pady=4)
        self.currency_combo.set("India – INR")

        tk.Label(form_box, text="Description:").grid(row=4, column=0, sticky="w", pady=4)
        self.desc_entry = tk.Entry(form_box, width=20)
        self.desc_entry.grid(row=4, column=1, sticky="e", pady=4)

        btn_box = tk.Frame(form_box)
        btn_box.grid(row=5, column=0, columnspan=2, pady=8)
        self.add_btn = tk.Button(btn_box, text="Add Transaction", command=self.add_or_update_transaction)
        self.add_btn.pack(side="left", padx=4)
        tk.Button(btn_box, text="Clear", command=self.clear_inputs).pack(side="left", padx=4)

        # Budget box
        budget_box = ttk.LabelFrame(self.left_frame, text="Monthly Budget", padding=(10, 10))
        budget_box.pack(fill="x", padx=8, pady=8)

        tk.Label(budget_box, text="Month:").grid(row=0, column=0, sticky="w")
        self.budget_month = tk.Spinbox(budget_box, from_=1, to=12, width=6)
        self.budget_month.grid(row=0, column=1)

        tk.Label(budget_box, text="Year:").grid(row=1, column=0, sticky="w", pady=4)
        self.budget_year = tk.Spinbox(budget_box, from_=2020, to=2035, width=6)
        self.budget_year.grid(row=1, column=1, pady=4)

        tk.Label(budget_box, text="Amount (₹):").grid(row=2, column=0, sticky="w", pady=4)
        self.budget_entry = tk.Entry(budget_box, width=12)
        self.budget_entry.grid(row=2, column=1, sticky="e", pady=4)

        tk.Button(budget_box, text="Set Budget", command=self.set_budget).grid(
            row=3, column=0, columnspan=2, pady=6
        )
        self.budget_label = tk.Label(budget_box, text="No budget set")
        self.budget_label.grid(row=4, column=0, columnspan=2)

        # Filters box
        filter_box = ttk.LabelFrame(self.left_frame, text="Filters & Actions", padding=(10, 10))
        filter_box.pack(fill="x", padx=8, pady=8)

        tk.Label(filter_box, text="Month:").grid(row=0, column=0, sticky="w")
        self.filter_month = tk.Spinbox(filter_box, from_=1, to=12, width=6)
        self.filter_month.grid(row=0, column=1)

        tk.Label(filter_box, text="Year:").grid(row=1, column=0, sticky="w", pady=4)
        self.filter_year = tk.Spinbox(filter_box, from_=2020, to=2035, width=6)
        self.filter_year.grid(row=1, column=1, pady=4)

        tk.Button(filter_box, text="View Month", command=self.view_month).grid(
            row=2, column=0, pady=6, sticky="ew"
        )
        tk.Button(filter_box, text="View All", command=self.refresh_all).grid(
            row=2, column=1, pady=6, sticky="ew"
        )
        tk.Button(filter_box, text="Show Report", command=self.show_monthly_report).grid(
            row=3, column=0, columnspan=2, pady=6, sticky="ew"
        )
        tk.Button(filter_box, text="Visualize", command=self.show_visualization).grid(
            row=4, column=0, columnspan=2, pady=6, sticky="ew"
        )
        tk.Button(filter_box, text="Delete Selected", command=self.delete_selected).grid(
            row=5, column=0, columnspan=2, pady=6, sticky="ew"
        )

        # RIGHT PANEL – Transaction table
        self.build_right_panel()

    def build_right_panel(self):
        right_outer = tk.Frame(self.main_frame, bg=self.current_theme["panel_bg"])
        right_outer.pack(side="right", fill="both", expand=True)

        tk.Label(
            right_outer,
            text="Transaction History",
            font=("Arial", 14, "bold"),
            bg=self.current_theme["panel_bg"],
            fg=self.current_theme["text"]
        ).pack(pady=8)

        table_frame = tk.Frame(right_outer)
        table_frame.pack(fill="both", expand=True, padx=6, pady=6)

        self.tree = ttk.Treeview(
            table_frame,
            columns=(
                "ID", "Date", "Category", "Amount_Original",
                "Currency", "Amount_INR", "Description"
            ),
            show="headings"
        )
        vsb = ttk.Scrollbar(table_frame, orient="vertical", command=self.tree.yview)
        hsb = ttk.Scrollbar(table_frame, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        vsb.pack(side="right", fill="y")
        hsb.pack(side="bottom", fill="x")
        self.tree.pack(fill="both", expand=True)

        self.tree.heading("ID", text="ID")
        self.tree.heading("Date", text="Date")
        self.tree.heading("Category", text="Category")
        self.tree.heading("Amount_Original", text="Original Amount")
        self.tree.heading("Currency", text="Currency")
        self.tree.heading("Amount_INR", text="Amount (₹)")
        self.tree.heading("Description", text="Description")

        self.tree.column("ID", width=50, anchor="center")
        self.tree.column("Date", width=110, anchor="center")
        self.tree.column("Category", width=140, anchor="center")
        self.tree.column("Amount_Original", width=120, anchor="e")
        self.tree.column("Currency", width=80, anchor="center")
        self.tree.column("Amount_INR", width=120, anchor="e")
        self.tree.column("Description", width=360, anchor="w")

        # double-click row => edit that row
        self.tree.bind("<Double-1>", self.on_tree_double_click)

    # -----------------
    #  THEME
    # -----------------

    def apply_theme(self):
        t = self.current_theme
        self.root.configure(bg=t["root_bg"])
        self.main_frame.configure(bg=t["root_bg"])
        self.title_frame.configure(bg=t["title_bg"])

    def toggle_theme(self):
        self.current_theme = self.theme_dark if self.current_theme == self.theme_light else self.theme_light
        self.apply_theme()

    # -----------------
    #  FORM / CRUD
    # -----------------

    def clear_inputs(self):
        """Reset form and exit edit mode (if active)."""
        try:
            self.date_entry.set_date(date.today())
        except Exception:
            pass

        self.category_combo.set("Food")
        self.amount_entry.delete(0, tk.END)
        self.desc_entry.delete(0, tk.END)
        self.currency_combo.set("India – INR")

        self.editing_id = None
        self.add_btn.configure(text="Add Transaction")

    def add_or_update_transaction(self):
        """Handles both Add and Update depending on self.editing_id."""

        # date
        try:
            date_str = self.date_entry.get_date().strftime("%Y-%m-%d")
        except Exception:
            date_str = self.date_entry.get()

        category = self.category_var.get()
        desc = self.desc_entry.get().strip()

        amt_text = self.amount_entry.get().strip()
        if not amt_text:
            messagebox.showerror("Input error", "Please enter amount.")
            return
        try:
            amount_original = float(amt_text)
        except ValueError:
            messagebox.showerror("Input error", "Amount must be a number.")
            return
        if amount_original <= 0:
            messagebox.showerror("Input error", "Amount must be positive.")
            return

        # currency
        label = self.currency_var.get()
        currency_code = self.currency_list.get(label, "INR")
        rate = self.currency_rates.get(currency_code, 1.0)
        amount_in_inr = amount_original * rate

        if self.editing_id:
            # update existing
            changed = self.db.update_transaction(
                self.editing_id, date_str, category, amount_original,
                currency_code, amount_in_inr, desc
            )
            if changed:
                messagebox.showinfo("Updated", "Transaction updated successfully.")
            else:
                messagebox.showinfo("Updated", "No changes.")
            self.editing_id = None
            self.add_btn.configure(text="Add Transaction")
        else:
            # add new
            self.db.add_transaction(date_str, category, amount_original, currency_code, amount_in_inr, desc)
            messagebox.showinfo("Added", f"Transaction added ({currency_code} → ₹{amount_in_inr:.2f})")

        self.clear_inputs()
        self.refresh_all()

    def populate_tree(self, rows):
        """Fill TreeView with list of rows."""
        for item in self.tree.get_children():
            self.tree.delete(item)
        for r in rows:
            self.tree.insert(
                "", "end",
                values=(
                    r[0],
                    r[1],
                    r[2],
                    f"{(r[3] or 0):.2f}",
                    r[4] or "INR",
                    f"₹{(r[5] or 0):.2f}",
                    r[6] or ""
                )
            )

    def refresh_all(self):
        """Refresh table, dashboard, budget progress."""
        rows = self.db.get_all_transactions()
        self.populate_tree(rows)
        self.update_dashboard()
        self.update_budget_progress()

    def view_month(self):
        """Filter by selected month/year from left filter box."""
        try:
            year = int(self.filter_year.get())
            month = int(self.filter_month.get())
        except Exception:
            messagebox.showerror("Filter error", "Enter valid month and year.")
            return
        rows = self.db.get_transactions_by_month(year, month)
        self.populate_tree(rows)
        self.update_dashboard()
        self.update_budget_progress()

    def on_tree_double_click(self, event):
        """Double-click row => load row into form for editing."""
        sel = self.tree.selection()
        if not sel:
            return
        vals = self.tree.item(sel[0])["values"]
        trans_id = vals[0]

        # get transaction by ID from DB
        all_rows = self.db.get_all_transactions()
        record = next((r for r in all_rows if r[0] == trans_id), None)
        if not record:
            return

        self.editing_id = record[0]
        # date
        try:
            self.date_entry.set_date(datetime.strptime(record[1], "%Y-%m-%d").date())
        except Exception:
            pass

        self.category_combo.set(record[2])
        self.amount_entry.delete(0, tk.END)
        self.amount_entry.insert(0, str(record[3] or ""))

        # currency
        currency_code = record[4] or "INR"
        label = next((k for k, v in self.currency_list.items() if v == currency_code), "India – INR")
        self.currency_combo.set(label)

        self.desc_entry.delete(0, tk.END)
        if record[6]:
            self.desc_entry.insert(0, record[6])

        self.add_btn.configure(text="Update Transaction")

    def delete_selected(self):
        """Delete selected row from TreeView and DB."""
        sel = self.tree.selection()
        if not sel:
            messagebox.showwarning("Select", "Please select a transaction to delete.")
            return
        vals = self.tree.item(sel[0])["values"]
        tid = vals[0]
        if messagebox.askyesno("Confirm", f"Delete transaction ID {tid}?"):
            self.db.delete_transaction(tid)
            self.refresh_all()

    # -----------------
    #  DASHBOARD / BUDGET
    # -----------------

    def update_dashboard(self):
        """Update Today / Week / Month + top categories panel."""
        today = date.today()

        # Today
        start_today = today.strftime("%Y-%m-%d")
        end_today = (today + timedelta(days=1)).strftime("%Y-%m-%d")

        # Week (Monday to Sunday)
        start_week_date = today - timedelta(days=today.weekday())
        start_week = start_week_date.strftime("%Y-%m-%d")
        end_week = (start_week_date + timedelta(days=7)).strftime("%Y-%m-%d")

        # Month
        year = today.year
        month = today.month
        start_month = f"{year}-{month:02d}-01"
        if month == 12:
            end_month = f"{year+1}-01-01"
        else:
            end_month = f"{year}-{month+1:02d}-01"

        today_total = self.db.get_totals_for_range(start_today, end_today)
        week_total = self.db.get_totals_for_range(start_week, end_week)
        month_total = self.db.get_totals_for_range(start_month, end_month)

        self.dash_today.configure(text=f"Today: ₹{today_total:.2f}")
        self.dash_week.configure(text=f"This Week: ₹{week_total:.2f}")
        self.dash_month.configure(text=f"This Month: ₹{month_total:.2f}")

        # top categories current month
        cats = self.db.get_category_summary(year, month)
        txt = ""
        for c, a in cats[:5]:
            txt += f"{c}: ₹{a:.2f}\n"
        self.dash_top.configure(text=txt.strip() or "No data")

    def set_budget(self):
        """Read month/year/amount and save monthly budget."""
        try:
            year = int(self.budget_year.get())
            month = int(self.budget_month.get())
            amount = float(self.budget_entry.get())
        except Exception:
            messagebox.showerror("Input", "Enter valid budget, month and year.")
            return
        if amount <= 0:
            messagebox.showerror("Input", "Budget must be positive.")
            return
        self.db.set_budget(year, month, amount)
        messagebox.showinfo("Budget", "Budget saved.")
        self.update_budget_progress()

    def update_budget_progress(self):
        """Show 'Budget: X, Spent: Y (Z%)' for selected or current month."""
        try:
            year = int(self.filter_year.get())
            month = int(self.filter_month.get())
        except Exception:
            year = date.today().year
            month = date.today().month

        budget = self.db.get_budget(year, month)
        if budget is None:
            self.budget_label.configure(text="No budget set", fg=self.current_theme["text"])
            return

        rows = self.db.get_transactions_by_month(year, month)
        spent = sum((r[5] or 0) for r in rows)
        pct = (spent / budget * 100) if budget > 0 else 0

        color = "red" if spent > budget else self.current_theme["text"]
        self.budget_label.configure(
            text=f"Budget: ₹{budget:.2f}  Spent: ₹{spent:.2f} ({pct:.1f}%)",
            fg=color
        )

    # -----------------
    #  SEARCH
    # -----------------

    def search(self):
        """Filter rows in memory based on search text."""
        q = self.search_var.get().strip().lower()
        if not q:
            messagebox.showinfo("Search", "Enter search text.")
            return

        all_rows = self.db.get_all_transactions()
        filtered = []
        for r in all_rows:
            if (
                q in str(r[1]).lower() or
                q in str(r[2]).lower() or
                q in str(r[3]).lower() or
                q in str(r[4]).lower() or
                (r[6] and q in r[6].lower())
            ):
                filtered.append(r)

        self.populate_tree(filtered)
        # dashboard here still shows overall stats (optional to change)

    def clear_search(self):
        self.search_var.set("")
        self.refresh_all()

    # -----------------
    #  REPORTS / VISUALS
    # -----------------

    def show_monthly_report(self):
        """Open window with total + category breakdown for selected month."""
        try:
            year = int(self.filter_year.get())
            month = int(self.filter_month.get())
        except Exception:
            messagebox.showerror("Input", "Enter valid month/year.")
            return

        rows = self.db.get_transactions_by_month(year, month)
        cats = self.db.get_category_summary(year, month)
        if not rows:
            messagebox.showinfo("Report", "No transactions for selected month.")
            return

        win = tk.Toplevel(self.root)
        win.title(f"Report - {datetime(year, month, 1).strftime('%B %Y')}")
        win.geometry("700x500")

        tk.Label(
            win,
            text=f"Expense Report - {datetime(year, month, 1).strftime('%B %Y')}",
            font=("Arial", 14, "bold")
        ).pack(pady=8)

        total = sum(r[5] or 0 for r in rows)
        tk.Label(win, text=f"Total: ₹{total:.2f}", font=("Arial", 12, "bold")).pack()
        tk.Label(win, text=f"Transactions: {len(rows)}").pack(pady=6)

        frame = tk.Frame(win)
        frame.pack(fill="both", expand=True, padx=10, pady=10)

        cat_tree = ttk.Treeview(frame, columns=("Category", "Amount", "Percentage"), show="headings")
        cat_tree.pack(fill="both", expand=True, side="left")
        vsb = ttk.Scrollbar(frame, orient="vertical", command=cat_tree.yview)
        vsb.pack(side="right", fill="y")
        cat_tree.configure(yscrollcommand=vsb.set)

        cat_tree.heading("Category", text="Category")
        cat_tree.heading("Amount", text="Amount (₹)")
        cat_tree.heading("Percentage", text="Percentage")

        for cat, amt in cats:
            pct = (amt / total * 100) if total else 0
            cat_tree.insert("", "end", values=(cat, f"₹{amt:.2f}", f"{pct:.1f}%"))

    def show_visualization(self):
        """Open Matplotlib charts window for selected month."""
        try:
            year = int(self.filter_year.get())
            month = int(self.filter_month.get())
        except Exception:
            messagebox.showerror("Input", "Enter valid month/year.")
            return

        rows = self.db.get_transactions_by_month(year, month)
        cats = self.db.get_category_summary(year, month)
        if not rows:
            messagebox.showinfo("Visualize", "No data for selected month.")
            return

        viz = tk.Toplevel(self.root)
        viz.title("Spending Visualization")
        viz.geometry("1000x700")

        fig, ((ax1, ax2), (ax3, ax4)) = plt.subplots(2, 2, figsize=(12, 9))
        fig.suptitle(
            f"Expense Analysis - {datetime(year, month, 1).strftime('%B %Y')}",
            fontsize=14,
            fontweight="bold"
        )

        # Category pie & bar
        categories = [c for c, _ in cats]
        amounts = [a for _, a in cats]
        cmap = plt.cm.Set3(range(len(categories))) if categories else None

        if categories and amounts:
            ax1.pie(amounts, labels=categories, autopct="%1.1f%%", colors=cmap, startangle=90)
            ax1.set_title("Spending by Category")

            ax2.barh(categories, amounts, color=cmap)
            ax2.set_title("Category Comparison")
            ax2.invert_yaxis()
            ax2.set_xlabel("Amount (₹)")
        else:
            ax1.text(0.5, 0.5, "No category data", ha="center", va="center")
            ax2.text(0.5, 0.5, "No category data", ha="center", va="center")

        # Daily trend
        daily = defaultdict(float)
        for r in rows:
            daily[r[1]] += r[5] or 0
        dates = sorted(daily.keys())
        daily_amt = [daily[d] for d in dates]
        ax3.plot(dates, daily_amt, marker="o")
        ax3.set_title("Daily Spending")
        ax3.tick_params(axis="x", rotation=45)

        # Stats box
        total = sum(amounts) if amounts else sum((r[5] or 0) for r in rows)
        avg = total / len(rows) if rows else 0
        largest = max((r[5] or 0) for r in rows) if rows else 0
        top_cat = categories[0] if categories else "-"

        stats_text = (
            f"Total: ₹{total:,.2f}\n"
            f"Transactions: {len(rows)}\n"
            f"Average: ₹{avg:.2f}\n"
            f"Largest: ₹{largest:.2f}\n"
            f"Top Category: {top_cat}"
        )
        ax4.axis("off")
        ax4.text(0.05, 0.5, stats_text, fontsize=11, family="monospace")

        plt.tight_layout(rect=[0, 0.03, 1, 0.95])

        canvas = FigureCanvasTkAgg(fig, master=viz)
        canvas.draw()
        canvas.get_tk_widget().pack(fill="both", expand=True)

    # -----------------
    #  EXPORTS
    # -----------------

    def export_csv(self):
        """Export current table view to CSV."""
        filename = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv")]
        )
        if not filename:
            return

        rows = []
        for item in self.tree.get_children():
            vals = self.tree.item(item)["values"]
            rows.append(vals)

        try:
            with open(filename, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(["ID", "Date", "Category", "OriginalAmount",
                                 "Currency", "Amount_INR", "Description"])
                for r in rows:
                    writer.writerow(r)
            messagebox.showinfo("Export CSV", f"Saved: {filename}")
        except Exception as e:
            messagebox.showerror("Export CSV", f"Failed: {e}")

    def export_pdf(self):
        """Export current table view to PDF (if reportlab is installed)."""
        if not REPORTLAB_AVAILABLE:
            messagebox.showwarning(
                "PDF Export",
                "reportlab not installed.\nInstall using: pip install reportlab"
            )
            return

        filename = filedialog.asksaveasfilename(
            defaultextension=".pdf",
            filetypes=[("PDF files", "*.pdf")]
        )
        if not filename:
            return

        data = [["ID", "Date", "Category", "OriginalAmount", "Currency", "Amount_INR", "Description"]]
        for item in self.tree.get_children():
            vals = self.tree.item(item)["values"]
            data.append([str(v) for v in vals])

        try:
            doc = SimpleDocTemplate(filename, pagesize=landscape(A4))
            styles = getSampleStyleSheet()
            story = [Paragraph("Expense Report", styles["Title"]), Spacer(1, 12)]

            table = Table(data, repeatRows=1)
            table.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1155CC")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("GRID", (0, 0), (-1, -1), 0.25, colors.black),
                ("FONTSIZE", (0, 0), (-1, -1), 8),
            ]))
            story.append(table)
            doc.build(story)
            messagebox.showinfo("Export PDF", f"Saved: {filename}")
        except Exception as e:
            messagebox.showerror("Export PDF", f"Failed: {e}")

    # -----------------
    #  CLEANUP
    # -----------------

    def close(self):
        self.db.close()
        self.root.destroy()


# =========================
#  ENTRY POINT
# =========================

def main():
    root = tk.Tk()
    app = ExpenseTrackerApp(root)
    root.protocol("WM_DELETE_WINDOW", app.close)
    root.mainloop()


if __name__ == "__main__":
    main()
