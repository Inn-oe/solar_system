import sqlite3
import os

def migrate_customer_centric_ids():
    db_path = 'instance/database.db'
    if not os.path.exists(db_path):
        print(f"Database not found at {db_path}")
        return

    print(f"Connecting to database at {db_path}...")
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    try:
        # Populate quotations
        print("Migrating quotations...")
        cursor.execute("""
            SELECT q.id, c.name, c.identification_number
            FROM quotations q
            JOIN customers c ON q.customer_id = c.identification_number
            ORDER BY q.id ASC
        """)
        quotations = cursor.fetchall()
        
        q_counts = {} # track sequence per customer
        for q in quotations:
            cid = q['identification_number']
            prefix = (q['name'][:2].upper() if q['name'] else 'XX')
            base_code = f"{prefix}{cid}"
            
            if cid not in q_counts:
                num = base_code
                q_counts[cid] = 1
            else:
                num = f"{base_code}{q_counts[cid]}"
                q_counts[cid] += 1
                
            print(f"Update Quotation #{q['id']} -> {num}")
            cursor.execute("UPDATE quotations SET quotation_number = ? WHERE id = ?", (num, q['id']))

        # Populate invoices
        print("\nMigrating invoices...")
        cursor.execute("""
            SELECT i.id, c.name, c.identification_number
            FROM invoices i
            JOIN customers c ON i.customer_id = c.identification_number
            ORDER BY i.id ASC
        """)
        invoices = cursor.fetchall()
        
        i_counts = {}
        for inv in invoices:
            cid = inv['identification_number']
            prefix = (inv['name'][:2].upper() if inv['name'] else 'XX')
            base_code = f"{prefix}{cid}"
            
            if cid not in i_counts:
                num = base_code
                i_counts[cid] = 1
            else:
                num = f"{base_code}{i_counts[cid]}"
                i_counts[cid] += 1
                
            print(f"Update Invoice #{inv['id']} -> {num}")
            cursor.execute("UPDATE invoices SET invoice_number = ? WHERE id = ?", (num, inv['id']))

        conn.commit()
        print("\nMigration complete.")

    except Exception as e:
        print(f"Error during migration: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    migrate_customer_centric_ids()
