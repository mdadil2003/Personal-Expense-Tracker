"""
Personal Expense Tracker — Multi-currency (Country – CODE) | Dark Mode | Export | Charts
File: personal_expense_tracker_multicurrency.py

Features:
 - Tkinter GUI (left control panel + right table)
 - Scrollable left panel and scrollable right table
 - Dark/Light theme toggle
 - Add / Edit / Delete transactions
 - Search across fields
 - Filter by month & year
 - Export CSV and PDF (reportlab optional)
 - Visualization using Matplotlib
 - Multi-currency dropdown (Country – CODE)
 - Stores original amount + currency + converted INR amount in DB
 - Static conversion table + optional live fetch using requests
 - Well-commented for viva / report
"""

import os
import sqlite3
import csv
from datetime import datetime, timedelta, date
from collections import defaultdict
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from tkcalendar import DateEntry
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

# Optional libraries — import safely
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

# Database filename
DB_NAME = "expenses.db"


# --------------------------
# Backend: Database Handler
# --------------------------
class ExpenseDB:
    """Handles all SQLite operations: schema, CRUD, budgets."""
    def __init__(self, filename=DB_NAME):
        self.db = sqlite3.connect(filename)
        self.cur = self.db.cursor()
        self._create_tables()

    def _create_tables(self):
        """Create transactions and budgets tables."""
        self.cur.execute('''
            CREATE TABLE IF NOT EXISTS transactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT NOT NULL,
                category TEXT NOT NULL,
                amount_original REAL NOT NULL,
                currency TEXT NOT NULL,
                amount_in_inr REAL NOT NULL,
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
        self.db.commit()

    def add_transaction(self, date_str, category, amount_original, currency, amount_in_inr, description=""):
        self.cur.execute('''
            INSERT INTO transactions (date, category, amount_original, currency, amount_in_inr, description)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (date_str, category, amount_original, currency, amount_in_inr, description))
        self.db.commit()
        return self.cur.lastrowid

    def update_transaction(self, trans_id, date_str, category, amount_original, currency, amount_in_inr, description=""):
        self.cur.execute('''
            UPDATE transactions
            SET date=?, category=?, amount_original=?, currency=?, amount_in_inr=?, description=?
            WHERE id=?
        ''', (date_str, category, amount_original, currency, amount_in_inr, description, trans_id))
        self.db.commit()
        return self.cur.rowcount

    def delete_transaction(self, trans_id):
        self.cur.execute('DELETE FROM transactions WHERE id=?', (trans_id,))
        self.db.commit()
        return self.cur.rowcount

    def get_all_transactions(self):
        self.cur.execute('''
            SELECT id, date, category, amount_original, currency, amount_in_inr, description
            FROM transactions
            ORDER BY date DESC
        ''')
        return self.cur.fetchall()

    def get_transactions_by_month(self, year, month):
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
        self.cur.execute('''
            SELECT SUM(amount_in_inr) FROM transactions WHERE date >= ? AND date < ?
        ''', (start_date_str, end_date_str))
        row = self.cur.fetchone()
        return row[0] or 0.0

    def get_budget(self, year, month):
        self.cur.execute('SELECT amount FROM budgets WHERE year=? AND month=?', (year, month))
        row = self.cur.fetchone()
        return row[0] if row else None

    def set_budget(self, year, month, amount):
        if self.get_budget(year, month) is None:
            self.cur.execute('INSERT INTO budgets (year, month, amount) VALUES (?, ?, ?)', (year, month, amount))
        else:
            self.cur.execute('UPDATE budgets SET amount=? WHERE year=? AND month=?', (amount, year, month))
        self.db.commit()

    def close(self):
        self.db.close()


