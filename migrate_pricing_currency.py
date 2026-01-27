import sqlite3
import os

def migrate_pricing_currency():
    db_path = 'instance/database.db'
    if not os.path.exists(db_path):
        print(f"Database not found at {db_path}")
        return

    print(f"Connecting to database at {db_path}...")
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    try:
        # Check if the column already exists
        cursor.execute("PRAGMA table_info(pricing)")
        columns = [column[1] for column in cursor.fetchall()]
        
        if 'currency' not in columns:
            print("Adding 'currency' column to 'pricing' table...")
            # Adding as TEXT since Enums are stored as strings in SQLite by SQLAlchemy
            cursor.execute("ALTER TABLE pricing ADD COLUMN currency VARCHAR(50) DEFAULT 'USD'")
            print("Column added successfully.")
        else:
            print("Column 'currency' already exists in 'pricing' table.")

        conn.commit()
    except Exception as e:
        print(f"Error during migration: {e}")
        conn.rollback()
    finally:
        conn.close()

if __name__ == "__main__":
    migrate_pricing_currency()
