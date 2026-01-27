import sqlite3
import os

def migrate_ids():
    db_path = 'instance/database.db'
    if not os.path.exists(db_path):
        print(f"Database not found at {db_path}")
        return

    print(f"Connecting to database at {db_path}...")
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    try:
        # 1. Add columns if they don't exist
        for table, col in [('quotations', 'quotation_number'), ('invoices', 'invoice_number')]:
            cursor.execute(f"PRAGMA table_info({table})")
            columns = [column[1] for column in cursor.fetchall()]
            if col not in columns:
                print(f"Adding '{col}' column to '{table}' table...")
                cursor.execute(f"ALTER TABLE {table} ADD COLUMN {col} VARCHAR(20)")
                conn.commit()
            else:
                print(f"'{col}' column already exists in '{table}'.")

        # 2. Populate existing quotations
        print("Populating existing quotations...")
        cursor.execute("""
            SELECT q.id, c.name 
            FROM quotations q 
            JOIN customers c ON q.customer_id = c.identification_number
            WHERE q.quotation_number IS NULL
        """)
        quotations = cursor.fetchall()
        for q in quotations:
            prefix = (q['name'][:2].upper() if q['name'] else 'XX')
            num = f"{prefix}{q['id']:05d}"
            cursor.execute("UPDATE quotations SET quotation_number = ? WHERE id = ?", (num, q['id']))
        
        # 3. Populate existing invoices
        print("Populating existing invoices...")
        cursor.execute("""
            SELECT i.id, c.name 
            FROM invoices i 
            JOIN customers c ON i.customer_id = c.identification_number
            WHERE i.invoice_number IS NULL
        """)
        invoices = cursor.fetchall()
        for inv in invoices:
            prefix = (inv['name'][:2].upper() if inv['name'] else 'XX')
            num = f"{prefix}{inv['id']:05d}"
            cursor.execute("UPDATE invoices SET invoice_number = ? WHERE id = ?", (num, inv['id']))

        conn.commit()
        print("Migration complete.")

    except Exception as e:
        print(f"Error during migration: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    migrate_ids()
