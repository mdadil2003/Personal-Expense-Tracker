# Personal-Expense-Tracker-Project 
import sqlite3
import csv
from datetime import datetime, timedelta
from collections import defaultdict

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from tkcalendar import DateEntry

import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

# PDF export (optional, handled safely if missing)
try:
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.styles import getSampleStyleSheet
    REPORTLAB_AVAILABLE = True
except Exception:
    REPORTLAB_AVAILABLE = False

#  BACKEND: DATABASE LAYER


class ExpenseTrackerDB:
    """
    Handles all database operations:
    - create table
    - add, update, delete transactions
    - fetch all, fetch by month, search
    """
    def __init__(self, db_name="expenses.db"):
        self.db_name = db_name
        self.conn = sqlite3.connect(self.db_name)
        self.cursor = self.conn.cursor()
        self.create_tables()

    def create_tables(self):
        """Create the transactions table if it doesn't exist."""
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
        """Insert a new transaction row."""
        self.cursor.execute('''
            INSERT INTO transactions (date, category, amount, description)
            VALUES (?, ?, ?, ?)
        ''', (date, category, amount, description))
        self.conn.commit()
        return self.cursor.lastrowid

    def update_transaction(self, trans_id, date, category, amount, description=""):
        """Update an existing transaction by ID."""
        self.cursor.execute('''
            UPDATE transactions
            SET date=?, category=?, amount=?, description=?
            WHERE id=?
        ''', (date, category, amount, description, trans_id))
        self.conn.commit()
        return self.cursor.rowcount

    def get_all_transactions(self):
        """Fetch all transactions sorted by date (newest first)."""
        self.cursor.execute('''
            SELECT id, date, category, amount, description
            FROM transactions
            ORDER BY date DESC
        ''')
        return self.cursor.fetchall()

    def get_transactions_by_month(self, year, month):
        """Fetch all transactions for a specific month and year."""
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
        Return category-wise total for:
        - given month/year, or
        - all data if year/month not provided.
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

    def delete_transaction(self, trans_id):
        """Delete a transaction by ID."""
        self.cursor.execute('DELETE FROM transactions WHERE id = ?', (trans_id,))
        self.conn.commit()
        return self.cursor.rowcount > 0

    def search(self, keyword):
        """Simple search by category or description (case-insensitive)."""
        key = f"%{keyword.lower()}%"
        self.cursor.execute('''
            SELECT id, date, category, amount, description
            FROM transactions
            WHERE LOWER(category) LIKE ? OR LOWER(description) LIKE ?
            ORDER BY date DESC
        ''', (key, key))
        return self.cursor.fetchall()

    def close(self):
        """Close database connection."""
        if self.conn:
            self.conn.close()


