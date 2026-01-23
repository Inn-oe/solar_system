from sqlalchemy import create_engine, text
import os

# Connect to the database
db_path = os.path.join(os.getcwd(), 'instance', 'database.db')
engine = create_engine(f'sqlite:///{db_path}')

with engine.connect() as conn:
    # Add cost_price to inventory
    try:
        conn.execute(text("ALTER TABLE inventory ADD COLUMN cost_price FLOAT DEFAULT 0.0"))
        print("Added cost_price to inventory.")
    except Exception as e:
        print(f"Error adding cost_price to inventory: {e}")

    # Add cost_price to invoice_items
    try:
        conn.execute(text("ALTER TABLE invoice_items ADD COLUMN cost_price FLOAT DEFAULT 0.0"))
        print("Added cost_price to invoice_items.")
    except Exception as e:
        print(f"Error adding cost_price to invoice_items: {e}")

    conn.commit()
    print("Migration completed.")
