from sqlalchemy import create_engine, text

# Initialize database connection
import os
import sys
sys.path.append(os.getcwd())

from database import engine

try:
    with engine.connect() as conn:
        print(f"Connected to {engine.url}")
        
        # Check for invalid statuses in invoices
        try:
            print("Checking for invalid 'PENDING' status in invoices...")
            result = conn.execute(text("SELECT count(*) FROM invoices WHERE status = 'PENDING'"))
            count = result.scalar()
            
            if count > 0:
                print(f"Found {count} invoices with invalid 'PENDING' status. Updating to 'DRAFT'...")
                conn.execute(text("UPDATE invoices SET status = 'DRAFT' WHERE status = 'PENDING'"))
                conn.commit()
                print("Successfully updated invalid statuses.")
            else:
                print("No invoices with 'PENDING' status found.")
                
        except Exception as e:
            print(f"Error updating invoices: {e}")
            
except Exception as e:
    print(f"Failed to connect: {e}")
