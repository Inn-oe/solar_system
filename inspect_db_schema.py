
import sqlalchemy
from sqlalchemy import create_engine, text
import sys

# Remote DB URL
DB_URL = os.environ.get("DATABASE_URL") or input("Enter RENDER_DATABASE_URL: ").strip()

def check_columns():
    try:
        engine = create_engine(DB_URL)
        with engine.connect() as connection:
            print("Connected to remote DB.")
            print("Checking columns for table 'customers'...")
            
            result = connection.execute(text("""
                SELECT column_name, data_type 
                FROM information_schema.columns 
                WHERE table_name = 'customers';
            """))
            
            columns = result.fetchall()
            print(f"Found {len(columns)} columns:")
            for col in columns:
                print(f" - {col[0]} ({col[1]})")
                
            col_names = [c[0] for c in columns]
            if 'surname' not in col_names:
                print("\n[CRITICAL] 'surname' column is MISSING!")
            else:
                print("\n[OK] 'surname' column exists.")

    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    check_columns()
