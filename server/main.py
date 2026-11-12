from fastapi import FastAPI, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from pydantic import BaseModel
from typing import List
from db import get_connection, create_tables
import json

app = FastAPI(title="Head Office Server")
create_tables()

class Product(BaseModel):
    id: int
    branch_id: str
    name: str
    price: float
    cost_price: float = 0
    stock: int

class Sale(BaseModel):
    id: int
    branch_id: str
    product_id: int
    quantity: int
    total: float
    payment_type: str
    created_at: str

class ReturnItem(BaseModel):
    id: int
    branch_id: str
    sale_id: int
    product_id: int
    quantity: int
    refund_amount: float
    created_at: str

class Purchase(BaseModel):
    id: int
    branch_id: str
    supplier_name: str
    product_name: str
    quantity: int
    cost_price: float
    status: str
    created_at: str

@app.post("/sync/products")
def sync_products(products: List[Product]):
    conn = get_connection()
    cursor = conn.cursor()
    for p in products:
        cursor.execute("SELECT id FROM products WHERE id = %s AND branch_id = 'HEAD_OFFICE'", (p.id,))
        if cursor.fetchone():
            cursor.execute("INSERT INTO products (id, branch_id, name, price, cost_price, stock) VALUES (%s, %s, %s, %s, %s, %s) ON CONFLICT (id, branch_id) DO UPDATE SET stock = EXCLUDED.stock", (p.id, p.branch_id, p.name, p.price, p.cost_price, p.stock))
        else:
            cursor.execute("INSERT INTO products (id, branch_id, name, price, cost_price, stock) VALUES (%s, %s, %s, %s, %s, %s) ON CONFLICT (id, branch_id) DO UPDATE SET name = EXCLUDED.name, price = EXCLUDED.price, stock = EXCLUDED.stock", (p.id, p.branch_id, p.name, p.price, p.cost_price, p.stock))
    conn.commit()
    conn.close()
    return {"status": "success"}

@app.post("/sync/sales")
def sync_sales(sales: List[Sale]):
    conn = get_connection()
    cursor = conn.cursor()
    for s in sales:
        cursor.execute("INSERT INTO sales (id, branch_id, product_id, quantity, total, payment_type, created_at) VALUES (%s, %s, %s, %s, %s, %s, %s) ON CONFLICT (id, branch_id) DO NOTHING", (s.id, s.branch_id, s.product_id, s.quantity, s.total, s.payment_type, s.created_at))
    conn.commit()
    conn.close()
    return {"status": "success"}

@app.post("/sync/returns")
def sync_returns(returns: List[ReturnItem]):
    conn = get_connection()
    cursor = conn.cursor()
    for r in returns:
        cursor.execute("INSERT INTO returns (id, branch_id, sale_id, product_id, quantity, refund_amount, created_at) VALUES (%s, %s, %s, %s, %s, %s, %s) ON CONFLICT (id, branch_id) DO NOTHING", (r.id, r.branch_id, r.sale_id, r.product_id, r.quantity, r.refund_amount, r.created_at))
    conn.commit()
    conn.close()
    return {"status": "success"}

@app.post("/sync/purchases")
def sync_purchases(purchases: List[Purchase]):
    conn = get_connection()
    cursor = conn.cursor()
    for p in purchases:
        cursor.execute("""
            INSERT INTO purchases (id, branch_id, supplier_name, product_name, quantity, cost_price, status, created_at) 
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s) 
            ON CONFLICT (id, branch_id) DO UPDATE SET status = EXCLUDED.status
        """, (p.id, p.branch_id, p.supplier_name, p.product_name, p.quantity, p.cost_price, p.status, p.created_at))
    conn.commit()
    conn.close()
    return {"status": "success"}

@app.get("/master/products")
def get_master_products():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, branch_id, name, price, cost_price, stock FROM products WHERE branch_id = 'HEAD_OFFICE'")
    rows = cursor.fetchall()
    conn.close()
    return [{"id": r[0], "branch_id": r[1], "name": r[2], "price": r[3], "cost_price": r[4], "stock": r[5]} for r in rows]

