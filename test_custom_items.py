import urllib.request
import urllib.parse
import sqlite3

BASE_URL = 'http://localhost:5002'

def test_custom_item_entry():
    # We need a customer ID first
    conn = sqlite3.connect('instance/database.db')
    cursor = conn.cursor()
    cursor.execute("SELECT identification_number FROM customers LIMIT 1")
    customer_id = cursor.fetchone()[0]
    conn.close()

    print(f"--- Testing Direct Custom Item Entry for Customer: {customer_id} ---")
    
    # Simulate the form data sent by the improved UI
    data = urllib.parse.urlencode({
        'customer_identification': customer_id,
        'item_id[]': ['custom'], # JS sets this to 'custom'
        'item_search[]': ['Direct Typed Item'], 
        'quantity[]': ['3'],
        'unit_price[]': ['150.0'],
        'custom_item_name[]': ['Direct Typed Item'], # JS sets this to the typed value
        'notes': 'Test UI improvement'
    }, doseq=True).encode()
    
    req = urllib.request.Request(f"{BASE_URL}/quotations/add", data=data)
    try:
        with urllib.request.urlopen(req) as f:
            print(f"POST /quotations/add: {f.getcode()}")
    except Exception as e:
        print(f"Error: {e}")

    # Check DB
    conn = sqlite3.connect('instance/database.db')
    cursor = conn.cursor()
    cursor.execute("""
        SELECT qi.description, qi.quantity, qi.unit_price 
        FROM quotation_items qi 
        JOIN quotations q ON qi.quotation_id = q.id 
        WHERE q.notes = 'Test UI improvement'
    """)
    rows = cursor.fetchall()
    for row in rows:
        print(f"Saved Item: {row}")
    conn.close()

if __name__ == "__main__":
    test_custom_item_entry()
