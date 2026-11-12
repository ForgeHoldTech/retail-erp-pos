import requests
from database import get_connection, BRANCH_ID

SERVER_URL = "http://127.0.0.1:8000"

def sync_products():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, name, price, stock FROM products")
    products = [{"id": r[0], "branch_id": BRANCH_ID, "name": r[1], "price": r[2], "stock": r[3]} for r in cursor.fetchall()]
    conn.close()
    try:
        return requests.post(f"{SERVER_URL}/sync/products", json=products, timeout=5).status_code == 200
    except: return False

def sync_sales():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, total, payment_type, created_at FROM sales WHERE synced = 0")
    sales = [{"id": r[0], "branch_id": BRANCH_ID, "product_id": 0, "quantity": 1, "total": r[1], "payment_type": r[2], "created_at": r[3]} for r in cursor.fetchall()]
    
    if not sales:
        conn.close()
        return True
    try:
        response = requests.post(f"{SERVER_URL}/sync/sales", json=sales, timeout=5)
        if response.status_code == 200:
            cursor.execute("UPDATE sales SET synced = 1 WHERE synced = 0")
            conn.commit()
        conn.close()
        return response.status_code == 200
    except:
        conn.close()
        return False

def sync_returns():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, sale_id, product_id, quantity, refund_amount, created_at FROM returns WHERE synced = 0")
    returns = [{"id": r[0], "branch_id": BRANCH_ID, "sale_id": r[1], "product_id": r[2], "quantity": r[3], "refund_amount": r[4], "created_at": r[5]} for r in cursor.fetchall()]
    if not returns:
        conn.close()
        return True
    try:
        response = requests.post(f"{SERVER_URL}/sync/returns", json=returns, timeout=5)
        if response.status_code == 200:
            cursor.execute("UPDATE returns SET synced = 1 WHERE synced = 0")
            conn.commit()
        conn.close()
        return response.status_code == 200
    except:
        conn.close()
        return False

def sync_purchases():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT p.id, s.name, pr.name, p.quantity, p.cost_price, p.status, p.created_at 
        FROM purchases p
        JOIN suppliers s ON p.supplier_id = s.id
        JOIN products pr ON p.product_id = pr.id
    """)
    purchases = [{"id": r[0], "branch_id": BRANCH_ID, "supplier_name": r[1], "product_name": r[2], "quantity": r[3], "cost_price": r[4], "status": r[5], "created_at": r[6]} for r in cursor.fetchall()]
    conn.close()
    try:
        return requests.post(f"{SERVER_URL}/sync/purchases", json=purchases, timeout=5).status_code == 200
    except: return False

def download_master_products():
    try:
        response = requests.get(f"{SERVER_URL}/master/products", timeout=5)
        if response.status_code == 200:
            conn = get_connection()
            cursor = conn.cursor()
            for p in response.json():
                cursor.execute("SELECT id FROM products WHERE id = ?", (p["id"],))
                if not cursor.fetchone():
                    cursor.execute("INSERT INTO products (id, name, price, stock) VALUES (?, ?, ?, 0)", (p["id"], p["name"], p["price"]))
            conn.commit()
            conn.close()

        response = requests.get(f"{SERVER_URL}/master/suppliers", timeout=5)
        if response.status_code == 200:
            conn = get_connection()
            cursor = conn.cursor()
            for s in response.json():
                cursor.execute("SELECT id FROM suppliers WHERE id = ?", (s["id"],))
                if not cursor.fetchone():
                    cursor.execute("INSERT INTO suppliers (id, name, phone) VALUES (?, ?, ?)", (s["id"], s["name"], s["phone"]))
            conn.commit()
            conn.close()
        return True
    except: pass
    return False

def fetch_my_stock():
    try:
        response = requests.get(f"{SERVER_URL}/branch/{BRANCH_ID}/products", timeout=5)
        if response.status_code == 200:
            conn = get_connection()
            cursor = conn.cursor()
            for p in response.json():
                cursor.execute("SELECT id FROM products WHERE id = ?", (p["id"],))
                if cursor.fetchone():
                    cursor.execute("UPDATE products SET stock = ? WHERE id = ?", (p["stock"], p["id"]))
                else:
                    cursor.execute("INSERT INTO products (id, name, price, stock) VALUES (?, ?, ?, ?)", (p["id"], p["name"], p["price"], p["stock"]))
            conn.commit()
            conn.close()
            return True
    except: pass
    return False