@app.get("/master/suppliers")
def get_master_suppliers():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, name, phone FROM suppliers WHERE branch_id = 'HEAD_OFFICE'")
    rows = cursor.fetchall()
    conn.close()
    return [{"id": r[0], "name": r[1], "phone": r[2]} for r in rows]

@app.get("/branch/{branch_id}/products")
def get_branch_products(branch_id: str):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, name, price, stock FROM products WHERE branch_id = %s", (branch_id,))
    rows = cursor.fetchall()
    conn.close()
    return [{"id": r[0], "name": r[1], "price": r[2], "stock": r[3]} for r in rows]

@app.get("/", response_class=HTMLResponse)
@app.get("/dashboard", response_class=HTMLResponse)
def dashboard():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT DISTINCT branch_id FROM products WHERE branch_id != 'HEAD_OFFICE' UNION SELECT DISTINCT branch_id FROM sales")
    branches = [r[0] for r in cursor.fetchall()]

    cursor.execute("SELECT COALESCE(SUM(total), 0), COUNT(*) FROM sales")
    total_revenue, total_sales_count = cursor.fetchone()

    cursor.execute("SELECT branch_id, COALESCE(SUM(total), 0) FROM sales GROUP BY branch_id")
    chart_data = cursor.fetchall()
    branch_labels = [row[0] for row in chart_data]
    branch_revenues = [row[1] for row in chart_data]

    cursor.execute("SELECT payment_type, COALESCE(SUM(total), 0) FROM sales GROUP BY payment_type")
    payment_data = cursor.fetchall()
    cash_val = sum([r[1] for r in payment_data if r[0].lower() == 'cash'])
    online_val = sum([r[1] for r in payment_data if r[0].lower() != 'cash'])

    cursor.execute("""
        SELECT p.name, SUM(s.quantity) as total_qty
        FROM sales s
        JOIN products p ON s.product_id = p.id
        GROUP BY p.name
        ORDER BY total_qty DESC LIMIT 5
    """)
    top_products = cursor.fetchall()

    cursor.execute("SELECT branch_id, name, stock FROM products WHERE stock < 5 AND branch_id != 'HEAD_OFFICE' ORDER BY stock ASC")
    low_stocks = cursor.fetchall()
    low_stock_rows = "".join(f"<tr><td style='color:red;'>{r[0]}</td><td>{r[1]}</td><td style='color:red;'>{r[2]}</td></tr>" for r in low_stocks)

    cursor.execute("SELECT branch_id, supplier_name, product_name, quantity, cost_price, status, created_at FROM purchases ORDER BY id DESC LIMIT 20")
    purchases = cursor.fetchall()
    purchase_rows = "".join(
        f"<tr><td>{p[0]}</td><td>{p[1]}</td><td>{p[2]}</td><td>{p[3]}</td><td>Rs. {p[4]:,.0f}</td><td style='color:{'green' if p[5] == 'received' else 'orange'}; font-weight:bold;'>{p[5].upper()}</td><td>{p[6]}</td></tr>"
        for p in purchases
    )

    cursor.execute("SELECT id, name, price FROM products WHERE branch_id = 'HEAD_OFFICE' ORDER BY id DESC")
    master_products = cursor.fetchall()
    master_rows = "".join(f"<tr><td>{p[0]}</td><td>{p[1]}</td><td>Rs. {p[2]:,.0f}</td></tr>" for p in master_products)

    cursor.execute("SELECT id, name, phone FROM suppliers WHERE branch_id = 'HEAD_OFFICE' ORDER BY id DESC")
    master_sups = cursor.fetchall()
    sup_rows = "".join(f"<tr><td>{s[0]}</td><td>{s[1]}</td><td>{s[2]}</td></tr>" for s in master_sups)

    cursor.execute("SELECT t.from_branch, t.to_branch, p.name, t.quantity, t.created_at FROM transfers t LEFT JOIN products p ON t.product_id = p.id AND t.from_branch = p.branch_id ORDER BY t.id DESC LIMIT 10")
    transfers = cursor.fetchall()
    transfer_rows = "".join(f"<tr><td>{t[0]}</td><td>{t[1]}</td><td>{t[2] or 'Unknown'}</td><td>{t[3]}</td><td>{t[4]}</td></tr>" for t in transfers)

    conn.close()
    
    labels_json = json.dumps(branch_labels)
    revenues_json = json.dumps(branch_revenues)
    
    branches_options = "".join(f"<option value='{b}'>{b}</option>" for b in branches)
    
    top_products_rows = "".join(f"<tr><td>{p[0]}</td><td>{p[1]} units</td></tr>" for p in top_products)

    html = f"""
    <html>
    <head>
        <title>Head Office Dashboard</title>
        <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
        <style>
            body {{ font-family: 'Segoe UI', sans-serif; margin: 0; padding: 20px; background: #eef2f5; }}
            .stats-grid {{ display: grid; grid-template-columns: repeat(3, 1fr); gap: 20px; margin-bottom: 20px; }}
            .stat-box {{ background: white; padding: 20px; border-radius: 8px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); text-align: center; border-top: 4px solid #2c3e50; }}
            .stat-box h3 {{ margin: 0; color: #7f8c8d; font-size: 14px; }}
            .stat-box p {{ margin: 10px 0 0 0; font-size: 24px; font-weight: bold; color: #2c3e50; }}
            
            .charts-grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 20px; margin-bottom: 20px; }}
            .card {{ background: white; padding: 20px; border-radius: 8px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); margin-bottom: 20px; }}
            
            table {{ border-collapse: collapse; width: 100%; background: white; }}
            th, td {{ border: 1px solid #ddd; padding: 12px; text-align: left; }}
            th {{ background: #2c3e50; color: white; }}
            input, select {{ padding: 8px; border: 1px solid #ccc; border-radius: 4px; margin-right: 10px; }}
            button {{ padding: 9px 15px; background: #3498db; color: white; border: none; border-radius: 4px; cursor: pointer; font-weight: bold; }}
            button:hover {{ background: #2980b9; }}
            .btn-green {{ background: #2ecc71; }}
            .btn-purple {{ background: #9b59b6; }}
        </style>
    </head>
    <body>
        <h1 style="color: #2c3e50;">Head Office Dashboard</h1>
        
        <div class="stats-grid">
            <div class="stat-box"><h3>Total Sales</h3><p>{total_sales_count}</p></div>
            <div class="stat-box"><h3>Total Revenue</h3><p>PKR {total_revenue:,.0f}</p></div>
            <div class="stat-box" style="border-top-color: #e74c3c;"><h3>Low Stock Alerts</h3><p style="color: #e74c3c;">{len(low_stocks)}</p></div>
        </div>

        <div class="charts-grid">
            <div class="card">
                <h2 style="text-align: center; color: #2c3e50; font-size: 18px;">Branch-wise Revenue</h2>
                <canvas id="revenueChart" style="max-height: 250px;"></canvas>
            </div>
            
            <div class="card">
                <h2 style="text-align: center; color: #2c3e50; font-size: 18px;">Cash vs Online Payments</h2>
                <canvas id="paymentChart" style="max-height: 250px;"></canvas>
            </div>
        </div>

        <div class="charts-grid">
            <div class="card" style="border-left: 5px solid #e67e22;">
                <h2 style="color: #2c3e50; margin-top: 0;">Top 5 Selling Products</h2>
                <table>
                    <tr><th>Product Name</th><th>Quantity Sold</th></tr>
                    {top_products_rows if top_products_rows else "<tr><td colspan='2'>No sales yet.</td></tr>"}
                </table>
            </div>

            <div class="card" style="border-left: 5px solid #3498db;">
                <h2 style="color: #2c3e50; margin-top: 0;">Branch Inventory Viewer</h2>
                <label>Select Branch:</label>
                <select id="branchSelect" onchange="fetchBranchInventory()">
                    <option value="">-- Select a Branch --</option>
                    {branches_options}
                </select>
                <table id="inventoryTable" style="margin-top: 15px; display: none;">
                    <thead><tr><th>Product ID</th><th>Product Name</th><th>Price</th><th>Stock</th></tr></thead>
                    <tbody id="inventoryBody"></tbody>
                </table>
            </div>
        </div>

        <div class="card" style="border-left: 5px solid #f39c12;">
            <h2 style="color: #2c3e50; margin-top: 0;">Branch Purchase Orders</h2>
            <table>
                <tr><th>Branch</th><th>Supplier</th><th>Product</th><th>Qty</th><th>Cost</th><th>Status</th><th>Date</th></tr>
                {purchase_rows if purchase_rows else "<tr><td colspan='7'>No purchase orders found.</td></tr>"}
            </table>
        </div>

        <div class="card" style="border-left: 5px solid #e74c3c;">
            <h2 style="color: #e74c3c; margin-top: 0;">⚠ Low Stock Alerts</h2>
            <table>
                <tr><th>Branch</th><th>Product Name</th><th>Remaining Stock</th></tr>
                {low_stock_rows if low_stock_rows else "<tr><td colspan='3'>All stocks are healthy.</td></tr>"}
            </table>
        </div>

        <div class="charts-grid">
            <div class="card" style="border-left: 5px solid #9b59b6;">
                <h2 style="color: #2c3e50; margin-top: 0;">Create Master Supplier</h2>
                <form action="/master/add_supplier" method="post">
                    <label>Supplier Name:</label><input type="text" name="name" required placeholder="e.g. Ali Distributors"><br><br>
                    <label>Phone:</label><input type="text" name="phone" required placeholder="e.g. 03001234567"><br><br>
                    <button type="submit" class="btn-purple">Create Supplier</button>
                </form>
            </div>

            <div class="card" style="border-left: 5px solid #2ecc71;">
                <h2 style="color: #2c3e50; margin-top: 0;">Create Master Product</h2>
                <form action="/master/add" method="post">
                    <label>Product Name:</label><input type="text" name="name" required placeholder="e.g. iPhone 15"><br><br>
                    <label>Price:</label><input type="number" step="0.01" name="price" required placeholder="e.g. 250000"><br><br>
                    <button type="submit" class="btn-green">Create Product</button>
                </form>
            </div>
        </div>

        <div class="card">
            <h2 style="color: #2c3e50; margin-top: 0;">Stock Transfer Between Branches</h2>
            <form action="/transfer" method="post">
                <label>From Branch:</label><select name="from_branch" required>{branches_options}</select>
                <label>To Branch:</label><select name="to_branch" required>{branches_options}</select>
                <label>Product ID:</label><input type="number" name="product_id" required placeholder="e.g. 1">
                <label>Quantity:</label><input type="number" name="quantity" required placeholder="e.g. 5">
                <button type="submit">Transfer Stock</button>
            </form>
        </div>

        <div class="card">
            <h2 style="color: #2c3e50;">Master Products List</h2>
            <table><tr><th>ID</th><th>Product Name</th><th>Price</th></tr>{master_rows}</table>
        </div>

        <div class="card">
            <h2 style="color: #2c3e50;">Master Suppliers List</h2>
            <table><tr><th>ID</th><th>Supplier Name</th><th>Phone</th></tr>{sup_rows}</table>
        </div>

        <script>
            new Chart(document.getElementById('revenueChart'), {{
                type: 'bar', 
                data: {{ labels: {labels_json}, datasets: [{{ label: 'Revenue', data: {revenues_json}, backgroundColor: '#3498db' }}] }},
                options: {{ plugins: {{ legend: {{ display: false }} }} }}
            }});

            new Chart(document.getElementById('paymentChart'), {{
                type: 'pie',
                data: {{
                    labels: ['Cash', 'Online'],
                    datasets: [{{
                        data: [{cash_val}, {online_val}],
                        backgroundColor: ['#2ecc71', '#9b59b6']
                    }}]
                }}
            }});

            async function fetchBranchInventory() {{
                const branch = document.getElementById('branchSelect').value;
                const table = document.getElementById('inventoryTable');
                const tbody = document.getElementById('inventoryBody');
                if (!branch) {{ table.style.display = 'none'; return; }}
                const response = await fetch(`/branch/${{branch}}/products`);
                const data = await response.json();
                tbody.innerHTML = '';
                if (data.length === 0) {{ tbody.innerHTML = '<tr><td colspan="4">No products found in this branch.</td></tr>'; }} 
                else {{ data.forEach(p => {{ 
                    let color = p.stock < 5 ? 'red' : 'black'; 
                    let price_str = Number(p.price).toLocaleString('en-PK', {{maximumFractionDigits: 0}});
                    tbody.innerHTML += `<tr><td>${{p.id}}</td><td>${{p.name}}</td><td>Rs. ${{price_str}}</td><td style="color:${{color}}; font-weight:bold;">${{p.stock}}</td></tr>`; 
                }}); }}
                table.style.display = 'table';
            }}
        </script>
    </body>
    </html>
    """
    return html

