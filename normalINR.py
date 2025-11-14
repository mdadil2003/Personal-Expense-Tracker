import sqlite3
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from datetime import datetime, timedelta
from collections import defaultdict
import tkinter as tk
from tkinter import ttk, messagebox
from tkcalendar import DateEntry

class ExpenseTracker:
    def __init__(self, db_name="expenses.db"):
        self.db_name = db_name
        self.conn = None
        self.cursor = None
        self.connect()
        self.create_tables()
    
    def connect(self):
        """Connect to the SQLite database"""
        self.conn = sqlite3.connect(self.db_name)
        self.cursor = self.conn.cursor()
    
    def create_tables(self):
        """Create necessary tables if they don't exist"""
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
        """Add a new transaction"""
        self.cursor.execute('''
            INSERT INTO transactions (date, category, amount, description)
            VALUES (?, ?, ?, ?)
        ''', (date, category, amount, description))
        self.conn.commit()
        return self.cursor.lastrowid
    
    def get_all_transactions(self):
        """Retrieve all transactions"""
        self.cursor.execute('''
            SELECT id, date, category, amount, description 
            FROM transactions 
            ORDER BY date DESC
        ''')
        return self.cursor.fetchall()
    
    def get_transactions_by_month(self, year, month):
        """Get transactions for a specific month"""
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
        """Get spending summary by category"""
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
        """Get spending trend over multiple months"""
        end_date = datetime.now()
        start_date = end_date - timedelta(days=months*30)
        
        self.cursor.execute('''
            SELECT strftime('%Y-%m', date) as month, SUM(amount) as total
            FROM transactions
            WHERE date >= ?
            GROUP BY month
            ORDER BY month
        ''', (start_date.strftime('%Y-%m-%d'),))
        
        return self.cursor.fetchall()
    
    def delete_transaction(self, transaction_id):
        """Delete a transaction by ID"""
        self.cursor.execute('DELETE FROM transactions WHERE id = ?', (transaction_id,))
        self.conn.commit()
        return self.cursor.rowcount > 0
    
    def close(self):
        """Close database connection"""
        if self.conn:
            self.conn.close()


class ExpenseTrackerGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Personal Expense Tracker (INR Version)")
        self.root.geometry("1200x700")
        self.root.configure(bg='#f0f0f0')
        
        self.tracker = ExpenseTracker()
        
        self.colors = {
            'primary': "#0015FF",
            'secondary': '#A23B72',
            'success': '#06A77D',
            'danger': '#D90368',
            'light': '#F0F0F0',
            'dark': '#2C3E50'
        }
        
        self.create_widgets()
        self.refresh_transactions()
    
    def create_widgets(self):
        """Create all GUI widgets"""
        title_frame = tk.Frame(self.root, bg=self.colors['primary'], height=60)
        title_frame.pack(fill='x')
        title_frame.pack_propagate(False)
        
        tk.Label(title_frame, text="💰 Personal Expense Tracker (₹ INR)", 
                font=('Arial', 20, 'bold'), bg=self.colors['primary'], 
                fg='white').pack(pady=15)
        
        main_container = tk.Frame(self.root, bg='#f0f0f0')
        main_container.pack(fill='both', expand=True, padx=10, pady=10)
        
        left_panel = tk.Frame(main_container, bg='white', relief='raised', bd=2)
        left_panel.pack(side='left', fill='both', padx=(0, 5), pady=0)
        
        add_frame = tk.LabelFrame(left_panel, text="Add New Transaction", 
                                 font=('Arial', 12, 'bold'), bg='white', 
                                 fg=self.colors['dark'], padx=15, pady=15)
        add_frame.pack(fill='x', padx=10, pady=10)
        
        tk.Label(add_frame, text="Date:", bg='white', font=('Arial', 10)).grid(
            row=0, column=0, sticky='w', pady=5)
        self.date_entry = DateEntry(add_frame, width=20, background=self.colors['primary'],
                                    foreground='white', borderwidth=2, date_pattern='yyyy-mm-dd')
        self.date_entry.grid(row=0, column=1, pady=5, sticky='ew')
        
        tk.Label(add_frame, text="Category:", bg='white', font=('Arial', 10)).grid(
            row=1, column=0, sticky='w', pady=5)
        self.category_var = tk.StringVar()
        categories = ['Food', 'Transport', 'Entertainment', 'Shopping', 
                     'Bills', 'Healthcare', 'Education', 'Other']
        self.category_combo = ttk.Combobox(add_frame, textvariable=self.category_var, 
                                          values=categories, width=18, state='normal')
        self.category_combo.grid(row=1, column=1, pady=5, sticky='ew')
        self.category_combo.set('Food')
        
        tk.Label(add_frame, text="Amount (₹):", bg='white', font=('Arial', 10)).grid(
            row=2, column=0, sticky='w', pady=5)
        self.amount_entry = tk.Entry(add_frame, width=20)
        self.amount_entry.grid(row=2, column=1, pady=5, sticky='ew')
        
        tk.Label(add_frame, text="Description:", bg='white', font=('Arial', 10)).grid(
            row=3, column=0, sticky='w', pady=5)
        self.desc_entry = tk.Entry(add_frame, width=20)
        self.desc_entry.grid(row=3, column=1, pady=5, sticky='ew')
        
        add_frame.columnconfigure(1, weight=1)
        
        tk.Button(add_frame, text="Add Transaction", command=self.add_transaction,
                 bg=self.colors['success'], fg='white', font=('Arial', 11, 'bold'),
                 cursor='hand2', relief='flat', padx=20, pady=8).grid(
                     row=4, column=0, columnspan=2, pady=10, sticky='ew')
        
        filter_frame = tk.LabelFrame(left_panel, text="Filter & Actions", 
                                    font=('Arial', 12, 'bold'), bg='white',
                                    fg=self.colors['dark'], padx=15, pady=15)
        filter_frame.pack(fill='x', padx=10, pady=10)
        
        tk.Label(filter_frame, text="Month:", bg='white', font=('Arial', 10)).grid(
            row=0, column=0, sticky='w', pady=5)
        self.month_var = tk.IntVar(value=datetime.now().month)
        self.month_spin = tk.Spinbox(filter_frame, from_=1, to=12, width=18,
                                    textvariable=self.month_var)
        self.month_spin.grid(row=0, column=1, pady=5, sticky='ew')
        
        tk.Label(filter_frame, text="Year:", bg='white', font=('Arial', 10)).grid(
            row=1, column=0, sticky='w', pady=5)
        self.year_var = tk.IntVar(value=datetime.now().year)
        self.year_spin = tk.Spinbox(filter_frame, from_=2020, to=2030, width=18,
                                   textvariable=self.year_var)
        self.year_spin.grid(row=1, column=1, pady=5, sticky='ew')
        
        filter_frame.columnconfigure(1, weight=1)
        
        btn_frame = tk.Frame(filter_frame, bg='white')
        btn_frame.grid(row=2, column=0, columnspan=2, pady=10, sticky='ew')
        
        tk.Button(btn_frame, text="View Month", command=self.filter_by_month,
                 bg=self.colors['primary'], fg='white', font=('Arial', 10, 'bold'),
                 cursor='hand2', relief='flat', padx=10, pady=6).pack(
                     side='left', expand=True, fill='x', padx=2)
        
        tk.Button(btn_frame, text="View All", command=self.refresh_transactions,
                 bg=self.colors['secondary'], fg='white', font=('Arial', 10, 'bold'),
                 cursor='hand2', relief='flat', padx=10, pady=6).pack(
                     side='left', expand=True, fill='x', padx=2)
        
        tk.Button(filter_frame, text="Generate Report", command=self.show_monthly_report,
                 bg='#F39C12', fg='white', font=('Arial', 10, 'bold'),
                 cursor='hand2', relief='flat', padx=10, pady=6).grid(
                     row=3, column=0, columnspan=2, pady=5, sticky='ew')
        
        tk.Button(filter_frame, text="Visualize Spending", command=self.show_visualization,
                 bg='#9B59B6', fg='white', font=('Arial', 10, 'bold'),
                 cursor='hand2', relief='flat', padx=10, pady=6).grid(
                     row=4, column=0, columnspan=2, pady=5, sticky='ew')
        
        tk.Button(filter_frame, text="Delete Selected", command=self.delete_selected,
                 bg=self.colors['danger'], fg='white', font=('Arial', 10, 'bold'),
                 cursor='hand2', relief='flat', padx=10, pady=6).grid(
                     row=5, column=0, columnspan=2, pady=5, sticky='ew')
        
        right_panel = tk.Frame(main_container, bg='white', relief='raised', bd=2)
        right_panel.pack(side='right', fill='both', expand=True, padx=(5, 0), pady=0)
        
        list_label = tk.Label(right_panel, text="Transaction History", 
                            font=('Arial', 14, 'bold'), bg='white',
                            fg=self.colors['dark'])
        list_label.pack(pady=10)
        
        tree_frame = tk.Frame(right_panel, bg='white')
        tree_frame.pack(fill='both', expand=True, padx=10, pady=5)
        
        tree_scroll_y = tk.Scrollbar(tree_frame)
        tree_scroll_y.pack(side='right', fill='y')
        
        tree_scroll_x = tk.Scrollbar(tree_frame, orient='horizontal')
        tree_scroll_x.pack(side='bottom', fill='x')
        
        self.tree = ttk.Treeview(tree_frame, columns=('ID', 'Date', 'Category', 
                                                       'Amount', 'Description'),
                                show='headings', yscrollcommand=tree_scroll_y.set,
                                xscrollcommand=tree_scroll_x.set)
        
        tree_scroll_y.config(command=self.tree.yview)
        tree_scroll_x.config(command=self.tree.xview)
        
        self.tree.heading('ID', text='ID')
        self.tree.heading('Date', text='Date')
        self.tree.heading('Category', text='Category')
        self.tree.heading('Amount', text='Amount (₹)')
        self.tree.heading('Description', text='Description')
        
        self.tree.column('ID', width=50, anchor='center')
        self.tree.column('Date', width=100, anchor='center')
        self.tree.column('Category', width=120, anchor='center')
        self.tree.column('Amount', width=100, anchor='e')
        self.tree.column('Description', width=300, anchor='w')
        
        self.tree.pack(fill='both', expand=True)
        
        style = ttk.Style()
        style.theme_use('clam')
        style.configure('Treeview', rowheight=25, font=('Arial', 10))
        style.configure('Treeview.Heading', font=('Arial', 11, 'bold'),
                       background=self.colors['primary'], foreground='white')
        
        self.summary_label = tk.Label(right_panel, text="Total: ₹0.00", 
                                     font=('Arial', 13, 'bold'), bg='white',
                                     fg=self.colors['success'])
        self.summary_label.pack(pady=10)
    
    def add_transaction(self):
        """Add a new transaction"""
        try:
            date = self.date_entry.get_date().strftime('%Y-%m-%d')
            category = self.category_var.get()
            amount = float(self.amount_entry.get())
            description = self.desc_entry.get()
            
            if amount <= 0:
                messagebox.showerror("Error", "Amount must be positive!")
                return
            
            if not category:
                messagebox.showerror("Error", "Please select a category!")
                return
            
            self.tracker.add_transaction(date, category, amount, description)
            messagebox.showinfo("Success", "Transaction added successfully!")
            
            self.amount_entry.delete(0, tk.END)
            self.desc_entry.delete(0, tk.END)
            
            self.refresh_transactions()
            
        except ValueError:
            messagebox.showerror("Error", "Invalid amount!")
    
    def refresh_transactions(self):
        """Refresh all transactions in the UI"""
        for item in self.tree.get_children():
            self.tree.delete(item)
        
        transactions = self.tracker.get_all_transactions()
        total = 0
        
        for t in transactions:
            self.tree.insert('', 'end', values=(t[0], t[1], t[2], f'₹{t[3]:.2f}', t[4]))
            total += t[3]
        
        self.summary_label.config(text=f"Total: ₹{total:.2f} | Transactions: {len(transactions)}")
    
    def filter_by_month(self):
        """Filter transactions by selected month"""
        for item in self.tree.get_children():
            self.tree.delete(item)
        
        year = self.year_var.get()
        month = self.month_var.get()
        
        transactions = self.tracker.get_transactions_by_month(year, month)
        total = 0
        
        for t in transactions:
            self.tree.insert('', 'end', values=(t[0], t[1], t[2], f'₹{t[3]:.2f}', t[4]))
            total += t[3]
        
        month_name = datetime(year, month, 1).strftime('%B %Y')
        self.summary_label.config(
            text=f"{month_name} - Total: ₹{total:.2f} | Transactions: {len(transactions)}")
    
    def delete_selected(self):
        """Delete selected transaction"""
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
    
    def show_monthly_report(self):
        """Show monthly report window"""
        year = self.year_var.get()
        month = self.month_var.get()
        
        transactions = self.tracker.get_transactions_by_month(year, month)
        category_summary = self.tracker.get_category_summary(year, month)
        
        if not transactions:
            messagebox.showinfo("Info", "No transactions found for this month!")
            return
        
        report_win = tk.Toplevel(self.root)
        report_win.title(f"Report - {datetime(year, month, 1).strftime('%B %Y')}")
        report_win.geometry("600x500")
        report_win.configure(bg='white')
        
        tk.Label(report_win, text="Expense Report", 
                font=('Arial', 18, 'bold'), bg='white',
                fg=self.colors['primary']).pack(pady=20)
        
        tk.Label(report_win, text=datetime(year, month, 1).strftime('%B %Y'),
                font=('Arial', 14), bg='white', fg=self.colors['dark']).pack()
        
        total = sum(t[3] for t in transactions)
        summary_frame = tk.Frame(report_win, bg='#ecf0f1', relief='solid', bd=1)
        summary_frame.pack(fill='x', padx=20, pady=20)
        
        tk.Label(summary_frame, text=f"Total Expenses: ₹{total:.2f}",
                font=('Arial', 14, 'bold'), bg='#ecf0f1',
                fg=self.colors['danger']).pack(pady=10)
        tk.Label(summary_frame, text=f"Number of Transactions: {len(transactions)}",
                font=('Arial', 12), bg='#ecf0f1').pack(pady=5)
        
        tk.Label(report_win, text="Category Breakdown", 
                font=('Arial', 13, 'bold'), bg='white',
                fg=self.colors['dark']).pack(pady=(20, 10))
        
        cat_frame = tk.Frame(report_win, bg='white')
        cat_frame.pack(fill='both', expand=True, padx=20, pady=10)
        
        cat_tree = ttk.Treeview(cat_frame, columns=('Category', 'Amount', 'Percentage'),
                               show='headings', height=10)
        
        cat_tree.heading('Category', text='Category')
        cat_tree.heading('Amount', text='Amount (₹)')
        cat_tree.heading('Percentage', text='Percentage')
        
        cat_tree.column('Category', width=200, anchor='w')
        cat_tree.column('Amount', width=150, anchor='e')
        cat_tree.column('Percentage', width=150, anchor='e')
        
        for cat, amount in category_summary:
            percentage = (amount / total) * 100
            cat_tree.insert('', 'end', values=(cat, f'₹{amount:.2f}', f'{percentage:.1f}%'))
        
        cat_tree.pack(fill='both', expand=True)
    
    def show_visualization(self):
        """Show spending visualization window"""
        year = self.year_var.get()
        month = self.month_var.get()
        
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
        colors = plt.cm.Set3(range(len(categories)))
        
        ax1.pie(amounts, labels=categories, autopct='%1.1f%%', colors=colors, startangle=90)
        ax1.set_title('Spending by Category')
        
        ax2.barh(categories, amounts, color=colors)
        ax2.set_xlabel('Amount (₹)')
        ax2.set_title('Category Comparison')
        ax2.invert_yaxis()
        for i, v in enumerate(amounts):
            ax2.text(v, i, f' ₹{v:.2f}', va='center')
        
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
        total = sum(amounts)
        avg_per_transaction = total / len(transactions)
        max_transaction = max(t[3] for t in transactions)
        
        stats_text = f"""
SUMMARY STATISTICS
{'─' * 30}

Total Spending:        ₹{total:,.2f}

Transactions:          {len(transactions)}

Average/Transaction:   ₹{avg_per_transaction:.2f}

Largest Transaction:   ₹{max_transaction:.2f}

Top Category:          {categories[0]}
                      (₹{amounts[0]:.2f})
        """
        ax4.text(0.1, 0.5, stats_text, fontsize=11, family='monospace',
                verticalalignment='center')
        
        plt.tight_layout()
        
        canvas = FigureCanvasTkAgg(fig, master=viz_win)
        canvas.draw()
        canvas.get_tk_widget().pack(fill='both', expand=True)
    
    def on_closing(self):
        """Clean close"""
        self.tracker.close()
        self.root.destroy()


def main():
    root = tk.Tk()
    app = ExpenseTrackerGUI(root)
    root.protocol("WM_DELETE_WINDOW", app.on_closing)
    root.mainloop()


if __name__ == "__main__":
    main()
