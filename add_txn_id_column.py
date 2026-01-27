import sqlite3
import os

def migrate_payments_table():
    db_path = 'instance/database.db'
    if not os.path.exists(db_path):
        print(f"Database not found at {db_path}")
        return

    print(f"Connecting to database at {db_path}...")
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    try:
        # Check if column already exists
        cursor.execute("PRAGMA table_info(payments)")
        columns = [column[1] for column in cursor.fetchall()]
        
        if 'transaction_id' not in columns:
            print("Adding 'transaction_id' column to 'payments' table...")
            cursor.execute("ALTER TABLE payments ADD COLUMN transaction_id VARCHAR(50)")
            conn.commit()
            print("Column added successfully.")
        else:
            print("'transaction_id' column already exists.")

    except Exception as e:
        print(f"Error during migration: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    migrate_payments_table()
