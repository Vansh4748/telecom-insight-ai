import sqlite3
from app.config import DB_PATH

SQL_SCRIPT = """
DROP TABLE IF EXISTS billing;
DROP TABLE IF EXISTS usage_records;
DROP TABLE IF EXISTS customers;

CREATE TABLE customers (
    customer_id INTEGER PRIMARY KEY,
    customer_name TEXT,
    city TEXT,
    plan_type TEXT,
    join_date DATE
);

INSERT INTO customers VALUES
(101, 'Rahul Sharma', 'Pune', 'Prepaid', '2024-01-15'),
(102, 'Ananya Singh', 'Mumbai', 'Postpaid', '2023-08-22'),
(103, 'Vikram Patel', 'Delhi', 'Postpaid', '2024-03-10'),
(104, 'Priya Mehta', 'Bangalore', 'Prepaid', '2024-07-01'),
(105, 'Karan Gupta', 'Hyderabad', 'Postpaid', '2023-12-05'),
(106, 'Sneha Iyer', 'Chennai', 'Postpaid', '2024-05-18'),
(107, 'Amit Verma', 'Kolkata', 'Prepaid', '2023-11-12'),
(108, 'Neha Kapoor', 'Pune', 'Postpaid', '2024-02-27');

CREATE TABLE usage_records (
    usage_id INTEGER PRIMARY KEY,
    customer_id INTEGER,
    usage_month TEXT,
    data_gb REAL,
    call_minutes INTEGER,
    sms_count INTEGER,
    FOREIGN KEY(customer_id) REFERENCES customers(customer_id)
);

INSERT INTO usage_records VALUES
(1, 101, '2025-01', 12.5, 320, 45),
(2, 102, '2025-01', 45.2, 780, 12),
(3, 103, '2025-01', 28.7, 540, 25),
(4, 104, '2025-01', 8.3, 210, 80),
(5, 105, '2025-01', 62.1, 910, 8),
(6, 106, '2025-01', 35.4, 610, 18),
(7, 107, '2025-01', NULL, 275, 60),
(8, 108, '2025-01', 250.0, 830, 15);

CREATE TABLE billing (
    bill_id INTEGER PRIMARY KEY,
    customer_id INTEGER,
    bill_month TEXT,
    bill_amount REAL,
    payment_status TEXT,
    FOREIGN KEY(customer_id) REFERENCES customers(customer_id)
);

INSERT INTO billing VALUES
(1001, 101, '2025-01', 299.00, 'Paid'),
(1002, 102, '2025-01', 899.00, 'Paid'),
(1003, 103, '2025-01', 699.00, 'Pending'),
(1004, 104, '2025-01', 249.00, 'Paid'),
(1005, 105, '2025-01', 1199.00, 'Pending'),
(1006, 106, '2025-01', 799.00, 'Paid'),
(1007, 107, '2025-01', NULL, 'Overdue'),
(1008, 108, '2025-01', 949.00, 'Paid');
"""

DB_PATH.parent.mkdir(exist_ok=True)
with sqlite3.connect(DB_PATH) as conn:
    conn.executescript(SQL_SCRIPT)

print("Database created at:", DB_PATH)