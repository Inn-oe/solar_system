import os
import sqlite3
import shutil
from datetime import datetime
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from models import Base, Supplier, Customer, Inventory, Activity, quotation, Invoice, quotationItem, InvoiceItem, Payment, StockTransaction, FinancialRecord, ActivityType, FinancialCategory

DB_PATH = 'instance/database.db'
BACKUP_PATH = f'backups/pre_migration_{datetime.now().strftime("%Y%m%d_%H%M%S")}.db'

def migrate():
    if not os.path.exists(DB_PATH):
        print("Database not found. Initializing new database.")
        from database import init_db
        init_db()
        return

    print(f"Backing up database to {BACKUP_PATH}...")
    if not os.path.exists('backups'):
        os.makedirs('backups')
    shutil.copy2(DB_PATH, BACKUP_PATH)

    # 1. Extract data using raw SQLite
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    def get_all(table):
        try:
            cursor.execute(f"SELECT * FROM {table}")
            return [dict(row) for row in cursor.fetchall()]
        except sqlite3.OperationalError:
            return []

    print("Extracting data...")
    old_suppliers = get_all('suppliers')
    old_customers = get_all('customers')
    old_inventory = get_all('inventory')
    old_activities = get_all('activities')
    old_quotations = get_all('quotations')
    old_quotation_items = get_all('quotation_items')
    old_invoices = get_all('invoices')
    old_invoice_items = get_all('invoice_items')
    old_payments = get_all('payments')
    old_stock_transactions = get_all('stock_transactions')
    old_financial_records = get_all('financial_records')
    old_activity_types = get_all('activity_types')
    old_financial_categories = get_all('financial_categories')

    print("Clearing old tables...")
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = [row[0] for row in cursor.fetchall() if not row[0].startswith('sqlite_')]
    for table in tables:
        try:
            cursor.execute(f"DROP TABLE IF EXISTS {table}")
        except sqlite3.OperationalError as e:
            print(f"Warning: Could not drop table {table}: {e}")
    conn.commit()
    conn.close()

    # 2. Create new DB with new schema
    print("Initializing new schema...")
    engine = create_engine(f'sqlite:///{DB_PATH}')
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()

    # 3. Map old IDs to new identification_numbers
    supplier_map = {} # old_id -> identification_number
    customer_map = {} # old_id -> identification_number

    print("Migrating Suppliers...")
    supplier_id_map = {} # old_identification_number -> new_int_id
    for i, s in enumerate(old_suppliers):
        # We need to restore an integer ID. 
        # If the current PK is identification_number (e.g. "SUPP-001"), extract the int.
        # Otherwise, just use a new incrementing ID.
        try:
            old_id_str = s.get('identification_number', '')
            if old_id_str.startswith('SUPP-'):
                new_id = int(old_id_str.split('-')[1])
            else:
                new_id = i + 1
        except:
            new_id = i + 1
            
        new_s = Supplier(
            id=new_id,
            name=s['name'],
            contact_person=s['contact_person'],
            phone=s['phone'],
            email=s['email'],
            address=s['address'],
            payment_terms=s['payment_terms'],
            notes=s['notes'],
            date_created=datetime.fromisoformat(s['date_created']) if isinstance(s['date_created'], str) else s['date_created']
        )
        session.add(new_s)
        supplier_id_map[s.get('identification_number')] = new_id

    print("Migrating Customers...")
    for c in old_customers:
        # Customers keep identification_number as PK. 
        # It might be in 'identification_number' column if it's already the PK.
        id_num = c.get('identification_number')
        new_c = Customer(
            identification_number=id_num,
            name=c['name'],
            citizenship=c['citizenship'],
            address=c['address'],
            phone=c['phone'],
            email=c['email'],
            date_created=datetime.fromisoformat(c['date_created']) if isinstance(c['date_created'], str) else c['date_created']
        )
        session.add(new_c)

    session.flush()

    print("Migrating Activity Types...")
    for at in old_activity_types:
        new_at = ActivityType(
            id=at['id'],
            name=at['name'],
            description=at['description'],
            is_active=bool(at['is_active']),
            date_created=datetime.fromisoformat(at['date_created']) if isinstance(at['date_created'], str) else at['date_created']
        )
        session.add(new_at)

    print("Migrating Inventory...")
    for i in old_inventory:
        # Map supplier_id (string) back to integer ID
        new_supplier_id = supplier_id_map.get(i['supplier_id']) or i['supplier_id']
        new_i = Inventory(
            id=i['id'],
            name=i['name'],
            brand=i['brand'],
            category=i['category'],
            specifications=i['specifications'],
            quantity=i['quantity'],
            unit_price=i['unit_price'],
            supplier_id=new_supplier_id,
            minimum_stock_level=i['minimum_stock_level'],
            notes=i['notes'],
            date_created=datetime.fromisoformat(i['date_created']) if isinstance(i['date_created'], str) else i['date_created']
        )
        session.add(new_i)

    print("Migrating Activities...")
    for a in old_activities:
        new_a = Activity(
            id=a['id'],
            customer_id=customer_map.get(a['customer_id']),
            activity_type_id=a['activity_type_id'],
            description=a['description'],
            date=datetime.fromisoformat(a['date']) if isinstance(a['date'], str) else a['date'],
            technician=a['technician'],
            equipment_used=a['equipment_used'],
            labor_hours=a['labor_hours'],
            labor_cost=a['labor_cost'],
            material_cost=a['material_cost'],
            total_cost=a['total_cost'],
            notes=a['notes'],
            date_created=datetime.fromisoformat(a['date_created']) if isinstance(a['date_created'], str) else a['date_created']
        )
        session.add(new_a)

    print("Migrating Quotations...")
    for q in old_quotations:
        new_q = quotation(
            id=q['id'],
            customer_id=customer_map.get(q['customer_id']),
            total_amount=q['total_amount'],
            tax_amount=q['tax_amount'],
            discount_amount=q['discount_amount'],
            status=q['status'],
            notes=q['notes'],
            date_created=datetime.fromisoformat(q['date_created']) if isinstance(q['date_created'], str) else q['date_created']
        )
        session.add(new_q)

    print("Migrating Quotation Items...")
    for qi in old_quotation_items:
        new_qi = quotationItem(
            id=qi['id'],
            quotation_id=qi['quotation_id'],
            inventory_id=qi['inventory_id'],
            quantity=qi['quantity'],
            unit_price=qi['unit_price'],
            description=qi['description'],
            item_code=qi['item_code']
        )
        session.add(new_qi)

    print("Migrating Invoices...")
    for iv in old_invoices:
        new_iv = Invoice(
            id=iv['id'],
            customer_id=customer_map.get(iv['customer_id']),
            quotation_id=iv['quotation_id'],
            total_amount=iv['total_amount'],
            paid_amount=iv['paid_amount'],
            balance_due=iv['balance_due'],
            status=iv['status'],
            notes=iv['notes'],
            date_created=datetime.fromisoformat(iv['date_created']) if isinstance(iv['date_created'], str) else iv['date_created']
        )
        session.add(new_iv)

    print("Migrating Invoice Items...")
    for ii in old_invoice_items:
        new_ii = InvoiceItem(
            id=ii['id'],
            invoice_id=ii['invoice_id'],
            inventory_id=ii['inventory_id'],
            item_code=ii['item_code'],
            description=ii['description'],
            quantity=ii['quantity'],
            unit_price=ii['unit_price'],
            amount=ii['amount']
        )
        session.add(new_ii)

    print("Migrating Payments...")
    for p in old_payments:
        new_p = Payment(
            id=p['id'],
            invoice_id=p['invoice_id'],
            amount=p['amount'],
            payment_date=datetime.fromisoformat(p['payment_date']) if isinstance(p['payment_date'], str) else p['payment_date'],
            payer_name=p.get('payer_name'),
            reference_number=p['reference_number'],
            notes=p['notes'],
            date_created=datetime.fromisoformat(p['date_created']) if isinstance(p['date_created'], str) else p['date_created']
        )
        session.add(new_p)

    print("Migrating Stock Transactions...")
    for st in old_stock_transactions:
        new_st = StockTransaction(
            id=st['id'],
            inventory_id=st['inventory_id'],
            transaction_type=st['transaction_type'],
            quantity=st['quantity'],
            unit_price=st['unit_price'],
            total_value=st['total_value'],
            customer_name=st['customer_name'],
            notes=st['notes'],
            date_created=datetime.fromisoformat(st['date_created']) if isinstance(st['date_created'], str) else st['date_created']
        )
        session.add(new_st)

    print("Migrating Financial Categories...")
    for fc in old_financial_categories:
        new_fc = FinancialCategory(
            id=fc['id'],
            name=fc['name'],
            type=fc['type'],
            description=fc['description'],
            is_active=bool(fc['is_active']),
            date_created=datetime.fromisoformat(fc['date_created']) if isinstance(fc['date_created'], str) else fc['date_created']
        )
        session.add(new_fc)

    print("Migrating Financial Records...")
    for fr in old_financial_records:
        new_fr = FinancialRecord(
            id=fr['id'],
            type=fr['type'],
            category=fr['category'],
            description=fr['description'],
            amount=fr['amount'],
            date=datetime.fromisoformat(fr['date']) if isinstance(fr['date'], str) else fr['date'],
            receipt_number=fr['receipt_number'],
            vendor_supplier=fr['vendor_supplier'],
            reference_id=fr['reference_id'],
            notes=fr['notes'],
            date_created=datetime.fromisoformat(fr['date_created']) if isinstance(fr['date_created'], str) else fr['date_created']
        )
        session.add(new_fr)

    session.commit()
    session.close()
    print("Migration completed successfully!")

if __name__ == "__main__":
    migrate()
