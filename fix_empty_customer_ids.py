from sqlalchemy import create_engine, MetaData, Table, select, update
import sqlite3

# Using sqlite3 for direct control over ROWID
def fix_ids():
    db_path = 'instance/database.db'
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Get customers with empty or null identification_number
    cursor.execute("SELECT rowid, name FROM customers WHERE identification_number IS NULL OR identification_number = ''")
    empty_customers = cursor.fetchall()
    
    if not empty_customers:
        print("No empty IDs found.")
        conn.close()
        return

    # Find the current max numeric ID to start incrementing
    cursor.execute("SELECT identification_number FROM customers WHERE identification_number GLOB '[0-9]*'")
    numeric_ids = cursor.fetchall()
    
    max_id = 0
    for (id_str,) in numeric_ids:
        try:
            val = int(id_str)
            if val > max_id:
                max_id = val
        except ValueError:
            continue
            
    print(f"Found {len(empty_customers)} customers with empty IDs. Starting from {max_id + 1:05d}")
    
    for rowid, name in empty_customers:
        max_id += 1
        new_id = f"{max_id:05d}"
        print(f"Updating '{name}' (ROWID: {rowid}) with ID: {new_id}")
        cursor.execute("UPDATE customers SET identification_number = ? WHERE rowid = ?", (new_id, rowid))
        
    conn.commit()
    conn.close()
    print("Cleanup complete.")

if __name__ == "__main__":
    fix_ids()
