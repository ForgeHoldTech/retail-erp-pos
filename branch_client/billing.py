from database import get_connection, get_local_time

def create_multi_sale(cart_items, payment_type="cash", overall_discount_pct=0.0):
    conn = get_connection()
    cursor = conn.cursor()
    
    for item in cart_items:
        cursor.execute("SELECT stock, name FROM products WHERE id = ?", (item['product_id'],))
        res = cursor.fetchone()
        if not res:
            conn.close()
            return None, f"Product ID {item['product_id']} not found"
        if res[0] < item['quantity']:
            conn.close()
            return None, f"Not enough stock for {res[1]}"

    sub_total = 0
    for item in cart_items:
        item_total = (item['price'] * item['quantity']) * (1 - (item['discount_pct'] / 100))
        sub_total += item_total

    overall_discount_amt = sub_total * (overall_discount_pct / 100)
    final_total = sub_total - overall_discount_amt

    local_time = get_local_time()
    
    cursor.execute("""
        INSERT INTO sales (total, payment_type, discount, discount_amount, created_at) 
        VALUES (?, ?, ?, ?, ?)
    """, (final_total, payment_type, overall_discount_pct, overall_discount_amt, local_time))
    
    sale_id = cursor.lastrowid

    for item in cart_items:
        item_total = (item['price'] * item['quantity']) * (1 - (item['discount_pct'] / 100))
        
        cursor.execute("""
            INSERT INTO sale_items (sale_id, product_id, quantity, price, item_discount_pct, final_price)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (sale_id, item['product_id'], item['quantity'], item['price'], item['discount_pct'], item_total))
        
        cursor.execute("UPDATE products SET stock = stock - ? WHERE id = ?", (item['quantity'], item['product_id']))
        
    conn.commit()
    conn.close()
    return final_total, sale_id

def get_sales():
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute("SELECT id, total, discount, payment_type, created_at FROM sales ORDER BY id DESC")
    sales = cursor.fetchall()
    
    results = []
    for s in sales:
        sale_id, total, overall_discount_pct, p_type, created_at = s
        
        cursor.execute("""
            SELECT p.name, si.quantity, si.item_discount_pct
            FROM sale_items si
            JOIN products p ON si.product_id = p.id
            WHERE si.sale_id = ?
        """, (sale_id,))
        items = cursor.fetchall()
        
        item_names = ", ".join([f"{item[0]} ({item[1]}) [Disc: {item[2]}%]" for item in items])
        
        results.append((sale_id, item_names, total, overall_discount_pct, p_type, created_at))
        
    conn.close()
    return results