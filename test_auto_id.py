import urllib.request
import urllib.parse
import sqlite3

BASE_URL = 'http://localhost:5002'

def test_auto_id():
    print("--- Testing Auto-ID Generation ---")
    data = urllib.parse.urlencode({
        'name': 'Auto Test Customer',
        'identification_number': '', # Leave blank for auto-gen
        'citizenship': 'Testopia',
        'address': '123 Test St',
        'phone': '555-0123',
        'email': 'test@example.com'
    }).encode()
    
    req = urllib.request.Request(f"{BASE_URL}/customers/add", data=data)
    try:
        with urllib.request.urlopen(req) as f:
            print(f"POST /customers/add: {f.getcode()}")
    except urllib.error.HTTPError as e:
        print(f"POST /customers/add: {e.code}")
    except Exception as e:
        print(f"Error: {e}")

    # Check DB
    conn = sqlite3.connect('instance/database.db')
    cursor = conn.cursor()
    cursor.execute("SELECT identification_number FROM customers WHERE name = 'Auto Test Customer' ORDER BY date_created DESC LIMIT 1")
    row = cursor.fetchone()
    if row:
        print(f"Generated ID: {row[0]}")
    conn.close()

if __name__ == "__main__":
    test_auto_id()
