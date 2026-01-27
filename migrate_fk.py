
import sqlalchemy
from sqlalchemy import create_engine, text
import sys

# Remote DB URL
DB_URL = "postgresql://giebee_user:AMGuGARixKT15xI4ZSs5ZV0jxwuhgobY@dpg-d5nlskvgi27c73eof1b0-a.oregon-postgres.render.com/giebee_erp"

def migrate_fk():
    try:
        engine = create_engine(DB_URL)
        with engine.connect() as connection:
            print("Connected to remote DB.")
            
            # 1. Add temporary column
            print("Adding temporary column 'customer_id_new'...")
            connection.execute(text("ALTER TABLE quotations ADD COLUMN IF NOT EXISTS customer_id_new VARCHAR(50);"))
            connection.commit()
            
            # 2. Migrate data
            print("Migrating data from 'customers' table...")
            # Matches old Integer ID in quotations (customer_id) with customers.id, grabbing the proper identification_number
            connection.execute(text("""
                UPDATE quotations 
                SET customer_id_new = c.identification_number 
                FROM customers c 
                WHERE quotations.customer_id = c.id;
            """))
            connection.commit()
            
            # 2.5 Verify migration
            result = connection.execute(text("SELECT count(*) FROM quotations WHERE customer_id_new IS NULL;"))
            nulls = result.scalar()
            print(f"Rows with NULL new ID: {nulls}")
            
            if nulls > 0:
                print("WARNING: Some records could not be mapped (orphan records). They will have NULL customer.")
            
            # 3. Drop old column
            print("Dropping old 'customer_id' column...")
            connection.execute(text("ALTER TABLE quotations DROP COLUMN customer_id;"))
            connection.commit()
            
            # 4. Rename new column
            print("Renaming 'customer_id_new' to 'customer_id'...")
            connection.execute(text("ALTER TABLE quotations RENAME COLUMN customer_id_new TO customer_id;"))
            connection.commit()
            
            print("Migration successful: Quotations now point to identification_number.")

    except Exception as e:
        print(f"Migration Failed: {e}")
        # Only rollback if we were in a transaction block, but here we commit step by step.
        # Manual intervention might be needed if it fails halfway.
        sys.exit(1)

if __name__ == "__main__":
    migrate_fk()
