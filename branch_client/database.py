import sqlite3
from datetime import datetime

BRANCH_ID = "branch_1" 
DB_NAME = f"branch_data_{BRANCH_ID}.db"

def get_connection():
    conn = sqlite3.connect(DB_NAME)
    return conn

def get_local_time():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def create_tables():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("CREATE TABLE IF NOT EXISTS products (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, price REAL, stock INTEGER)")
    
    cursor.execute("CREATE TABLE IF NOT EXISTS sales (id INTEGER PRIMARY KEY AUTOINCREMENT, total REAL, payment_type TEXT DEFAULT 'cash', discount REAL DEFAULT 0, discount_amount REAL DEFAULT 0, created_at TEXT, synced INTEGER DEFAULT 0)")
    
    cursor.execute("PRAGMA table_info(sales)")
    columns = [column[1] for column in cursor.fetchall()]
    if 'payment_type' not in columns:
        cursor.execute("ALTER TABLE sales ADD COLUMN payment_type TEXT DEFAULT 'cash'")
    if 'discount' not in columns:
        cursor.execute("ALTER TABLE sales ADD COLUMN discount REAL DEFAULT 0")
    if 'discount_amount' not in columns:
        cursor.execute("ALTER TABLE sales ADD COLUMN discount_amount REAL DEFAULT 0")

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS sale_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sale_id INTEGER,
            product_id INTEGER,
            quantity INTEGER,
            price REAL,
            item_discount_pct REAL DEFAULT 0,
            final_price REAL
        )
    """)

    cursor.execute("CREATE TABLE IF NOT EXISTS returns (id INTEGER PRIMARY KEY AUTOINCREMENT, sale_id INTEGER, product_id INTEGER, quantity INTEGER, refund_amount REAL, created_at TEXT, synced INTEGER DEFAULT 0)")
    cursor.execute("CREATE TABLE IF NOT EXISTS shifts (id INTEGER PRIMARY KEY AUTOINCREMENT, opening_cash REAL, closing_cash REAL, expected_cash REAL, difference REAL, closed_at TEXT)")
    cursor.execute("CREATE TABLE IF NOT EXISTS suppliers (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, phone TEXT)")
    cursor.execute("CREATE TABLE IF NOT EXISTS purchases (id INTEGER PRIMARY KEY AUTOINCREMENT, supplier_id INTEGER, product_id INTEGER, quantity INTEGER, cost_price REAL, status TEXT DEFAULT 'pending', created_at TEXT)")
    
    conn.commit()
    conn.close()

def reset_database():
    conn = get_connection()
    cursor = conn.cursor()
    for table in ['products', 'sales', 'sale_items', 'returns', 'shifts', 'suppliers', 'purchases']:
        cursor.execute(f"DROP TABLE IF EXISTS {table}")
    conn.commit()
    conn.close()
    create_tables()

def get_products():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, name, price, stock FROM products")
    rows = cursor.fetchall()
    conn.close()
    return rows

def update_stock(product_id, new_stock):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE products SET stock = ? WHERE id = ?", (new_stock, product_id))
    conn.commit()
    conn.close()

def process_return(sale_id, return_qty):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT total FROM sales WHERE id = ?", (sale_id,))
    sale = cursor.fetchone()
    if not sale:
        conn.close()
        return None, "Sale ID not found"

    original_total = sale[0]
    refund_amount = original_total 
    
    cursor.execute("INSERT INTO returns (sale_id, product_id, quantity, refund_amount, created_at) VALUES (?, 0, ?, ?, ?)", (sale_id, return_qty, refund_amount, get_local_time()))
    cursor.execute("DELETE FROM sales WHERE id = ?", (sale_id,))
    
    conn.commit()
    conn.close()
    return refund_amount, None

def close_shift(opening_cash, closing_cash):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT COALESCE(SUM(total), 0) FROM sales WHERE payment_type = 'cash'")
    cash_sales = cursor.fetchone()[0]
    cursor.execute("SELECT COALESCE(SUM(refund_amount), 0) FROM returns")
    cash_refunds = cursor.fetchone()[0]
    expected_cash = opening_cash + cash_sales - cash_refunds
    difference = closing_cash - expected_cash
    cursor.execute("INSERT INTO shifts (opening_cash, closing_cash, expected_cash, difference, closed_at) VALUES (?, ?, ?, ?, ?)", (opening_cash, closing_cash, expected_cash, difference, get_local_time()))
    conn.commit()
    conn.close()
    return expected_cash, difference

def get_suppliers():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, name, phone FROM suppliers")
    rows = cursor.fetchall()
    conn.close()
    return rows

def add_purchase_order(supplier_id, product_id, quantity, cost_price):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("INSERT INTO purchases (supplier_id, product_id, quantity, cost_price, created_at) VALUES (?, ?, ?, ?, ?)", (supplier_id, product_id, quantity, cost_price, get_local_time()))
    conn.commit()
    conn.close()

def receive_purchase_order(purchase_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT product_id, quantity FROM purchases WHERE id = ? AND status = 'pending'", (purchase_id,))
    po = cursor.fetchone()
    if po:
        product_id, quantity = po
        cursor.execute("UPDATE products SET stock = stock + ? WHERE id = ?", (quantity, product_id))
        cursor.execute("UPDATE purchases SET status = 'received' WHERE id = ?", (purchase_id,))
        conn.commit()
        conn.close()
        return True
    conn.close()
    return False

def get_purchase_orders():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT p.id, s.name, pr.name, p.quantity, p.cost_price, p.status, p.created_at 
        FROM purchases p
        JOIN suppliers s ON p.supplier_id = s.id
        JOIN products pr ON p.product_id = pr.id
        ORDER BY p.id DESC
    """)
    rows = cursor.fetchall()
    conn.close()
    return rows