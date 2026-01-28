import os
import sys
import sqlalchemy as sa
from sqlalchemy import text

def migrate_remote(database_url):
    print(f"Connecting to remote database...")
    if database_url.startswith("postgres://"):
        database_url = database_url.replace("postgres://", "postgresql://", 1)
    
    engine = sa.create_engine(database_url)
    
    # Define columns to check and add
    # Format: (table_name, column_name, column_type)
    migrations = [
        ('pricing', 'currency', 'VARCHAR(50) DEFAULT \'USD\''),
        ('activities', 'currency', 'VARCHAR(50) DEFAULT \'USD\''),
        ('suppliers', 'currency', 'VARCHAR(50) DEFAULT \'USD\''),
        ('stock_transactions', 'currency', 'VARCHAR(50) DEFAULT \'USD\''),
        ('invoices', 'invoice_number', 'VARCHAR(20) UNIQUE'),
        ('quotations', 'quotation_number', 'VARCHAR(20) UNIQUE'),
        ('customers', 'identification_number', 'VARCHAR(50)'),
        ('payments', 'transaction_id', 'VARCHAR(50) UNIQUE'),
        ('payments', 'payer_name', 'VARCHAR(100)'),
        ('invoice_items', 'cost_price', 'FLOAT DEFAULT 0.0'),
    ]
    
    with engine.connect() as conn:
        for table, column, col_type in migrations:
            print(f"Checking {table}.{column}...")
            # Check if column exists
            check_query = text(f"""
                SELECT count(*) 
                FROM information_schema.columns 
                WHERE table_name='{table}' AND column_name='{column}';
            """)
            result = conn.execute(check_query).scalar()
            
            if result == 0:
                print(f"Adding column {column} to table {table}...")
                try:
                    conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {col_type};"))
                    conn.commit()
                    print(f"Successfully added {column}.")
                except Exception as e:
                    print(f"Failed to add {column}: {e}")
                    conn.rollback()
            else:
                print(f"Column {column} already exists in {table}.")

    print("\nMigration check complete!")

if __name__ == "__main__":
    url = input("Please enter your RENDER_DATABASE_URL: ").strip()
    if not url:
        print("Error: No URL provided.")
        sys.exit(1)
    
    migrate_remote(url)
