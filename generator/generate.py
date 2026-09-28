import random
import time
import psycopg
from faker import Faker

fake = Faker()

conn = psycopg.connect("host=localhost port=5432 dbname=shop user=shop password=shop")
conn.autocommit = True
cur = conn.cursor()

STATUS_FLOW = {"placed": "shipped", "shipped": "delivered"}


def seed_products():
    cur.execute("SELECT count(*) FROM products")
    if cur.fetchone()[0] > 0:
        return
    products = [
        ("Wireless Mouse", "electronics", 24.99),
        ("USB-C Hub", "electronics", 39.99),
        ("Mechanical Keyboard", "electronics", 89.99),
        ("Coffee Mug", "kitchen", 12.50),
        ("French Press", "kitchen", 29.00),
        ("Water Bottle", "outdoors", 18.00),
        ("Hiking Socks", "outdoors", 14.99),
        ("Notebook", "office", 6.99),
        ("Desk Lamp", "office", 34.50),
        ("Hoodie", "apparel", 45.00),
    ]
    cur.executemany(
        "INSERT INTO products (name, category, price) VALUES (%s, %s, %s)", products
    )
    print("Seeded products")


def new_customer():
    cur.execute(
        "INSERT INTO customers (name, email, address) VALUES (%s, %s, %s)",
        (fake.name(), fake.email(), fake.address().replace("\n", ", ")),
    )
    print("New customer")


def duplicate_customer():
    # Same person signs up twice -- messy on purpose, cleaned up later in dbt
    cur.execute("SELECT name, email FROM customers ORDER BY random() LIMIT 1")
    row = cur.fetchone()
    if row:
        cur.execute(
            "INSERT INTO customers (name, email, address) VALUES (%s, %s, %s)",
            (row[0], row[1].upper(), fake.address().replace("\n", ", ")),
        )
        print("Duplicate customer")


def place_order():
    cur.execute("SELECT id, address FROM customers ORDER BY random() LIMIT 1")
    customer = cur.fetchone()
    if not customer:
        return
    cur.execute(
        "INSERT INTO orders (customer_id, shipping_address) VALUES (%s, %s) RETURNING id",
        (customer[0], customer[1]),  # snapshot of the address right now
    )
    order_id = cur.fetchone()[0]
    cur.execute("SELECT id, price FROM products ORDER BY random() LIMIT %s", (random.randint(1, 3),))
    for product_id, price in cur.fetchall():
        cur.execute(
            "INSERT INTO order_items (order_id, product_id, quantity, unit_price) VALUES (%s, %s, %s, %s)",
            (order_id, product_id, random.randint(1, 4), price),  # price at time of purchase
        )
    print(f"Order {order_id} placed")


def advance_order():
    cur.execute("SELECT id, status FROM orders WHERE status IN ('placed', 'shipped') ORDER BY random() LIMIT 1")
    row = cur.fetchone()
    if row:
        new_status = random.choice([STATUS_FLOW[row[1]], "cancelled"]) if row[1] == "placed" else STATUS_FLOW[row[1]]
        cur.execute("UPDATE orders SET status = %s, updated_at = now() WHERE id = %s", (new_status, row[0]))
        print(f"Order {row[0]} -> {new_status}")


def change_address():
    cur.execute(
        "UPDATE customers SET address = %s, updated_at = now() "
        "WHERE id = (SELECT id FROM customers ORDER BY random() LIMIT 1)",
        (fake.address().replace("\n", ", "),),
    )
    print("Customer moved")


def change_price():
    cur.execute(
        "UPDATE products SET price = round((price * %s)::numeric, 2), updated_at = now() "
        "WHERE id = (SELECT id FROM products ORDER BY random() LIMIT 1)",
        (random.uniform(0.8, 1.2),),
    )
    print("Price changed")


def delete_cancelled_order():
    cur.execute(
        "DELETE FROM orders WHERE id = (SELECT id FROM orders WHERE status = 'cancelled' ORDER BY random() LIMIT 1)"
    )
    print("Cancelled order deleted")


ACTIONS = [
    (place_order, 40),
    (advance_order, 25),
    (new_customer, 15),
    (change_address, 8),
    (change_price, 5),
    (delete_cancelled_order, 4),
    (duplicate_customer, 3),
]

if __name__ == "__main__":
    seed_products()
    for _ in range(5):
        new_customer()
    functions, weights = zip(*ACTIONS)
    while True:
        random.choices(functions, weights)[0]()
        time.sleep(1)