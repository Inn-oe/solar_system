
import sqlalchemy
from sqlalchemy import create_engine, text
import sys

# Remote DB URL
DB_URL = "postgresql://giebee_user:AMGuGARixKT15xI4ZSs5ZV0jxwuhgobY@dpg-d5nlskvgi27c73eof1b0-a.oregon-postgres.render.com/giebee_erp"

def check_quotation_columns():
    try:
        engine = create_engine(DB_URL)
        with engine.connect() as connection:
            print("Connected to remote DB.\n")
            
            # Check 'quotations'
            print("Checking 'quotations' table...")
            result = connection.execute(text("""
                SELECT column_name
                FROM information_schema.columns 
                WHERE table_name = 'quotations';
            """))
            cols = [r[0] for r in result.fetchall()]
            print(f"Columns: {cols}")
            
            expected_q = ['tax_amount', 'discount_amount', 'notes', 'customer_id']
            for c in expected_q:
                if c not in cols:
                    print(f" [CRITICAL] Missing '{c}' in quotations")
            
            print("\n-------------------\n")

            # Check 'quotation_items'
            print("Checking 'quotation_items' table...")
            result = connection.execute(text("""
                SELECT column_name
                FROM information_schema.columns 
                WHERE table_name = 'quotation_items';
            """))
            cols = [r[0] for r in result.fetchall()]
            print(f"Columns: {cols}")

            expected_qi = ['item_code', 'description']
            for c in expected_qi:
                if c not in cols:
                    print(f" [CRITICAL] Missing '{c}' in quotation_items")

    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    check_quotation_columns()
