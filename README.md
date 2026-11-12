# ForgeHold Multi-Branch Retail ERP & POS

A multi-branch retail management system built by **Forgehold Technologies**. It has two parts: an offline-first desktop Point of Sale client that runs at each store, and a central Head Office server that collects data from every branch and provides real-time analytics.

Branches keep selling during internet outages. Every sale is saved to a local SQLite database first and synced to the Head Office automatically when the connection returns, so no data is lost.

---

## Features

### Branch Client (PyQt6 Desktop App)
- **Cashier billing**: multi-product cart, per-item discount percentage, overall bill discount, and cash or online payment
- **Customer receipts**: a receipt dialog is generated after every checkout
- **Returns**: sales can be returned by Sale ID with refund tracking
- **Inventory manager**: view products, update stock, and download master products from Head Office
- **Purchase orders**: create orders for suppliers and receive them to increase stock automatically
- **Shift closing**: enter opening and closing cash; the system calculates expected cash and the difference
- **Offline-first sync**: products, sales, returns and purchases are pushed to Head Office on a timer whenever the server is reachable

### Head Office Server (FastAPI + PostgreSQL)
- **Analytics dashboard** with total sales, total revenue and a low-stock alert count
- **Charts** (Chart.js): branch-wise revenue (bar) and cash vs online payments (pie)
- **Top 5 selling products**
- **Branch inventory viewer** that loads any branch's live stock
- **Low-stock alerts** for products with fewer than 5 units
- **Branch purchase orders** with pending/received status
- **Master data**: create master products and suppliers that branches can download
- **Stock transfer** between branches with a full transfer history

---

## Architecture

```
+---------------------------+          REST API (JSON)          +-----------------------------+
|   Branch Client (PyQt6)   |  ------------------------------>  |  Head Office Server         |
|   Local SQLite database   |  <------------------------------  |  FastAPI + PostgreSQL       |
|   Works fully offline     |     master products / stock       |  Web analytics dashboard    |
+---------------------------+                                   +-----------------------------+
```

- Each branch has its own SQLite file (`branch_data_<BRANCH_ID>.db`).
- Records carry a `synced` flag, so only new data is sent to the server.
- On the server, every table uses a composite key `(id, branch_id)`, which keeps each branch's data separate. Head Office master records use `branch_id = 'HEAD_OFFICE'`.

---

## Tech Stack

| Layer | Technologies |
|---|---|
| Desktop client | Python, PyQt6, SQLite, Requests |
| Backend server | Python, FastAPI, Uvicorn, Pydantic, Psycopg2, Python-Multipart |
| Database | PostgreSQL (Head Office), SQLite (branches) |
| Dashboard | HTML5, CSS3, JavaScript, Chart.js |

---

## Project Structure

```
retail-software/
├── branch_client/
│   ├── main.py          # PyQt6 application (Billing, Returns, Manager tabs)
│   ├── database.py      # SQLite schema, returns, shifts, purchase orders
│   ├── billing.py       # Multi-item sales with discounts
│   └── sync.py          # Sync with the Head Office server
├── server/
│   ├── main.py          # FastAPI app, sync endpoints and dashboard
│   └── db.py            # PostgreSQL connection and schema
├── requirements.txt
└── README.md
```

---

## Getting Started

### Prerequisites
- Python 3.12
- PostgreSQL 14 or later

### 1. Clone the repository
```bash
git clone https://github.com/ForgeHoldTech/retail-erp-pos.git
cd retail-erp-pos
```

### 2. Create a virtual environment and install dependencies
```bash
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

### 3. Create the database
Create an empty PostgreSQL database named `retail_head_office`. The tables are created automatically when the server starts for the first time.

### 4. Configure the database connection
The server reads its settings from environment variables:

| Variable | Default |
|---|---|
| `DB_HOST` | `localhost` |
| `DB_PORT` | `5432` |
| `DB_NAME` | `retail_head_office` |
| `DB_USER` | `postgres` |
| `DB_PASSWORD` | *(empty)* |

Windows (CMD):
```bash
set DB_PASSWORD=your_password
```

### 5. Run the Head Office server
```bash
cd server
uvicorn main:app --reload
```
Open the dashboard at **http://127.0.0.1:8000/dashboard**

### 6. Run a branch client
Open a new terminal:
```bash
venv\Scripts\activate
cd branch_client
python main.py
```
To run another branch, change `BRANCH_ID` in `branch_client/database.py` (for example `branch_2`). If the server runs on a different machine, update `SERVER_URL` in `branch_client/sync.py`.

---

## API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| POST | `/sync/products` | Push branch products and stock |
| POST | `/sync/sales` | Push unsynced sales |
| POST | `/sync/returns` | Push unsynced returns |
| POST | `/sync/purchases` | Push purchase orders |
| GET | `/master/products` | Download master products |
| GET | `/master/suppliers` | Download master suppliers |
| GET | `/branch/{branch_id}/products` | Get a branch's current stock |
| GET | `/dashboard` | Head Office analytics dashboard |
| POST | `/master/add` | Create a master product |
| POST | `/master/add_supplier` | Create a master supplier |
| POST | `/transfer` | Transfer stock between branches |

Interactive API documentation is available at **http://127.0.0.1:8000/docs** while the server is running.

---

## Author

**Usman Ahmad**, Forgehold Technologies

- GitHub: [github.com/ForgeHoldTech](https://github.com/ForgeHoldTech)
- Portfolio: [forgeholdtech.github.io](https://forgeholdtech.github.io)
- Email: uahmad1666@gmail.com
