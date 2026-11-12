import os
import psycopg2

DB_CONFIG = {
    "host": os.environ.get("DB_HOST", "localhost"),
    "port": int(os.environ.get("DB_PORT", "5432")),
    "database": os.environ.get("DB_NAME", "retail_head_office"),
    "user": os.environ.get("DB_USER", "postgres"),
    "password": os.environ.get("DB_PASSWORD", "")
}

def get_connection():
    conn = psycopg2.connect(**DB_CONFIG)
    return conn

def create_tables():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER, branch_id TEXT, name TEXT NOT NULL, price REAL NOT NULL, cost_price REAL DEFAULT 0, stock INTEGER NOT NULL,
            PRIMARY KEY (id, branch_id)
        )
    """)
    cursor.execute("""
        SELECT column_name FROM information_schema.columns 
        WHERE table_name='products' AND column_name='cost_price'
    """)
    if not cursor.fetchone():
        cursor.execute("ALTER TABLE products ADD COLUMN cost_price REAL DEFAULT 0")
    cursor.execute("CREATE TABLE IF NOT EXISTS sales (id INTEGER, branch_id TEXT, product_id INTEGER, quantity INTEGER NOT NULL, total REAL NOT NULL, payment_type TEXT DEFAULT 'cash', created_at TEXT, PRIMARY KEY (id, branch_id))")
    cursor.execute("CREATE TABLE IF NOT EXISTS returns (id INTEGER, branch_id TEXT, sale_id INTEGER, product_id INTEGER, quantity INTEGER NOT NULL, refund_amount REAL NOT NULL, created_at TEXT, PRIMARY KEY (id, branch_id))")
    cursor.execute("CREATE TABLE IF NOT EXISTS transfers (id SERIAL PRIMARY KEY, from_branch TEXT, to_branch TEXT, product_id INTEGER, quantity INTEGER, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)")
    cursor.execute("CREATE TABLE IF NOT EXISTS suppliers (id INTEGER, branch_id TEXT DEFAULT 'HEAD_OFFICE', name TEXT NOT NULL, phone TEXT NOT NULL, PRIMARY KEY (id, branch_id))")
    cursor.execute("CREATE TABLE IF NOT EXISTS purchases (id INTEGER, branch_id TEXT, supplier_name TEXT, product_name TEXT, quantity INTEGER, cost_price REAL, status TEXT, created_at TEXT, PRIMARY KEY (id, branch_id))")
    conn.commit()
    conn.close()