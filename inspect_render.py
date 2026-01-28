from sqlalchemy import create_engine, text
import os

url = os.environ.get("DATABASE_URL") or input("Enter RENDER_DATABASE_URL: ").strip()
engine = create_engine(url)

def inspect_db():
    print("Inspecting Render Database...")
    with engine.connect() as conn:
        # Get all tables
        result = conn.execute(text("SELECT table_name FROM information_schema.tables WHERE table_schema='public'"))
        tables = [row[0] for row in result.fetchall()]
        
        print(f"{'Table Name':<25} | {'Row Count':<10}")
        print("-" * 40)
        for table in tables:
            try:
                count = conn.execute(text(f"SELECT count(*) FROM {table}")).scalar()
                print(f"{table:<25} | {count}")
            except Exception as e:
                print(f"{table:<25} | Error: {e}")

        # Check Invoices structure
        print("\nColumns in 'invoices' table:")
        res = conn.execute(text("SELECT column_name, data_type FROM information_schema.columns WHERE table_name='invoices'"))
        for col in res.fetchall():
            print(f" - {col[0]} ({col[1]})")

if __name__ == "__main__":
    inspect_db()