class ExpenseTrackerGUI:
    """
    GUI application:
    - Left side: Add/Edit form + Filters + Search
    - Right side: Transaction table + Summary + Export + Visualize
    """

    def __init__(self, root):
        self.root = root
        self.root.title("Personal Expense Tracker (INR Version)")
        self.root.geometry("1200x700")

        self.db = ExpenseTrackerDB()
        self.editing_id = None      # will store the ID when editing a record
        self.dark_mode = False      # theme flag

        # Color themes
        self.light_colors = {
            "bg": "#f0f0f0",
            "panel": "white",
            "primary": "#2E379A",
            "secondary": "#A23B72",
            "success": "#06A77D",
            "danger": "#D90368",
            "text": "#222"
        }
        self.dark_colors = {
            "bg": "#1e1e1e",
            "panel": "#2a2a2a",
            "primary": "#3949AB",
            "secondary": "#EC407A",
            "success": "#26A69A",
            "danger": "#EF5350",
            "text": "#f0f0f0"
        }
        self.colors = self.light_colors

        self.build_ui()
        self.apply_theme()
        self.refresh_transactions()


    def build_ui(self):
        # Title bar
        self.title_frame = tk.Frame(self.root, height=60)
        self.title_frame.pack(fill='x')
        self.title_frame.pack_propagate(False)

        self.title_label = tk.Label(
            self.title_frame,
            text="Personal Expense Tracker (INR Version)",
            font=('Arial', 20, 'bold')
        )
        self.title_label.pack(side='left', padx=10, pady=10)

        # Top-right: search + export + theme
        top_right = tk.Frame(self.title_frame)
        top_right.pack(side='right', padx=10)

        # Search bar
        self.search_var = tk.StringVar()
        self.search_entry = tk.Entry(top_right, textvariable=self.search_var, width=25)
        self.search_entry.pack(side='left', padx=3)
        tk.Button(top_right, text="Search", command=self.search_records).pack(side='left', padx=2)
        tk.Button(top_right, text="Clear", command=self.clear_search).pack(side='left', padx=2)

        # Export buttons
        tk.Button(top_right, text="Export CSV", command=self.export_csv).pack(side='left', padx=4)
        tk.Button(top_right, text="Export PDF", command=self.export_pdf).pack(side='left', padx=4)

        # Dark mode toggle
        tk.Button(top_right, text="Toggle Dark", command=self.toggle_theme).pack(side='left', padx=4)

        # Main container
        self.main_container = tk.Frame(self.root)
        self.main_container.pack(fill='both', expand=True, padx=10, pady=10)

        # Left panel (form + filters)
        self.left_panel = tk.Frame(self.main_container, bd=2, relief='raised')
        self.left_panel.pack(side='left', fill='y', padx=(0, 5))

        # Right panel (table + summary)
        self.right_panel = tk.Frame(self.main_container, bd=2, relief='raised')
        self.right_panel.pack(side='right', fill='both', expand=True, padx=(5, 0))

        self.build_left_panel()
        self.build_right_panel()

    def build_left_panel(self):
        # Add Transaction frame
        self.add_frame = tk.LabelFrame(
            self.left_panel, text="Add / Edit Transaction",
            font=('Arial', 12, 'bold'), padx=15, pady=15
        )
        self.add_frame.pack(fill='x', padx=10, pady=10)

        # Date
        tk.Label(self.add_frame, text="Date:", font=('Arial', 10)).grid(row=0, column=0, sticky='w', pady=5)
        self.date_entry = DateEntry(self.add_frame, width=20, date_pattern='yyyy-mm-dd')
        self.date_entry.grid(row=0, column=1, pady=5, sticky='ew')

        # Category
        tk.Label(self.add_frame, text="Category:", font=('Arial', 10)).grid(row=1, column=0, sticky='w', pady=5)
        self.category_var = tk.StringVar()
        categories = ['Food', 'Transport', 'Entertainment', 'Shopping',
                      'Bills', 'Healthcare', 'Education', 'Other']
        self.category_combo = ttk.Combobox(
            self.add_frame, textvariable=self.category_var,
            values=categories, width=18, state='readonly'
        )
        self.category_combo.grid(row=1, column=1, pady=5, sticky='ew')
        self.category_combo.set('Food')

        # Amount
        tk.Label(self.add_frame, text="Amount (₹):", font=('Arial', 10)).grid(row=2, column=0, sticky='w', pady=5)
        self.amount_entry = tk.Entry(self.add_frame, width=20)
        self.amount_entry.grid(row=2, column=1, pady=5, sticky='ew')

        # Description
        tk.Label(self.add_frame, text="Description:", font=('Arial', 10)).grid(row=3, column=0, sticky='w', pady=5)
        self.desc_entry = tk.Entry(self.add_frame, width=20)
        self.desc_entry.grid(row=3, column=1, pady=5, sticky='ew')

        self.add_frame.columnconfigure(1, weight=1)

        # Add / Update buttons
        self.add_button = tk.Button(
            self.add_frame, text="Add Transaction",
            command=self.add_or_update_transaction,
            font=('Arial', 11, 'bold'), padx=20, pady=6
        )
        self.add_button.grid(row=4, column=0, columnspan=2, pady=8, sticky='ew')

        tk.Button(
            self.add_frame, text="Clear",
            command=self.clear_form
        ).grid(row=5, column=0, columnspan=2, sticky='ew')

        # Filter & Actions frame (month/year + actions)
        self.filter_frame = tk.LabelFrame(
            self.left_panel, text="Filter & Actions",
            font=('Arial', 12, 'bold'), padx=15, pady=15
        )
        self.filter_frame.pack(fill='x', padx=10, pady=10)

        tk.Label(self.filter_frame, text="Month:", font=('Arial', 10)).grid(row=0, column=0, sticky='w', pady=5)
        self.month_var = tk.IntVar(value=datetime.now().month)
        self.month_spin = tk.Spinbox(self.filter_frame, from_=1, to=12, width=8, textvariable=self.month_var)
        self.month_spin.grid(row=0, column=1, pady=5, sticky='ew')

        tk.Label(self.filter_frame, text="Year:", font=('Arial', 10)).grid(row=1, column=0, sticky='w', pady=5)
        self.year_var = tk.IntVar(value=datetime.now().year)
        self.year_spin = tk.Spinbox(self.filter_frame, from_=2020, to=2035, width=8, textvariable=self.year_var)
        self.year_spin.grid(row=1, column=1, pady=5, sticky='ew')

        self.filter_frame.columnconfigure(1, weight=1)

        # Buttons under filter
        tk.Button(
            self.filter_frame, text="View Month",
            command=self.filter_by_month
        ).grid(row=2, column=0, columnspan=2, pady=5, sticky='ew')

        tk.Button(
            self.filter_frame, text="View All",
            command=self.refresh_transactions
        ).grid(row=3, column=0, columnspan=2, pady=5, sticky='ew')

        tk.Button(
            self.filter_frame, text="Monthly Report",
            command=self.show_monthly_report
        ).grid(row=4, column=0, columnspan=2, pady=5, sticky='ew')

        tk.Button(
            self.filter_frame, text="Visualize Spending",
            command=self.show_visualization
        ).grid(row=5, column=0, columnspan=2, pady=5, sticky='ew')

        tk.Button(
            self.filter_frame, text="Edit Selected",
            command=self.edit_selected
        ).grid(row=6, column=0, columnspan=2, pady=5, sticky='ew')

        tk.Button(
            self.filter_frame, text="Delete Selected",
            command=self.delete_selected
        ).grid(row=7, column=0, columnspan=2, pady=5, sticky='ew')

    def build_right_panel(self):
        # Title above table
        self.list_label = tk.Label(
            self.right_panel,
            text="Transaction History",
            font=('Arial', 14, 'bold')
        )
        self.list_label.pack(pady=10)

        # Treeview frame + scrollbars
        tree_frame = tk.Frame(self.right_panel)
        tree_frame.pack(fill='both', expand=True, padx=10, pady=5)

        tree_scroll_y = tk.Scrollbar(tree_frame)
        tree_scroll_y.pack(side='right', fill='y')

        tree_scroll_x = tk.Scrollbar(tree_frame, orient='horizontal')
        tree_scroll_x.pack(side='bottom', fill='x')

        self.tree = ttk.Treeview(
            tree_frame,
            columns=('ID', 'Date', 'Category', 'Amount', 'Description'),
            show='headings',
            yscrollcommand=tree_scroll_y.set,
            xscrollcommand=tree_scroll_x.set
        )

        tree_scroll_y.config(command=self.tree.yview)
        tree_scroll_x.config(command=self.tree.xview)

        # Columns
        self.tree.heading('ID', text='ID')
        self.tree.heading('Date', text='Date')
        self.tree.heading('Category', text='Category')
        self.tree.heading('Amount', text='Amount (₹)')
        self.tree.heading('Description', text='Description')

        self.tree.column('ID', width=50, anchor='center')
        self.tree.column('Date', width=100, anchor='center')
        self.tree.column('Category', width=120, anchor='center')
        self.tree.column('Amount', width=100, anchor='e')
        self.tree.column('Description', width=350, anchor='w')

        self.tree.pack(fill='both', expand=True)

        # Style for TreeView
        self.style = ttk.Style()
        self.style.theme_use('clam')
        self.apply_tree_style()

        # Summary label at bottom
        self.summary_label = tk.Label(
            self.right_panel, text="Total: ₹0.00",
            font=('Arial', 13, 'bold')
        )
        self.summary_label.pack(pady=10)



    def apply_tree_style(self):
        """Apply treeview colors based on current theme."""
        fg = self.colors["text"]
        bg = self.colors["panel"]
        header_bg = self.colors["primary"]
        header_fg = "white"

        self.style.configure(
            "Treeview",
            background=bg,
            foreground=fg,
            fieldbackground=bg,
            rowheight=25,
            font=('Arial', 10)
        )
        self.style.configure(
            "Treeview.Heading",
            font=('Arial', 11, 'bold'),
            background=header_bg,
            foreground=header_fg
        )

    def apply_theme(self):
        """Apply current color theme to major widgets."""
        c = self.colors
        self.root.configure(bg=c["bg"])
        self.title_frame.configure(bg=c["primary"])
        self.title_label.configure(bg=c["primary"], fg="white")

        self.main_container.configure(bg=c["bg"])
        self.left_panel.configure(bg=c["panel"])
        self.right_panel.configure(bg=c["panel"])

        self.add_frame.configure(bg=c["panel"], fg=c["text"])
        self.filter_frame.configure(bg=c["panel"], fg=c["text"])

        # Labels in left panel
        for child in self.add_frame.winfo_children():
            if isinstance(child, tk.Label):
                child.configure(bg=c["panel"], fg=c["text"])
        for child in self.filter_frame.winfo_children():
            if isinstance(child, tk.Label):
                child.configure(bg=c["panel"], fg=c["text"])

        self.list_label.configure(bg=c["panel"], fg=c["text"])
        self.summary_label.configure(bg=c["panel"], fg=c["success"])

        self.apply_tree_style()

    def toggle_theme(self):
        """Switch between light and dark themes."""
        self.dark_mode = not self.dark_mode
        self.colors = self.dark_colors if self.dark_mode else self.light_colors
        self.apply_theme()



    def clear_form(self):
        """Reset form fields and exit edit mode."""
        self.date_entry.set_date(datetime.now().date())
        self.category_combo.set('Food')
        self.amount_entry.delete(0, tk.END)
        self.desc_entry.delete(0, tk.END)
        self.editing_id = None
        self.add_button.configure(text="Add Transaction")

    def add_or_update_transaction(self):
        """Add a new transaction OR update existing based on editing_id."""
        try:
            date_str = self.date_entry.get_date().strftime('%Y-%m-%d')
        except Exception:
            date_str = self.date_entry.get()

        category = self.category_var.get()
        description = self.desc_entry.get()

        # Validate amount
        try:
            amount = float(self.amount_entry.get())
        except ValueError:
            messagebox.showerror("Error", "Invalid amount. Please enter a number.")
            return

        if amount <= 0:
            messagebox.showerror("Error", "Amount must be positive.")
            return

        if self.editing_id:
            # Update existing
            self.db.update_transaction(self.editing_id, date_str, category, amount, description)
            messagebox.showinfo("Updated", "Transaction updated successfully.")
            self.editing_id = None
            self.add_button.configure(text="Add Transaction")
        else:
            # Add new
            self.db.add_transaction(date_str, category, amount, description)
            messagebox.showinfo("Success", "Transaction added successfully.")

        self.clear_form()
        self.refresh_transactions()

    def refresh_transactions(self, rows=None):
        """Refresh the TreeView with all or given rows."""
        # Clear table
        for item in self.tree.get_children():
            self.tree.delete(item)

        if rows is None:
            rows = self.db.get_all_transactions()

        total = 0
        for t in rows:
            self.tree.insert('', 'end', values=(t[0], t[1], t[2], f'₹{t[3]:.2f}', t[4]))
            total += t[3]

        self.summary_label.config(text=f"Total: ₹{total:.2f} | Transactions: {len(rows)}")

    def filter_by_month(self):
        """Filter transactions by month/year from spinboxes."""
        year = int(self.year_var.get())
        month = int(self.month_var.get())
        rows = self.db.get_transactions_by_month(year, month)
        self.refresh_transactions(rows)

    def delete_selected(self):
        """Delete selected row from the table and DB."""
        selected = self.tree.selection()
        if not selected:
            messagebox.showwarning("Warning", "Please select a transaction to delete!")
            return

        item = self.tree.item(selected[0])
        trans_id = item['values'][0]

        if messagebox.askyesno("Confirm", "Are you sure you want to delete this transaction?"):
            if self.db.delete_transaction(trans_id):
                messagebox.showinfo("Success", "Transaction deleted!")
                self.refresh_transactions()
            else:
                messagebox.showerror("Error", "Could not delete transaction!")

    def edit_selected(self):
        """Load selected row data into form for editing."""
        selected = self.tree.selection()
        if not selected:
            messagebox.showwarning("Warning", "Please select a transaction to edit!")
            return

        values = self.tree.item(selected[0])['values']
        trans_id = values[0]

        # Fetch row from DB 
        record = self.db.cursor.execute(
            "SELECT id, date, category, amount, description FROM transactions WHERE id=?",
            (trans_id,)
        ).fetchone()

        if not record:
            messagebox.showerror("Error", "Could not fetch transaction from database!")
            return

        self.editing_id = record[0]
        try:
            self.date_entry.set_date(datetime.strptime(record[1], '%Y-%m-%d').date())
        except Exception:
            pass

        self.category_combo.set(record[2])
        self.amount_entry.delete(0, tk.END)
        self.amount_entry.insert(0, str(record[3]))
        self.desc_entry.delete(0, tk.END)
        self.desc_entry.insert(0, record[4] or "")

        self.add_button.configure(text="Update Transaction")


    def search_records(self):
        """Search transactions by category or description."""
        keyword = self.search_var.get().strip()
        if not keyword:
            messagebox.showinfo("Search", "Please enter a search keyword.")
            return

        results = self.db.search(keyword)
        self.refresh_transactions(results)

    def clear_search(self):
        self.search_var.set("")
        self.refresh_transactions()



    def show_monthly_report(self):
        """Show monthly summary (total + category breakdown)."""
        year = int(self.year_var.get())
        month = int(self.month_var.get())

        transactions = self.db.get_transactions_by_month(year, month)
        category_summary = self.db.get_category_summary(year, month)

        if not transactions:
            messagebox.showinfo("Info", "No transactions found for this month!")
            return

        report_win = tk.Toplevel(self.root)
        report_win.title(f"Report - {datetime(year, month, 1).strftime('%B %Y')}")
        report_win.geometry("600x500")

        tk.Label(report_win, text="Expense Report",
                 font=('Arial', 18, 'bold')).pack(pady=20)

        tk.Label(report_win, text=datetime(year, month, 1).strftime('%B %Y'),
                 font=('Arial', 14)).pack()

        total = sum(t[3] for t in transactions)
        summary_frame = tk.Frame(report_win, bd=1, relief='solid')
        summary_frame.pack(fill='x', padx=20, pady=20)

        tk.Label(summary_frame, text=f"Total Expenses: ₹{total:.2f}",
                 font=('Arial', 14, 'bold'), fg="red").pack(pady=10)
        tk.Label(summary_frame, text=f"Number of Transactions: {len(transactions)}",
                 font=('Arial', 12)).pack(pady=5)

        tk.Label(report_win, text="Category Breakdown",
                 font=('Arial', 13, 'bold')).pack(pady=(20, 10))

        cat_frame = tk.Frame(report_win)
        cat_frame.pack(fill='both', expand=True, padx=20, pady=10)

        cat_tree = ttk.Treeview(cat_frame, columns=('Category', 'Amount', 'Percentage'),
                                show='headings', height=10)
        cat_tree.heading('Category', text='Category')
        cat_tree.heading('Amount', text='Amount (₹)')
        cat_tree.heading('Percentage', text='Percentage')

        cat_tree.column('Category', width=200, anchor='w')
        cat_tree.column('Amount', width=150, anchor='e')
        cat_tree.column('Percentage', width=150, anchor='e')

        cat_tree.pack(fill='both', expand=True)

        for cat, amount in category_summary:
            percentage = (amount / total) * 100 if total else 0
            cat_tree.insert('', 'end', values=(cat, f'₹{amount:.2f}', f'{percentage:.1f}%'))


    #  VISUALIZATION (CHARTS)
   
    def show_visualization(self):
        """Show pie, bar, daily line chart and stats in a new window."""
        year = int(self.year_var.get())
        month = int(self.month_var.get())

        transactions = self.db.get_transactions_by_month(year, month)
        category_summary = self.db.get_category_summary(year, month)

        if not transactions:
            messagebox.showinfo("Info", "No data to visualize for this month!")
            return

        viz_win = tk.Toplevel(self.root)
        viz_win.title(f"Spending Analysis - {datetime(year, month, 1).strftime('%B %Y')}")
        viz_win.geometry("1000x800")

        # Apply dark or light style to charts
        if self.dark_mode:
            plt.style.use("dark_background")
        else:
            plt.style.use("default")

        fig, ((ax1, ax2), (ax3, ax4)) = plt.subplots(2, 2, figsize=(12, 10))
        fig.suptitle(f'Expense Analysis - {datetime(year, month, 1).strftime("%B %Y")}',
                     fontsize=16, fontweight='bold')

        # Pie chart
        categories = [cat for cat, _ in category_summary]
        amounts = [amt for _, amt in category_summary]
        colors = plt.cm.Set3(range(len(categories))) if categories else None

        if categories:
            ax1.pie(amounts, labels=categories, autopct='%1.1f%%',
                    colors=colors, startangle=90)
            ax1.set_title('Spending by Category')
        else:
            ax1.text(0.5, 0.5, "No category data", ha="center", va="center")
            ax1.set_axis_off()

        # Bar chart
        if categories:
            ax2.barh(categories, amounts, color=colors)
            ax2.set_xlabel('Amount (₹)')
            ax2.set_title('Category Comparison')
            ax2.invert_yaxis()
            for i, v in enumerate(amounts):
                ax2.text(v, i, f' ₹{v:.2f}', va='center')
        else:
            ax2.text(0.5, 0.5, "No data", ha="center", va="center")
            ax2.set_axis_off()

    # Daily spending line chart
        daily_spending = defaultdict(float)
        for t in transactions:
            daily_spending[t[1]] += t[3]

        dates = sorted(daily_spending.keys())
        daily_amounts = [daily_spending[d] for d in dates]

        ax3.plot(dates, daily_amounts, marker='o', linestyle='-', linewidth=2, markersize=6)
        ax3.set_xlabel('Date')
        ax3.set_ylabel('Amount (₹)')
        ax3.set_title('Daily Spending Pattern')
        ax3.tick_params(axis='x', rotation=45)
        ax3.grid(True, alpha=0.3)


        ax4.axis('off')
        total = sum(amounts) if amounts else sum(t[3] for t in transactions)
        avg_per_transaction = total / len(transactions) if transactions else 0
        max_transaction = max(t[3] for t in transactions) if transactions else 0
        top_cat = categories[0] if categories else "N/A"

        stats_text = f"""
SUMMARY STATISTICS
{'─' * 30}

Total Spending:        ₹{total:,.2f}

Transactions:          {len(transactions)}

Average/Transaction:   ₹{avg_per_transaction:.2f}

Largest Transaction:   ₹{max_transaction:.2f}

Top Category:          {top_cat}
        """
        ax4.text(0.05, 0.5, stats_text, fontsize=11, family='monospace',
                 verticalalignment='center')

        plt.tight_layout()

        canvas = FigureCanvasTkAgg(fig, master=viz_win)
        canvas.draw()
        canvas.get_tk_widget().pack(fill='both', expand=True)


    def export_csv(self):
        """Export current table view to CSV."""
        file_path = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv")]
        )
        if not file_path:
            return

        try:
            with open(file_path, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(["ID", "Date", "Category", "Amount (₹)", "Description"])
                for item in self.tree.get_children():
                    row = self.tree.item(item)["values"]
                    writer.writerow(row)
            messagebox.showinfo("Export CSV", f"Data exported to {file_path}")
        except Exception as e:
            messagebox.showerror("Export CSV", f"Error: {e}")

    def export_pdf(self):
        """Export current table view as a simple PDF report (if reportlab is available)."""
        if not REPORTLAB_AVAILABLE:
            messagebox.showwarning(
                "Export PDF",
                "reportlab is not installed.\nInstall it using:\n\npip install reportlab"
            )
            return

        file_path = filedialog.asksaveasfilename(
            defaultextension=".pdf",
            filetypes=[("PDF files", "*.pdf")]
        )
        if not file_path:
            return

        # Collect data from treeview
        data = [["ID", "Date", "Category", "Amount (₹)", "Description"]]
        for item in self.tree.get_children():
            row = self.tree.item(item)["values"]
            data.append([str(x) for x in row])

        try:
            doc = SimpleDocTemplate(file_path, pagesize=landscape(A4))
            styles = getSampleStyleSheet()
            story = []

            story.append(Paragraph("Personal Expense Report", styles["Title"]))
            story.append(Spacer(1, 12))

            table = Table(data, repeatRows=1)
            table.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2E379A")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.black),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ]))
            story.append(table)
            doc.build(story)

            messagebox.showinfo("Export PDF", f"PDF exported to {file_path}")
        except Exception as e:
            messagebox.showerror("Export PDF", f"Error: {e}")



    def on_closing(self):
        self.db.close()
        self.root.destroy()


def main():
    root = tk.Tk()
    app = ExpenseTrackerGUI(root)
    root.protocol("WM_DELETE_WINDOW", app.on_closing)
    root.mainloop()


if __name__ == "__main__":
    main()
# End of Personal-Expense-Tracker-Project
