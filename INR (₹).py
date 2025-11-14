import sqlite3
import csv
import os
from datetime import datetime
from collections import defaultdict
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from tkcalendar import DateEntry
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

# Try import reportlab for PDF export
try:
    from reportlab.lib.pagesizes import letter
    from reportlab.pdfgen import canvas as pdf_canvas
    REPORTLAB_AVAILABLE = True
except:
    REPORTLAB_AVAILABLE = False


# ---------------- DATABASE ----------------

class ExpenseTracker:
    def __init__(self, db_name="expenses.db"):
        self.conn = sqlite3.connect(db_name)
        self.cursor = self.conn.cursor()
        self.create_tables()

    def create_tables(self):
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS transactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT NOT NULL,
                category TEXT NOT NULL,
                amount REAL NOT NULL,
                description TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        self.conn.commit()

    def add_transaction(self, date, category, amount, desc):
        self.cursor.execute("""
            INSERT INTO transactions (date, category, amount, description)
            VALUES (?, ?, ?, ?)
        """, (date, category, amount, desc))
        self.conn.commit()

    def get_all(self):
        self.cursor.execute("SELECT * FROM transactions ORDER BY date DESC")
        return self.cursor.fetchall()

    def get_by_month(self, year, month):
        start = f"{year}-{month:02d}-01"
        if month == 12:
            end = f"{year+1}-01-01"
        else:
            end = f"{year}-{month+1:02d}-01"

        self.cursor.execute("""
            SELECT * FROM transactions 
            WHERE date >= ? AND date < ?
            ORDER BY date DESC
        """, (start, end))
        return self.cursor.fetchall()

    def get_category_summary(self, year, month):
        start = f"{year}-{month:02d}-01"
        if month == 12:
            end = f"{year+1}-01-01"
        else:
            end = f"{year}-{month+1:02d}-01"

        self.cursor.execute("""
            SELECT category, SUM(amount)
            FROM transactions
            WHERE date >= ? AND date < ?
            GROUP BY category
        """, (start, end))
        return self.cursor.fetchall()

    def update(self, tid, amount, desc):
        self.cursor.execute("""
            UPDATE transactions 
            SET amount=?, description=? 
            WHERE id=?
        """, (amount, desc, tid))
        self.conn.commit()

    def delete(self, tid):
        self.cursor.execute("DELETE FROM transactions WHERE id=?", (tid,))
        self.conn.commit()

    def close(self):
        try:
            self.conn.close()
        except:
            pass



# ---------------- GUI ----------------

class ExpenseTrackerGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Expense Tracker — INR (₹)")
        self.root.geometry("1200x720")

        # Light & Dark Theme
        self.light = {
            "bg": "#F5F5F5",
            "panel": "#FFFFFF",
            "card": "#FFFFFF",
            "text": "#000000",
            "primary": "#007ACC",
            "success": "#5CB85C",
            "danger": "#D9534F",
            "muted": "#CCCCCC",
        }
        self.dark = {
            "bg": "#1E1E1E",
            "panel": "#252526",
            "card": "#2D2D30",
            "text": "#FFFFFF",
            "primary": "#007ACC",
            "success": "#5CB85C",
            "danger": "#D9534F",
            "muted": "#333333",
        }

        self.theme = self.dark

        self.db = ExpenseTracker()

        self.build_ui()
        self.refresh()

    # --------- THEME TOGGLE -----

    def toggle_theme(self):
        self.theme = self.light if self.theme == self.dark else self.dark
        self.apply_theme(self.root)
        self.treeview_theme()

    def apply_theme(self, widget):
        """Recursively update widget colors"""
        try:
            bg = self.theme["panel"]
            fg = self.theme["text"]
            if isinstance(widget, (tk.Frame, tk.LabelFrame)):
                widget.configure(bg=bg)
            elif isinstance(widget, tk.Label):
                widget.configure(bg=bg, fg=fg)
            elif isinstance(widget, tk.Button):
                widget.configure(bg=self.theme["primary"], fg="white")
            elif isinstance(widget, tk.Entry):
                widget.configure(bg=self.theme["card"], fg=fg, insertbackground=fg)
            elif isinstance(widget, tk.Spinbox):
                widget.configure(bg=self.theme["card"], fg=fg)
        except:
            pass

        for child in widget.winfo_children():
            self.apply_theme(child)

    def treeview_theme(self):
        style = ttk.Style()
        style.theme_use("clam")
        style.configure(
            "Treeview",
            background=self.theme["card"],
            fieldbackground=self.theme["card"],
            foreground=self.theme["text"],
            rowheight=26,
        )
        style.configure(
            "Treeview.Heading",
            background=self.theme["primary"],
            foreground="white",
            font=("Arial", 11, "bold"),
        )
        style.map("Treeview", background=[("selected", self.theme["primary"])])

    # ---------- UI BUILDING ----------

    def build_ui(self):
        c = self.theme

        # Top title bar
        title = tk.Frame(self.root, bg=c["primary"], height=60)
        title.pack(fill="x")
        tk.Label(
            title,
            text="💰 Personal Expense Tracker — INR (₹)",
            fg="white",
            bg=c["primary"],
            font=("Arial", 20, "bold"),
        ).pack(pady=10)

        main = tk.Frame(self.root, bg=c["bg"])
        main.pack(fill="both", expand=True)

        # ---------------- LEFT PANEL ----------------
        left = tk.Frame(main, bg=c["panel"], width=300)
        left.pack(side="left", fill="y", padx=10, pady=10)

        # Add box
        addbox = tk.LabelFrame(left, text="Add Transaction", bg=c["card"], fg=c["text"])
        addbox.pack(fill="x", pady=10)

        tk.Label(addbox, text="Date:", bg=c["card"], fg=c["text"]).pack(anchor="w")
        self.date = DateEntry(addbox, date_pattern="yyyy-mm-dd")
        self.date.pack(fill="x", pady=3)

        tk.Label(addbox, text="Category:", bg=c["card"], fg=c["text"]).pack(anchor="w")
        self.cat = ttk.Combobox(
            addbox,
            values=[
                "Food",
                "Transport",
                "Shopping",
                "Bills",
                "Healthcare",
                "Entertainment",
                "Education",
                "Other",
            ],
        )
        self.cat.set("Food")
        self.cat.pack(fill="x", pady=3)

        tk.Label(addbox, text="Amount (₹):", bg=c["card"], fg=c["text"]).pack(anchor="w")
        self.amount = tk.Entry(addbox)
        self.amount.pack(fill="x", pady=3)

        tk.Label(addbox, text="Description:", bg=c["card"], fg=c["text"]).pack(anchor="w")
        self.desc = tk.Entry(addbox)
        self.desc.pack(fill="x", pady=3)

        tk.Button(
            addbox,
            text="Add Transaction",
            bg=c["success"],
            fg="white",
            command=self.add,
        ).pack(fill="x", pady=10)

        # FILTERS + ACTION BUTTONS
        actions = tk.LabelFrame(left, text="Actions", bg=c["card"], fg=c["text"])
        actions.pack(fill="x")

        tk.Label(actions, text="Month:", bg=c["card"], fg=c["text"]).pack()
        self.month = tk.Spinbox(actions, from_=1, to=12)
        self.month.pack(fill="x", pady=2)

        tk.Label(actions, text="Year:", bg=c["card"], fg=c["text"]).pack()
        self.year = tk.Spinbox(actions, from_=2020, to=2050)
        self.year.pack(fill="x", pady=2)

        tk.Button(actions, text="View Month", bg=c["primary"], fg="white", command=self.filter_month).pack(
            fill="x", pady=5
        )
        tk.Button(actions, text="View All", bg=c["muted"], fg=c["text"], command=self.refresh).pack(
            fill="x", pady=5
        )
        tk.Button(actions, text="Edit Selected", bg="#17A2B8", fg="white", command=self.edit).pack(
            fill="x", pady=5
        )
        tk.Button(actions, text="Delete Selected", bg=c["danger"], fg="white", command=self.delete).pack(
            fill="x", pady=5
        )
        tk.Button(actions, text="Export CSV", bg="#5BC0DE", fg="white", command=self.export_csv).pack(
            fill="x", pady=5
        )
        tk.Button(actions, text="Export PDF", bg="#AF7AC5", fg="white", command=self.export_pdf).pack(
            fill="x", pady=5
        )
        tk.Button(actions, text="Toggle Theme", bg=c["primary"], fg="white", command=self.toggle_theme).pack(
            fill="x", pady=5
        )

        # ---------------- RIGHT PANEL ----------------
        right = tk.Frame(main, bg=c["panel"])
        right.pack(fill="both", expand=True, padx=10, pady=10)

        # Search Bar
        searchframe = tk.Frame(right, bg=c["panel"])
        searchframe.pack(fill="x")

        tk.Label(searchframe, text="Search:", bg=c["panel"], fg=c["text"]).pack(side="left")
        self.searchvar = tk.StringVar()
        tk.Entry(searchframe, textvariable=self.searchvar).pack(side="left", padx=5)
        tk.Button(searchframe, text="Go", bg=c["primary"], fg="white", command=self.search).pack(
            side="left", padx=5
        )
        tk.Button(searchframe, text="Clear", bg=c["muted"], fg=c["text"], command=self.clear_search).pack(
            side="left"
        )

        # Table
        self.tree = ttk.Treeview(
            right,
            columns=("ID", "Date", "Category", "Amount", "Description"),
            show="headings",
        )
        self.tree.heading("ID", text="ID")
        self.tree.heading("Date", text="Date")
        self.tree.heading("Category", text="Category")
        self.tree.heading("Amount", text="Amount (₹)")
        self.tree.heading("Description", text="Description")

        self.tree.column("ID", width=50, anchor="center")
        self.tree.column("Amount", width=100, anchor="e")
        self.tree.pack(fill="both", expand=True)

        # Summary
        self.summary = tk.Label(
            right, text="Total: ₹0.00 | Transactions: 0", bg=c["panel"], fg=c["success"]
        )
        self.summary.pack(anchor="e", pady=10)

        self.treeview_theme()

    # ---------------- ACTIONS ----------------

    def add(self):
        try:
            amt = float(self.amount.get().strip())
        except:
            messagebox.showerror("Error", "Enter valid amount")
            return

        if amt <= 0:
            messagebox.showerror("Error", "Amount must be positive")
            return

        self.db.add_transaction(
            self.date.get_date().strftime("%Y-%m-%d"),
            self.cat.get(),
            amt,
            self.desc.get().strip(),
        )
        messagebox.showinfo("Success", "Transaction added!")
        self.refresh()

    def refresh(self):
        for row in self.tree.get_children():
            self.tree.delete(row)

        rows = self.db.get_all()
        total = 0
        for r in rows:
            self.tree.insert("", "end", values=(r[0], r[1], r[2], f"₹{r[3]:.2f}", r[4]))
            total += r[3]

        self.summary.config(text=f"Total: ₹{total:.2f} | Transactions: {len(rows)}")

    def filter_month(self):
        try:
            y = int(self.year.get())
            m = int(self.month.get())
        except:
            messagebox.showerror("Error", "Invalid year/month")
            return

        for row in self.tree.get_children():
            self.tree.delete(row)

        rows = self.db.get_by_month(y, m)
        total = 0
        for r in rows:
            self.tree.insert("", "end", values=(r[0], r[1], r[2], f"₹{r[3]:.2f}", r[4]))
            total += r[3]

        name = datetime(y, m, 1).strftime("%B %Y")
        self.summary.config(text=f"{name}: ₹{total:.2f} | {len(rows)} transactions")

    def delete(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showwarning("Warning", "Select a row to delete")
            return

        tid = self.tree.item(sel[0])["values"][0]
        if messagebox.askyesno("Confirm", "Delete this record?"):
            self.db.delete(tid)
            self.refresh()

    def edit(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showwarning("Warning", "Select a row to edit")
            return

        item = self.tree.item(sel[0])["values"]
        tid, date, cat, amt_str, desc = item

        win = tk.Toplevel(self.root)
        win.title("Edit Transaction")
        win.geometry("300x200")

        tk.Label(win, text=f"ID: {tid}").pack()
        tk.Label(win, text=f"Date: {date}").pack()
        tk.Label(win, text=f"Category: {cat}").pack()

        tk.Label(win, text="Amount (₹):").pack()
        amt_entry = tk.Entry(win)
        amt_entry.insert(0, amt_str.replace("₹", ""))
        amt_entry.pack()

        tk.Label(win, text="Description:").pack()
        desc_entry = tk.Entry(win)
        desc_entry.insert(0, desc)
        desc_entry.pack()

        def save():
            try:
                new_amt = float(amt_entry.get().strip())
                new_desc = desc_entry.get().strip()
            except:
                messagebox.showerror("Error", "Invalid amount")
                return

            self.db.update(tid, new_amt, new_desc)
            win.destroy()
            self.refresh()

        tk.Button(win, text="Save", bg=self.theme["success"], fg="white", command=save).pack(pady=10)

    # ---------------- SEARCH ----------------

    def search(self):
        q = self.searchvar.get().lower().strip()
        if not q:
            self.refresh()
            return

        for row in self.tree.get_children():
            self.tree.delete(row)

        rows = self.db.get_all()
        results = []

        for r in rows:
            if (
                q in str(r[1]).lower()
                or q in str(r[2]).lower()
                or q in str(r[4]).lower()
                or q in f"{r[3]:.2f}"
            ):
                results.append(r)

        total = 0
        for r in results:
            self.tree.insert("", "end", values=(r[0], r[1], r[2], f"₹{r[3]:.2f}", r[4]))
            total += r[3]

        self.summary.config(text=f"Search: ₹{total:.2f} | {len(results)} records")

    def clear_search(self):
        self.searchvar.set("")
        self.refresh()

    # ---------------- EXPORT ----------------

    def export_csv(self):
        fp = filedialog.asksaveasfilename(
            defaultextension=".csv", filetypes=[("CSV Files", "*.csv")]
        )
        if not fp:
            return

        rows = self.db.get_all()

        with open(fp, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["ID", "Date", "Category", "Amount", "Description"])
            for r in rows:
                w.writerow([r[0], r[1], r[2], r[3], r[4]])

        messagebox.showinfo("Exported", "CSV saved successfully.")

    def export_pdf(self):
        if not REPORTLAB_AVAILABLE:
            messagebox.showerror("Error", "Install reportlab: pip install reportlab")
            return

        fp = filedialog.asksaveasfilename(
            defaultextension=".pdf", filetypes=[("PDF Files", "*.pdf")]
        )
        if not fp:
            return

        rows = self.db.get_all()

        c = pdf_canvas.Canvas(fp, pagesize=letter)
        y = 750
        c.setFont("Helvetica", 14)
        c.drawString(40, y, "Expense Report")
        y -= 30
        c.setFont("Helvetica", 10)

        for r in rows:
            text = f"{r[0]} | {r[1]} | {r[2]} | ₹{r[3]:.2f} | {r[4]}"
            c.drawString(40, y, text)
            y -= 15
            if y < 50:
                c.showPage()
                y = 750
                c.setFont("Helvetica", 10)

        c.save()
        messagebox.showinfo("Exported", "PDF saved successfully.")

    # ---------------- VISUALIZATION ----------------

    def visualize(self):
        pass  # optional: can add graphs here later

    # ---------------- CLOSE ----------------

    def on_close(self):
        self.db.close()
        self.root.destroy()


# ---------------- RUN ----------------

def main():
    root = tk.Tk()
    app = ExpenseTrackerGUI(root)
    root.protocol("WM_DELETE_WINDOW", app.on_close)
    root.mainloop()


if __name__ == "__main__":
    main()
