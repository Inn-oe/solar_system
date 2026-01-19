import sqlite3
import os

db_path = 'instance/database.db'
if not os.path.exists(db_path):
    print("Database not found.")
else:
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    checks = {
        'inventory': ['quantity', 'minimum_stock_level', 'unit_price'],
        'invoices': ['status', 'total_amount', 'balance_due', 'date_created'],
        'payments': ['payment_date', 'payment_method', 'amount'],
        'activities': ['status', 'date', 'total_cost'],
        'quotations': ['status', 'total_amount', 'date_created']
    }
    
    for table, columns in checks.items():
        print(f"Checking table: {table}")
        for col in columns:
            try:
                cursor.execute(f"SELECT count(*) FROM {table} WHERE {col} IS NULL")
                null_count = cursor.fetchone()[0]
                print(f"  - {col}: {null_count} NULLs")
            except Exception as e:
                print(f"  - {col}: Error checking NULLs: {e}")
    conn.close()
