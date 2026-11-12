import sys
import os
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QLabel, QPushButton,
    QLineEdit, QListWidget, QListWidgetItem, QVBoxLayout, QWidget, QTabWidget, QFormLayout, QMessageBox, QDialog, QComboBox, QHBoxLayout
)
from PyQt6.QtCore import QTimer, Qt
from PyQt6.QtGui import QIcon, QColor, QIntValidator, QDoubleValidator
from database import (
    create_tables, get_products, process_return, reset_database, close_shift, update_stock,
    get_suppliers, add_purchase_order, receive_purchase_order, get_purchase_orders, BRANCH_ID
)
from billing import create_multi_sale, get_sales
from sync import sync_products, sync_sales, sync_returns, sync_purchases, download_master_products, fetch_my_stock

MANAGER_PIN = "1234"

class ReceiptDialog(QDialog):
    def __init__(self, branch_id, cart_items, overall_discount, final_total, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Customer Receipt")
        self.setFixedSize(350, 500)
        layout = QVBoxLayout()
        
        shop_name = QLabel("RETAIL STORE")
        shop_name.setStyleSheet("font-size: 16px; font-weight: bold;")
        shop_name.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        branch_info = QLabel(f"Branch: {branch_id}")
        branch_info.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        layout.addWidget(shop_name)
        layout.addWidget(branch_info)
        layout.addWidget(QLabel("-" * 35, alignment=Qt.AlignmentFlag.AlignCenter))
        
        for item in cart_items:
            item_price = f"{item['price']:,.0f}" if item['price'].is_integer() else f"{item['price']:,.2f}"
            item_text = f"{item['name']} x{item['quantity']} @ {item_price}\n"
            if item['discount_pct'] > 0:
                item_text += f"  (Disc {item['discount_pct']}%)\n"
            item_label = QLabel(item_text)
            layout.addWidget(item_label)
            
        layout.addWidget(QLabel("-" * 35, alignment=Qt.AlignmentFlag.AlignCenter))
        
        if overall_discount > 0:
            disc_label = QLabel(f"Overall Discount: -{overall_discount}%")
            disc_label.setStyleSheet("color: red;")
            layout.addWidget(disc_label)
            
        total_str = f"{final_total:,.0f}" if final_total.is_integer() else f"{final_total:,.2f}"
        total_label = QLabel(f"Grand Total: PKR {total_str}")
        total_label.setStyleSheet("font-size: 16px; font-weight: bold; color: green;")
        layout.addWidget(total_label)
        
        layout.addStretch()
        print_btn = QPushButton("Close & Print")
        print_btn.setStyleSheet("background-color: #3498db; color: white; padding: 10px;")
        print_btn.clicked.connect(self.accept) 
        layout.addWidget(print_btn)
        
        self.setLayout(layout)

class SuppliersDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Manage Purchase Orders")
        self.setGeometry(300, 300, 500, 600)
        layout = QVBoxLayout()
        po_form = QFormLayout()
        self.sup_combo = QComboBox()
        self.prod_combo = QComboBox()
        self.po_qty = QLineEdit()
        self.po_qty.setValidator(QIntValidator()) 
        self.po_cost = QLineEdit()
        self.po_cost.setValidator(QDoubleValidator()) 
        self.sup_combo.addItem("-- Select Supplier --", None)
        for sup in get_suppliers():
            sid, name, phone = sup
            self.sup_combo.addItem(name, sid)
        self.prod_combo.addItem("-- Select Product --", None)
        for pid, name, price, stock in get_products():
            self.prod_combo.addItem(name, pid)
        self.create_po_btn = QPushButton("Create Purchase Order")
        self.create_po_btn.clicked.connect(self.create_po)
        po_form.addRow("Select Supplier:", self.sup_combo)
        po_form.addRow("Select Product:", self.prod_combo)
        po_form.addRow("Quantity:", self.po_qty)
        po_form.addRow("Cost Price:", self.po_cost)
        layout.addWidget(QLabel("<h3>Create New Purchase Order</h3>"))
        layout.addLayout(po_form)
        layout.addWidget(self.create_po_btn)
        layout.addWidget(QLabel("<h3>Pending Purchase Orders</h3>"))
        self.po_list = QListWidget()
        layout.addWidget(self.po_list)
        self.receive_btn = QPushButton("Receive Selected PO (Add to Stock)")
        self.receive_btn.setStyleSheet("background-color: #2ecc71; color: white; font-weight: bold; padding: 10px;")
        self.receive_btn.clicked.connect(self.receive_po)
        layout.addWidget(self.receive_btn)
        self.setLayout(layout)
        self.load_data()

    def load_data(self):
        self.po_list.clear()
        for p in get_purchase_orders():
            text = f"PO #{p[0]} | Sup: {p[1]} | Prod: {p[2]} | Qty: {p[3]} | Status: {p[5].upper()}"
            item = QListWidgetItem(text)
            item.setData(Qt.ItemDataRole.UserRole, p[0]) 
            self.po_list.addItem(item)

    def create_po(self):
        sup_id = self.sup_combo.currentData()
        prod_id = self.prod_combo.currentData()
        if not sup_id or not prod_id:
            QMessageBox.warning(self, "Error", "Please select both Supplier and Product.")
            return
        try:
            qty = int(self.po_qty.text())
            cost = float(self.po_cost.text())
            add_purchase_order(sup_id, prod_id, qty, cost)
            sync_purchases()
            QMessageBox.information(self, "Success", "Purchase Order created!")
            self.load_data()
            self.po_qty.clear(); self.po_cost.clear()
            self.sup_combo.setCurrentIndex(0); self.prod_combo.setCurrentIndex(0)
        except ValueError:
            QMessageBox.warning(self, "Error", "Please enter valid numbers.")

    def receive_po(self):
        selected = self.po_list.currentItem()
        if selected:
            po_id = selected.data(Qt.ItemDataRole.UserRole)
            if receive_purchase_order(po_id):
                sync_products()
                sync_purchases()
                QMessageBox.information(self, "Success", "Stock received and updated!")
                self.load_data()
                self.parent().load_products()
            else:
                QMessageBox.warning(self, "Error", "Could not receive. Maybe already received?")

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"Retail Software - Branch: {BRANCH_ID}")
        self.setGeometry(200, 200, 650, 850)
        
        icon_path = os.path.join(os.path.dirname(__file__), 'icon.png')
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))

        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout()

        self.tabs = QTabWidget()
        self.cart_items = [] 
        
        self.tab_billing = QWidget()
        self.setup_billing_tab()
        
        self.tab_returns = QWidget()
        self.setup_returns_tab()
        
        self.tab_manager = QWidget()
        self.setup_manager_tab()

        self.tabs.addTab(self.tab_billing, "Cashier (Billing)")
        self.tabs.addTab(self.tab_returns, "Returns")
        self.tabs.addTab(self.tab_manager, "Manager (Inventory)")
        
        self.tabs.currentChanged.connect(self.on_tab_changed)

        self.sync_status = QLabel("Auto-Sync is running...")
        self.sync_status.setStyleSheet("color: green; font-weight: bold; margin-top: 10px;")
        
        main_layout.addWidget(self.tabs)
        main_layout.addWidget(self.sync_status)
        central.setLayout(main_layout)
        
        self.load_products()
        self.load_sales()

        self.timer = QTimer()
        self.timer.timeout.connect(self.auto_sync)
        self.timer.start(10000) 

    def on_tab_changed(self, index):
        if index != 2:
            self.login_widget.show()
            self.add_product_widget.hide()
            self.pin_input.clear()
            self.login_msg.clear()

    def setup_billing_tab(self):
        layout = QVBoxLayout()
        self.product_list = QListWidget()
        
        add_form = QHBoxLayout()
        self.bill_product_id = QLineEdit()
        self.bill_product_id.setValidator(QIntValidator()) 
        self.bill_product_id.setPlaceholderText("Prod ID")
        
        self.bill_quantity = QLineEdit()
        self.bill_quantity.setValidator(QIntValidator()) 
        self.bill_quantity.setPlaceholderText("Qty")
        
        self.bill_item_discount = QLineEdit()
        self.bill_item_discount.setValidator(QDoubleValidator())
        self.bill_item_discount.setPlaceholderText("Disc %")
        
        self.add_to_cart_btn = QPushButton("+ Add to Bill")
        self.add_to_cart_btn.setStyleSheet("background-color: #2980b9; color: white; font-weight: bold;")
        self.add_to_cart_btn.clicked.connect(self.add_to_cart_clicked)
        
        add_form.addWidget(self.bill_product_id)
        add_form.addWidget(self.bill_quantity)
        add_form.addWidget(self.bill_item_discount)
        add_form.addWidget(self.add_to_cart_btn)

        self.cart_list = QListWidget()
        
        checkout_form = QFormLayout()
        self.overall_discount = QLineEdit()
        self.overall_discount.setValidator(QDoubleValidator())
        self.overall_discount.setPlaceholderText("0.0")
        
        self.bill_payment_type = QComboBox()
        self.bill_payment_type.addItems(["Cash", "Online"])

        self.checkout_btn = QPushButton("Generate Final Bill & Print")
        self.checkout_btn.setStyleSheet("background-color: #27ae60; color: white; font-weight: bold; padding: 10px; font-size: 14px;")
        self.checkout_btn.clicked.connect(self.checkout_clicked)
        
        checkout_form.addRow("Overall Bill Discount (%):", self.overall_discount)
        checkout_form.addRow("Payment Type:", self.bill_payment_type)
        
        layout.addWidget(QLabel("<h3>Available Products</h3>"))
        layout.addWidget(self.product_list)
        layout.addWidget(QLabel("<h3>Add Product to Current Bill</h3>"))
        layout.addLayout(add_form)
        
        layout.addWidget(QLabel("<h3>Current Cart (Customer Items)</h3>"))
        layout.addWidget(self.cart_list)
        
        layout.addWidget(QLabel("<h3>Checkout</h3>"))
        layout.addLayout(checkout_form)
        layout.addWidget(self.checkout_btn)

        layout.addWidget(QLabel("<h3>Today's Sales</h3>"))
        self.sales_list = QListWidget()
        layout.addWidget(self.sales_list)
        
        self.tab_billing.setLayout(layout)

    def add_to_cart_clicked(self):
        pid_text = self.bill_product_id.text()
        qty_text = self.bill_quantity.text()
        disc_text = self.bill_item_discount.text()
        
        if not pid_text or not qty_text:
            QMessageBox.warning(self, "Error", "Please enter Product ID and Quantity.")
            return
            
        pid = int(pid_text)
        qty = int(qty_text)
        disc_pct = float(disc_text) if disc_text else 0.0

        products = get_products()
        found = False
        p_name, p_price, p_stock = "", 0, 0
        for p in products:
            if p[0] == pid:
                p_name, p_price, p_stock = p[1], p[2], p[3]
                found = True
                break
                
        if not found:
            QMessageBox.warning(self, "Error", "Product not found.")
            return
            
        if p_stock < qty:
            QMessageBox.warning(self, "Error", f"Only {p_stock} stock available.")
            return

        self.cart_items.append({
            'product_id': pid,
            'name': p_name,
            'price': p_price,
            'quantity': qty,
            'discount_pct': disc_pct
        })
        
        price_str = f"{p_price:,.0f}" if p_price.is_integer() else f"{p_price:,.2f}"
        item_text = f"{p_name} | Qty: {qty} | Price: {price_str} | Disc: {disc_pct}%"
        self.cart_list.addItem(item_text)
        
        self.bill_product_id.clear()
        self.bill_quantity.clear()
        self.bill_item_discount.clear()

    def checkout_clicked(self):
        if not self.cart_items:
            QMessageBox.warning(self, "Error", "Cart is empty. Add some products first.")
            return

        overall_disc_text = self.overall_discount.text()
        overall_disc_pct = float(overall_disc_text) if overall_disc_text else 0.0
        p_type = self.bill_payment_type.currentText().lower()

        final_total, result = create_multi_sale(self.cart_items, payment_type=p_type, overall_discount_pct=overall_disc_pct)
        
        if final_total is None:
            QMessageBox.warning(self, "Error", result) 
        else:
            ReceiptDialog(BRANCH_ID, self.cart_items, overall_disc_pct, final_total, self).exec()
            
            sync_products()
            sync_sales()
            
            self.cart_items = []
            self.cart_list.clear()
            self.overall_discount.clear()
            self.load_products()
            self.load_sales()

    def setup_returns_tab(self):
        layout = QVBoxLayout()
        form = QFormLayout()
        self.return_sale_id = QLineEdit()
        self.return_sale_id.setValidator(QIntValidator()) 
        self.return_qty = QLineEdit()
        self.return_qty.setValidator(QIntValidator()) 
        self.return_btn = QPushButton("Process Return & Refund")
        self.return_btn.setStyleSheet("background-color: #e74c3c; color: white; font-weight: bold; padding: 8px;")
        self.return_btn.clicked.connect(self.process_return_clicked)
        self.return_msg = QLabel("")
        self.return_msg.setStyleSheet("font-weight: bold; color: blue;")
        form.addRow("Sale ID (Bill No):", self.return_sale_id)
        form.addRow("Return Quantity:", self.return_qty)
        layout.addWidget(QLabel("<h3>Customer Return / Refund</h3>"))
        layout.addLayout(form)
        layout.addWidget(self.return_btn)
        layout.addWidget(self.return_msg)
        self.tab_returns.setLayout(layout)

    def setup_manager_tab(self):
        layout = QVBoxLayout()
        self.login_widget = QWidget()
        login_layout = QVBoxLayout()
        self.pin_input = QLineEdit()
        self.pin_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.pin_input.setValidator(QIntValidator()) 
        self.pin_input.setPlaceholderText("Enter Manager PIN (Default: 1234)")
        self.login_btn = QPushButton("Unlock")
        self.login_btn.clicked.connect(self.check_pin)
        self.login_msg = QLabel("")
        self.login_msg.setStyleSheet("color: red;")
        login_layout.addWidget(QLabel("<h3>Manager Access Required</h3>"))
        login_layout.addWidget(self.pin_input)
        login_layout.addWidget(self.login_btn)
        login_layout.addWidget(self.login_msg)
        self.login_widget.setLayout(login_layout)
        
        self.add_product_widget = QWidget()
        add_layout = QVBoxLayout()
        self.download_btn = QPushButton("Download Master Products & Suppliers")
        self.download_btn.setStyleSheet("background-color: #2ecc71; color: white; font-weight: bold; padding: 10px;")
        self.download_btn.clicked.connect(self.download_master_clicked)
        add_layout.addWidget(self.download_btn)

        self.update_stock_btn = QPushButton("Update Stock from Head Office")
        self.update_stock_btn.setStyleSheet("background-color: #3498db; color: white; font-weight: bold; padding: 10px;")
        self.update_stock_btn.clicked.connect(self.update_stock_clicked)
        add_layout.addWidget(self.update_stock_btn)
        
        self.suppliers_btn = QPushButton("Manage Purchase Orders")
        self.suppliers_btn.setStyleSheet("background-color: #9b59b6; color: white; font-weight: bold; padding: 10px;")
        self.suppliers_btn.clicked.connect(self.open_suppliers)
        add_layout.addWidget(self.suppliers_btn)

        add_layout.addWidget(QLabel("<h3>Set Product Stock</h3>"))
        stock_form = QFormLayout()
        self.stock_pid = QLineEdit()
        self.stock_pid.setValidator(QIntValidator()) 
        self.stock_pid.setPlaceholderText("Product ID")
        self.stock_qty = QLineEdit()
        self.stock_qty.setValidator(QIntValidator()) 
        self.stock_qty.setPlaceholderText("New Stock Quantity")
        self.set_stock_btn = QPushButton("Update Stock")
        self.set_stock_btn.setStyleSheet("background-color: #f39c12; color: white; font-weight: bold; padding: 8px;")
        self.set_stock_btn.clicked.connect(self.set_stock_clicked)
        stock_form.addRow("Product ID:", self.stock_pid)
        stock_form.addRow("Quantity:", self.stock_qty)
        add_layout.addLayout(stock_form)
        add_layout.addWidget(self.set_stock_btn)
        
        add_layout.addWidget(QLabel("<h3>Shift Closing</h3>"))
        shift_form = QFormLayout()
        self.opening_cash = QLineEdit()
        self.opening_cash.setValidator(QDoubleValidator()) 
        self.opening_cash.setPlaceholderText("e.g. 5000")
        self.closing_cash = QLineEdit()
        self.closing_cash.setValidator(QDoubleValidator()) 
        self.closing_cash.setPlaceholderText("Actual cash in drawer")
        self.close_shift_btn = QPushButton("Close Shift & Calculate")
        self.close_shift_btn.setStyleSheet("background-color: #8e44ad; color: white; font-weight: bold; padding: 8px;")
        self.close_shift_btn.clicked.connect(self.close_shift_clicked)
        shift_form.addRow("Opening Cash:", self.opening_cash)
        shift_form.addRow("Closing Cash:", self.closing_cash)
        add_layout.addLayout(shift_form)
        add_layout.addWidget(self.close_shift_btn)
        
        self.reset_btn = QPushButton("Reset Branch Database")
        self.reset_btn.setStyleSheet("background-color: #c0392b; color: white; font-weight: bold; padding: 10px; margin-top: 20px; margin-bottom: 10px;")
        self.reset_btn.clicked.connect(self.reset_db_clicked)
        add_layout.addWidget(self.reset_btn)
        
        add_layout.addWidget(QLabel("<h3>Inventory List</h3>"))
        self.manager_product_list = QListWidget()
        add_layout.addWidget(self.manager_product_list)
        
        self.add_product_widget.setLayout(add_layout)
        self.add_product_widget.hide()
        
        layout.addWidget(self.login_widget)
        layout.addWidget(self.add_product_widget)
        
        self.sync_button = QPushButton("Force Sync Now")
        self.sync_button.clicked.connect(self.sync_clicked)
        layout.addWidget(self.sync_button)

        self.tab_manager.setLayout(layout)

    def open_suppliers(self):
        dlg = SuppliersDialog(self)
        dlg.exec()

    def set_stock_clicked(self):
        pid = self.stock_pid.text()
        qty = self.stock_qty.text()
        if pid and qty:
            try:
                update_stock(int(pid), int(qty))
                sync_products() 
                QMessageBox.information(self, "Success", "Stock updated successfully!")
                self.stock_pid.clear(); self.stock_qty.clear()
                self.load_products()
            except ValueError:
                pass

    def update_stock_clicked(self):
        if fetch_my_stock():
            QMessageBox.information(self, "Success", "Stock updated from Head Office successfully!")
            self.load_products()
        else:
            QMessageBox.warning(self, "Error", "Could not fetch stock.")

    def close_shift_clicked(self):
        try:
            op_cash = float(self.opening_cash.text())
            cl_cash = float(self.closing_cash.text())
        except ValueError:
            QMessageBox.warning(self, "Error", "Please enter valid numbers for cash.")
            return

        expected, diff = close_shift(op_cash, cl_cash)
        
        if diff == 0:
            QMessageBox.information(self, "Shift Closed", f"Perfect Match!\nExpected Cash: {expected}\nActual Cash: {cl_cash}")
        elif diff > 0:
            QMessageBox.information(self, "Shift Closed", f"Cash is EXCESS by Rs. {diff}\nExpected: {expected}\nActual: {cl_cash}")
        else:
            QMessageBox.warning(self, "Shift Closed", f"Cash is SHORT by Rs. {abs(diff)}\nExpected: {expected}\nActual: {cl_cash}")
            
        self.opening_cash.clear(); self.closing_cash.clear()

    def reset_db_clicked(self):
        reply = QMessageBox.question(self, "Confirm Reset", "Are you sure you want to delete ALL local data?", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            reset_database()
            self.cart_items = []
            self.cart_list.clear()
            self.load_products(); self.load_sales()
            QMessageBox.information(self, "Success", "Database reset successfully.")

    def download_master_clicked(self):
        if download_master_products():
            QMessageBox.information(self, "Success", "Master products & suppliers downloaded!")
            self.load_products()
        else:
            QMessageBox.warning(self, "Error", "Check server connection.")

    def check_pin(self):
        if self.pin_input.text() == MANAGER_PIN:
            self.login_widget.hide()
            self.add_product_widget.show()
            self.pin_input.clear()
        else:
            self.login_msg.setText("Incorrect PIN!")

    def process_return_clicked(self):
        sale_id = self.return_sale_id.text()
        qty = self.return_qty.text()
        if sale_id and qty:
            refund, error = process_return(int(sale_id), int(qty))
            if error:
                self.return_msg.setText(f"Error: {error}")
            else:
                sync_products()
                sync_returns()
                self.return_msg.setText(f"Return Successful! Refund Amount: PKR {refund}")
                self.return_sale_id.clear(); self.return_qty.clear()
                self.load_products(); self.load_sales()

    def sync_clicked(self):
        self.sync_status.setText("Syncing...")
        QApplication.processEvents()
        p_ok, s_ok, r_ok = sync_products(), sync_sales(), sync_returns()
        pur_ok = sync_purchases()
        if p_ok and s_ok and r_ok and pur_ok:
            self.sync_status.setText("Sync successful! Data sent to Head Office.")
        else:
            self.sync_status.setText("Offline: Data saved locally.")

    def auto_sync(self):
        p_ok, s_ok, r_ok = sync_products(), sync_sales(), sync_returns()
        pur_ok = sync_purchases()
        if p_ok and s_ok and r_ok and pur_ok:
            self.sync_status.setText("Auto-Sync: Online (All data synced)")
        else:
            self.sync_status.setText("Auto-Sync: Offline (Data saving locally)")

    def load_products(self):
        self.product_list.clear()
        self.manager_product_list.clear()
        for pid, name, price, stock in get_products():
            price_str = f"{price:,.0f}" if price.is_integer() else f"{price:,.2f}"
            text = f"ID: {pid} | {name} | Price: {price_str} | Stock: {stock}"
            
            item_main = QListWidgetItem(text)
            item_manager = QListWidgetItem(text)
            if stock < 5:
                item_main.setForeground(QColor("red"))
                item_manager.setForeground(QColor("red"))
            self.product_list.addItem(item_main)
            self.manager_product_list.addItem(item_manager)

    def load_sales(self):
        self.sales_list.clear()
        for sid, item_names, total, overall_discount, p_type, created in get_sales():
            total_str = f"{total:,.0f}" if total.is_integer() else f"{total:,.2f}"
            
            discount_text = ""
            if overall_discount > 0:
                discount_text = f" | Bill Disc: -{overall_discount}%"
                
            self.sales_list.addItem(f"Bill ID: {sid} | {item_names}{discount_text} | Total: {total_str} | [{p_type.upper()}]")

create_tables()
app = QApplication(sys.argv)
window = MainWindow()
window.show()
sys.exit(app.exec())