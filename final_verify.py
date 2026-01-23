import urllib.request
import urllib.error
from sqlalchemy import create_engine, MetaData, Table, select

BASE_URL = 'http://localhost:5002'
DB_PATH = 'sqlite:///instance/database.db'

def test_routes():
    print("--- Testing Routes ---")
    routes = [
        '/customers',
        '/suppliers',
        '/suppliers/add',
        '/customers/add'
    ]
    for route in routes:
        try:
            r = urllib.request.urlopen(f"{BASE_URL}{route}")
            print(f"GET {route}: {r.getcode()}")
        except Exception as e:
            print(f"Error GET {route}: {e}")

def verify_data():
    print("\n--- Verifying Database Data ---")
    engine = create_engine(DB_PATH)
    metadata = MetaData()
    with engine.connect() as conn:
        try:
            customers = Table('customers', metadata, autoload_with=engine)
            suppliers = Table('suppliers', metadata, autoload_with=engine)
            
            print("Customer Column Names:", [c.name for c in customers.columns])
            print("Supplier Column Names:", [c.name for c in suppliers.columns])
            
            print("\nSample Customer (should have identification_number):")
            s = select(customers).limit(1)
            row = conn.execute(s).fetchone()
            print(row)
            
            print("\nSample Supplier (should have integer id):")
            s = select(suppliers).limit(1)
            row = conn.execute(s).fetchone()
            print(row)
        except Exception as e:
            print(f"Error: {e}")

if __name__ == "__main__":
    test_routes()
    verify_data()
