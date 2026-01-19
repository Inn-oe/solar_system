from sqlalchemy import create_engine, text

# Initialize database connection
engine = create_engine('sqlite:///instance/application.db') # Assuming default SQLite path based on schema.sql/models.py usually found in standard Flask apps, or just 'sqlite:///test.db' if that's what's used.
# Let's check main.py or database.py for the actual DB URI. 
# Looking at file list, there is 'test.db' and 'instance/'.
# Usually Flask-SQLAlchemy uses instance/something.db.
# Let's try to load the config from database.py if possible, or just try both common paths.

import os
if os.path.exists('instance/application.sqlite'):
    db_path = 'sqlite:///instance/application.sqlite'
elif os.path.exists('test.db'):
    db_path = 'sqlite:///test.db'
elif os.path.exists('instance/test.db'):
    db_path = 'sqlite:///instance/test.db'
else:
    # Fallback to looking at database.py or assuming a default
    # Let's read database.py momentarily? No, let's just use the one from main.py's context if we can import it.
    pass

# Better approach: Import engine from database.py
import sys
import os
sys.path.append(os.getcwd())
try:
    from database import engine
    with engine.connect() as conn:
        print(f"Connected to {engine.url}")
        
        # Check if column exists
        try:
            result = conn.execute(text("PRAGMA table_info(invoices)"))
            columns = [row[1] for row in result.fetchall()]
            if 'quotation_id' in columns:
                print("Column 'quotation_id' already exists.")
            else:
                print("Column 'quotation_id' missing. Adding it...")
                conn.execute(text("ALTER TABLE invoices ADD COLUMN quotation_id INTEGER REFERENCES quotations(id)"))
                conn.commit()
                print("Successfully added 'quotation_id' column.")

            if 'paid_amount' in columns:
                print("Column 'paid_amount' already exists.")
            else:
                print("Column 'paid_amount' missing. Adding it...")
                conn.execute(text("ALTER TABLE invoices ADD COLUMN paid_amount FLOAT DEFAULT 0.0"))
                conn.commit()
                print("Successfully added 'paid_amount' column.")

            if 'balance_due' in columns:
                print("Column 'balance_due' already exists.")
            else:
                # If balance_due is new, we might want to default it to total_amount if possible, but for now 0.0 or let the app logic handle it if it updates. 
                # Actually, if we add it, existing rows might have inconsistency (balance=0 but total!=0).
                # We can update it after adding.
                print("Column 'balance_due' missing. Adding it...")
                conn.execute(text("ALTER TABLE invoices ADD COLUMN balance_due FLOAT DEFAULT 0.0"))
                conn.commit()
                # Attempt to update balance_due = total_amount for existing records if it was just added
                conn.execute(text("UPDATE invoices SET balance_due = total_amount WHERE balance_due = 0 AND total_amount > 0"))
                conn.commit()
                print("Successfully added 'balance_due' column and updated defaults.")
                
            try:
                result = conn.execute(text("PRAGMA table_info(invoice_items)"))
                ii_columns = [row[1] for row in result.fetchall()]
                
                if 'item_code' in ii_columns:
                    print("Column 'item_code' already exists in 'invoice_items'.")
                else:
                    print("Column 'item_code' missing in 'invoice_items'. Adding it...")
                    conn.execute(text("ALTER TABLE invoice_items ADD COLUMN item_code VARCHAR(50)"))
                    conn.commit()
                    print("Successfully added 'item_code' column to 'invoice_items'.")

                if 'amount' in ii_columns:
                    print("Column 'amount' already exists in 'invoice_items'.")
                else:
                    print("Column 'amount' missing in 'invoice_items'. Adding it...")
                    conn.execute(text("ALTER TABLE invoice_items ADD COLUMN amount FLOAT DEFAULT 0.0"))
                    conn.commit()
                    # Try to populate amount from quantity * unit_price
                    try:
                        conn.execute(text("UPDATE invoice_items SET amount = quantity * unit_price WHERE amount = 0"))
                        conn.commit()
                        print("Updated 'amount' values based on quantity * unit_price")
                    except Exception as e:
                        print(f"Could not update amount values: {e}")
                    print("Successfully added 'amount' column to 'invoice_items'.")

            except Exception as e:
                print(f"Error checking/adding invoice_items columns: {e}")

        except Exception as e:
            print(f"Error checking/adding column: {e}")
            
except Exception as e:
    print(f"Failed to import/connect: {e}")
