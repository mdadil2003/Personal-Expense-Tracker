"""
Personal Expense Tracker (INR Version) - Final
Features:
 - Add / Edit / Delete transactions
 - Filter by month/year
 - View all transactions
 - Category summary & monthly report
 - Visualizations (Matplotlib embedded in Tkinter)
 - Export to CSV and PDF
 - Clean comments: combined professional + deep explanations
Author: Md Adil Raza
"""

import sqlite3  # SQLite DB (file-based, no server)
import csv
from datetime import datetime, timedelta
from collections import defaultdict
import tkinter as tk
from tkinter import ttk, messagebox
from tkinter.filedialog import asksaveasfilename

# Matplotlib for charts and embedding into Tkinter
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

# Date picker widget for accurate date selection
from tkcalendar import DateEntry

# PDF export (reportlab). If not installed: pip install reportlab
try:
    from reportlab.lib.pagesizes import letter
    from reportlab.pdfgen import canvas
    REPORTLAB_AVAILABLE = True
except Exception:
    REPORTLAB_AVAILABLE = False


# ------------------------------------------------------------
# BACKEND: ExpenseTracker
# Responsible for all DB operations (connect, CRUD, queries).
# Separation of concerns: keeps DB logic isolated from GUI.
# ------------------------------------------------------------
class ExpenseTracker:
    def __init__(self, db_name="expenses.db"):
        """
        Initialize DB connection and ensure tables exist.
        db_name: filename for SQLite database.
        """
        self.db_name = db_name
        self.conn = None
        self.cursor = None
        self.connect()
        self.create_tables()

    def connect(self):
        """Open SQLite connection and cursor."""
        self.conn = sqlite3.connect(self.db_name)
        self.cursor = self.conn.cursor()

    def create_tables(self):
        """Create transactions table if missing."""
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
        self.conn.commit()

    def add_transaction(self, date, category, amount, description=""):
        """
        Insert a new transaction record into the DB.
        Returns last inserted row id.
        """
        self.cursor.execute('''
            INSERT INTO transactions (date, category, amount, description)
            VALUES (?, ?, ?, ?)
        ''', (date, category, amount, description))
        self.conn.commit()
        return self.cursor.lastrowid

    def get_all_transactions(self):
        """
        Retrieve all transactions ordered by date descending.
        Returns list of tuples: (id, date, category, amount, description)
        """
        self.cursor.execute('''
            SELECT id, date, category, amount, description
            FROM transactions
            ORDER BY date DESC
        ''')
        return self.cursor.fetchall()

    def get_transactions_by_month(self, year, month):
        """
        Retrieve transactions within the specified month.
        Uses inclusive start date and exclusive end date method.
        """
        start_date = f"{year}-{month:02d}-01"
        if month == 12:
            end_date = f"{year+1}-01-01"
        else:
            end_date = f"{year}-{month+1:02d}-01"

        self.cursor.execute('''
            SELECT id, date, category, amount, description
            FROM transactions
            WHERE date >= ? AND date < ?
            ORDER BY date DESC
        ''', (start_date, end_date))
        return self.cursor.fetchall()

    def get_category_summary(self, year=None, month=None):
        """
        Return aggregated spending by category.
        If year and month provided, filter to that month.
        """
        if year and month:
            start_date = f"{year}-{month:02d}-01"
            if month == 12:
                end_date = f"{year+1}-01-01"
            else:
                end_date = f"{year}-{month+1:02d}-01"

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

    def get_monthly_trend(self, months=6):
        """
        Return monthly totals for the last `months` months.
        Useful for trend charts.
        """
        end_date = datetime.now()
        start_date = end_date - timedelta(days=months * 30)
        self.cursor.execute('''
            SELECT strftime('%Y-%m', date) as month, SUM(amount) as total
            FROM transactions
            WHERE date >= ?
            GROUP BY month
            ORDER BY month
        ''', (start_date.strftime('%Y-%m-%d'),))
        return self.cursor.fetchall()

    def update_transaction(self, trans_id, date, category, amount, description):
        """Update a specific transaction by id."""
        self.cursor.execute('''
            UPDATE transactions
            SET date=?, category=?, amount=?, description=?
            WHERE id=?
        ''', (date, category, amount, description, trans_id))
        self.conn.commit()
        return self.cursor.rowcount

    def delete_transaction(self, transaction_id):
        """Delete transaction and return True if deleted."""
        self.cursor.execute('DELETE FROM transactions WHERE id = ?', (transaction_id,))
        self.conn.commit()
        return self.cursor.rowcount > 0

    def close(self):
        """Close DB connection."""
        if self.conn:
            self.conn.close()


