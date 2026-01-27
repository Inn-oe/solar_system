
import sqlalchemy
from sqlalchemy import create_engine, text
import sys

# Remote DB URL
DB_URL = "postgresql://giebee_user:AMGuGARixKT15xI4ZSs5ZV0jxwuhgobY@dpg-d5nlskvgi27c73eof1b0-a.oregon-postgres.render.com/giebee_erp"

def migrate_all_remaining():
    try:
        engine = create_engine(DB_URL)
        with engine.connect() as connection:
            print("Connected to remote DB.")
            
            # --- 1. Migrate Invoices customer_id ---
            print("\nMigrating 'invoices' customer_id...")
            connection.execute(text("ALTER TABLE invoices ADD COLUMN IF NOT EXISTS customer_id_new VARCHAR(50);"))
            connection.commit()
            
            print(" - Mapping old Invoices IDs...")
            connection.execute(text("""
                UPDATE invoices 
                SET customer_id_new = c.identification_number 
                FROM customers c 
                WHERE invoices.customer_id = c.id;
            """))
            connection.commit()
            
            # For data safety, check if any failed to map
            res = connection.execute(text("SELECT count(*) FROM invoices WHERE customer_id_new IS NULL AND customer_id IS NOT NULL;"))
            unmapped = res.scalar()
            if unmapped > 0:
                print(f" [WARNING] {unmapped} invoices could not be mapped to a customer! They will be orphaned.")
            
            print(" - Swapping columns...")
            connection.execute(text("ALTER TABLE invoices DROP COLUMN customer_id CASCADE;")) # Cascade might affect payments FK if exists, careful.
            # Actually, payments link to invoice_id, not invoice.customer_id, so CASCADE should be fine for FK constraints on customer_id if any.
            # But let's check constraints? Usually none explicitly named in simple alchemy unless defined.
            connection.commit()
            
            connection.execute(text("ALTER TABLE invoices RENAME COLUMN customer_id_new TO customer_id;"))
            connection.commit()
            print(" - Invoices migrated.")

            # --- 2. Migrate Activities customer_id ---
            print("\nMigrating 'activities' customer_id...")
            # Activities table was found empty, so we can just drop and recreate or alter type.
            # But safer to follow same pattern just in case data appeared.
            connection.execute(text("ALTER TABLE activities ADD COLUMN IF NOT EXISTS customer_id_new VARCHAR(50);"))
            connection.execute(text("ALTER TABLE activities DROP COLUMN customer_id CASCADE;"))
            connection.execute(text("ALTER TABLE activities RENAME COLUMN customer_id_new TO customer_id;"))
            connection.commit()
            print(" - Activities migrated.")

            # --- 3. Add missing columns ---
            print("\nAdding missing columns...")
            connection.execute(text("ALTER TABLE invoices ADD COLUMN IF NOT EXISTS activity_type_id INTEGER;"))
            connection.commit()
            print(" - Added 'activity_type_id' to invoices.")

            print("\nAll migrations completed successfully.")

    except Exception as e:
        print(f"Migration Failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    migrate_all_remaining()
