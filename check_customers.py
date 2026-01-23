import sqlite3

def check_data():
    conn = sqlite3.connect('instance/database.db')
    cursor = conn.cursor()
    
    print("--- Customers ---")
    cursor.execute("SELECT rowid, * FROM customers")
    rows = cursor.fetchall()
    for row in rows:
        print(row)
    
    conn.close()

if __name__ == "__main__":
    check_data()
