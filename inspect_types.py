
import sqlalchemy
from sqlalchemy import create_engine, text
import sys

# Remote DB URL
DB_URL = os.environ.get("DATABASE_URL") or input("Enter RENDER_DATABASE_URL: ").strip()

def check_types():
    try:
        engine = create_engine(DB_URL)
        with engine.connect() as connection:
            print("Connected to remote DB.\n")
            
            print("Checking 'quotations' column types...")
            result = connection.execute(text("""
                SELECT column_name, data_type
                FROM information_schema.columns 
                WHERE table_name = 'quotations' AND column_name = 'customer_id';
            """))
            for r in result.fetchall():
                print(f" - {r[0]}: {r[1]}")

            print("\nChecking 'customers' column types...")
            result = connection.execute(text("""
                SELECT column_name, data_type
                FROM information_schema.columns 
                WHERE table_name = 'customers' AND column_name = 'identification_number';
            """))
            for r in result.fetchall():
                print(f" - {r[0]}: {r[1]}")

    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    check_types()
