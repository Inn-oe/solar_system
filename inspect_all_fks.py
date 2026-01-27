
import sqlalchemy
from sqlalchemy import create_engine, text
import sys

# Remote DB URL
DB_URL = "postgresql://giebee_user:AMGuGARixKT15xI4ZSs5ZV0jxwuhgobY@dpg-d5nlskvgi27c73eof1b0-a.oregon-postgres.render.com/giebee_erp"

def inspect_all():
    try:
        engine = create_engine(DB_URL)
        with engine.connect() as connection:
            print("Connected to remote DB.")
            
            # Tables to check that link to customers
            tables_to_check = ['invoices', 'activities']
            
            for table in tables_to_check:
                print(f"\n--- Checking Table: {table} ---")
                
                # 1. Check Column Type
                result = connection.execute(text(f"""
                    SELECT column_name, data_type 
                    FROM information_schema.columns 
                    WHERE table_name = '{table}' AND column_name = 'customer_id';
                """))
                col_info = result.fetchone()
                
                if not col_info:
                     print(f" [WARNING] 'customer_id' column MISSING in {table}!")
                     continue
                     
                col_name, data_type = col_info
                print(f" Column 'customer_id' type: {data_type}")
                
                if 'int' in data_type.lower():
                    print(f" [CRITICAL] {table}.customer_id is INTEGER. Needs migration to VARCHAR (Identification Number).")
                    
                    # Check for orphan data or data needing migration
                    result = connection.execute(text(f"SELECT count(*) FROM {table}"))
                    count = result.scalar()
                    print(f" Total rows in {table}: {count}")
                    
                    if count > 0:
                        print(f" Data exists! Migration needed.")
                else:
                    print(f" [OK] {table}.customer_id seems to be correct type (String/Varchar).")

            print("\n--- Checking for missing common columns ---")
             # Check for other recently added columns in models that might be missing
            input_checks = [
                ('invoices', 'activity_type_id'),
                ('invoices', 'quotation_id'),
                ('invoices', 'paid_amount'),
            ]
            
            for tbl, col in input_checks:
                res = connection.execute(text(f"""
                    SELECT column_name 
                    FROM information_schema.columns 
                    WHERE table_name = '{tbl}' AND column_name = '{col}';
                """))
                if not res.fetchone():
                    print(f" [CRITICAL] Missing '{col}' in '{tbl}'")
                else:
                    print(f" [OK] '{col}' exists in '{tbl}'")

    except Exception as e:
        print(f"Inspection Failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    inspect_all()
