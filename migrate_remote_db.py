
import sqlalchemy
from sqlalchemy import create_engine, text
import sys

# Remote DB URL
DB_URL = "postgresql://giebee_user:AMGuGARixKT15xI4ZSs5ZV0jxwuhgobY@dpg-d5nlskvgi27c73eof1b0-a.oregon-postgres.render.com/giebee_erp"

def migrate_db():
    try:
        engine = create_engine(DB_URL)
        with engine.connect() as connection:
            print("Connected to remote DB.")
            print("Attempting to add 'surname' column to 'customers' table...")
            
            # Using text() for raw SQL execution and wrapped in a transaction if needed (autocommit=False usually requires explicit commit)
            # SQLAlchemy 2.0+ pattern for schema changes
            connection.execute(text("ALTER TABLE customers ADD COLUMN IF NOT EXISTS surname VARCHAR(100);"))
            connection.commit()
            
            print("Migration successful: Added 'surname' column.")

    except Exception as e:
        print(f"Migration Failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    migrate_db()
