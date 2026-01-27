from main import app, db_session
from models import Customer, quotation, Invoice
import json

def inspect():
    with app.app_context():
        # Check customers
        customers = db_session.query(Customer).limit(5).all()
        cust_data = [{"name": c.name, "sid": c.identification_number} for c in customers]
        
        # Check quotations
        quotations = db_session.query(quotation).order_by(quotation.id.desc()).limit(10).all()
        q_data = [{"id": q.id, "num": getattr(q, 'quotation_number', 'N/A'), "cust": q.customer_id} for q in quotations]
        
        # Check invoices
        invoices = db_session.query(Invoice).order_by(Invoice.id.desc()).limit(10).all()
        i_data = [{"id": i.id, "num": getattr(i, 'invoice_number', 'N/A'), "cust": i.customer_id} for i in invoices]
        
        print("CUSTOMERS:")
        print(json.dumps(cust_data, indent=2))
        print("\nQUOTATIONS:")
        print(json.dumps(q_data, indent=2))
        print("\nINVOICES:")
        print(json.dumps(i_data, indent=2))

if __name__ == "__main__":
    inspect()