# ------------------------------------------------------------
# FRONTEND: ExpenseTrackerGUI
# Tkinter GUI layer — builds layout, handles user actions,
# delegates DB calls to ExpenseTracker.
# ------------------------------------------------------------
class ExpenseTrackerGUI:
    def __init__(self, root):
        """
        Initialize the main GUI window and components.
        root: Tk() instance.
        """
        self.root = root
        self.root.title("Personal Expense Tracker (INR Version)")
        self.root.geometry("1200x700")
        self.root.configure(bg='#f0f0f0')

        # Backend instance
        self.tracker = ExpenseTracker()

        # Color theme
        self.colors = {
            'primary': "#2E379A",
            'secondary': '#A23B72',
            'success': '#06A77D',
            'danger': '#D90368',
            'light': '#F0F0F0',
            'dark': '#2C3E50'
        }

        # Build UI & load records
        self.create_widgets()
        self.refresh_transactions()

    # ----------------------------
    # Build UI components
    # ----------------------------
    def create_widgets(self):
        """Create and arrange GUI widgets (title, left controls, right table)."""

        # Title bar - application heading
        title_frame = tk.Frame(self.root, bg=self.colors['primary'], height=60)
        title_frame.pack(fill='x')
        title_frame.pack_propagate(False)
        tk.Label(title_frame, text="Personal Expense Tracker (₹ INR)",
                 font=('Arial', 20, 'bold'),
                 bg=self.colors['primary'],
                 fg='white').pack(pady=15)

        # Main container splits left controls and right table
        main_container = tk.Frame(self.root, bg='#f0f0f0')
        main_container.pack(fill='both', expand=True, padx=10, pady=10)

        # Left: Add and actions panel
        left_panel = tk.Frame(main_container, bg='white', relief='raised', bd=2)
        left_panel.pack(side='left', fill='both', padx=(0, 5), pady=0)

        # ---- Add Transaction frame ----
        add_frame = tk.LabelFrame(left_panel, text="Add New Transaction",
                                  font=('Arial', 12, 'bold'), bg='white',
                                  fg=self.colors['dark'], padx=15, pady=15)
        add_frame.pack(fill='x', padx=10, pady=10)

        # Date entry using DateEntry ensures consistent date format
        tk.Label(add_frame, text="Date:", bg='white', font=('Arial', 10)).grid(row=0, column=0, sticky='w', pady=5)
        self.date_entry = DateEntry(add_frame, width=20, background=self.colors['primary'],
                                    foreground='white', borderwidth=2, date_pattern='yyyy-mm-dd')
        self.date_entry.grid(row=0, column=1, pady=5, sticky='ew')

        # Category dropdown using ttk.Combobox for better UI
        tk.Label(add_frame, text="Category:", bg='white', font=('Arial', 10)).grid(row=1, column=0, sticky='w', pady=5)
        self.category_var = tk.StringVar()
        categories = ['Food', 'Transport', 'Entertainment', 'Shopping',
                      'Bills', 'Healthcare', 'Education', 'Other']
        self.category_combo = ttk.Combobox(add_frame, textvariable=self.category_var,
                                           values=categories, width=18, state='readonly')
        self.category_combo.grid(row=1, column=1, pady=5, sticky='ew')
        self.category_combo.set('Food')

        # Amount and description fields
        tk.Label(add_frame, text="Amount (₹):", bg='white', font=('Arial', 10)).grid(row=2, column=0, sticky='w', pady=5)
        self.amount_entry = tk.Entry(add_frame, width=20)
        self.amount_entry.grid(row=2, column=1, pady=5, sticky='ew')

        tk.Label(add_frame, text="Description:", bg='white', font=('Arial', 10)).grid(row=3, column=0, sticky='w', pady=5)
        self.desc_entry = tk.Entry(add_frame, width=20)
        self.desc_entry.grid(row=3, column=1, pady=5, sticky='ew')

        add_frame.columnconfigure(1, weight=1)

        # Add button (calls self.add_transaction)
        tk.Button(add_frame, text="Add Transaction", command=self.add_transaction,
                  bg=self.colors['success'], fg='white', font=('Arial', 11, 'bold'),
                  relief='flat', padx=20, pady=8).grid(row=4, column=0, columnspan=2, pady=10, sticky='ew')

        # ---- Filter & Action frame ----
        filter_frame = tk.LabelFrame(left_panel, text="Filter & Actions",
                                     font=('Arial', 12, 'bold'), bg='white',
                                     fg=self.colors['dark'], padx=15, pady=15)
        filter_frame.pack(fill='x', padx=10, pady=10)

        # Month/Year selectors for filtering
        tk.Label(filter_frame, text="Month:", bg='white', font=('Arial', 10)).grid(row=0, column=0, sticky='w', pady=5)
        self.month_var = tk.IntVar(value=datetime.now().month)
        self.month_spin = tk.Spinbox(filter_frame, from_=1, to=12, width=18, textvariable=self.month_var)
        self.month_spin.grid(row=0, column=1, pady=5, sticky='ew')

        tk.Label(filter_frame, text="Year:", bg='white', font=('Arial', 10)).grid(row=1, column=0, sticky='w', pady=5)
        self.year_var = tk.IntVar(value=datetime.now().year)
        self.year_spin = tk.Spinbox(filter_frame, from_=2020, to=2030, width=18, textvariable=self.year_var)
        self.year_spin.grid(row=1, column=1, pady=5, sticky='ew')

        filter_frame.columnconfigure(1, weight=1)

        # Row of basic action buttons
        btn_frame = tk.Frame(filter_frame, bg='white')
        btn_frame.grid(row=2, column=0, columnspan=2, pady=10, sticky='ew')

        tk.Button(btn_frame, text="View Month", command=self.filter_by_month,
                  bg=self.colors['primary'], fg='white', font=('Arial', 10, 'bold')).pack(side='left', expand=True, fill='x', padx=2)

        tk.Button(btn_frame, text="View All", command=self.refresh_transactions,
                  bg=self.colors['secondary'], fg='white', font=('Arial', 10, 'bold')).pack(side='left', expand=True, fill='x', padx=2)

        # Buttons for report, visualization, edit, delete, export
        tk.Button(filter_frame, text="Generate Report", command=self.show_monthly_report,
                  bg="#937A52", fg='white', font=('Arial', 10, 'bold')).grid(row=3, column=0, columnspan=2, pady=5, sticky='ew')

        tk.Button(filter_frame, text="Visualize Spending", command=self.show_visualization,
                  bg='#9B59B6', fg='white', font=('Arial', 10, 'bold')).grid(row=4, column=0, columnspan=2, pady=5, sticky='ew')

        # EDIT feature button - opens an edit dialog for selected row
        tk.Button(filter_frame, text="Edit Selected", command=self.edit_selected,
                  bg="#1ABC9C", fg='white', font=('Arial', 10, 'bold')).grid(row=5, column=0, columnspan=2, pady=5, sticky='ew')

        # DELETE selected
        tk.Button(filter_frame, text="Delete Selected", command=self.delete_selected,
                  bg=self.colors['danger'], fg='white', font=('Arial', 10, 'bold')).grid(row=6, column=0, columnspan=2, pady=5, sticky='ew')

        # EXPORT buttons
        tk.Button(filter_frame, text="Export CSV", command=self.export_csv,
                  bg="#34495E", fg='white', font=("Arial", 10, "bold")).grid(row=7, column=0, columnspan=2, pady=5, sticky="ew")

        tk.Button(filter_frame, text="Export PDF", command=self.export_pdf,
                  bg="#8E44AD", fg='white', font=("Arial", 10, "bold")).grid(row=8, column=0, columnspan=2, pady=5, sticky="ew")

        # ---- Right side: transaction table and summary ----
        right_panel = tk.Frame(main_container, bg='white', relief='raised', bd=2)
        right_panel.pack(side='right', fill='both', expand=True, padx=(5, 0), pady=0)

        tk.Label(right_panel, text="Transaction History",
                 font=('Arial', 14, 'bold'), bg='white', fg=self.colors['dark']).pack(pady=10)

        tree_frame = tk.Frame(right_panel, bg='white')
        tree_frame.pack(fill='both', expand=True, padx=10, pady=5)

        # Scrollbars
        tree_scroll_y = tk.Scrollbar(tree_frame)
        tree_scroll_y.pack(side='right', fill='y')
        tree_scroll_x = tk.Scrollbar(tree_frame, orient='horizontal')
        tree_scroll_x.pack(side='bottom', fill='x')

        # Treeview shows ID, Date, Category, Amount, Description
        self.tree = ttk.Treeview(tree_frame, columns=('ID', 'Date', 'Category', 'Amount', 'Description'),
                                 show='headings', yscrollcommand=tree_scroll_y.set, xscrollcommand=tree_scroll_x.set)

        tree_scroll_y.config(command=self.tree.yview)
        tree_scroll_x.config(command=self.tree.xview)

        # Column headings and widths
        self.tree.heading('ID', text='ID')
        self.tree.heading('Date', text='Date')
        self.tree.heading('Category', text='Category')
        self.tree.heading('Amount', text='Amount(₹)')
        self.tree.heading('Description', text='Description')

        self.tree.column('ID', width=50, anchor='center')
        self.tree.column('Date', width=100, anchor='center')
        self.tree.column('Category', width=120, anchor='center')
        self.tree.column('Amount', width=100, anchor='e')
        self.tree.column('Description', width=300, anchor='w')

        self.tree.pack(fill='both', expand=True)

        # Tree style for consistent look
        style = ttk.Style()
        style.theme_use('clam')
        style.configure('Treeview', rowheight=25, font=('Arial', 10))
        style.configure('Treeview.Heading', font=('Arial', 11, 'bold'),
                        background=self.colors['primary'], foreground='white')

        # Footer summary label
        self.summary_label = tk.Label(right_panel, text="Total: ₹0.00",
                                      font=('Arial', 13, 'bold'), bg='white', fg=self.colors['success'])
        self.summary_label.pack(pady=10)

    # ----------------------------
    # Add Transaction
    # ----------------------------
    def add_transaction(self):
        """
        Read values from inputs, validate, insert into DB, and refresh table.
        """
        try:
            # DateEntry returns a datetime.date — format it as string
            date = self.date_entry.get_date().strftime('%Y-%m-%d')
            category = self.category_var.get()
            amount = float(self.amount_entry.get())  # validate numeric
            description = self.desc_entry.get()

            if amount <= 0:
                messagebox.showerror("Error", "Amount must be positive!")
                return

            # Delegate DB insert to backend
            self.tracker.add_transaction(date, category, amount, description)
            messagebox.showinfo("Success", "Transaction added successfully!")

            # Clear inputs
            self.amount_entry.delete(0, tk.END)
            self.desc_entry.delete(0, tk.END)

            # Refresh UI table
            self.refresh_transactions()

        except ValueError:
            messagebox.showerror("Error", "Invalid amount! Please enter a number.")

    # ----------------------------
    # Refresh (show all) transactions
    # ----------------------------
    def refresh_transactions(self):
        """Refresh the TreeView with all DB rows and update summary."""
        # Clear existing rows
        for item in self.tree.get_children():
            self.tree.delete(item)

        transactions = self.tracker.get_all_transactions()
        total = 0.0

        # Insert rows and compute total
        for t in transactions:
            # t: (id, date, category, amount, description)
            self.tree.insert('', 'end', values=(t[0], t[1], t[2], f'₹{t[3]:.2f}', t[4]))
            total += float(t[3])

        # Update footer summary
        self.summary_label.config(text=f"Total: ₹{total:.2f} | Transactions: {len(transactions)}")

    # ----------------------------
    # Filter transactions by month/year
    # ----------------------------
    def filter_by_month(self):
        """Display rows only for the selected month and update summary label."""
        for item in self.tree.get_children():
            self.tree.delete(item)

        year = int(self.year_var.get())
        month = int(self.month_var.get())

        transactions = self.tracker.get_transactions_by_month(year, month)
        total = 0.0

        for t in transactions:
            self.tree.insert('', 'end', values=(t[0], t[1], t[2], f'₹{t[3]:.2f}', t[4]))
            total += float(t[3])

        month_name = datetime(year, month, 1).strftime('%B %Y')
        self.summary_label.config(text=f"{month_name} - Total: ₹{total:.2f} | Transactions: {len(transactions)}")

    # ----------------------------
    # Edit Selected Transaction
    # ----------------------------
    def edit_selected(self):
        """
        Open a dialog to edit selected transaction.
        Uses backend update_transaction to persist changes.
        """
        selected = self.tree.selection()
        if not selected:
            messagebox.showwarning("Warning", "Please select a transaction to edit!")
            return

        item = self.tree.item(selected[0])
        trans_id, date, category, amount_str, description = item['values']
        # amount_str is like '₹123.45' — strip currency symbol
        try:
            amount_value = float(str(amount_str).replace('₹', '').replace(',', ''))
        except Exception:
            amount_value = 0.0

        # Edit window
        edit_win = tk.Toplevel(self.root)
        edit_win.title("Edit Transaction")
        edit_win.geometry("420x360")
        edit_win.configure(bg="white")

        # Date field
        tk.Label(edit_win, text="Date:", bg="white").pack(pady=6)
        date_entry = DateEntry(edit_win, width=20, date_pattern="yyyy-mm-dd")
        date_entry.set_date(datetime.strptime(date, "%Y-%m-%d"))
        date_entry.pack()

        # Category
        tk.Label(edit_win, text="Category:", bg="white").pack(pady=6)
        category_var = tk.StringVar(value=category)
        categories = ['Food', 'Transport', 'Entertainment', 'Shopping',
                      'Bills', 'Healthcare', 'Education', 'Other']
        category_box = ttk.Combobox(edit_win, textvariable=category_var, values=categories, state='readonly')
        category_box.pack()

        # Amount
        tk.Label(edit_win, text="Amount (₹):", bg="white").pack(pady=6)
        amount_entry = tk.Entry(edit_win)
        amount_entry.insert(0, f"{amount_value:.2f}")
        amount_entry.pack()

        # Description
        tk.Label(edit_win, text="Description:", bg="white").pack(pady=6)
        desc_entry = tk.Entry(edit_win)
        desc_entry.insert(0, description)
        desc_entry.pack()

        # Save changes closure
        def save_changes():
            try:
                new_date = date_entry.get_date().strftime("%Y-%m-%d")
                new_cat = category_var.get()
                new_amount = float(amount_entry.get())
                new_desc = desc_entry.get()

                if new_amount <= 0:
                    messagebox.showerror("Error", "Amount must be positive!")
                    return

                # Call backend update
                self.tracker.update_transaction(trans_id, new_date, new_cat, new_amount, new_desc)
                messagebox.showinfo("Success", "Transaction updated!")
                edit_win.destroy()
                self.refresh_transactions()
            except ValueError:
                messagebox.showerror("Error", "Invalid amount! Enter a number.")

        tk.Button(edit_win, text="Save Changes", bg="#27AE60", fg="white",
                  font=("Arial", 12, "bold"), command=save_changes).pack(pady=14)

    # ----------------------------
    # Delete selected transaction
    # ----------------------------
    def delete_selected(self):
        """Delete selected transaction after confirmation."""
        selected = self.tree.selection()
        if not selected:
            messagebox.showwarning("Warning", "Please select a transaction to delete!")
            return

        item = self.tree.item(selected[0])
        trans_id = item['values'][0]

        if messagebox.askyesno("Confirm", "Are you sure you want to delete this transaction?"):
            if self.tracker.delete_transaction(trans_id):
                messagebox.showinfo("Success", "Transaction deleted!")
                self.refresh_transactions()
            else:
                messagebox.showerror("Error", "Could not delete transaction!")

    # ----------------------------
    # Monthly report window (table)
    # ----------------------------
    def show_monthly_report(self):
        """Open a window that shows monthly totals and category breakdown."""
        year = int(self.year_var.get())
        month = int(self.month_var.get())

        transactions = self.tracker.get_transactions_by_month(year, month)
        category_summary = self.tracker.get_category_summary(year, month)

        if not transactions:
            messagebox.showinfo("Info", "No transactions found for this month!")
            return

        report_win = tk.Toplevel(self.root)
        report_win.title(f"Report - {datetime(year, month, 1).strftime('%B %Y')}")
        report_win.geometry("640x520")
        report_win.configure(bg='white')

        tk.Label(report_win, text="Expense Report", font=('Arial', 18, 'bold'),
                 bg='white', fg=self.colors['primary']).pack(pady=16)
        tk.Label(report_win, text=datetime(year, month, 1).strftime('%B %Y'),
                 font=('Arial', 14), bg='white', fg=self.colors['dark']).pack()

        total = sum(t[3] for t in transactions)
        summary_frame = tk.Frame(report_win, bg='#ecf0f1', relief='solid', bd=1)
        summary_frame.pack(fill='x', padx=20, pady=16)
        tk.Label(summary_frame, text=f"Total Expenses: ₹{total:.2f}", font=('Arial', 14, 'bold'),
                 bg='#ecf0f1', fg=self.colors['danger']).pack(pady=8)
        tk.Label(summary_frame, text=f"Number of Transactions: {len(transactions)}",
                 font=('Arial', 12), bg='#ecf0f1').pack(pady=4)

        tk.Label(report_win, text="Category Breakdown", font=('Arial', 13, 'bold'),
                 bg='white', fg=self.colors['dark']).pack(pady=(18, 8))

        cat_frame = tk.Frame(report_win, bg='white')
        cat_frame.pack(fill='both', expand=True, padx=20, pady=10)

        cat_tree = ttk.Treeview(cat_frame, columns=('Category', 'Amount', 'Percentage'),
                                show='headings', height=10)
        cat_tree.heading('Category', text='Category')
        cat_tree.heading('Amount', text='Amount (₹)')
        cat_tree.heading('Percentage', text='Percentage')
        cat_tree.column('Category', width=220, anchor='w')
        cat_tree.column('Amount', width=180, anchor='e')
        cat_tree.column('Percentage', width=120, anchor='e')

        # Populate category tree with percentages
        for cat, amount in category_summary:
            percentage = (amount / total) * 100 if total else 0
            cat_tree.insert('', 'end', values=(cat, f'₹{amount:.2f}', f'{percentage:.1f}%'))

        cat_tree.pack(fill='both', expand=True)

    # ----------------------------
    # Visualization window (charts)
    # ----------------------------
    def show_visualization(self):
        """Plot pie, bar and daily line charts for selected month."""
        year = int(self.year_var.get())
        month = int(self.month_var.get())

        transactions = self.tracker.get_transactions_by_month(year, month)
        category_summary = self.tracker.get_category_summary(year, month)

        if not transactions:
            messagebox.showinfo("Info", "No data to visualize for this month!")
            return

        viz_win = tk.Toplevel(self.root)
        viz_win.title(f"Spending Analysis - {datetime(year, month, 1).strftime('%B %Y')}")
        viz_win.geometry("1000x800")

        fig, ((ax1, ax2), (ax3, ax4)) = plt.subplots(2, 2, figsize=(12, 10))
        fig.suptitle(f'Expense Analysis - {datetime(year, month, 1).strftime("%B %Y")}',
                     fontsize=16, fontweight='bold')

        categories = [cat for cat, _ in category_summary]
        amounts = [amt for _, amt in category_summary]
        colors = plt.cm.Set3(range(len(categories))) if categories else None

        # Pie chart: category distribution
        if categories and amounts:
            ax1.pie(amounts, labels=categories, autopct='%1.1f%%', colors=colors, startangle=90)
        ax1.set_title('Spending by Category')

        # Bar chart: horizontal comparison
        ax2.barh(categories, amounts, color=colors)
        ax2.set_xlabel('Amount (₹)')
        ax2.set_title('Category Comparison')
        ax2.invert_yaxis()
        for i, v in enumerate(amounts):
            ax2.text(v, i, f' ₹{v:.2f}', va='center')

        # Daily spending: aggregate per date
        daily_spending = defaultdict(float)
        for t in transactions:
            # t[1] is date string; accumulate spending per date
            daily_spending[t[1]] += float(t[3])

        dates = sorted(daily_spending.keys())
        daily_amounts = [daily_spending[d] for d in dates]

        ax3.plot(dates, daily_amounts, marker='o', linestyle='-', linewidth=2, markersize=6)
        ax3.set_xlabel('Date')
        ax3.set_ylabel('Amount (₹)')
        ax3.set_title('Daily Spending Pattern')
        ax3.tick_params(axis='x', rotation=45)
        ax3.grid(True, alpha=0.3)

        # Summary stats textbox
        ax4.axis('off')
        total = sum(amounts) if amounts else 0
        avg_per_transaction = total / len(transactions) if transactions else 0
        max_transaction = max(float(t[3]) for t in transactions) if transactions else 0

        top_cat = categories[0] if categories else "N/A"
        top_amt = amounts[0] if amounts else 0

        stats_text = f"""SUMMARY STATISTICS
{'─' * 30}

Total Spending:        ₹{total:,.2f}

Transactions:          {len(transactions)}

Average/Transaction:   ₹{avg_per_transaction:.2f}

Largest Transaction:   ₹{max_transaction:.2f}

Top Category:          {top_cat}
                      (₹{top_amt:.2f})
"""
        ax4.text(0.05, 0.5, stats_text, fontsize=11, family='monospace', verticalalignment='center')

        plt.tight_layout()

        # Embed matplotlib figure in Tkinter window
        canvas = FigureCanvasTkAgg(fig, master=viz_win)
        canvas.draw()
        canvas.get_tk_widget().pack(fill='both', expand=True)

    # ----------------------------
    # Export to CSV
    # ----------------------------
    def export_csv(self):
        """Export all transactions to CSV (asks for save location)."""
        transactions = self.tracker.get_all_transactions()
        if not transactions:
            messagebox.showwarning("Warning", "No data to export!")
            return

        file_path = asksaveasfilename(defaultextension=".csv", filetypes=[("CSV Files", "*.csv")])
        if not file_path:
            return

        try:
            with open(file_path, "w", newline="", encoding="utf-8") as file:
                writer = csv.writer(file)
                writer.writerow(["ID", "Date", "Category", "Amount (₹)", "Description"])
                for row in transactions:
                    writer.writerow(row)
            messagebox.showinfo("Success", f"Data exported to CSV:\n{file_path}")
        except Exception as e:
            messagebox.showerror("Error", f"Could not export CSV:\n{e}")

    # ----------------------------
    # Export to PDF (simple text table)
    # ----------------------------
    def export_pdf(self):
        """
        Export transactions into a simple PDF.
        Uses reportlab if available; otherwise shows an error.
        """
        if not REPORTLAB_AVAILABLE:
            messagebox.showerror("Dependency Missing", "reportlab is required for PDF export.\nInstall with: pip install reportlab")
            return

        transactions = self.tracker.get_all_transactions()
        if not transactions:
            messagebox.showwarning("Warning", "No data to export!")
            return

        file_path = asksaveasfilename(defaultextension=".pdf", filetypes=[("PDF Files", "*.pdf")])
        if not file_path:
            return

        try:
            c = canvas.Canvas(file_path, pagesize=letter)
            c.setFont("Helvetica-Bold", 14)
            c.drawCentredString(300, 750, "Expense Report")
            c.setFont("Helvetica", 10)
            c.line(40, 744, 560, 744)

            y = 720
            for row in transactions:
                text_line = f"ID: {row[0]}   Date: {row[1]}   Category: {row[2]}   Amount: ₹{row[3]:.2f}"
                c.drawString(40, y, text_line)
                if row[4]:
                    # Draw description on next line if present
                    y -= 14
                    c.drawString(60, y, f"Description: {row[4]}")
                y -= 24
                if y < 60:
                    c.showPage()
                    y = 750
                    c.setFont("Helvetica", 10)

            c.save()
            messagebox.showinfo("Success", f"PDF exported:\n{file_path}")
        except Exception as e:
            messagebox.showerror("Error", f"Could not export PDF:\n{e}")

    # ----------------------------
    # Clean shutdown
    # ----------------------------
    def on_closing(self):
        """Ensure DB connection closed when the application exits."""
        self.tracker.close()
        self.root.destroy()


# ------------------------------------------------------------
# MAIN: launch the application
# ------------------------------------------------------------
def main():
    root = tk.Tk()
    app = ExpenseTrackerGUI(root)
    root.protocol("WM_DELETE_WINDOW", app.on_closing)
    root.mainloop()


if __name__ == "__main__":
    main()