# --------------------------
# App: GUI + Logic
# --------------------------
class ExpenseTrackerApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Personal Expense Tracker — Multi-currency")
        self.root.geometry("1200x720")
        self.root.minsize(1000, 600)

        # backend
        self.db = ExpenseDB()

        # currency list (Country – CODE) mapping to code
        self.currency_list = {
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

        # currency rates: mapping currency_code -> INR rate (1 unit of currency equals rate INR)
        # These are example static rates — replace with fetch_live_rates() for live data
        self.currency_rates = {
            "INR": 1.0, "USD": 83.0, "EUR": 90.0, "GBP": 104.0, "AED": 22.6,
            "SAR": 22.15, "QAR": 22.8, "KWD": 270.0, "BHD": 220.0,
            "CAD": 61.0, "AUD": 55.0, "SGD": 62.0, "JPY": 0.56, "CNY": 11.5,
            "CHF": 95.5, "NZD": 50.0, "HKD": 10.7, "SEK": 7.9, "NOK": 8.0,
            "DKK": 12.1, "ZAR": 4.3, "PKR": 0.30, "BDT": 0.75, "LKR": 0.28,
            "IDR": 0.0053
        }

        # UI theme colors (light/dark)
        self.theme_light = {
            'root_bg': '#f0f0f0',
            'panel_bg': 'white',
            'title_bg': '#1155CC',  # blue header
            'title_fg': 'white',
            'accent': '#2E379A',
            'success': '#06A77D',
            'danger': '#D90368',
            'text': '#222'
        }
        self.theme_dark = {
            'root_bg': '#1e1e1e',
            'panel_bg': '#2b2b2b',
            'title_bg': '#0b3a66',
            'title_fg': 'white',
            'accent': '#4C5CEB',
            'success': '#13C48B',
            'danger': '#F2557A',
            'text': '#ddd'
        }
        self.current_theme = self.theme_light

        # editing state
        self.editing_id = None

        # build UI
        self.build_ui()
        # initial load
        self.refresh_all()

    # --------------------------
    # Optional: fetch live rates (uses requests)
    # --------------------------
    def fetch_live_rates(self, base="INR"):
        """Fetch live rates from a free API and update self.currency_rates.
        Uses open.er-api.com which is free; requires internet.
        This function is optional—failures are handled gracefully."""
        if not REQUESTS_AVAILABLE:
            messagebox.showwarning("Requests missing", "requests library not installed. Live rates unavailable.")
            return False
        try:
            # Example: get all rates relative to INR
            url = f"https://open.er-api.com/v6/latest/{base}"
            resp = requests.get(url, timeout=8)
            data = resp.json()
            if data.get("result") == "success":
                rates = data.get("rates", {})
                # rates: 1 INR equals rates[CUR] ??? depends on API; for open.er-api, base is base currency
                # We'll convert so that currency_rates[c] = value_of_1_c_in_INR
                # If base == 'INR', rates gives how many of target currency equals 1 INR -> invert
                if base == "INR":
                    for cur, val in rates.items():
                        if val and val != 0:
                            self.currency_rates[cur] = 1.0 / val
                else:
                    # If base is USD or others, we need to fetch rates for that base and then compute relative to INR
                    # Fetch INR-base rates then compute. Simpler: fetch USD, then compute pairwise (not implemented here).
                    pass
                messagebox.showinfo("Live rates", "Live currency rates updated from API.")
                return True
            else:
                messagebox.showwarning("Rate fetch failed", "API did not return success.")
                return False
        except Exception as e:
            messagebox.showwarning("Rate fetch error", f"Could not fetch live rates:\n{e}")
            return False

    # --------------------------
    # Build UI
    # --------------------------
    def build_ui(self):
        # title bar
        self.title_frame = tk.Frame(self.root, bg=self.current_theme['title_bg'], height=60)
        self.title_frame.pack(fill='x')
        self.title_frame.pack_propagate(False)

        tk.Label(self.title_frame, text="  Personal Expense Tracker", bg=self.current_theme['title_bg'],
                 fg=self.current_theme['title_fg'], font=('Arial', 18, 'bold')).pack(side='left', padx=10)

        # Toggle theme button
        self.theme_btn = tk.Button(self.title_frame, text="Toggle Theme", command=self.toggle_theme)
        self.theme_btn.pack(side='right', padx=8, pady=10)

        # Export buttons
        export_frame = tk.Frame(self.title_frame, bg=self.current_theme['title_bg'])
        export_frame.pack(side='right', padx=6)
        tk.Button(export_frame, text="Export CSV", command=self.export_csv).pack(side='left', padx=4)
        tk.Button(export_frame, text="Export PDF", command=self.export_pdf).pack(side='left', padx=4)

        # Search bar (in title)
        search_frame = tk.Frame(self.title_frame, bg=self.current_theme['title_bg'])
        search_frame.pack(side='right', padx=10)
        tk.Label(search_frame, text="Search:", bg=self.current_theme['title_bg'], fg='white').pack(side='left')
        self.search_var = tk.StringVar()
        self.search_entry = tk.Entry(search_frame, textvariable=self.search_var, width=22)
        self.search_entry.pack(side='left', padx=4)
        tk.Button(search_frame, text="Search", command=self.search).pack(side='left', padx=4)
        tk.Button(search_frame, text="Clear", command=self.clear_search).pack(side='left', padx=2)

        # main container
        self.main_frame = tk.Frame(self.root, bg=self.current_theme['root_bg'])
        self.main_frame.pack(fill='both', expand=True, padx=8, pady=8)

        # Left panel (scrollable)
        self.build_left_panel()

        # Right panel (table)
        self.build_right_panel()

        # Bottom summary
        self.summary_frame = tk.Frame(self.root, bg=self.current_theme['panel_bg'], height=36)
        self.summary_frame.pack(fill='x', side='bottom')
        self.summary_label = tk.Label(self.summary_frame, text="Total: ₹0.00", bg=self.current_theme['panel_bg'],
                                      fg=self.current_theme['text'], font=('Arial', 11, 'bold'))
        self.summary_label.pack(side='right', padx=12, pady=6)

        # Apply theme to widgets
        self.apply_theme()

    def build_left_panel(self):
        left_outer = tk.Frame(self.main_frame, width=360, bg=self.current_theme['panel_bg'])
        left_outer.pack(side='left', fill='y', padx=(0, 8))
        left_outer.pack_propagate(False)

        # Canvas inside left_outer to provide scrolling
        left_canvas = tk.Canvas(left_outer, bg=self.current_theme['panel_bg'], highlightthickness=0)
        left_canvas.pack(side='left', fill='both', expand=True)
        left_vsb = ttk.Scrollbar(left_outer, orient='vertical', command=left_canvas.yview)
        left_vsb.pack(side='right', fill='y')
        left_canvas.configure(yscrollcommand=left_vsb.set)

        self.left_frame = tk.Frame(left_canvas, bg=self.current_theme['panel_bg'])
        left_canvas.create_window((0, 0), window=self.left_frame, anchor='nw')

        # update scroll region
        def on_config(event):
            left_canvas.configure(scrollregion=left_canvas.bbox("all"))

        self.left_frame.bind("<Configure>", on_config)

        # Mouse wheel binding for better UX
        def _on_mousewheel(event):
            left_canvas.yview_scroll(int(-1*(event.delta/120)), "units")

        self.left_frame.bind("<Enter>", lambda e: self.left_frame.bind_all("<MouseWheel>", _on_mousewheel))
        self.left_frame.bind("<Leave>", lambda e: self.left_frame.unbind_all("<MouseWheel>"))

        # Dashboard small box
        dash_box = ttk.LabelFrame(self.left_frame, text="Dashboard", padding=(10, 8))
        dash_box.pack(fill='x', padx=8, pady=8)
        self.dash_today = tk.Label(dash_box, text="Today: ₹0.00", anchor='w')
        self.dash_today.pack(fill='x')
        self.dash_week = tk.Label(dash_box, text="This Week: ₹0.00", anchor='w')
        self.dash_week.pack(fill='x')
        self.dash_month = tk.Label(dash_box, text="This Month: ₹0.00", anchor='w')
        self.dash_month.pack(fill='x')
        tk.Label(dash_box, text="Top Categories:", anchor='w').pack(fill='x', pady=(6, 0))
        self.dash_top = tk.Label(dash_box, text="-", anchor='w', justify='left')
        self.dash_top.pack(fill='x')

        # Add / Edit Transaction box
        add_box = ttk.LabelFrame(self.left_frame, text="Add / Edit Transaction", padding=(10, 10))
        add_box.pack(fill='x', padx=8, pady=8)

        tk.Label(add_box, text="Date:").grid(row=0, column=0, sticky='w', pady=4)
        self.date_entry = DateEntry(add_box, width=18, date_pattern='yyyy-mm-dd')
        self.date_entry.grid(row=0, column=1, sticky='e', pady=4)

        tk.Label(add_box, text="Category:").grid(row=1, column=0, sticky='w', pady=4)
        self.category_var = tk.StringVar()
        categories = ['Food', 'Transport', 'Entertainment', 'Shopping', 'Bills', 'Healthcare', 'Education', 'Other']
        self.category_combo = ttk.Combobox(add_box, values=categories, textvariable=self.category_var, width=16, state='readonly')
        self.category_combo.grid(row=1, column=1, sticky='e', pady=4)
        self.category_combo.set('Food')

        tk.Label(add_box, text="Amount:").grid(row=2, column=0, sticky='w', pady=4)
        self.amount_entry = tk.Entry(add_box, width=18)
        self.amount_entry.grid(row=2, column=1, sticky='e', pady=4)

        # Currency dropdown (Country – CODE)
        tk.Label(add_box, text="Currency:").grid(row=3, column=0, sticky='w', pady=4)
        self.currency_var = tk.StringVar()
        self.currency_combo = ttk.Combobox(add_box, values=list(self.currency_list.keys()),
                                           textvariable=self.currency_var, width=18, state='readonly')
        self.currency_combo.grid(row=3, column=1, sticky='e', pady=4)
        self.currency_combo.set("India – INR")

        tk.Label(add_box, text="Description:").grid(row=4, column=0, sticky='w', pady=4)
        self.desc_entry = tk.Entry(add_box, width=20)
        self.desc_entry.grid(row=4, column=1, sticky='e', pady=4)

        # Buttons: Add / Clear
        btn_frame = tk.Frame(add_box)
        btn_frame.grid(row=5, column=0, columnspan=2, pady=8)
        self.add_btn = tk.Button(btn_frame, text="Add Transaction", command=self.add_or_update_transaction)
        self.add_btn.pack(side='left', padx=6)
        tk.Button(btn_frame, text="Clear", command=self.clear_inputs).pack(side='left', padx=6)

        # Budget box (month-year)
        budget_box = ttk.LabelFrame(self.left_frame, text="Monthly Budget", padding=(10, 10))
        budget_box.pack(fill='x', padx=8, pady=8)
        tk.Label(budget_box, text="Month:").grid(row=0, column=0, sticky='w')
        self.budget_month = tk.Spinbox(budget_box, from_=1, to=12, width=6)
        self.budget_month.grid(row=0, column=1)
        tk.Label(budget_box, text="Year:").grid(row=1, column=0, sticky='w', pady=4)
        self.budget_year = tk.Spinbox(budget_box, from_=2020, to=2035, width=6)
        self.budget_year.grid(row=1, column=1)
        tk.Label(budget_box, text="Amount (₹):").grid(row=2, column=0, sticky='w', pady=4)
        self.budget_entry = tk.Entry(budget_box, width=12)
        self.budget_entry.grid(row=2, column=1, sticky='e', pady=4)
        tk.Button(budget_box, text="Set Budget", command=self.set_budget).grid(row=3, column=0, columnspan=2, pady=6)
        self.budget_label = tk.Label(budget_box, text="No budget set")
        self.budget_label.grid(row=4, column=0, columnspan=2)

        # Filters & actions
        filter_box = ttk.LabelFrame(self.left_frame, text="Filters & Actions", padding=(10, 10))
        filter_box.pack(fill='x', padx=8, pady=8)
        tk.Label(filter_box, text="Month:").grid(row=0, column=0, sticky='w')
        self.filter_month = tk.Spinbox(filter_box, from_=1, to=12, width=6)
        self.filter_month.grid(row=0, column=1)
        tk.Label(filter_box, text="Year:").grid(row=1, column=0, sticky='w', pady=4)
        self.filter_year = tk.Spinbox(filter_box, from_=2020, to=2035, width=6)
        self.filter_year.grid(row=1, column=1, pady=4)
        tk.Button(filter_box, text="View Month", command=self.view_month).grid(row=2, column=0, pady=6, sticky='ew')
        tk.Button(filter_box, text="View All", command=self.refresh_all).grid(row=2, column=1, pady=6, sticky='ew')
        tk.Button(filter_box, text="Show Report", command=self.show_monthly_report).grid(row=3, column=0, columnspan=2, pady=6, sticky='ew')
        tk.Button(filter_box, text="Visualize", command=self.show_visualization).grid(row=4, column=0, columnspan=2, pady=6, sticky='ew')
        tk.Button(filter_box, text="Delete Selected", command=self.delete_selected).grid(row=5, column=0, columnspan=2, pady=6, sticky='ew')

    def build_right_panel(self):
        right_outer = tk.Frame(self.main_frame, bg=self.current_theme['panel_bg'])
        right_outer.pack(side='right', fill='both', expand=True)

        tk.Label(right_outer, text="Transaction History", font=('Arial', 14, 'bold'),
                 bg=self.current_theme['panel_bg'], fg=self.current_theme['text']).pack(pady=8)

        table_frame = tk.Frame(right_outer)
        table_frame.pack(fill='both', expand=True, padx=6, pady=6)

        # Treeview with scrollbars
        self.tree = ttk.Treeview(table_frame, columns=('ID', 'Date', 'Category', 'Amount_Original', 'Currency', 'Amount_INR', 'Description'),
                                 show='headings')
        vsb = ttk.Scrollbar(table_frame, orient='vertical', command=self.tree.yview)
        hsb = ttk.Scrollbar(table_frame, orient='horizontal', command=self.tree.xview)
        self.tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        vsb.pack(side='right', fill='y')
        hsb.pack(side='bottom', fill='x')
        self.tree.pack(fill='both', expand=True)

        # Headings
        self.tree.heading('ID', text='ID')
        self.tree.heading('Date', text='Date')
        self.tree.heading('Category', text='Category')
        self.tree.heading('Amount_Original', text='Original Amount')
        self.tree.heading('Currency', text='Currency')
        self.tree.heading('Amount_INR', text='Amount (₹)')
        self.tree.heading('Description', text='Description')

        # Column widths
        self.tree.column('ID', width=50, anchor='center')
        self.tree.column('Date', width=110, anchor='center')
        self.tree.column('Category', width=140, anchor='center')
        self.tree.column('Amount_Original', width=120, anchor='e')
        self.tree.column('Currency', width=80, anchor='center')
        self.tree.column('Amount_INR', width=120, anchor='e')
        self.tree.column('Description', width=360, anchor='w')

        # Double-click -> Edit
        self.tree.bind("<Double-1>", self.on_tree_double_click)

        # Style tree headings
        style = ttk.Style()
        style.configure("Treeview.Heading", font=('Arial', 11, 'bold'), foreground='white', background=self.current_theme['title_bg'])

    # --------------------------
    # Theme
    # --------------------------
    def apply_theme(self):
        t = self.current_theme
        self.root.configure(bg=t['root_bg'])
        self.main_frame.configure(bg=t['root_bg'])
        self.title_frame.configure(bg=t['title_bg'])
        # update add button color
        try:
            self.add_btn.configure(bg=t['success'], fg='white')
        except Exception:
            pass
        # update summary
        self.summary_frame.configure(bg=t['panel_bg'])
        self.summary_label.configure(bg=t['panel_bg'], fg=t['text'])

    def toggle_theme(self):
        self.current_theme = self.theme_dark if self.current_theme == self.theme_light else self.theme_light
        self.apply_theme()

    # --------------------------
    # CRUD: Add, Update, Delete
    # --------------------------
    def add_or_update_transaction(self):
        """Add or update depending on self.editing_id."""
        # read fields
        try:
            date_str = self.date_entry.get_date().strftime('%Y-%m-%d')
        except Exception:
            date_str = self.date_entry.get()
        category = self.category_var.get()
        desc = self.desc_entry.get().strip()
        # amount and currency
        amt_text = self.amount_entry.get().strip()
        if not amt_text:
            messagebox.showerror("Input error", "Enter amount")
            return
        try:
            amount_original = float(amt_text)
        except ValueError:
            messagebox.showerror("Input error", "Amount must be numeric")
            return
        if amount_original <= 0:
            messagebox.showerror("Input error", "Amount must be positive")
            return

        country_currency = self.currency_var.get()
        currency_code = self.currency_list.get(country_currency, "INR")

        # conversion: amount_in_inr = amount_original * rate_of_currency_to_INR
        rate = self.currency_rates.get(currency_code, 1.0)
        amount_in_inr = amount_original * rate

        if self.editing_id:
            # update
            updated = self.db.update_transaction(self.editing_id, date_str, category, amount_original, currency_code, amount_in_inr, desc)
            if updated:
                messagebox.showinfo("Updated", "Transaction updated successfully.")
            else:
                messagebox.showwarning("Update", "No changes made.")
            self.editing_id = None
            self.add_btn.configure(text="Add Transaction")
        else:
            self.db.add_transaction(date_str, category, amount_original, currency_code, amount_in_inr, desc)
            messagebox.showinfo("Added", f"Saved ({currency_code} → ₹{amount_in_inr:.2f})")

        # clear and refresh
        self.clear_inputs()
        self.refresh_all()

    def clear_inputs(self):
        try:
            self.date_entry.set_date(date.today())
        except Exception:
            pass
        self.category_combo.set('Food')
        self.amount_entry.delete(0, tk.END)
        self.desc_entry.delete(0, tk.END)
        self.currency_combo.set("India – INR")
        self.editing_id = None
        try:
            self.add_btn.configure(text="Add Transaction")
        except Exception:
            pass

    def on_tree_double_click(self, event):
        """Load selected row into left form for edit"""
        sel = self.tree.selection()
        if not sel:
            return
        vals = self.tree.item(sel[0])['values']
        trans_id = vals[0]
        # find full record from DB
        rows = self.db.get_all_transactions()
        record = None
        for r in rows:
            if r[0] == trans_id:
                record = r
                break
        if not record:
            return
        # populate form
        self.editing_id = record[0]
        try:
            self.date_entry.set_date(datetime.strptime(record[1], '%Y-%m-%d').date())
        except Exception:
            pass
        self.category_combo.set(record[2])
        self.amount_entry.delete(0, tk.END)
        self.amount_entry.insert(0, str(record[3]))
        # set currency dropdown by code -> key
        currency_code = record[4]
        # find key for this code
        key = next((k for k, v in self.currency_list.items() if v == currency_code), "India – INR")
        self.currency_combo.set(key)
        self.desc_entry.delete(0, tk.END)
        if record[6]:
            self.desc_entry.insert(0, record[6])
        try:
            self.add_btn.configure(text="Update Transaction")
        except Exception:
            pass

    def delete_selected(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showwarning("Select", "Select a transaction to delete")
            return
        vals = self.tree.item(sel[0])['values']
        tid = vals[0]
        if messagebox.askyesno("Confirm", f"Delete transaction ID {tid}?"):
            self.db.delete_transaction(tid)
            self.refresh_all()

    # --------------------------
    # Refresh / View / Search
    # --------------------------
    def refresh_all(self):
        rows = self.db.get_all_transactions()
        self.populate_tree(rows)
        self.update_summary_and_dashboard(rows)
        self.update_budget_progress()

    def view_month(self):
        try:
            year = int(self.filter_year.get())
            month = int(self.filter_month.get())
        except Exception:
            messagebox.showerror("Input", "Enter valid month/year")
            return
        rows = self.db.get_transactions_by_month(year, month)
        self.populate_tree(rows)
        self.update_summary_and_dashboard(rows)
        self.update_budget_progress()

    def populate_tree(self, rows):
        # clear
        for item in self.tree.get_children():
            self.tree.delete(item)
        # insert
        for r in rows:
            # r: (id, date, category, amount_original, currency, amount_in_inr, description)
            self.tree.insert('', 'end', values=(r[0], r[1], r[2], f"{r[3]:.2f}", r[4], f"₹{r[5]:.2f}", r[6] or ""))

    def update_summary_and_dashboard(self, rows):
        # total INR across passed rows
        total_inr = sum([r[5] for r in rows]) if rows else 0.0
        self.summary_label.configure(text=f"Total: ₹{total_inr:.2f} | Transactions: {len(rows)}")
        # dashboard -> overall (today/week/month)
        self.update_dashboard()

    def search(self):
        q = self.search_var.get().strip().lower()
        if not q:
            messagebox.showinfo("Search", "Enter search text.")
            return
        all_rows = self.db.get_all_transactions()
        filtered = []
        for r in all_rows:
            if (q in str(r[1]).lower() or q in str(r[2]).lower() or
                    q in str(r[3]).lower() or q in str(r[4]).lower() or
                    (r[6] and q in r[6].lower())):
                filtered.append(r)
        self.populate_tree(filtered)
        self.update_summary_and_dashboard(filtered)

    def clear_search(self):
        self.search_var.set("")
        self.refresh_all()

    # --------------------------
    # Dashboard & Budget
    # --------------------------
    def update_dashboard(self):
        today = date.today()
        start_today = today.strftime('%Y-%m-%d')
        end_today = (today + timedelta(days=1)).strftime('%Y-%m-%d')
        start_week = (today - timedelta(days=today.weekday())).strftime('%Y-%m-%d')
        end_week = (datetime.strptime(start_week, '%Y-%m-%d') + timedelta(days=7)).strftime('%Y-%m-%d')
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

        # top categories this month
        cats = self.db.get_category_summary(year, month)
        top_text = ""
        for c, a in cats[:5]:
            top_text += f"{c}: ₹{a:.2f}\n"
        self.dash_top.configure(text=top_text.strip() or "No data")

    def set_budget(self):
        try:
            year = int(self.budget_year.get())
            month = int(self.budget_month.get())
            amount = float(self.budget_entry.get())
        except Exception:
            messagebox.showerror("Input", "Enter valid budget, month, year")
            return
        if amount <= 0:
            messagebox.showerror("Input", "Budget must be positive")
            return
        self.db.set_budget(year, month, amount)
        messagebox.showinfo("Budget", "Saved")
        self.update_budget_progress()

    def update_budget_progress(self):
        try:
            year = int(self.filter_year.get())
            month = int(self.filter_month.get())
        except Exception:
            year = date.today().year
            month = date.today().month
        budget = self.db.get_budget(year, month)
        if budget is None:
            self.budget_label.configure(text="No budget set")
            return
        rows = self.db.get_transactions_by_month(year, month)
        spent = sum([r[5] for r in rows])
        pct = (spent / budget) * 100 if budget > 0 else 0
        self.budget_label.configure(text=f"Budget: ₹{budget:.2f}  Spent: ₹{spent:.2f} ({pct:.1f}%)")
        if spent > budget:
            self.budget_label.configure(fg='red')
        else:
            self.budget_label.configure(fg='black')

    # --------------------------
    # Reporting & Visualization
    # --------------------------
    def show_monthly_report(self):
        try:
            year = int(self.filter_year.get())
            month = int(self.filter_month.get())
        except Exception:
            messagebox.showerror("Input", "Enter valid month/year")
            return
        rows = self.db.get_transactions_by_month(year, month)
        cats = self.db.get_category_summary(year, month)
        if not rows:
            messagebox.showinfo("Report", "No transactions for selected month.")
            return
        win = tk.Toplevel(self.root)
        win.title(f"Report - {datetime(year, month, 1).strftime('%B %Y')}")
        win.geometry("700x500")
        tk.Label(win, text=f"Expense Report - {datetime(year, month, 1).strftime('%B %Y')}", font=('Arial', 14, 'bold')).pack(pady=8)
        total = sum(r[5] for r in rows)
        tk.Label(win, text=f"Total: ₹{total:.2f}", font=('Arial', 12, 'bold')).pack()
        tk.Label(win, text=f"Transactions: {len(rows)}").pack(pady=6)

        # show category breakdown
        frame = tk.Frame(win)
        frame.pack(fill='both', expand=True, padx=10, pady=10)
        cat_tree = ttk.Treeview(frame, columns=('Category', 'Amount', 'Percentage'), show='headings')
        cat_tree.pack(fill='both', expand=True, side='left')
        vsb = ttk.Scrollbar(frame, orient='vertical', command=cat_tree.yview)
        vsb.pack(side='right', fill='y')
        cat_tree.configure(yscrollcommand=vsb.set)
        cat_tree.heading('Category', text='Category')
        cat_tree.heading('Amount', text='Amount (₹)')
        cat_tree.heading('Percentage', text='Percentage')
        for cat, amt in cats:
            pct = (amt / total) * 100 if total else 0
            cat_tree.insert('', 'end', values=(cat, f"₹{amt:.2f}", f"{pct:.1f}%"))

    def show_visualization(self):
        try:
            year = int(self.filter_year.get())
            month = int(self.filter_month.get())
        except Exception:
            messagebox.showerror("Input", "Enter valid month/year")
            return
        rows = self.db.get_transactions_by_month(year, month)
        cats = self.db.get_category_summary(year, month)
        if not rows:
            messagebox.showinfo("Visualize", "No data")
            return

        viz = tk.Toplevel(self.root)
        viz.title("Visualization")
        viz.geometry("1000x700")

        fig, ((ax1, ax2), (ax3, ax4)) = plt.subplots(2, 2, figsize=(12, 9))
        fig.suptitle(f'Expense Analysis - {datetime(year, month, 1).strftime("%B %Y")}', fontsize=14, fontweight='bold')

        categories = [c for c, _ in cats]
        amounts = [a for _, a in cats]
        cmap = plt.cm.Set3(range(len(categories)))

        ax1.pie(amounts, labels=categories, autopct='%1.1f%%', colors=cmap, startangle=90)
        ax1.set_title('By Category')

        ax2.barh(categories, amounts, color=cmap)
        ax2.set_title('Category Comparison')
        ax2.invert_yaxis()
        ax2.set_xlabel('Amount (₹)')

        daily = defaultdict(float)
        for r in rows:
            daily[r[1]] += r[5]
        dates = sorted(daily.keys())
        daily_amt = [daily[d] for d in dates]
        ax3.plot(dates, daily_amt, marker='o')
        ax3.set_title('Daily Spending')
        ax3.tick_params(axis='x', rotation=45)

        total = sum(amounts)
        avg = total / len(rows) if rows else 0
        largest = max(r[5] for r in rows)
        top_cat = categories[0] if categories else "-"
        stats = f"Total: ₹{total:,.2f}\nTransactions: {len(rows)}\nAverage: ₹{avg:.2f}\nLargest: ₹{largest:.2f}\nTop Category: {top_cat}"
        ax4.axis('off')
        ax4.text(0.05, 0.5, stats, fontsize=11, family='monospace')

        plt.tight_layout(rect=[0, 0.03, 1, 0.95])
        canvas = FigureCanvasTkAgg(fig, master=viz)
        canvas.draw()
        canvas.get_tk_widget().pack(fill='both', expand=True)

    # --------------------------
    # Export CSV/PDF
    # --------------------------
    def export_csv(self):
        # Export visible rows in table
        f = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("CSV", "*.csv")])
        if not f:
            return
        rows = []
        for item in self.tree.get_children():
            vals = self.tree.item(item)['values']
            # vals mapping: (ID, Date, Category, OriginalAmountStr, Currency, INRStr, Description)
            rows.append([vals[0], vals[1], vals[2], vals[3], vals[4], vals[5], vals[6]])
        try:
            with open(f, 'w', newline='', encoding='utf-8') as fp:
                writer = csv.writer(fp)
                writer.writerow(['ID', 'Date', 'Category', 'OriginalAmount', 'Currency', 'Amount_INR', 'Description'])
                writer.writerows(rows)
            messagebox.showinfo("Export CSV", f"Saved: {f}")
        except Exception as e:
            messagebox.showerror("Export CSV", f"Failed: {e}")

    def export_pdf(self):
        if not REPORTLAB_AVAILABLE:
            messagebox.showwarning("ReportLab", "reportlab lib not installed. Install with: pip install reportlab")
            return
        f = filedialog.asksaveasfilename(defaultextension=".pdf", filetypes=[("PDF", "*.pdf")])
        if not f:
            return
        data = [['ID', 'Date', 'Category', 'OriginalAmount', 'Currency', 'Amount_INR', 'Description']]
        for item in self.tree.get_children():
            vals = self.tree.item(item)['values']
            data.append([str(vals[0]), str(vals[1]), str(vals[2]), str(vals[3]), str(vals[4]), str(vals[5]), str(vals[6])])
        try:
            doc = SimpleDocTemplate(f, pagesize=landscape(A4))
            styles = getSampleStyleSheet()
            story = []
            story.append(Paragraph("Expense Report", styles['Title']))
            story.append(Spacer(1, 12))
            t = Table(data, repeatRows=1)
            t.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1155CC')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                ('GRID', (0, 0), (-1, -1), 0.25, colors.black),
                ('FONTSIZE', (0, 0), (-1, -1), 8),
            ]))
            story.append(t)
            doc.build(story)
            messagebox.showinfo("Export PDF", f"Saved: {f}")
        except Exception as e:
            messagebox.showerror("Export PDF", f"Failed: {e}")

    # --------------------------
    # Clean shutdown
    # --------------------------
    def close(self):
        self.db.close()
        self.root.destroy()


# --------------------------
# Entrypoint
# --------------------------
def main():
    root = tk.Tk()
    app = ExpenseTrackerApp(root)
    root.protocol("WM_DELETE_WINDOW", app.close)
    root.mainloop()


if __name__ == "__main__":
    main()
