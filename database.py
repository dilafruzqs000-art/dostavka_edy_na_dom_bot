import sqlite3
import json

conn = sqlite3.connect('food.db', check_same_thread=False)
cursor = conn.cursor()

# Таблица пользователей
cursor.execute('''
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    role TEXT CHECK(role IN ('client', 'courier')),
    name TEXT,
    phone TEXT,
    is_active BOOLEAN DEFAULT 1  # для курьеров: на линии или нет
)
''')

# Таблица заказов (добавили поле courier_id и статус)
cursor.execute('''
CREATE TABLE IF NOT EXISTS orders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id TEXT UNIQUE,
    user_id TEXT,                -- кто заказал
    courier_id INTEGER DEFAULT NULL,
    items TEXT,
    total INTEGER,
    address TEXT,
    phone TEXT,
    status TEXT DEFAULT 'new',    -- new, taken, delivered, paid
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
''')
conn.commit()

# ---------- Работа с пользователями ----------
def add_user(user_id, role, name, phone):
    cursor.execute('''
        INSERT OR REPLACE INTO users (user_id, role, name, phone, is_active)
        VALUES (?, ?, ?, ?, ?)
    ''', (user_id, role, name, phone, 1 if role == 'client' else 0))
    conn.commit()

def get_user(user_id):
    cursor.execute('SELECT * FROM users WHERE user_id = ?', (user_id,))
    row = cursor.fetchone()
    if row:
        return {'user_id': row[0], 'role': row[1], 'name': row[2], 'phone': row[3], 'is_active': row[4]}
    return None

def set_courier_active(user_id, active):
    cursor.execute('UPDATE users SET is_active = ? WHERE user_id = ?', (active, user_id))
    conn.commit()

def get_active_couriers():
    cursor.execute('SELECT user_id FROM users WHERE role = "courier" AND is_active = 1')
    return [row[0] for row in cursor.fetchall()]

# ---------- Работа с заказами ----------
def save_order(order_id, user_id, items, total, address, phone):
    cursor.execute('''
        INSERT INTO orders (order_id, user_id, items, total, address, phone, status)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', (order_id, user_id, json.dumps(items), total, address, phone, 'new'))
    conn.commit()
    return order_id

def get_new_orders():
    cursor.execute('SELECT * FROM orders WHERE status = "new"')
    rows = cursor.fetchall()
    return [{'order_id': row[1], 'user_id': row[2], 'items': json.loads(row[4]), 'total': row[5], 'address': row[6], 'phone': row[7]} for row in rows]

def take_order(order_id, courier_id):
    cursor.execute('UPDATE orders SET courier_id = ?, status = "taken" WHERE order_id = ? AND status = "new"', (courier_id, order_id))
    conn.commit()
    return cursor.rowcount > 0

def mark_order_paid(order_id):
    cursor.execute('UPDATE orders SET status = "paid" WHERE order_id = ?', (order_id,))
    conn.commit()