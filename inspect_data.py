
import sqlalchemy
from sqlalchemy import create_engine, text
import sys

# Remote DB URL
DB_URL = os.environ.get("DATABASE_URL") or input("Enter RENDER_DATABASE_URL: ").strip()

def check_data():
    try:
        engine = create_engine(DB_URL)
        with engine.connect() as connection:
            print("Connected to remote DB.\n")
            
            print("--- Quotations Sample ---")
            result = connection.execute(text("SELECT id, customer_id FROM quotations LIMIT 5;"))
            q_rows = result.fetchall()
            for r in q_rows:
                print(f"Quot ID: {r[0]}, Cust ID: {r[1]} (Type: {type(r[1])})")

            print("\n--- Customers Sample ---")
            result = connection.execute(text("SELECT id, identification_number, name FROM customers LIMIT 5;"))
            c_rows = result.fetchall()
            for r in c_rows:
                print(f"Cust ID: {r[0]}, Ident Num: {r[1]}, Name: {r[2]}")
                
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    check_data()
