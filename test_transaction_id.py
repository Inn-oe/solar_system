from main import app, db_session
from models import Payment, Invoice, Customer
from datetime import datetime
import os

def test_txn_id():
    with app.app_context():
        # Get a test customer and invoice
        customer = db_session.query(Customer).first()
        invoice = db_session.query(Invoice).first()
        
        if not (customer and invoice):
            print("Skipping test: No customer or invoice found.")
            return

        # Simulate add_payment logic
        import random
        import string
        suffix = ''.join(random.choices(string.ascii_uppercase + string.digits, k=4))
        transaction_id = f"TX-{datetime.now().strftime('%Y%m%d')}-{suffix}"
        
        print(f"Generated Test Transaction ID: {transaction_id}")
        
        # Create payment
        from models import PaymentType
        p = Payment(
            invoice_id=invoice.id,
            amount=1.0,
            payment_method=PaymentType.CASH,
            transaction_id=transaction_id,
            payment_date=datetime.now()
        )
        db_session.add(p)
        db_session.commit()
        
        # Verify it was saved
        saved_p = db_session.query(Payment).filter_by(transaction_id=transaction_id).first()
        if saved_p:
            print(f"SUCCESS: Payment saved with Transaction ID: {saved_p.transaction_id}")
        else:
            print("FAILURE: Payment not found.")

if __name__ == "__main__":
    test_txn_id()
