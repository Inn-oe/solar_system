from main import app, db_session
from models import Customer, quotation, Invoice
import os

def test_id_generation():
    with app.app_context():
        # 1. Create a test customer if not exists
        cust_id = "TEST999"
        customer = db_session.query(Customer).get(cust_id)
        if not customer:
            customer = Customer(
                identification_number=cust_id,
                name="TEST",
                surname="USER"
            )
            db_session.add(customer)
            db_session.commit()
            print(f"Created Test Customer: {cust_id}")
        
        # Helper to generate number (simulating route logic)
        from main import generate_document_number
        
        # 2. Test Quotation 1
        q1_num = generate_document_number(customer, quotation)
        print(f"Quotation 1 Expected: TE{cust_id}, Got: {q1_num}")
        
        q1 = quotation(customer_id=cust_id, total_amount=100, quotation_number=q1_num)
        db_session.add(q1)
        db_session.commit()
        
        # 3. Test Quotation 2
        q2_num = generate_document_number(customer, quotation)
        print(f"Quotation 2 Expected: TE{cust_id}1, Got: {q2_num}")
        
        q2 = quotation(customer_id=cust_id, total_amount=200, quotation_number=q2_num)
        db_session.add(q2)
        db_session.commit()
        
        # 4. Cleanup
        db_session.delete(q1)
        db_session.delete(q2)
        # db_session.delete(customer) # Keep customer for manual check if needed
        db_session.commit()
        print("Test Cleanup Done.")

if __name__ == "__main__":
    test_id_generation()
