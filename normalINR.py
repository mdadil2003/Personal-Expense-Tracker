"""
Personal Expense Tracker (INR Version) — Full-featured single-file application
Features:
 - Tkinter GUI (original left/right layout)
 - Dark/Light theme toggle
 - Scrollable left and right panels
 - Add / Edit / Delete transactions (SQLite)
 - Filter by month/year, search text
 - Export CSV and PDF (PDF via reportlab if available)
 - Dashboard: Today / Week / Month totals + top categories
 - Monthly budget with progress bar and persistence
 - Visualization window (matplotlib)
 - Detailed inline comments for each section — use for viva
"""

import sqlite3
import csv
import os
from datetime import datetime, timedelta, date
from collections import defaultdict
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from tkcalendar import DateEntry
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

# Try import for PDF export
try:
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.styles import getSampleStyleSheet
    REPORTLAB_AVAILABLE = True
except Exception:
    REPORTLAB_AVAILABLE = False

DB_NAME = "expenses.db"


# -----------------------------
# Backend: Database operations
# -----------------------------
class ExpenseTrackerDB:
    def __init__(self, db_name=DB_NAME):
        self.db_name = db_name
        self.conn = sqlite3.connect(self.db_name)
        self.cursor = self.conn.cursor()
        self.create_tables()

    def create_tables(self):
        """Create required tables: transactions and budgets"""
        # transactions table
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS transactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT NOT NULL,
                category TEXT NOT NULL,
                amount REAL NOT NULL,
                description TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        # budgets table (month-year unique)
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS budgets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                year INTEGER NOT NULL,
                month INTEGER NOT NULL,
                amount REAL NOT NULL,
                UNIQUE(year, month)
            )
        ''')
        self.conn.commit()

    def add_transaction(self, date_str, category, amount, description=""):
        """Insert a new transaction"""
        self.cursor.execute('''
            INSERT INTO transactions (date, category, amount, description)
            VALUES (?, ?, ?, ?)
        ''', (date_str, category, amount, description))
        self.conn.commit()
        return self.cursor.lastrowid

    def update_transaction(self, trans_id, date_str, category, amount, description=""):
        """Update an existing transaction"""
        self.cursor.execute('''
            UPDATE transactions
            SET date = ?, category = ?, amount = ?, description = ?
            WHERE id = ?
        ''', (date_str, category, amount, description, trans_id))
        self.conn.commit()
        return self.cursor.rowcount

    def delete_transaction(self, trans_id):
        """Delete transaction by id"""
        self.cursor.execute('DELETE FROM transactions WHERE id = ?', (trans_id,))
        self.conn.commit()
        return self.cursor.rowcount

    def get_all_transactions(self):
        """Return all transactions ordered by date desc"""
        self.cursor.execute('''
            SELECT id, date, category, amount, description FROM transactions
            ORDER BY date DESC
        ''')
        return self.cursor.fetchall()

    def get_transactions_by_month(self, year, month):
        """Return transactions within [start_of_month, start_of_next_month)"""
        start_date = f"{year}-{month:02d}-01"
        if month == 12:
            end_date = f"{year + 1}-01-01"
        else:
            end_date = f"{year}-{month + 1:02d}-01"
        self.cursor.execute('''
            SELECT id, date, category, amount, description FROM transactions
            WHERE date >= ? AND date < ?
            ORDER BY date DESC
        ''', (start_date, end_date))
        return self.cursor.fetchall()

    def get_category_summary(self, year=None, month=None):
        """Return (category, SUM(amount)) optionally filtered by month"""
        if year and month:
            start_date = f"{year}-{month:02d}-01"
            if month == 12:
                end_date = f"{year + 1}-01-01"
            else:
                end_date = f"{year}-{month + 1:02d}-01"
            self.cursor.execute('''
                SELECT category, SUM(amount) as total
                FROM transactions
                WHERE date >= ? AND date < ?
                GROUP BY category
                ORDER BY total DESC
            ''', (start_date, end_date))
        else:
            self.cursor.execute('''
                SELECT category, SUM(amount) as total
                FROM transactions
                GROUP BY category
                ORDER BY total DESC
            ''')
        return self.cursor.fetchall()

    def get_totals_for_range(self, start_date_str, end_date_str):
        """Return total amount in a date range"""
        self.cursor.execute('''
            SELECT SUM(amount) FROM transactions WHERE date >= ? AND date < ?
        ''', (start_date_str, end_date_str))
        row = self.cursor.fetchone()
        return row[0] or 0.0

    def get_budget(self, year, month):
        self.cursor.execute('''
            SELECT amount FROM budgets WHERE year = ? AND month = ?
        ''', (year, month))
        row = self.cursor.fetchone()
        return row[0] if row else None

    def set_budget(self, year, month, amount):
        """Insert or update budget for a month"""
        if self.get_budget(year, month) is None:
            self.cursor.execute('''
                INSERT INTO budgets (year, month, amount) VALUES (?, ?, ?)
            ''', (year, month, amount))
        else:
            self.cursor.execute('''
                UPDATE budgets SET amount = ? WHERE year = ? AND month = ?
            ''', (amount, year, month))
        self.conn.commit()

    def close(self):
        self.conn.close()


# -----------------------------
# Frontend: GUI application
# -----------------------------
class ExpenseTrackerApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Personal Expense Tracker (INR Version)")
        self.root.geometry("1200x700")
        # allow resizing
        self.root.minsize(1000, 600)

        # backend
        self.db = ExpenseTrackerDB()

        # Theme dictionaries (light and dark)
        self.theme_light = {
            'bg': '#f0f0f0',
            'panel_bg': 'white',
            'title_bg': '#0D47A1',   # blue header
            'title_fg': 'white',
            'button_bg': '#06A77D',  # green for add
            'text_fg': '#222',
            'accent': '#2E379A',     # primary used for headings
            'header_blue': '#1155CC',
            'summary_fg': '#06A77D'
        }
        self.theme_dark = {
            'bg': '#2b2b2b',
            'panel_bg': '#333333',
            'title_bg': '#1b4b72',
            'title_fg': 'white',
            'button_bg': '#1E8E65',
            'text_fg': '#ddd',
            'accent': '#2E86AB',
            'header_blue': '#0b63a4',
            'summary_fg': '#3bdc97'
        }

        self.current_theme = self.theme_light  # default
        self.editing_transaction = None  # holds id when editing

        # Build UI
        self.build_ui()
        # initial refresh
        self.refresh_all()

    # -----------------------------
    # UI construction helpers
    # -----------------------------
    def build_ui(self):
        """Construct the entire GUI layout: title, left scrollable panel, right panel with tree"""
        # Title frame
        self.title_frame = tk.Frame(self.root, bg=self.current_theme['title_bg'], height=60)
        self.title_frame.pack(fill='x')
        self.title_frame.pack_propagate(False)

        title_label = tk.Label(self.title_frame, text="  Personal Expense Tracker (₹ INR)",
                               bg=self.current_theme['title_bg'],
                               fg=self.current_theme['title_fg'],
                               font=('Arial', 18, 'bold'))
        title_label.pack(side='left', padx=12)

        # Theme toggle button on title bar (right side)
        self.theme_btn = tk.Button(self.title_frame, text="Toggle Dark", command=self.toggle_theme,
                                   bg='white', fg='black')
        self.theme_btn.pack(side='right', padx=8, pady=10)

        # Export buttons on title
        export_frame = tk.Frame(self.title_frame, bg=self.current_theme['title_bg'])
        export_frame.pack(side='right', padx=6)
        tk.Button(export_frame, text="Export CSV", command=self.export_csv).pack(side='left', padx=4, pady=8)
        tk.Button(export_frame, text="Export PDF", command=self.export_pdf).pack(side='left', padx=4, pady=8)

        # Search bar
        search_frame = tk.Frame(self.title_frame, bg=self.current_theme['title_bg'])
        search_frame.pack(side='right', padx=10)
        self.search_var = tk.StringVar()
        tk.Label(search_frame, text="Search:", bg=self.current_theme['title_bg'], fg='white').pack(side='left')
        self.search_entry = tk.Entry(search_frame, textvariable=self.search_var, width=20)
        self.search_entry.pack(side='left', padx=4)
        tk.Button(search_frame, text="Search", command=self.search_transactions).pack(side='left', padx=4)
        tk.Button(search_frame, text="Clear", command=self.clear_search).pack(side='left')

        # Main container below title
        self.main_container = tk.Frame(self.root, bg=self.current_theme['bg'])
        self.main_container.pack(fill='both', expand=True, padx=8, pady=8)

        # LEFT: Scrollable panel with menu (Add transaction, Dashboard, Filters)
        self.build_left_panel()

        # RIGHT: Transaction history table (with scroll)
        self.build_right_panel()

        # Bottom summary bar
        self.summary_bar = tk.Frame(self.root, bg=self.current_theme['panel_bg'], height=30)
        self.summary_bar.pack(fill='x', side='bottom')
        self.total_label = tk.Label(self.summary_bar, text="Total: ₹0.00 | Transactions: 0",
                                    bg=self.current_theme['panel_bg'], fg=self.current_theme['summary_fg'],
                                    font=('Arial', 11, 'bold'))
        self.total_label.pack(side='right', padx=20)

        # Apply theme once
        self.apply_theme()

    def build_left_panel(self):
        """Create a scrollable left panel. Inside it we place dashboard, add transaction, filters & actions, budget"""
        left_outer = tk.Frame(self.main_container, width=300, bg=self.current_theme['panel_bg'])
        left_outer.pack(side='left', fill='y', padx=(0, 8), pady=0)
        left_outer.pack_propagate(False)

        # create canvas to allow scrolling
        canvas = tk.Canvas(left_outer, borderwidth=0, highlightthickness=0,
                           bg=self.current_theme['panel_bg'])
        canvas.pack(side='left', fill='both', expand=True)

        vsb = ttk.Scrollbar(left_outer, orient="vertical", command=canvas.yview)
        vsb.pack(side='right', fill='y')
        canvas.configure(yscrollcommand=vsb.set)

        # inner frame inside canvas
        self.left_frame = tk.Frame(canvas, bg=self.current_theme['panel_bg'])
        canvas.create_window((0, 0), window=self.left_frame, anchor='nw')

        # ensure scrolling works with mousewheel
        def on_mousewheel(event):
            canvas.yview_scroll(int(-1*(event.delta/120)), "units")

        # bindings
        self.left_frame.bind("<Enter>", lambda e: self._bind_mousewheel(canvas, on_mousewheel))
        self.left_frame.bind("<Leave>", lambda e: self._unbind_mousewheel(canvas))

        # Dashboard box
        dash_box = ttk.LabelFrame(self.left_frame, text="Dashboard", padding=(10, 10))
        dash_box.pack(fill='x', padx=8, pady=8)
        self.dash_today = tk.Label(dash_box, text="Today: ₹0.00", anchor='w')
        self.dash_today.pack(fill='x')
        self.dash_week = tk.Label(dash_box, text="This Week: ₹0.00", anchor='w')
        self.dash_week.pack(fill='x')
        self.dash_month = tk.Label(dash_box, text="This Month: ₹0.00", anchor='w')
        self.dash_month.pack(fill='x')
        tk.Label(dash_box, text="Top categories:", anchor='w').pack(fill='x', pady=(6, 0))
        self.dash_top = tk.Label(dash_box, text="-", anchor='w', justify='left')
        self.dash_top.pack(fill='x')

        # Add New Transaction box
        add_box = ttk.LabelFrame(self.left_frame, text="Add / Edit Transaction", padding=(10, 10))
        add_box.pack(fill='x', padx=8, pady=8)

        tk.Label(add_box, text="Date:").grid(row=0, column=0, sticky='w', pady=4)
        self.date_entry = DateEntry(add_box, width=18, date_pattern='yyyy-mm-dd')
        self.date_entry.grid(row=0, column=1, pady=4, sticky='e')

        tk.Label(add_box, text="Category:").grid(row=1, column=0, sticky='w', pady=4)
        self.category_var = tk.StringVar()
        categories = ['Food', 'Transport', 'Entertainment', 'Shopping', 'Bills', 'Healthcare', 'Education', 'Other']
        self.category_combo = ttk.Combobox(add_box, values=categories, textvariable=self.category_var, width=16, state='readonly')
        self.category_combo.grid(row=1, column=1, pady=4, sticky='e')
        self.category_combo.set('Food')

        tk.Label(add_box, text="Amount (₹):").grid(row=2, column=0, sticky='w', pady=4)
        self.amount_entry = tk.Entry(add_box, width=20)
        self.amount_entry.grid(row=2, column=1, pady=4, sticky='e')

        tk.Label(add_box, text="Description:").grid(row=3, column=0, sticky='w', pady=4)
        self.desc_entry = tk.Entry(add_box, width=20)
        self.desc_entry.grid(row=3, column=1, pady=4, sticky='e')

        # Buttons: Add / Update / Clear
        btn_frame = tk.Frame(add_box)
        btn_frame.grid(row=4, column=0, columnspan=2, pady=8)
        self.add_btn = tk.Button(btn_frame, text="Add Transaction", command=self.add_or_update_transaction,
                                 bg=self.current_theme['button_bg'], fg='white')
        self.add_btn.pack(side='left', padx=6)
        self.clear_btn = tk.Button(btn_frame, text="Clear", command=self.clear_inputs)
        self.clear_btn.pack(side='left', padx=6)

        # Budget box
        budget_box = ttk.LabelFrame(self.left_frame, text="Monthly Budget", padding=(10, 10))
        budget_box.pack(fill='x', padx=8, pady=8)
        tk.Label(budget_box, text="Set budget (₹):").pack(anchor='w')
        self.budget_var = tk.StringVar()
        self.budget_entry = tk.Entry(budget_box, textvariable=self.budget_var, width=18)
        self.budget_entry.pack(pady=6)
        tk.Button(budget_box, text="Set Budget", command=self.set_budget).pack()
        self.budget_progress = ttk.Progressbar(budget_box, orient='horizontal', length=200, mode='determinate')
        self.budget_progress.pack(pady=6)
        self.budget_label = tk.Label(budget_box, text="No budget set")
        self.budget_label.pack()

        # Filters & Actions
        filter_box = ttk.LabelFrame(self.left_frame, text="Filters & Actions", padding=(10, 10))
        filter_box.pack(fill='x', padx=8, pady=8)
        tk.Label(filter_box, text="Month:").grid(row=0, column=0, sticky='w', pady=4)
        self.filter_month = tk.IntVar(value=datetime.now().month)
        self.month_spin = tk.Spinbox(filter_box, from_=1, to=12, textvariable=self.filter_month, width=6)
        self.month_spin.grid(row=0, column=1, sticky='e')
        tk.Label(filter_box, text="Year:").grid(row=1, column=0, sticky='w', pady=4)
        self.filter_year = tk.IntVar(value=datetime.now().year)
        self.year_spin = tk.Spinbox(filter_box, from_=2020, to=2030, textvariable=self.filter_year, width=6)
        self.year_spin.grid(row=1, column=1, sticky='e')

        tk.Button(filter_box, text="View Month", command=self.view_month).grid(row=2, column=0, pady=6, sticky='ew', padx=2)
        tk.Button(filter_box, text="View All", command=self.refresh_all).grid(row=2, column=1, pady=6, sticky='ew', padx=2)

        tk.Button(filter_box, text="Generate Report", command=self.show_monthly_report).grid(row=3, column=0, columnspan=2, pady=6, sticky='ew')
        tk.Button(filter_box, text="Visualize Spending", command=self.show_visualization).grid(row=4, column=0, columnspan=2, pady=6, sticky='ew')
        tk.Button(filter_box, text="Delete Selected", command=self.delete_selected).grid(row=5, column=0, columnspan=2, pady=6, sticky='ew')

        # Make sure canvas scrollregion is updated
        self.left_frame.update_idletasks()
        canvas.config(scrollregion=canvas.bbox("all"))

    def _bind_mousewheel(self, canvas, handler):
        canvas.bind_all("<MouseWheel>", handler)
        canvas.bind_all("<Button-4>", handler)  # Linux
        canvas.bind_all("<Button-5>", handler)

    def _unbind_mousewheel(self, canvas):
        canvas.unbind_all("<MouseWheel>")
        canvas.unbind_all("<Button-4>")
        canvas.unbind_all("<Button-5>")

    def build_right_panel(self):
        """Create the right side: transaction table inside a frame with both scrollbars"""
        right_frame = tk.Frame(self.main_container, bg=self.current_theme['panel_bg'])
        right_frame.pack(side='right', fill='both', expand=True)

        # Label
        lbl = tk.Label(right_frame, text="Transaction History", font=('Arial', 14, 'bold'),
                       bg=self.current_theme['panel_bg'], fg=self.current_theme['text_fg'])
        lbl.pack(pady=8)

        table_outer = tk.Frame(right_frame)
        table_outer.pack(fill='both', expand=True, padx=6, pady=6)

        # Create Treeview with horizontal and vertical scrollbars
        self.tree = ttk.Treeview(table_outer, columns=('ID', 'Date', 'Category', 'Amount', 'Description'), show='headings')
        vsb = ttk.Scrollbar(table_outer, orient='vertical', command=self.tree.yview)
        hsb = ttk.Scrollbar(table_outer, orient='horizontal', command=self.tree.xview)
        self.tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        vsb.pack(side='right', fill='y')
        hsb.pack(side='bottom', fill='x')
        self.tree.pack(fill='both', expand=True)

        # Define columns
        self.tree.heading('ID', text='ID')
        self.tree.heading('Date', text='Date')
        self.tree.heading('Category', text='Category')
        self.tree.heading('Amount', text='Amount (₹)')
        self.tree.heading('Description', text='Description')

        self.tree.column('ID', width=50, anchor='center')
        self.tree.column('Date', width=110, anchor='center')
        self.tree.column('Category', width=140, anchor='center')
        self.tree.column('Amount', width=120, anchor='e')
        self.tree.column('Description', width=360, anchor='w')

        # Bind double-click to load record into left panel for editing
        self.tree.bind("<Double-1>", self.on_tree_double_click)

        # Make style consistent
        style = ttk.Style()
        style.configure("Treeview", rowheight=28, font=('Arial', 10))
        style.configure("Treeview.Heading", font=('Arial', 11, 'bold'),
                        foreground='white', background=self.current_theme['header_blue'])

    # -----------------------------
    # Theme / UI utilities
    # -----------------------------
    def apply_theme(self):
        """Apply current theme colors to major widgets"""
        t = self.current_theme
        self.root.configure(bg=t['bg'])
        self.main_container.configure(bg=t['bg'])
        self.title_frame.configure(bg=t['title_bg'])
        # title children recolor handled at creation (keeps readable)
        # left_frame and right panel coloring
        if hasattr(self, 'left_frame'):
            self.left_frame.configure(bg=t['panel_bg'])
            for child in self.left_frame.winfo_children():
                try:
                    child.configure(background=t['panel_bg'])
                except Exception:
                    pass
        # summary bar
        self.summary_bar.configure(bg=t['panel_bg'])
        self.total_label.configure(bg=t['panel_bg'], fg=t['summary_fg'])
        # tree headings color
        style = ttk.Style()
        style.configure("Treeview.Heading", background=t['header_blue'], foreground='white')
        # Add button color
        try:
            self.add_btn.configure(bg=t['button_bg'], fg='white')
        except Exception:
            pass
        # theme button look
        try:
            if t is self.theme_dark:
                self.theme_btn.configure(text="Switch to Light")
            else:
                self.theme_btn.configure(text="Switch to Dark")
        except Exception:
            pass

    def toggle_theme(self):
        """Switch between light and dark"""
        self.current_theme = self.theme_dark if self.current_theme == self.theme_light else self.theme_light
        self.apply_theme()

    # -----------------------------
    # CRUD and UI actions
    # -----------------------------
    def add_or_update_transaction(self):
        """If editing_transaction is set => update, else add a new transaction"""
        try:
            date_str = self.date_entry.get_date().strftime('%Y-%m-%d')
        except Exception:
            # fallback if DateEntry not available
            date_str = self.date_entry.get()
        category = self.category_var.get()
        desc = self.desc_entry.get().strip()
        try:
            amount = float(self.amount_entry.get())
        except ValueError:
            messagebox.showerror("Invalid input", "Amount must be a number.")
            return

        if amount <= 0:
            messagebox.showerror("Invalid input", "Amount must be positive.")
            return

        if not category:
            messagebox.showerror("Invalid input", "Please select a category.")
            return

        if self.editing_transaction:
            # Update
            updated = self.db.update_transaction(self.editing_transaction, date_str, category, amount, desc)
            if updated:
                messagebox.showinfo("Updated", "Transaction updated successfully.")
            else:
                messagebox.showwarning("No change", "No transaction was updated.")
            self.editing_transaction = None
            self.add_btn.configure(text="Add Transaction")
        else:
            self.db.add_transaction(date_str, category, amount, desc)
            messagebox.showinfo("Added", "Transaction added successfully.")

        self.clear_inputs()
        self.refresh_all()

    def clear_inputs(self):
        """Clear the add/edit fields"""
        try:
            self.date_entry.set_date(date.today())
        except Exception:
            pass
        self.category_combo.set('Food')
        self.amount_entry.delete(0, tk.END)
        self.desc_entry.delete(0, tk.END)
        self.editing_transaction = None
        self.add_btn.configure(text="Add Transaction")

    def on_tree_double_click(self, event):
        """Load selected row into form for editing"""
        item = self.tree.selection()
        if not item:
            return
        vals = self.tree.item(item[0], 'values')
        trans_id = vals[0]
        # fetch full record to ensure correct fields
        rows = self.db.get_all_transactions()
        record = None
        for r in rows:
            if str(r[0]) == str(trans_id):
                record = r
                break
        if not record:
            return
        # populate fields
        self.editing_transaction = record[0]
        # record[1] is date string
        try:
            self.date_entry.set_date(datetime.strptime(record[1], '%Y-%m-%d').date())
        except Exception:
            pass
        self.category_combo.set(record[2])
        self.amount_entry.delete(0, tk.END)
        self.amount_entry.insert(0, str(record[3]))
        self.desc_entry.delete(0, tk.END)
        if record[4]:
            self.desc_entry.insert(0, record[4])
        self.add_btn.configure(text="Update Transaction")

    def delete_selected(self):
        """Delete selected row from DB and refresh"""
        item = self.tree.selection()
        if not item:
            messagebox.showwarning("Select", "Please select a transaction to delete.")
            return
        vals = self.tree.item(item[0], 'values')
        trans_id = vals[0]
        if messagebox.askyesno("Confirm Delete", "Are you sure you want to delete this transaction?"):
            self.db.delete_transaction(trans_id)
            self.refresh_all()

    # -----------------------------
    # Filtering, searching, view month
    # -----------------------------
    def refresh_all(self):
        """Load all transactions into the tree and update dashboard/budget/summary"""
        rows = self.db.get_all_transactions()
        self._populate_tree(rows)
        self.update_summary(rows)
        self.update_dashboard()
        self.update_budget_progress()

    def view_month(self):
        year = int(self.filter_year.get())
        month = int(self.filter_month.get())
        rows = self.db.get_transactions_by_month(year, month)
        self._populate_tree(rows)
        self.update_summary(rows)
        self.update_dashboard()
        self.update_budget_progress()

    def _populate_tree(self, rows):
        """Clear and insert rows into treeview"""
        for item in self.tree.get_children():
            self.tree.delete(item)
        for r in rows:
            # r = (id, date, category, amount, description)
            self.tree.insert('', 'end', values=(r[0], r[1], r[2], f"₹{r[3]:.2f}", r[4] or ""))

    def update_summary(self, rows):
        """Update bottom summary label"""
        total = sum([r[3] for r in rows])
        self.total_label.configure(text=f"Total: ₹{total:.2f} | Transactions: {len(rows)}")

    def search_transactions(self):
        """Search by simple text match across date, category, amount, description"""
        query = self.search_var.get().strip().lower()
        if not query:
            messagebox.showinfo("Search", "Enter text to search.")
            return
        all_rows = self.db.get_all_transactions()
        filtered = []
        for r in all_rows:
            if (query in str(r[1]).lower() or
                query in str(r[2]).lower() or
                query in str(r[3]).lower() or
                (r[4] and query in r[4].lower())):
                filtered.append(r)
        self._populate_tree(filtered)
        self.update_summary(filtered)

    def clear_search(self):
        self.search_var.set("")
        self.refresh_all()

    # -----------------------------
    # Dashboard and budget utilities
    # -----------------------------
    def update_dashboard(self):
        """Compute Today / Week / Month totals and top categories"""
        today = datetime.now().date()
        start_today = today.strftime('%Y-%m-%d')
        end_today = (today + timedelta(days=1)).strftime('%Y-%m-%d')

        # week: start of current week (Mon) to next week
        start_week = (today - timedelta(days=today.weekday())).strftime('%Y-%m-%d')
        end_week = (datetime.strptime(start_week, '%Y-%m-%d') + timedelta(days=7)).strftime('%Y-%m-%d')

        # month
        year = today.year
        month = today.month
        start_month = f"{year}-{month:02d}-01"
        if month == 12:
            end_month = f"{year+1}-01-01"
        else:
            end_month = f"{year}-{month+1:02d}-01"

        total_today = self.db.get_totals_for_range(start_today, end_today)
        total_week = self.db.get_totals_for_range(start_week, end_week)
        total_month = self.db.get_totals_for_range(start_month, end_month)

        self.dash_today.configure(text=f"Today: ₹{total_today:.2f}")
        self.dash_week.configure(text=f"This Week: ₹{total_week:.2f}")
        self.dash_month.configure(text=f"This Month: ₹{total_month:.2f}")

        # Top categories this month
        cats = self.db.get_category_summary(year, month)
        top_text = ""
        for c, amt in cats[:5]:
            top_text += f"{c}: ₹{amt:.2f}\n"
        if not top_text:
            top_text = "No data"
        self.dash_top.configure(text=top_text.strip())

    def set_budget(self):
        """Set monthly budget for selected filter month/year"""
        try:
            val = float(self.budget_var.get())
            if val <= 0:
                messagebox.showerror("Invalid", "Budget must be positive.")
                return
        except ValueError:
            messagebox.showerror("Invalid", "Enter a number for budget.")
            return
        year = int(self.filter_year.get())
        month = int(self.filter_month.get())
        self.db.set_budget(year, month, val)
        messagebox.showinfo("Budget", "Monthly budget saved.")
        self.update_budget_progress()

    def update_budget_progress(self):
        """Compute monthly spending relative to budget and update progress bar"""
        year = int(self.filter_year.get())
        month = int(self.filter_month.get())
        budget = self.db.get_budget(year, month)
        if budget is None:
            self.budget_label.configure(text="No budget set")
            self.budget_progress['value'] = 0
            self.budget_progress['maximum'] = 100
            return
        # compute spent this month
        rows = self.db.get_transactions_by_month(year, month)
        spent = sum([r[3] for r in rows])
        # percent
        percent = min(100.0, (spent / budget) * 100 if budget > 0 else 0)
        self.budget_progress['value'] = percent
        self.budget_progress['maximum'] = 100
        self.budget_label.configure(text=f"Budget: ₹{budget:.2f}  Spent: ₹{spent:.2f} ({percent:.1f}%)")
        # change color of progress bar based on percent (ttk progressbar color customizations are platform-dependent)
        # We keep it default; but show overspend message
        if spent > budget:
            self.budget_label.configure(fg='red')

    # -----------------------------
    # Reporting / Visualization
    # -----------------------------
    def show_monthly_report(self):
        """Show a simple report window for selected month"""
        y = int(self.filter_year.get())
        m = int(self.filter_month.get())
        rows = self.db.get_transactions_by_month(y, m)
        cats = self.db.get_category_summary(y, m)
        if not rows:
            messagebox.showinfo("Report", "No transactions for selected month.")
            return

        win = tk.Toplevel(self.root)
        win.title(f"Report - {datetime(y, m, 1).strftime('%B %Y')}")
        win.geometry("700x500")
        tk.Label(win, text=f"Expense Report - {datetime(y, m, 1).strftime('%B %Y')}",
                 font=('Arial', 14, 'bold')).pack(pady=10)
        total = sum(r[3] for r in rows)
        tk.Label(win, text=f"Total Expenses: ₹{total:.2f}", font=('Arial', 12, 'bold')).pack()
        tk.Label(win, text=f"Transactions: {len(rows)}").pack(pady=8)

        # Category breakdown as treeview
        tframe = tk.Frame(win)
        tframe.pack(fill='both', expand=True, padx=10, pady=10)
        cat_tree = ttk.Treeview(tframe, columns=('Category', 'Amount', 'Percentage'), show='headings')
        cat_tree.pack(fill='both', expand=True, side='left')
        vsb = ttk.Scrollbar(tframe, orient='vertical', command=cat_tree.yview)
        vsb.pack(side='right', fill='y')
        cat_tree.configure(yscrollcommand=vsb.set)
        cat_tree.heading('Category', text='Category')
        cat_tree.heading('Amount', text='Amount (₹)')
        cat_tree.heading('Percentage', text='Percentage')
        for cat, amt in cats:
            pct = (amt / total) * 100 if total else 0
            cat_tree.insert('', 'end', values=(cat, f"₹{amt:.2f}", f"{pct:.1f}%"))

    def show_visualization(self):
        """Create a matplotlib-based visualization window for the selected month"""
        y = int(self.filter_year.get())
        m = int(self.filter_month.get())
        rows = self.db.get_transactions_by_month(y, m)
        cats = self.db.get_category_summary(y, m)
        if not rows:
            messagebox.showinfo("Visualize", "No data to visualize for selected month.")
            return

        viz_win = tk.Toplevel(self.root)
        viz_win.title(f"Spending Analysis - {datetime(y, m, 1).strftime('%B %Y')}")
        viz_win.geometry("1000x700")

        # create figure with 2x2 grid
        fig, ((ax1, ax2), (ax3, ax4)) = plt.subplots(2, 2, figsize=(12, 9))
        fig.suptitle(f'Expense Analysis - {datetime(y, m, 1).strftime("%B %Y")}', fontsize=14, fontweight='bold')

        categories = [c for c, _ in cats]
        amounts = [a for _, a in cats]
        colors_map = plt.cm.Set3(range(len(categories)))

        # Pie
        ax1.pie(amounts, labels=categories, autopct='%1.1f%%', colors=colors_map, startangle=90)
        ax1.set_title('Spending by Category')

        # Bar horizontal
        ax2.barh(categories, amounts, color=colors_map)
        ax2.set_title('Category Comparison')
        ax2.set_xlabel('Amount (₹)')
        ax2.invert_yaxis()

        # Daily spending
        daily = defaultdict(float)
        for r in rows:
            daily[r[1]] += r[3]
        dates = sorted(daily.keys())
        daily_amounts = [daily[d] for d in dates]
        ax3.plot(dates, daily_amounts, marker='o')
        ax3.set_title('Daily Spending Pattern')
        ax3.set_xlabel('Date')
        ax3.set_ylabel('Amount (₹)')
        ax3.tick_params(axis='x', rotation=45)

        # summary stats
        total = sum(amounts)
        avg = total / len(rows) if rows else 0
        largest = max(r[3] for r in rows)
        top_cat = categories[0] if categories else "-"
        stats = f"Total Spending: ₹{total:,.2f}\nTransactions: {len(rows)}\nAverage/Transaction: ₹{avg:,.2f}\nLargest: ₹{largest:.2f}\nTop Category: {top_cat}"
        ax4.axis('off')
        ax4.text(0.1, 0.5, stats, fontsize=11, family='monospace')

        plt.tight_layout(rect=[0, 0.03, 1, 0.95])

        canvas = FigureCanvasTkAgg(fig, master=viz_win)
        canvas.draw()
        canvas.get_tk_widget().pack(fill='both', expand=True)

    # -----------------------------
    # Export: CSV and PDF
    # -----------------------------
    def export_csv(self):
        """Export currently displayed transactions in tree to csv"""
        # ask file path
        fpath = filedialog.asksaveasfilename(defaultextension=".csv",
                                             filetypes=[("CSV files", "*.csv")],
                                             title="Save CSV")
        if not fpath:
            return
        # gather current rows in tree
        rows = []
        for item in self.tree.get_children():
            vals = self.tree.item(item)['values']
            # vals: (id, date, category, '₹xxx', description)
            amount_str = str(vals[3]).replace('₹', '').replace(',', '')
            rows.append([vals[0], vals[1], vals[2], amount_str, vals[4]])
        # write csv
        try:
            with open(fpath, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(['ID', 'Date', 'Category', 'Amount', 'Description'])
                writer.writerows(rows)
            messagebox.showinfo("Export CSV", f"CSV saved to: {fpath}")
        except Exception as e:
            messagebox.showerror("Export CSV", f"Failed to save CSV: {e}")

    def export_pdf(self):
        """Export current tree content to a simple PDF using reportlab (if available)"""
        if not REPORTLAB_AVAILABLE:
            messagebox.showwarning("ReportLab required", "PDF export requires 'reportlab'.\nInstall with:\n\npip install reportlab")
            return
        fpath = filedialog.asksaveasfilename(defaultextension=".pdf", filetypes=[("PDF files", "*.pdf")])
        if not fpath:
            return

        # gather rows
        data = [['ID', 'Date', 'Category', 'Amount (₹)', 'Description']]
        for item in self.tree.get_children():
            vals = self.tree.item(item)['values']
            data.append([str(vals[0]), str(vals[1]), str(vals[2]), str(vals[3]), str(vals[4])])

        # create PDF
        try:
            doc = SimpleDocTemplate(fpath, pagesize=landscape(A4))
            styles = getSampleStyleSheet()
            story = []
            story.append(Paragraph("Expense Report", styles['Title']))
            story.append(Spacer(1, 12))
            t = Table(data, repeatRows=1)
            t.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1155CC')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                ('GRID', (0, 0), (-1, -1), 0.25, colors.black),
                ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
                ('FONTSIZE', (0, 0), (-1, -1), 8),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ]))
            story.append(t)
            doc.build(story)
            messagebox.showinfo("Export PDF", f"PDF saved to: {fpath}")
        except Exception as e:
            messagebox.showerror("Export PDF", f"Failed to create PDF: {e}")

    # -----------------------------
    # Clean shutdown
    # -----------------------------
    def on_close(self):
        self.db.close()
        self.root.destroy()


# -----------------------------
# Entrypoint
# -----------------------------
def main():
    root = tk.Tk()
    app = ExpenseTrackerApp(root)
    # hook close
    root.protocol("WM_DELETE_WINDOW", app.on_close)
    root.mainloop()


if __name__ == "__main__":
    main()