@app.post("/master/add")
def add_master_product(name: str = Form(...), price: float = Form(...)):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT COALESCE(MAX(id), 0) FROM products")
    new_id = cursor.fetchone()[0] + 1
    cursor.execute("INSERT INTO products (id, branch_id, name, price, cost_price, stock) VALUES (%s, 'HEAD_OFFICE', %s, %s, 0, 0)", (new_id, name, price))
    conn.commit()
    conn.close()
    return RedirectResponse(url="/dashboard", status_code=303)

@app.post("/master/add_supplier")
def add_master_supplier(name: str = Form(...), phone: str = Form(...)):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT COALESCE(MAX(id), 0) FROM suppliers")
    new_id = cursor.fetchone()[0] + 1
    cursor.execute("INSERT INTO suppliers (id, branch_id, name, phone) VALUES (%s, 'HEAD_OFFICE', %s, %s)", (new_id, name, phone))
    conn.commit()
    conn.close()
    return RedirectResponse(url="/dashboard", status_code=303)

@app.post("/transfer")
def transfer_stock_web(from_branch: str = Form(...), to_branch: str = Form(...), product_id: int = Form(...), quantity: int = Form(...)):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT stock FROM products WHERE branch_id = %s AND id = %s", (from_branch, product_id))
    result = cursor.fetchone()
    if not result or result[0] < quantity:
        conn.close()
        return HTMLResponse("<h3 style='color:red;'>Error: Not enough stock in source branch! <br><br><a href='/dashboard'>Go Back to Dashboard</a></h3>")
    cursor.execute("UPDATE products SET stock = stock - %s WHERE branch_id = %s AND id = %s", (quantity, from_branch, product_id))
    cursor.execute("SELECT stock FROM products WHERE branch_id = %s AND id = %s", (to_branch, product_id))
    if cursor.fetchone():
        cursor.execute("UPDATE products SET stock = stock + %s WHERE branch_id = %s AND id = %s", (quantity, to_branch, product_id))
    else:
        cursor.execute("INSERT INTO products (id, branch_id, name, price, cost_price, stock) SELECT id, %s, name, price, cost_price, %s FROM products WHERE branch_id = %s AND id = %s", (to_branch, quantity, from_branch, product_id))
    cursor.execute("INSERT INTO transfers (from_branch, to_branch, product_id, quantity) VALUES (%s, %s, %s, %s)", (from_branch, to_branch, product_id, quantity))
    conn.commit()
    conn.close()
    return RedirectResponse(url="/dashboard", status_code=303)