
import sqlalchemy
from sqlalchemy import create_engine, text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey

import sys
import datetime

# Remote DB URL
DB_URL = os.environ.get("DATABASE_URL") or input("Enter RENDER_DATABASE_URL: ").strip()

# Define minimal models to replicate the crash condition
Base = declarative_base()

class Customer(Base):
    __tablename__ = 'customers'
    identification_number = Column(String(50), primary_key=True)
    name = Column(String(100))
    surname = Column(String(100))

class Quotation(Base):
    __tablename__ = 'quotations'
    id = Column(Integer, primary_key=True)
    customer_id = Column(String(50), ForeignKey('customers.identification_number'))
    customer = relationship('Customer')
    total_amount = Column(Float)
    status = Column(String(50))
    date_created = Column(DateTime)

def debug_data():
    try:
        engine = create_engine(DB_URL)
        Session = sessionmaker(bind=engine)
        session = Session()
        
        print("Connected to remote DB.")
        print("Querying quotations...")
        
        # replicate the view logic
        quotations = session.query(Quotations).order_by(Quotations.date_created.desc()).all()
        print(f"Found {len(quotations)} quotations.")
        
        for q in quotations:
            print(f"Checking Quotation ID: {q.id}")
            print(f" - Customer ID: {q.customer_id}")
            
            if q.customer:
                print(f" - Customer Name: {q.customer.name}")
                print(f" - Customer Surname: {q.customer.surname}")
            else:
                print(" - [WARNING] Customer is NONE/NULL!")
                if q.customer_id:
                     print("   -> Broken Foreign Key! customer_id exists but object not found.")

        print("\nSuccess! No crash during iteration.")

    except Exception as e:
        print(f"\n[CRASH] Error during iteration: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    # Fix class name typo in query if needed, but here used Quotation
    # Renaming class in query to match definition
    global Quotations
    Quotations = Quotation
    debug_data()
