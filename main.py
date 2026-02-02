import os
from flask import Flask, render_template, request, jsonify, redirect, url_for, flash, send_file
from datetime import datetime
import io
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image, HRFlowable
from reportlab.lib import colors
from reportlab.lib.units import inch
import sqlalchemy as db

# Import Excel storage and models
from models import (Supplier, Customer, Inventory, Activity, ActivityType, quotation, quotationItem,
                        StockTransaction, FinancialRecord, CustomField, FinancialCategory,
                        FuelRecord, MileageRecord, JourneyRecord, Location, Pricing,
                        StockChangeReason, FinancialType, TransactionType, PaymentType, Currency,
                        Invoice, InvoiceItem, Payment, InvoiceStatus)
from currency_converter import get_exchange_rates
from database import db_session, init_db

from whitenoise import WhiteNoise

# create the app
app = Flask(__name__)
app.wsgi_app = WhiteNoise(app.wsgi_app, root='static/', prefix='static/')

# setup a secret key, required by sessions
app.secret_key = os.environ.get("FLASK_SECRET_KEY") or "solar_company_secret_key"

def generate_document_number(customer, model_class):
    """Generate ID: [Prefix][IdentificationNumber][Suffix if count > 0]"""
    from models import Customer
    prefix = (customer.name[:2].upper() if customer.name else 'XX')
    base_code = f"{prefix}{customer.identification_number}"
    
    # Check current count for this customer to determine sequence
    count = db_session.query(model_class).filter_by(customer_id=customer.identification_number).count()
    if count == 0:
        return base_code
    return f"{base_code}{count}"

def normalize_enums():
    """Normalize enum strings in DB to match SQLAlchemy Enum definitions"""
    # Normalize quotation.status to uppercase values
    try:
        quotations = db_session.query(quotation).all()
        changed = 0
        for inv in quotations:
            if isinstance(inv.status, str):
                val = inv.status.strip()
                upper = val.upper()
                if upper in ("PENDING", "PAID", "OVERDUE", "CANCELLED") and val != upper:
                    inv.status = upper
                    changed += 1
            # Normalize payment_method
            if inv.payment_method and isinstance(inv.payment_method, str):
                val = inv.payment_method.strip().upper()
                if val in ("CASH", "ECOCASH", "SWIPE", "TRANSFER", "CREDIT"):
                    inv.payment_method = val
                    changed += 1
        if changed:
            db_session.commit()
    except Exception:
        db_session.rollback()


    # Normalize Inventory.payment_type
    try:
        inventories = db_session.query(Inventory).all()
        changed = 0
        for inv in inventories:
            if inv.payment_type and isinstance(inv.payment_type, str):
                val = inv.payment_type.strip().upper()
                if val in ("CASH", "ECOCASH", "SWIPE", "TRANSFER", "CREDIT"):
                    inv.payment_type = val
                    changed += 1
        if changed:
            db_session.commit()
    except Exception:
        db_session.rollback()

@app.context_processor
def inject_db_type():
    from database import engine
    try:
        db_url = str(engine.url)
        if 'sqlite' in db_url:
            return dict(db_type='SQLite (Local/Ephemeral)')
        elif 'postgres' in db_url:
            return dict(db_type='PostgreSQL (Persistent)')
    except Exception:
        pass
    return dict(db_type='Unknown Database')

    # Normalize FinancialRecord.payment_method
    try:
        financial_records = db_session.query(FinancialRecord).all()
        changed = 0
        for fr in financial_records:
            if fr.payment_method and isinstance(fr.payment_method, str):
                val = fr.payment_method.strip().upper()
                if val in ("CASH", "ECOCASH", "SWIPE", "TRANSFER", "CREDIT"):
                    fr.payment_method = val
                    changed += 1
        if changed:
            db_session.commit()
    except Exception:
        db_session.rollback()

def to_usd(value, currency, rates):
    return value * rates.get(currency, 1.0)

with app.app_context():
    try:
        print("Attempting to initialize database...")
        init_db()
        print("Database initialized successfully.")
    except Exception as e:
        print(f"Error initializing database: {e}")
        # We might want to re-raise if DB init is critical, but for now let's just log
        # In a real scenario, failure here is bad, but maybe the app can still serve static pages or 500s cleanly.

    try:
        print("Attempting to normalize enums...")
        normalize_enums()
        print("Enums normalized successfully.")
    except Exception as e:
        print(f"Error normalizing enums: {e}")

@app.route('/_health')
def health_check():
    """Health check endpoint for deployment monitoring"""
    try:
        # Simple DB check
        db_session.execute(db.text("SELECT 1"))
        return jsonify({"status": "healthy", "database": "connected"}), 200
    except Exception as e:
        return jsonify({"status": "unhealthy", "database": str(e)}), 500


@app.teardown_appcontext
def shutdown_session(exception=None):
    db_session.remove()

# Routes
@app.route('/')
def index():
    """Dashboard showing overview of activities and key metrics"""
    # Get counts for dashboard
    suppliers_count = db_session.query(Supplier).count()
    customers_count = db_session.query(Customer).count()
    inventory_count = db_session.query(Inventory).count()
    quotations_count = db_session.query(quotation).count()
    activities_count = db_session.query(Activity).count()

    # Location frequency for pie chart
    journey_records = db_session.query(JourneyRecord).all()
    location_counts = {}
    for jr in journey_records:
        location = jr.end_location or jr.start_location
        if location:
            location_counts[location] = location_counts.get(location, 0) + 1
    top_locations = sorted(location_counts.items(), key=lambda x: x[1], reverse=True)[:10]
    location_labels = [loc[0] for loc in top_locations]
    location_data = [loc[1] for loc in top_locations]

    return render_template('dashboard.html',
                         suppliers_count=suppliers_count,
                         customers_count=customers_count,
                         inventory_count=inventory_count,
                         quotations_count=quotations_count,
                         activities_count=activities_count,
                         top_locations=location_labels,
                         location_data=location_data)

@app.route('/suppliers')
def suppliers():
    """List all suppliers"""
    suppliers = db_session.query(Supplier).all()
    return render_template('suppliers.html', suppliers=suppliers)

@app.route('/customers')
def customers():
    """List all customers"""
    customers = db_session.query(Customer).all()
    return render_template('customers.html', customers=customers)

@app.route('/inventory')
def inventory():
    """View inventory with search and filter"""
    search = request.args.get('search', '')
    category = request.args.get('category', '')

    query = db_session.query(Inventory)

    if search:
        query = query.filter(
            db.or_(
                Inventory.name.contains(search),
                Inventory.brand.contains(search),
                Inventory.specifications.contains(search)
            )
        )

    if category:
        query = query.filter(Inventory.category == category)

    items = query.all()
    categories = db_session.query(Inventory.category).distinct().all()
    categories = [cat[0] for cat in categories if cat[0]]
    suppliers = db_session.query(Supplier).all()

    return render_template('inventory.html', items=items, categories=categories, 
                           search=search, selected_category=category, suppliers=suppliers)

@app.route('/quotations')
def quotations():
    """List all quotations"""
    quotations = db_session.query(quotation).order_by(quotation.date_created.desc()).all()
    return render_template('quotations.html', quotations=quotations)

@app.route('/activities')
def activities():
    """List company activities"""
    from models import ActivityType
    activities = db_session.query(Activity).order_by(Activity.date.desc()).all()
    # Also need activity_types for some filtering or modal UI if present
    activity_types = db_session.query(ActivityType).all()
    return render_template('activities.html', activities=activities, types=activity_types)

@app.route('/financial')
def financial():
    """Financial dashboard with Accrual-based Profit Calculation"""
    # Get month and year from query parameters
    selected_month = int(request.args.get('month', datetime.now().month))
    selected_year = int(request.args.get('year', datetime.now().year))

    # Calculate date range
    start_date = datetime(selected_year, selected_month, 1)
    if selected_month == 12:
        end_date = datetime(selected_year + 1, 1, 1)
    else:
        end_date = datetime(selected_year, selected_month + 1, 1)

    from models import FinancialType, InvoiceStatus
    
    # --- 1. KEY METRICS (ACCRUAL BASIS) ---
    # Revenue: Total value of Invoices created in this period (regardless of payment status)
    revenue = db_session.query(db.func.sum(Invoice.total_amount)).filter(
        Invoice.date_created >= start_date,
        Invoice.date_created < end_date,
        Invoice.status != InvoiceStatus.CANCELLED
    ).scalar() or 0

    # Other Income: Non-sales income (e.g., grants, interest)
    other_income = db_session.query(db.func.sum(FinancialRecord.amount)).filter(
        FinancialRecord.type == FinancialType.INCOME,
        FinancialRecord.category != 'Sales', 
        FinancialRecord.date >= start_date,
        FinancialRecord.date < end_date
    ).scalar() or 0

    # Expenses: Operating expenses
    expenses = db_session.query(db.func.sum(FinancialRecord.amount)).filter(
        FinancialRecord.type == FinancialType.EXPENSE,
        FinancialRecord.date >= start_date,
        FinancialRecord.date < end_date
    ).scalar() or 0

    # Total Income = Revenue + Other Income
    total_income = revenue + other_income
    
    # Financial Breakdown Dictionary
    financial_breakdown = {
        'Sales Revenue': revenue,
        'Other Income': other_income,
        'Operating Expenses': -expenses,
        'Total Income': total_income
    }
    
    # --- 2. BREAKDOWNS ---

    # A. Income by Source (Stock vs Services)
    stock_revenue = db_session.query(db.func.sum(InvoiceItem.amount)).join(Invoice).filter(
        Invoice.date_created >= start_date,
        Invoice.date_created < end_date,
        Invoice.status != InvoiceStatus.CANCELLED,
        InvoiceItem.inventory_id.isnot(None)
    ).scalar() or 0
    
    service_revenue = db_session.query(db.func.sum(InvoiceItem.amount)).join(Invoice).filter(
        Invoice.date_created >= start_date,
        Invoice.date_created < end_date,
        Invoice.status != InvoiceStatus.CANCELLED,
        InvoiceItem.inventory_id.is_(None)
    ).scalar() or 0
    
    income_by_source = {
        'Stock Sales': stock_revenue,
        'Services/Labor': service_revenue
    }

    # B. Income by Activity Type
    from models import ActivityType
    income_by_activity = {}
    activity_types = db_session.query(ActivityType).all()
    
    for at in activity_types:
        # Get income for this activity type
        act_rev = db_session.query(db.func.sum(Invoice.total_amount)).filter(
            Invoice.activity_type_id == at.id, 
            Invoice.date_created >= start_date, 
            Invoice.date_created < end_date,
            Invoice.status != InvoiceStatus.CANCELLED
        ).scalar() or 0
        if act_rev > 0:
            income_by_activity[at.name] = act_rev
            
    # General Sales (Uncategorized)
    uncat_rev = db_session.query(db.func.sum(Invoice.total_amount)).filter(
        Invoice.activity_type_id == None, 
        Invoice.date_created >= start_date, 
        Invoice.date_created < end_date,
        Invoice.status != InvoiceStatus.CANCELLED
    ).scalar() or 0
    if uncat_rev > 0:
        income_by_activity['General Sales'] = uncat_rev


    # C. Expense Breakdown
    expense_breakdown = {}
    expense_cats = db_session.query(FinancialRecord.category, db.func.sum(FinancialRecord.amount)).filter(
        FinancialRecord.type == FinancialType.EXPENSE,
        FinancialRecord.date >= start_date,
        FinancialRecord.date < end_date
    ).group_by(FinancialRecord.category).all()
    
    for cat, amount in expense_cats:
        expense_breakdown[cat or 'Uncategorized'] = amount

    # --- 3. TRENDS & LISTS ---
    
    # Recent Transactions
    recent_transactions = db_session.query(FinancialRecord).order_by(FinancialRecord.date.desc()).limit(10).all()

    # Monthly Trend (Revenue vs Expenses)
    months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
    monthly_revenue_data = []
    monthly_expenses_data = []

    for m in range(1, 13):
        m_start = datetime(selected_year, m, 1)
        if m == 12:
            m_end = datetime(selected_year + 1, 1, 1)
        else:
            m_end = datetime(selected_year, m + 1, 1)
            
        # Monthly Revenue (Invoiced)
        m_rev = db_session.query(db.func.sum(Invoice.total_amount)).filter(
            Invoice.date_created >= m_start, Invoice.date_created < m_end,
            Invoice.status != InvoiceStatus.CANCELLED
        ).scalar() or 0
        monthly_revenue_data.append(m_rev)
        
        # Monthly Expenses
        m_exp = db_session.query(db.func.sum(FinancialRecord.amount)).filter(
            FinancialRecord.type == FinancialType.EXPENSE,
            FinancialRecord.date >= m_start,
            FinancialRecord.date < m_end
        ).scalar() or 0
        monthly_expenses_data.append(m_exp)
    
    # Top Selling Items (Revenue)
    top_items = db_session.query(InvoiceItem.description, db.func.sum(InvoiceItem.amount)).join(Invoice).filter(
        Invoice.date_created >= start_date, Invoice.date_created < end_date
    ).group_by(InvoiceItem.description).order_by(db.func.sum(InvoiceItem.amount).desc()).limit(8).all()
    
    item_labels = [i[0] for i in top_items]
    item_data = [i[1] for i in top_items]

    # Location Analytics (unchanged)
    location_counts = {}
    journey_records = db_session.query(JourneyRecord).all() 
    for jr in journey_records:
        loc = jr.end_location or jr.start_location
        if loc:
            location_counts[loc] = location_counts.get(loc, 0) + 1
    top_locs = sorted(location_counts.items(), key=lambda x: x[1], reverse=True)[:5]
    location_labels = [l[0] for l in top_locs]
    location_data = [l[1] for l in top_locs]

    return render_template('financial.html',
                         selected_month=selected_month,
                         selected_year=selected_year,
                         months=months,
                         
                         # KPIs
                         total_sales=revenue,        
                         total_expenses=expenses,
                         total_income=total_income,
                         other_income=other_income,
                         
                         # Breakdowns
                         financial_breakdown=financial_breakdown,
                         income_by_activity=income_by_activity,
                         income_by_source=income_by_source,
                         expense_breakdown=expense_breakdown,
                         
                         # Charts
                         monthly_revenue_data=monthly_revenue_data,
                         monthly_expenses_data=monthly_expenses_data,
                         item_labels=item_labels,
                         item_data=item_data,
                         top_locations=location_labels,
                         location_data=location_data,
                         
                         # Extras
                         recent_transactions=recent_transactions)

@app.route('/fuel_tracking')
def fuel_tracking():
    """Fuel tracking dashboard"""
    fuel_records = db_session.query(FuelRecord).order_by(FuelRecord.date.desc()).all()

    # Calculate totals
    total_fuel_cost = sum(record.total_cost for record in fuel_records) if fuel_records else 0
    total_liters = sum(record.quantity_liters for record in fuel_records) if fuel_records else 0

    return render_template('fuel_tracking.html', fuel_records=fuel_records, total_fuel_cost=total_fuel_cost, total_liters=total_liters)

@app.route('/mileage_tracking')
def mileage_tracking():
    """Mileage tracking dashboard"""
    mileage_records = db_session.query(MileageRecord).order_by(MileageRecord.date.desc()).all()
    total_distance = sum(record.distance_km for record in mileage_records) if mileage_records else 0
    return render_template('mileage_tracking.html', mileage_records=mileage_records, total_distance=total_distance)

@app.route('/journey_tracking')
def journey_tracking():
    """Journey tracking dashboard"""
    journey_records = db_session.query(JourneyRecord).order_by(JourneyRecord.start_time.desc()).all()
    return render_template('journey_tracking.html', journey_records=journey_records)

@app.route('/locations')
def locations():
    """List all locations"""
    locations = db_session.query(Location).all()
    return render_template('locations.html', locations=locations)

@app.route('/pricing')
def pricing():
    """Pricing dashboard"""
    pricing_records = db_session.query(Pricing).all()
    return render_template('pricing.html', pricing_records=pricing_records)

@app.route('/suppliers/add', methods=['GET', 'POST'])
def add_supplier():
    """Add new supplier"""
    if request.method == 'POST':
        from models import Currency
        supplier = Supplier(
            name=request.form['name'],
            contact_person=request.form['contact_person'],
            phone=request.form['phone'],
            email=request.form['email'],
            address=request.form['address'],
            payment_terms=request.form['payment_terms'],
            currency=Currency(request.form['currency']) if request.form['currency'] else Currency.USD
        )
        db_session.add(supplier)
        db_session.commit()
        flash('Supplier added successfully!', 'success')
        return redirect(url_for('suppliers'))
    return render_template('add_supplier.html')

@app.route('/customers/add', methods=['GET', 'POST'])
def add_customer():
    """Add new customer"""
    if request.method == 'POST':
        try:
            id_num = request.form.get('identification_number', '').strip()
            
            if not id_num:
                # Auto-generate 5-digit ID (DB Agnostic)
                all_ids = db_session.query(Customer.identification_number).all()
                max_val = 0
                for (id_str,) in all_ids:
                    if id_str.isdigit():
                        try:
                            val = int(id_str)
                            if val > max_val:
                                max_val = val
                        except ValueError:
                            continue
                
                id_num = f"{max_val + 1:05d}"
            else:
                # Check if ID already exists
                existing = db_session.query(Customer).get(id_num)
                if existing:
                    flash(f'Customer ID {id_num} already exists.', 'error')
                    return redirect(url_for('add_customer'))

            if not request.form.get('name'):
                 flash('Customer Name is required.', 'error')
                 return redirect(url_for('add_customer'))

            customer = Customer(
                name=request.form['name'],
                surname=request.form.get('surname'),
                identification_number=id_num,
                citizenship=request.form.get('citizenship'),
                address=request.form.get('address'),
                phone=request.form.get('phone'),
                email=request.form.get('email')
            )
            db_session.add(customer)
            db_session.commit()
            flash('Customer added successfully!', 'success')
            return redirect(url_for('customers'))
            
        except Exception as e:
            db_session.rollback()
            flash(f'Error adding customer: {str(e)}', 'error')
            return redirect(url_for('add_customer'))

    return render_template('add_customer.html')

@app.route('/inventory/add', methods=['GET', 'POST'])
def add_inventory():
    """Add new inventory item"""
    if request.method == 'POST':
        category = request.form['category']
        if category == 'Other':
            category = request.form.get('new_category', 'Other')

        item = Inventory(
            name=request.form['name'],
            brand=request.form['brand'],
            category=category,
            specifications=request.form['specifications'],
            quantity=int(request.form['quantity']),
            unit_price=float(request.form['unit_price']),
            supplier_id=int(request.form['supplier_id']) if request.form['supplier_id'] else None
        )
        db_session.add(item)
        db_session.commit()

        # Record stock transaction
        from models import TransactionType
        stock_transaction = StockTransaction(
            inventory_id=item.id,
            transaction_type=TransactionType.STOCK_IN,
            quantity=item.quantity,
            unit_price=item.unit_price,
            total_value=item.quantity * item.unit_price,
            notes=f'Initial stock for {item.name}'
        )
        db_session.add(stock_transaction)
        db_session.commit()

        flash('Inventory item added successfully!', 'success')
        return redirect(url_for('inventory'))
    
    # Get distinct categories from existing items
    existing_categories = db_session.query(Inventory.category).distinct().all()
    categories = {c[0] for c in existing_categories if c[0]}
    # Add default categories if they don't exist
    defaults = ["Solar Panel", "Battery", "Inverter", "CCTV", "Geyser", "Alarm System", "Borehole Equipment", "Electrical Appliances"]
    for d in defaults:
        categories.add(d)
    categories = sorted(list(categories))
    
    suppliers = db_session.query(Supplier).all()
    return render_template('add_inventory.html', suppliers=suppliers, categories=categories)

@app.route('/inventory/edit/<int:inventory_id>', methods=['GET', 'POST'])
def edit_inventory(inventory_id):
    """Edit inventory item"""
    item = db_session.query(Inventory).get(inventory_id)
    if not item:
        flash('Inventory item not found!', 'error')
        return redirect(url_for('inventory'))
    
    if request.method == 'POST':
        category = request.form['category']
        if category == 'Other':
            category = request.form.get('new_category', 'Other')

        item.name = request.form['name']
        item.brand = request.form['brand']
        item.category = category
        item.specifications = request.form['specifications']
        item.quantity = int(request.form['quantity'])
        item.unit_price = float(request.form['unit_price'])
        item.supplier_id = int(request.form['supplier_id']) if request.form['supplier_id'] else None
        
        db_session.commit()
        flash('Inventory item updated successfully!', 'success')
        return redirect(url_for('inventory'))
    
    # Get distinct categories from existing items
    existing_categories = db_session.query(Inventory.category).distinct().all()
    categories = {c[0] for c in existing_categories if c[0]}
    # Add default categories if they don't exist
    defaults = ["Solar Panel", "Battery", "Inverter", "CCTV", "Geyser", "Alarm System", "Borehole Equipment", "Electrical Appliances"]
    for d in defaults:
        categories.add(d)
    categories = sorted(list(categories))
    
    suppliers = db_session.query(Supplier).all()
    return render_template('edit_inventory.html', item=item, suppliers=suppliers, categories=categories)

@app.route('/quotations/add', methods=['GET', 'POST'])
def add_quotation():
    """Create new quotation"""
    if request.method == 'POST':
        from models import quotationstatus, TransactionType, Currency, PaymentType

        # Begin transaction
        try:
            # Process and validate quotation items first
            item_ids = request.form.getlist('item_id[]')
            quantities = request.form.getlist('quantity[]')
            unit_prices = request.form.getlist('unit_price[]')
            custom_item_names = request.form.getlist('custom_item_name[]')

            calculated_total = 0
            quotation_items_data = []

            # Validate all items and calculate total
            for i, item_id in enumerate(item_ids):
                if item_id:
                    if item_id == 'custom':
                        # Handle custom item
                        custom_name = custom_item_names[i] if i < len(custom_item_names) else ''
                        if not custom_name:
                            flash('Custom item name is required', 'error')
                            return redirect(url_for('add_quotation'))

                        qty = int(quantities[i])
                        unit_price = float(unit_prices[i])
                        item_total = qty * unit_price
                        calculated_total += item_total

                        quotation_items_data.append({
                            'inventory_id': None,  # No inventory item for custom
                            'custom_name': custom_name,
                            'quantity': qty,
                            'unit_price': unit_price,
                            'item_total': item_total
                        })
                    elif item_id:
                        # Handle regular inventory item
                        inventory_item = db_session.query(Inventory).get(int(item_id))
                        if not inventory_item:
                            flash(f'Item not found', 'error')
                            return redirect(url_for('add_quotation'))

                        qty = int(quantities[i])
                        if inventory_item.quantity < qty:
                            flash(f'Insufficient stock for {inventory_item.name}. Available: {inventory_item.quantity}', 'error')
                            return redirect(url_for('add_quotation'))

                        unit_price = float(unit_prices[i])
                        item_total = qty * unit_price
                        calculated_total += item_total

                        quotation_items_data.append({
                            'inventory_id': int(item_id),
                            'inventory_item': inventory_item,
                            'quantity': qty,
                            'unit_price': unit_price,
                            'item_total': item_total
                        })

            # Find customer by identification number
            customer_identification = request.form['customer_identification']
            customer = db_session.query(Customer).filter_by(identification_number=customer_identification).first()
            if not customer:
                flash(f'Customer with identification number {customer_identification} not found. Please add the customer first.', 'error')
                return redirect(url_for('add_quotation'))


            # Create quotation with calculated total
            new_quotation = quotation(
                customer_id=customer.identification_number,
                total_amount=calculated_total,
                status='PENDING'
            )
            db_session.add(new_quotation)
            db_session.flush()
            
            # Set custom sequence-aware quotation number
            new_quotation.quotation_number = generate_document_number(customer, quotation)

            # Create quotation items (Stock deduction MOVED to Invoice creation)
            for item_data in quotation_items_data:
                if item_data['inventory_id'] is None:
                    # Custom item
                    # Generate Custom Item Code
                    timestamp_code = datetime.now().strftime('%Y%m%d%H%M%S')
                    custom_code = f"CUST-{timestamp_code}"

                    quotation_item = quotationItem(
                        quotation_id=new_quotation.id,
                        inventory_id=None,
                        quantity=item_data['quantity'],
                        unit_price=item_data['unit_price'],
                        description=item_data['custom_name'],
                        item_code=custom_code
                    )
                    db_session.add(quotation_item)
                else:
                    # Regular inventory item
                    quotation_item = quotationItem(
                        quotation_id=new_quotation.id,
                        inventory_id=item_data['inventory_id'],
                        quantity=item_data['quantity'],
                        unit_price=item_data['unit_price'],
                        item_code=item_data['inventory_item'].specifications or "INV-ITM" # Use specs or fallback
                    )
                    db_session.add(quotation_item)

                    # NOTE: Stock is NOT deducted here anymore. It will be deducted when converting to Invoice.


            # Commit all changes
            db_session.commit()
            flash('quotation created successfully!', 'success')
            return redirect(url_for('quotations'))

        except Exception as e:
            db_session.rollback()
            flash(f'Error creating quotation: {str(e)}', 'error')
            return redirect(url_for('add_quotation'))

    customers = db_session.query(Customer).all()
    inventory_items = db_session.query(Inventory).filter(Inventory.quantity > 0).all()
    return render_template('add_quotation.html', customers=customers, inventory_items=inventory_items)

@app.route('/quotations/edit/<int:quotation_id>', methods=['GET', 'POST'])
def edit_quotation(quotation_id):
    """Edit existing quotation"""
    quotation_obj = db_session.query(quotation).get(quotation_id)
    if not quotation_obj:
        flash('Quotation not found', 'error')
        return redirect(url_for('quotations'))
    
    # Check if PROCESSED
    if quotation_obj.status == 'PROCESSED':
        flash('Cannot edit a processed quotation', 'warning')
        return redirect(url_for('quotations'))

    if request.method == 'POST':
        try:
            # Process and validate quotation items
            item_ids = request.form.getlist('item_id[]')
            quantities = request.form.getlist('quantity[]')
            unit_prices = request.form.getlist('unit_price[]')
            custom_item_names = request.form.getlist('custom_item_name[]')

            calculated_total = 0
            quotation_items_data = []

            for i, item_id in enumerate(item_ids):
                if item_id:
                    qty = int(quantities[i])
                    unit_price = float(unit_prices[i])
                    item_total = qty * unit_price
                    calculated_total += item_total

                    if item_id == 'custom':
                        custom_name = custom_item_names[i] if i < len(custom_item_names) else ''
                        quotation_items_data.append({
                            'inventory_id': None,
                            'custom_name': custom_name,
                            'quantity': qty,
                            'unit_price': unit_price,
                            'item_total': item_total
                        })
                    else:
                        inventory_item = db_session.query(Inventory).get(int(item_id))
                        quotation_items_data.append({
                            'inventory_id': int(item_id),
                            'inventory_item': inventory_item,
                            'quantity': qty,
                            'unit_price': unit_price,
                            'item_total': item_total
                        })

            # Update customer if changed
            customer_identification = request.form['customer_identification']
            if quotation_obj.customer_id != customer_identification:
                customer = db_session.query(Customer).filter_by(identification_number=customer_identification).first()
                if not customer:
                    flash(f'Customer {customer_identification} not found', 'error')
                    return redirect(url_for('edit_quotation', quotation_id=quotation_id))
                quotation_obj.customer_id = customer_identification

            # Update quotation details
            quotation_obj.total_amount = calculated_total
            quotation_obj.notes = request.form.get('notes')
            
            # Recreate items (cleaner than updating)
            # 1. Remove old items
            db_session.query(quotationItem).filter_by(quotation_id=quotation_id).delete()
            
            # 2. Add new items
            for item_data in quotation_items_data:
                if item_data['inventory_id'] is None:
                    timestamp_code = datetime.now().strftime('%Y%m%d%H%M%S')
                    custom_code = f"CUST-EDT-{timestamp_code}"
                    qi = quotationItem(
                        quotation_id=quotation_obj.id,
                        inventory_id=None,
                        quantity=item_data['quantity'],
                        unit_price=item_data['unit_price'],
                        description=item_data['custom_name'],
                        item_code=custom_code
                    )
                else:
                    qi = quotationItem(
                        quotation_id=quotation_obj.id,
                        inventory_id=item_data['inventory_id'],
                        quantity=item_data['quantity'],
                        unit_price=item_data['unit_price'],
                        item_code=item_data['inventory_item'].specifications or "INV-ITM"
                    )
                db_session.add(qi)

            db_session.commit()
            flash('Quotation updated successfully!', 'success')
            return redirect(url_for('quotations'))

        except Exception as e:
            db_session.rollback()
            flash(f'Error updating quotation: {str(e)}', 'error')
            return redirect(url_for('edit_quotation', quotation_id=quotation_id))

    customers = db_session.query(Customer).all()
    inventory_items = db_session.query(Inventory).filter(Inventory.quantity > 0).all()
    return render_template('edit_quotation.html', quotation=quotation_obj, customers=customers, inventory_items=inventory_items)

@app.route('/activities/add', methods=['GET', 'POST'])
def add_activity():
    """Add new activity"""
    if request.method == 'POST':
        try:
            from models import ActivityStatusEnum, Currency
            activity = Activity(
                customer_id=request.form['customer_id'],
                activity_type_id=int(request.form['activity_type_id']),
                description=request.form['description'],
                status=ActivityStatusEnum(request.form['status']),
                date=datetime.strptime(request.form['date'], '%Y-%m-%d').date(),
                currency=Currency.USD
            )
            db_session.add(activity)
            db_session.commit()
            flash('Activity added successfully!', 'success')
            return redirect(url_for('activities'))
        except Exception as e:
            db_session.rollback()
            flash(f'Error adding activity: {str(e)}', 'error')
            return redirect(url_for('add_activity'))

    customers = db_session.query(Customer).all()
    activity_types = db_session.query(ActivityType).filter_by(is_active=True).all()
    return render_template('add_activity.html', customers=customers, activity_types=activity_types)

@app.route('/activity_types')
def activity_types():
    """List all activity types"""
    activity_types = db_session.query(ActivityType).all()
    return render_template('activity_types.html', types=activity_types)

@app.route('/activity_types/add', methods=['GET', 'POST'])
def add_activity_type():
    """Add new activity type"""
    if request.method == 'POST':
        activity_type = ActivityType(
            name=request.form['name'],
            description=request.form['description'],
            is_active=True
        )
        db_session.add(activity_type)
        db_session.commit()
        flash('Activity type added successfully!', 'success')
        return redirect(url_for('activity_types'))
    return render_template('add_activity_type.html')

@app.route('/activities/edit/<int:activity_id>', methods=['GET', 'POST'])
def edit_activity(activity_id):
    """Edit activity"""
    activity = db_session.query(Activity).get(activity_id)
    if not activity:
        flash('Activity not found!', 'error')
        return redirect(url_for('activities'))

    if request.method == 'POST':
        try:
            from models import ActivityStatusEnum, Currency
            activity.customer_id = request.form['customer_id']
            activity.activity_type_id = int(request.form['activity_type_id'])
            activity.description = request.form['description']
            activity.status = ActivityStatusEnum(request.form['status'])
            activity.date = datetime.strptime(request.form['date'], '%Y-%m-%d').date()
            
            # Optional fields
            activity.technician = request.form.get('technician')
            if request.form.get('total_cost'):
                activity.total_cost = float(request.form['total_cost'])
            if request.form.get('currency'):
                activity.currency = Currency(request.form['currency'])
            activity.notes = request.form.get('notes')

            db_session.commit()
            flash('Activity updated successfully!', 'success')
            return redirect(url_for('activities'))
        except Exception as e:
            db_session.rollback()
            flash(f'Error updating activity: {str(e)}', 'error')
            return redirect(url_for('edit_activity', activity_id=activity_id))

    customers = db_session.query(Customer).all()
    activity_types = db_session.query(ActivityType).filter_by(is_active=True).all()
    return render_template('edit_activity.html', activity=activity, customers=customers, activity_types=activity_types)

@app.route('/financial/add', methods=['GET', 'POST'])
def add_financial_record():
    """Add financial record"""
    if request.method == 'POST':
        from models import FinancialType
        record = FinancialRecord(
            type=FinancialType(request.form['type']),
            category=request.form['category'],
            description=request.form['description'],
            amount=float(request.form['amount']),
            date=datetime.strptime(request.form['date'], '%Y-%m-%d').date()
        )
        db_session.add(record)
        db_session.commit()
        flash('Financial record added successfully!', 'success')
        return redirect(url_for('financial'))
    return render_template('add_financial_record.html')

@app.route('/financial/categories')
def financial_categories():
    """Financial categories management"""
    categories = db_session.query(FinancialCategory).all()
    return render_template('financial_categories.html', categories=categories)

@app.route('/financial/categories/add', methods=['GET', 'POST'])
def add_financial_category():
    """Add financial category"""
    if request.method == 'POST':
        category = FinancialCategory(
            name=request.form['name'],
            type=request.form['type'],
            description=request.form['description']
        )
        db_session.add(category)
        db_session.commit()
        flash('Financial category added successfully!', 'success')
        return redirect(url_for('financial_categories'))
    return render_template('add_financial_category.html')

@app.route('/financial/generate_income_statement/<int:month>/<int:year>')
def generate_income_statement(month, year):
    """Generate income statement PDF"""
    from models import FinancialType

    # Calculate date range
    start_date = datetime(year, month, 1)
    if month == 12:
        end_date = datetime(year + 1, 1, 1)
    else:
        end_date = datetime(year, month + 1, 1)

    # Get financial data
    total_sales = db_session.query(db.func.sum(Payment.amount)).filter(
        Payment.payment_date >= start_date,
        Payment.payment_date < end_date
    ).scalar() or 0

    total_expenses = db_session.query(db.func.sum(FinancialRecord.amount)).filter(
        FinancialRecord.type == FinancialType.EXPENSE,
        FinancialRecord.date >= start_date,
        FinancialRecord.date < end_date
    ).scalar() or 0

    total_income = db_session.query(db.func.sum(FinancialRecord.amount)).filter(
        FinancialRecord.type == FinancialType.INCOME,
        FinancialRecord.date >= start_date,
        FinancialRecord.date < end_date
    ).scalar() or 0

    cogs = db_session.query(db.func.sum(StockTransaction.total_value)).filter(
        StockTransaction.transaction_type == 'STOCK_OUT',
        StockTransaction.date_created >= start_date,
        StockTransaction.date_created < end_date
    ).scalar() or 0

    # Create PDF
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter)
    styles = getSampleStyleSheet()

    # Title style
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=16,
        spaceAfter=30,
        alignment=1  # Center alignment
    )

    # Content
    story = []

    # Title
    title = Paragraph(f"Income Statement - {start_date.strftime('%B %Y')}", title_style)
    story.append(title)
    story.append(Spacer(1, 12))

    # Income Statement Data
    data = [
        ['Revenue', '', ''],
        ['Sales', f"${total_sales:,.2f}", ''],
        ['Other Income', f"${total_income:,.2f}", ''],
        ['Total Revenue', f"${total_sales + total_income:,.2f}", ''],
        ['', '', ''],
        ['Cost of Goods Sold', f"${abs(cogs):,.2f}", ''],
        ['Gross Profit', f"${total_sales + total_income - abs(cogs):,.2f}", ''],
        ['', '', ''],
        ['Operating Expenses', f"${total_expenses:,.2f}", ''],
        ['Net Profit', f"${total_sales + total_income - abs(cogs) - total_expenses:,.2f}", '']
    ]

    table = Table(data, colWidths=[200, 100, 100])
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('ALIGN', (1, 0), (-1, -1), 'RIGHT'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
        ('GRID', (0, 0), (-1, -1), 1, colors.black)
    ]))

    story.append(table)

    doc.build(story)
    buffer.seek(0)

    return send_file(
        buffer,
        as_attachment=True,
        download_name=f'income_statement_{month}_{year}.pdf',
        mimetype='application/pdf'
    )

@app.route('/financial/generate_balance_sheet/<int:month>/<int:year>')
def generate_balance_sheet(month, year):
    """Generate balance sheet PDF"""
    from models import FinancialType

    # Calculate date range
    start_date = datetime(year, month, 1)
    if month == 12:
        end_date = datetime(year + 1, 1, 1)
    else:
        end_date = datetime(year, month + 1, 1)

    # Get financial data
    total_assets = db_session.query(db.func.sum(Inventory.unit_price * Inventory.quantity)).scalar() or 0

    total_liabilities = db_session.query(db.func.sum(FinancialRecord.amount)).filter(
        FinancialRecord.type == FinancialType.EXPENSE,
        FinancialRecord.category.in_(['Loan', 'Credit', 'Liability']),
        FinancialRecord.date <= end_date
    ).scalar() or 0

    total_equity = total_assets - total_liabilities

    # Create PDF
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter)
    styles = getSampleStyleSheet()

    # Title style
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=16,
        spaceAfter=30,
        alignment=1  # Center alignment
    )

    # Content
    story = []

    # Title
    title = Paragraph(f"Balance Sheet - {start_date.strftime('%B %Y')}", title_style)
    story.append(title)
    story.append(Spacer(1, 12))

    # Balance Sheet Data
    data = [
        ['Assets', '', ''],
        ['Current Assets', '', ''],
        ['Inventory', f"${total_assets:,.2f}", ''],
        ['Total Assets', f"${total_assets:,.2f}", ''],
        ['', '', ''],
        ['Liabilities & Equity', '', ''],
        ['Current Liabilities', f"${total_liabilities:,.2f}", ''],
        ['Equity', f"${total_equity:,.2f}", ''],
        ['Total Liabilities & Equity', f"${total_liabilities + total_equity:,.2f}", '']
    ]

    table = Table(data, colWidths=[200, 100, 100])
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('ALIGN', (1, 0), (-1, -1), 'RIGHT'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
        ('GRID', (0, 0), (-1, -1), 1, colors.black)
    ]))

    story.append(table)

    doc.build(story)
    buffer.seek(0)

    return send_file(
        buffer,
        as_attachment=True,
        download_name=f'balance_sheet_{month}_{year}.pdf',
        mimetype='application/pdf'
    )

@app.route('/financial/delete/<int:record_id>', methods=['POST'])
def delete_financial_record(record_id):
    """Delete financial record"""
    record = db_session.query(FinancialRecord).get(record_id)
    if record:
        db_session.delete(record)
        db_session.commit()
        flash('Financial record deleted successfully!', 'success')
    else:
        flash('Record not found!', 'error')
    return redirect(url_for('financial'))

@app.route('/inventory/stock_in', methods=['POST'])
def stock_in():
    """Add stock to inventory item"""
    item_id = int(request.form['item_id'])
    item = db_session.query(Inventory).get(item_id)
    if not item:
        flash('Item not found!', 'error')
        return redirect(url_for('inventory'))

    try:
        quantity = int(request.form['quantity'])
        unit_price = float(request.form['unit_price'])
        notes = request.form.get('notes', '')

        # Update inventory quantity
        item.quantity += quantity
        item.cost_price = unit_price  # Update cost price (buying price) from input
        # item.unit_price = unit_price # Do not overwrite selling price with cost

        # Record stock transaction
        from models import TransactionType
        stock_transaction = StockTransaction(
            inventory_id=item.id,
            transaction_type=TransactionType.STOCK_IN,
            quantity=quantity,
            unit_price=unit_price,
            total_value=quantity * unit_price,
            notes=notes
        )
        db_session.add(stock_transaction)
        db_session.commit()

        flash(f'Stock added successfully! New quantity: {item.quantity}', 'success')
    except Exception as e:
        db_session.rollback()
        flash(f'Error adding stock: {str(e)}', 'error')

    return redirect(url_for('inventory'))

@app.route('/inventory/stock_out', methods=['POST'])
def stock_out():
    """Remove stock from inventory item"""
    item_id = int(request.form['item_id'])
    item = db_session.query(Inventory).get(item_id)
    if not item:
        flash('Item not found!', 'error')
        return redirect(url_for('inventory'))

    try:
        quantity = int(request.form['quantity'])
        reason = request.form['reason']
        customer_name = request.form.get('customer_name', '')
        notes = request.form.get('notes', '')

        if item.quantity < quantity:
            flash(f'Insufficient stock! Available: {item.quantity}', 'error')
            return redirect(url_for('inventory'))

        # Update inventory quantity
        item.quantity -= quantity

        # Record stock transaction
        from models import TransactionType, StockChangeReason
        stock_transaction = StockTransaction(
            inventory_id=item.id,
            transaction_type=TransactionType.STOCK_OUT,
            quantity=-quantity,
            unit_price=item.unit_price,
            total_value=-quantity * item.unit_price,
            reason=StockChangeReason(reason),
            customer_name=customer_name,
            notes=notes
        )
        db_session.add(stock_transaction)
        db_session.commit()

        flash(f'Stock removed successfully! New quantity: {item.quantity}', 'success')
    except Exception as e:
        db_session.rollback()
        flash(f'Error removing stock: {str(e)}', 'error')

    return redirect(url_for('inventory'))

@app.route('/fuel_tracking/add', methods=['GET', 'POST'])
def add_fuel_record():
    """Add new fuel record"""
    if request.method == 'POST':
        from models import Currency
        fuel_record = FuelRecord(
            date=datetime.strptime(request.form['date'], '%Y-%m-%d').date(),
            fuel_type=request.form['fuel_type'],
            quantity_liters=float(request.form['quantity']),
            price_per_liter=float(request.form['cost']),
            total_cost=float(request.form['quantity']) * float(request.form['cost']),
            vehicle_id=request.form['vehicle'],
            fuel_station=request.form.get('location', ''),
            notes=request.form.get('notes', '')
        )
        db_session.add(fuel_record)
        
        # Automatically create an expense record in FinancialRecord
        from models import FinancialType, ExpenseCategory
        expense = FinancialRecord(
            type=FinancialType.EXPENSE,
            category="Fuel",
            description=f"Fuel for vehicle {fuel_record.vehicle_id} at {fuel_record.fuel_station}",
            amount=fuel_record.total_cost,
            date=fuel_record.date,
            notes=fuel_record.notes
        )
        db_session.add(expense)

        db_session.commit()
        flash('Fuel record added successfully!', 'success')
        return redirect(url_for('fuel_tracking'))
    return render_template('add_fuel_record.html')

@app.route('/fuel_tracking/delete/<int:fuel_record_id>', methods=['POST'])
def delete_fuel_record(fuel_record_id):
    """Delete fuel record"""
    record = db_session.query(FuelRecord).get(fuel_record_id)
    if record:
        db_session.delete(record)
        db_session.commit()
        flash('Fuel record deleted successfully!', 'success')
    else:
        flash('Fuel record not found!', 'error')
    return redirect(url_for('fuel_tracking'))

@app.route('/mileage_tracking/add', methods=['GET', 'POST'])
def add_mileage_record():
    """Add new mileage record"""
    if request.method == 'POST':
        mileage_record = MileageRecord(
            date=datetime.strptime(request.form['date'], '%Y-%m-%d').date(),
            vehicle_id=request.form['vehicle'],
            start_odometer=float(request.form['start_mileage']),
            end_odometer=float(request.form['end_mileage']),
            distance_km=float(request.form['distance']),
            notes=request.form.get('notes', '')
        )
        db_session.add(mileage_record)
        db_session.commit()
        flash('Mileage record added successfully!', 'success')
        return redirect(url_for('mileage_tracking'))
    return render_template('add_mileage_record.html')

@app.route('/mileage_tracking/delete/<int:mileage_record_id>', methods=['POST'])
def delete_mileage_record(mileage_record_id):
    """Delete mileage record"""
    record = db_session.query(MileageRecord).get(mileage_record_id)
    if record:
        db_session.delete(record)
        db_session.commit()
        flash('Mileage record deleted successfully!', 'success')
    else:
        flash('Mileage record not found!', 'error')
    return redirect(url_for('mileage_tracking'))

@app.route('/journey_tracking/add', methods=['GET', 'POST'])
def add_journey_record():
    """Add new journey record"""
    if request.method == 'POST':
        journey_record = JourneyRecord(
            start_time=datetime.strptime(request.form['start_time'], '%Y-%m-%dT%H:%M'),
            end_time=datetime.strptime(request.form['end_time'], '%Y-%m-%dT%H:%M') if request.form['end_time'] else None,
            start_location=request.form['start_location'],
            end_location=request.form['end_location'],
            total_distance=float(request.form['distance']),
            vehicle_id=request.form['vehicle'],
            driver=request.form['driver'],
            purpose=request.form['purpose'],
            notes=request.form.get('notes', '')
        )
        db_session.add(journey_record)
        db_session.commit()
        flash('Journey record added successfully!', 'success')
        return redirect(url_for('journey_tracking'))
    return render_template('add_journey_record.html')

@app.route('/journey_tracking/delete/<int:journey_record_id>', methods=['POST'])
def delete_journey_record(journey_record_id):
    """Delete journey record and handle dependencies"""
    record = db_session.query(JourneyRecord).get(journey_record_id)
    if not record:
        flash('Journey record not found!', 'error')
        return redirect(url_for('journey_tracking'))

    try:
        # Nullify references in fuel and mileage records
        db_session.query(FuelRecord).filter_by(journey_id=journey_record_id).update({FuelRecord.journey_id: None})
        db_session.query(MileageRecord).filter_by(journey_id=journey_record_id).update({MileageRecord.journey_id: None})
        
        db_session.delete(record)
        db_session.commit()
        flash('Journey record deleted successfully!', 'success')
    except Exception as e:
        db_session.rollback()
        flash(f'Error deleting journey record: {str(e)}', 'error')
        
    return redirect(url_for('journey_tracking'))

@app.route('/locations/add', methods=['GET', 'POST'])
def add_location():
    """Add new location"""
    if request.method == 'POST':
        location = Location(
            name=request.form['name'],
            address=request.form['address'],
            latitude=float(request.form['latitude']) if request.form['latitude'] else None,
            longitude=float(request.form['longitude']) if request.form['longitude'] else None,
            notes=request.form.get('notes', '')
        )
        db_session.add(location)
        db_session.commit()
        flash('Location added successfully!', 'success')
        return redirect(url_for('locations'))
    return render_template('add_location.html')

@app.route('/locations/delete/<int:location_id>', methods=['POST'])
def delete_location(location_id):
    """Delete location"""
    location = db_session.query(Location).get(location_id)
    if location:
        db_session.delete(location)
        db_session.commit()
        flash('Location deleted successfully!', 'success')
    else:
        flash('Location not found!', 'error')
    return redirect(url_for('locations'))

@app.route('/pricing/add', methods=['GET', 'POST'])
def add_pricing():
    """Add new pricing record"""
    if request.method == 'POST':
        from models import Currency
        pricing = Pricing(
            item_type=request.form['item_type'],
            item_name=request.form['item_name'],
            price=float(request.form['price']),
            currency=Currency(request.form['currency']) if request.form.get('currency') else Currency.USD,
            unit=request.form['unit'],
            effective_date=datetime.strptime(request.form['effective_date'], '%Y-%m-%d'),
            expiry_date=datetime.strptime(request.form['expiry_date'], '%Y-%m-%d') if request.form.get('expiry_date') else None,
            notes=request.form.get('notes', '')
        )
        db_session.add(pricing)
        db_session.commit()
        flash('Pricing record added successfully!', 'success')
        return redirect(url_for('pricing'))
    return render_template('add_pricing.html')

@app.route('/pricing/edit/<int:pricing_id>', methods=['GET', 'POST'])
def edit_pricing(pricing_id):
    """Edit existing pricing record"""
    pricing = db_session.query(Pricing).get(pricing_id)
    if not pricing:
        flash('Pricing record not found!', 'error')
        return redirect(url_for('pricing'))
        
    if request.method == 'POST':
        from models import Currency
        pricing.item_type = request.form['item_type']
        pricing.item_name = request.form['item_name']
        pricing.price = float(request.form['price'])
        pricing.currency = Currency(request.form['currency']) if request.form.get('currency') else Currency.USD
        pricing.unit = request.form['unit']
        pricing.effective_date = datetime.strptime(request.form['effective_date'], '%Y-%m-%d')
        pricing.expiry_date = datetime.strptime(request.form['expiry_date'], '%Y-%m-%d') if request.form.get('expiry_date') else None
        pricing.notes = request.form.get('notes', '')
        
        db_session.commit()
        flash('Pricing record updated successfully!', 'success')
        return redirect(url_for('pricing'))
        
    return render_template('edit_pricing.html', record=pricing)

@app.route('/pricing/delete/<int:pricing_id>', methods=['POST'])
def delete_pricing(pricing_id):
    """Delete pricing record"""
    pricing = db_session.query(Pricing).get(pricing_id)
    if pricing:
        db_session.delete(pricing)
        db_session.commit()
        flash('Pricing record deleted successfully!', 'success')
    else:
        flash('Pricing record not found!', 'error')
    return redirect(url_for('pricing'))

@app.route('/customers/edit/<string:customer_id>', methods=['GET', 'POST'])
def edit_customer(customer_id):
    """Edit customer details"""
    customer = db_session.query(Customer).get(customer_id)
    if not customer:
        flash('Customer not found!', 'error')
        return redirect(url_for('customers'))
    
    if request.method == 'POST':
        customer.name = request.form['name']
        customer.surname = request.form['surname']
        customer.citizenship = request.form['citizenship']
        customer.address = request.form['address']
        customer.phone = request.form['phone']
        customer.email = request.form['email']
        
        db_session.commit()
        flash('Customer updated successfully!', 'success')
        return redirect(url_for('customers'))
    
    return render_template('edit_customer.html', customer=customer)

@app.route('/customers/delete/<string:customer_id>', methods=['POST'])
def delete_customer(customer_id):
    """Delete customer and handle dependencies"""
    customer = db_session.query(Customer).get(customer_id)
    if not customer:
        flash('Customer not found!', 'error')
        return redirect(url_for('customers'))

    try:
        # Nullify customer references in other tables
        db_session.query(Activity).filter_by(customer_id=customer_id).update({Activity.customer_id: None})
        db_session.query(quotation).filter_by(customer_id=customer_id).update({quotation.customer_id: None})
        db_session.query(Invoice).filter_by(customer_id=customer_id).update({Invoice.customer_id: None})
        
        db_session.delete(customer)
        db_session.commit()
        flash('Customer deleted successfully!', 'success')
    except Exception as e:
        db_session.rollback()
        flash(f'Error deleting customer: {str(e)}', 'error')
        
    return redirect(url_for('customers'))

@app.route('/suppliers/edit/<int:supplier_id>', methods=['GET', 'POST'])
def edit_supplier(supplier_id):
    """Edit supplier details"""
    supplier = db_session.query(Supplier).get(supplier_id)
    if not supplier:
        flash('Supplier not found!', 'error')
        return redirect(url_for('suppliers'))
    
    if request.method == 'POST':
        from models import Currency
        supplier.name = request.form['name']
        supplier.contact_person = request.form['contact_person']
        supplier.phone = request.form['phone']
        supplier.email = request.form['email']
        supplier.address = request.form['address']
        supplier.payment_terms = request.form['payment_terms']
        supplier.currency = Currency(request.form['currency']) if request.form['currency'] else Currency.USD
        
        db_session.commit()
        flash('Supplier updated successfully!', 'success')
        return redirect(url_for('suppliers'))
    
    return render_template('edit_supplier.html', supplier=supplier)

@app.route('/suppliers/delete/<int:supplier_id>', methods=['POST'])
def delete_supplier(supplier_id):
    """Delete supplier and handle dependencies"""
    supplier = db_session.query(Supplier).get(supplier_id)
    if not supplier:
        flash('Supplier not found!', 'error')
        return redirect(url_for('suppliers'))

    try:
        # Nullify references in inventory items
        db_session.query(Inventory).filter_by(supplier_id=supplier_id).update({Inventory.supplier_id: None})
        
        db_session.delete(supplier)
        db_session.commit()
        flash('Supplier deleted successfully!', 'success')
    except Exception as e:
        db_session.rollback()
        flash(f'Error deleting supplier: {str(e)}', 'error')
        
    return redirect(url_for('suppliers'))

@app.route('/inventory/delete/<int:inventory_id>', methods=['POST'])
def delete_inventory(inventory_id):
    """Delete inventory item and handle dependencies"""
    item = db_session.query(Inventory).get(inventory_id)
    if not item:
        flash('Inventory item not found!', 'error')
        return redirect(url_for('inventory'))

    try:
        # 1. Delete associated stock transactions
        db_session.query(StockTransaction).filter_by(inventory_id=inventory_id).delete()
        
        # 2. Nullify references in quotation items (they keep their description/quantity)
        quotation_items = db_session.query(quotationItem).filter_by(inventory_id=inventory_id).all()
        for q_item in quotation_items:
            q_item.inventory_id = None
            
        # 3. Nullify references in invoice items
        invoice_items = db_session.query(InvoiceItem).filter_by(inventory_id=inventory_id).all()
        for i_item in invoice_items:
            i_item.inventory_id = None

        # 4. Delete the item itself
        db_session.delete(item)
        db_session.commit()
        flash('Inventory item and related transactions deleted successfully!', 'success')
    except Exception as e:
        db_session.rollback()
        flash(f'Error deleting inventory item: {str(e)}', 'error')
        
    return redirect(url_for('inventory'))

@app.route('/quotations/delete/<int:quotation_id>', methods=['POST'])
def delete_quotation(quotation_id):
    """Delete quotation and handle dependencies"""
    quotation_obj = db_session.query(quotation).get(quotation_id)
    if not quotation_obj:
        flash('Quotation not found!', 'error')
        return redirect(url_for('quotations'))

    try:
        # 1. Nullify references in invoices
        db_session.query(Invoice).filter_by(quotation_id=quotation_id).update({Invoice.quotation_id: None})
        
        # 2. Delete associated quotation items
        db_session.query(quotationItem).filter_by(quotation_id=quotation_id).delete()
        
        # 3. Delete the quotation itself
        db_session.delete(quotation_obj)
        db_session.commit()
        flash('Quotation deleted successfully!', 'success')
    except Exception as e:
        db_session.rollback()
        flash(f'Error deleting quotation: {str(e)}', 'error')
        
    return redirect(url_for('quotations'))

@app.route('/invoices/delete/<int:invoice_id>', methods=['POST'])
def delete_invoice(invoice_id):
    """Delete invoice and restore stock"""
    invoice = db_session.query(Invoice).get(invoice_id)
    if not invoice:
        flash('Invoice not found!', 'error')
        return redirect(url_for('invoices'))

    try:
        # Restore inventory quantities
        for item in invoice.items:
            if item.inventory_id and item.inventory:
                # Add stock back
                item.inventory.quantity += item.quantity
                
                # Record stock transaction for return
                from models import StockChangeReason, TransactionType
                stock_transaction = StockTransaction(
                    inventory_id=item.inventory_id,
                    transaction_type=TransactionType.STOCK_IN,
                    quantity=item.quantity,
                    unit_price=item.unit_price,
                    total_value=item.quantity * item.unit_price,
                    reason=StockChangeReason.RETURNED, 
                    reference_id=invoice.id,
                    reference_type='invoice_deletion',
                    notes=f'Restored from deleted Invoice #{invoice.id}'
                )
                db_session.add(stock_transaction)

        # Delete associated payments (cascade manually if needed, but relationship cascade might handle rows, logic should handle stats)
        # SQLAlchemy relationship cascade options could handle this, but explicit is safe.
        for payment in invoice.payments:
             db_session.delete(payment)
        
        # Delete invoice items (cascade usually handles this, but explicit loop needed for stock above)
        for item in invoice.items:
             db_session.delete(item)

        db_session.delete(invoice)
        db_session.commit()
        flash('Invoice deleted successfully and stock restored!', 'success')

    except Exception as e:
        db_session.rollback()
        flash(f'Error deleting invoice: {str(e)}', 'error')

    return redirect(url_for('invoices'))

@app.route('/payments/delete/<int:payment_id>', methods=['POST'])
def delete_payment(payment_id):
    """Delete payment and update invoice balance"""
    payment = db_session.query(Payment).get(payment_id)
    if not payment:
        flash('Payment not found!', 'error')
        return redirect(url_for('payments'))

    try:
        invoice = payment.invoice
        if invoice:
            # Revert invoice stats
            invoice.paid_amount -= payment.amount
            invoice.balance_due += payment.amount
            
            from models import InvoiceStatus
            if invoice.balance_due == invoice.total_amount:
                invoice.status = InvoiceStatus.SENT # Or DRAFT
            elif invoice.balance_due > 0:
                invoice.status = InvoiceStatus.PARTIAL
            else:
                invoice.status = InvoiceStatus.PAID # Should not happen if we are adding balance

        db_session.delete(payment)
        db_session.commit()
        flash('Payment deleted successfully!', 'success')
    
    except Exception as e:
        db_session.rollback()
        flash(f'Error deleting payment: {str(e)}', 'error')

    return redirect(url_for('payments'))

@app.route('/activities/delete/<int:activity_id>', methods=['POST'])
def delete_activity(activity_id):
    """Delete activity and handle dependencies"""
    activity = db_session.query(Activity).get(activity_id)
    if not activity:
        flash('Activity not found!', 'error')
        return redirect(url_for('activities'))

    try:
        # Nullify references in journey records
        db_session.query(JourneyRecord).filter_by(activity_id=activity_id).update({JourneyRecord.activity_id: None})
        
        db_session.delete(activity)
        db_session.commit()
        flash('Activity deleted successfully!', 'success')
    except Exception as e:
        db_session.rollback()
        flash(f'Error deleting activity: {str(e)}', 'error')
        
    return redirect(url_for('activities'))

@app.route('/activity_types/delete/<int:type_id>', methods=['POST'])
def delete_activity_type(type_id):
    """Delete activity type and handle dependencies"""
    activity_type = db_session.query(ActivityType).get(type_id)
    if not activity_type:
        flash('Activity type not found!', 'error')
        return redirect(url_for('activity_types'))

    try:
        # Nullify references in activities and invoices
        db_session.query(Activity).filter_by(activity_type_id=type_id).update({Activity.activity_type_id: None})
        db_session.query(Invoice).filter_by(activity_type_id=type_id).update({Invoice.activity_type_id: None})
        
        db_session.delete(activity_type)
        db_session.commit()
        flash('Activity type deleted successfully!', 'success')
    except Exception as e:
        db_session.rollback()
        flash(f'Error deleting activity type: {str(e)}', 'error')
        
    return redirect(url_for('activity_types'))

@app.route('/financial/categories/delete/<int:category_id>', methods=['POST'])
def delete_financial_category(category_id):
    """Delete financial category"""
    category = db_session.query(FinancialCategory).get(category_id)
    if category:
        db_session.delete(category)
        db_session.commit()
        flash('Financial category deleted successfully!', 'success')
    else:
        flash('Financial category not found!', 'error')
    return redirect(url_for('financial_categories'))

@app.route('/quotation/<int:quotation_id>')
def view_quotation(quotation_id):
    """View an quotation as an HTML page"""
    quotation_obj = db_session.query(quotation).get(quotation_id)
    if not quotation_obj:
        from flask import abort
        abort(404)
    quotation_items = db_session.query(quotationItem).filter_by(quotation_id=quotation_id).all()
    
    total_quantity = 0
    for item in quotation_items:
        total_quantity += item.quantity

    return render_template('view_quotation.html', quotation=quotation_obj, quotation_items=quotation_items, total_quantity=total_quantity)

@app.route('/quotation/<int:quotation_id>/pdf')
def generate_quotation_pdf(quotation_id):
    """Generate PDF quotation"""
    quotation_obj = db_session.query(quotation).get(quotation_id)
    if not quotation_obj:
        from flask import abort
        abort(404)
    quotation_items = db_session.query(quotationItem).filter_by(quotation_id=quotation_id).all()

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, topMargin=0.5*inch, bottomMargin=0.5*inch, leftMargin=0.5*inch, rightMargin=0.5*inch)
    styles = getSampleStyleSheet()
    story = []

    # Logo and Header
    logo_path = os.path.join(app.root_path, 'static', 'images', 'logo.png')
    logo = Image(logo_path, width=1.2*inch, height=1.2*inch, kind='proportional')

    company_name_style = ParagraphStyle(
        'company_name_style',
        parent=styles['h1'],
        fontSize=22,
        textColor=colors.red,
        alignment=0,
        leading=26
    )

    contact_info_style = ParagraphStyle(
        'contact_info_style',
        parent=styles['Normal'],
        fontSize=9,
        leading=11
    )

    address_style = ParagraphStyle(
        'address_style',
        parent=styles['Normal'],
        fontSize=9,
        leading=11,
        alignment=2
    )

    header_text = """
    <b>+263 774 040 059</b><br/>
    <b>+263 717 039 984</b><br/>
    <b>giebeeengineering@gmail.com</b>
    """
    address_text = """
    <b>108 Central Avenue</b><br/>
    <b>Room 8, 1st Floor</b><br/>
    <b>Harare, Zimbabwe</b>
    """

    header_table_data = [
        [logo, Paragraph('<b>GieBee Engineering (Pvt) Ltd</b>', company_name_style), ''],
        ['', Paragraph(header_text, contact_info_style), Paragraph(address_text, address_style)]
    ]

    header_table = Table(header_table_data, colWidths=[1.3*inch, 3.5*inch, 2.7*inch])
    header_table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('ALIGN', (0, 0), (0, -1), 'LEFT'),
        ('SPAN', (0, 0), (0, 1)), # Span logo over two rows
        ('SPAN', (1, 0), (2, 0)), # Span company name over two columns
        ('ALIGN', (2, 1), (2, 1), 'RIGHT'),
    ]))

    story.append(header_table)
    story.append(Spacer(1, 0.1*inch))
    story.append(HRFlowable(width="100%", thickness=1.5, color=colors.red))
    story.append(Spacer(1, 0.2*inch))

    # Quotation Title
    quotation_style = ParagraphStyle(
        'quotation_style',
        parent=styles['h2'],
        fontSize=16,
        alignment=0,
        spaceAfter=8
    )
    story.append(Paragraph('Quotation', quotation_style))
    story.append(Paragraph(f'SAL-QTN-2025-{quotation_obj.id:05d}', styles['Normal']))
    story.append(Spacer(1, 0.2*inch))
 
    # Customer Name and Date aligned
    customer_date_style = ParagraphStyle(
        'customer_date_style',
        parent=styles['Normal'],
        fontSize=12,
        alignment=0,  # Left alignment
        spaceAfter=10
    )
    story.append(Paragraph(f"<b>Customer:</b> {quotation_obj.customer.name} {quotation_obj.customer.surname or ''}", customer_date_style))
    story.append(Paragraph(f"<b>Date:</b> {quotation_obj.date_created.strftime('%d-%m-%Y')}", customer_date_style))
    story.append(Spacer(1, 0.2*inch))
 
    # Items Table
    items_data = [['Sr', 'Item Code', 'Description', 'Quantity', 'Price', 'Total Amount']]
    total_quantity = 0
    for i, item in enumerate(quotation_items):
        if item.inventory_id:
            inventory = db_session.query(Inventory).get(item.inventory_id)
            item_name = inventory.name if inventory else "Unknown Item"
            item_code = inventory.specifications or (inventory.brand if inventory else "N/A")
        else:
            item_name = item.description or "Custom Item"
            item_code = item.item_code or "Custom"
        
        quantity = item.quantity
        total_quantity += quantity
        price = item.unit_price
        amount = quantity * price
        
        # Wrap text in Paragraph objects for wrapping
        items_data.append([
            str(i + 1),
            Paragraph(item_code, styles['Normal']),
            Paragraph(item_name, styles['Normal']),
            str(quantity),
            f"${price:,.2f}",
            f"${amount:,.2f}"
        ])

    items_table = Table(items_data, colWidths=[0.4*inch, 1*inch, 3.1*inch, 0.7*inch, 1*inch, 1.3*inch])
    items_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.black),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('ALIGN', (3, 0), (-1, -1), 'RIGHT'),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('TOPPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.whitesmoke),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('LEFTPADDING', (0, 0), (-1, -1), 6),
        ('RIGHTPADDING', (0, 0), (-1, -1), 6),
    ]))
    story.append(items_table)
    story.append(Spacer(1, 0.2*inch))
    # Total
    total_data = [
        ['', '', '', '', '', f"Net Price ${quotation_obj.total_amount:,.2f}"]
    ]
    total_table = Table(total_data, colWidths=[0.4*inch, 1*inch, 3.1*inch, 0.7*inch, 1*inch, 1.3*inch])
    total_table.setStyle(TableStyle([
        ('ALIGN', (5, 0), (5, 0), 'RIGHT'),
        ('FONTNAME', (5, 0), (5, 0), 'Helvetica-Bold'),
    ]))
    story.append(total_table)
    story.append(Spacer(1, 0.4*inch))
 
    # Banking Details
    banking_details_style = ParagraphStyle(
        'banking_details_style',
        parent=styles['Normal'],
        spaceBefore=20,
        fontSize=10
    )
    story.append(Paragraph('<b>Banking Details</b>', banking_details_style))
    banking_info = """
    Giebee Engineering Pvt Ltd<br/>
    Bank Transfer: ZB Bank<br/>
    FCA: 411800483226405<br/>
    Branch: Chisipite<br/>
    """
    story.append(Paragraph(banking_info, styles['Normal']))
 
    doc.build(story)
    buffer.seek(0)
 
    return send_file(buffer, as_attachment=True, download_name=f'quotation_{quotation_obj.id}.pdf', mimetype='application/pdf')

@app.route('/payments/edit/<int:payment_id>', methods=['GET', 'POST'])
def edit_payment(payment_id):
    """Edit existing payment and adjust invoice balance"""
    payment_obj = db_session.query(Payment).get(payment_id)
    if not payment_obj:
        flash('Payment not found', 'error')
        return redirect(url_for('payments'))

    if request.method == 'POST':
        try:
            old_amount = payment_obj.amount
            new_amount = float(request.form['amount'])
            diff = new_amount - old_amount
            
            # Update payment
            payment_obj.amount = new_amount
            payment_obj.payment_method = request.form['payment_method']
            payment_obj.payer_name = request.form['payer_name']
            payment_obj.reference_number = request.form.get('reference')
            payment_obj.notes = request.form.get('notes')
            
            # Adjust invoice balance
            invoice = payment_obj.invoice
            if invoice:
                invoice.balance_due -= diff
                # Status update
                from models import InvoiceStatus
                if invoice.balance_due <= 0:
                    invoice.status = InvoiceStatus.PAID
                elif invoice.balance_due < invoice.total_amount:
                    invoice.status = InvoiceStatus.PARTIAL
                else:
                    invoice.status = InvoiceStatus.SENT # Or whatever default

            db_session.commit()
            flash('Payment updated successfully!', 'success')
            return redirect(url_for('payments'))

        except Exception as e:
            db_session.rollback()
            flash(f'Error updating payment: {str(e)}', 'error')
            return redirect(url_for('edit_payment', payment_id=payment_id))

    return render_template('edit_payment.html', payment=payment_obj)

@app.route('/invoices')
def invoices():
    """List all invoices"""
    invoices = db_session.query(Invoice).order_by(Invoice.date_created.desc()).all()
    return render_template('invoices.html', invoices=invoices)

@app.route('/invoices/add', methods=['GET', 'POST'])
def add_invoice():
    """Create new invoice"""
    if request.method == 'POST':
        from models import InvoiceStatus, TransactionType, Currency, PaymentType

        try:
            # Process and validate invoice items
            item_ids = request.form.getlist('item_id[]')
            quantities = request.form.getlist('quantity[]')
            unit_prices = request.form.getlist('unit_price[]')
            custom_item_names = request.form.getlist('custom_item_name[]')

            calculated_total = 0
            invoice_items_data = []

            for i, item_id in enumerate(item_ids):
                if item_id:
                    if item_id == 'custom':
                        custom_name = custom_item_names[i] if i < len(custom_item_names) else ''
                        if not custom_name:
                            flash('Custom item name is required', 'error')
                            return redirect(url_for('add_invoice'))

                        qty = int(quantities[i])
                        unit_price = float(unit_prices[i])
                        item_total = qty * unit_price
                        calculated_total += item_total

                        # Generate Custom Code
                        timestamp_code = datetime.now().strftime('%Y%m%d%H%M%S')
                        custom_code = f"CUST-{timestamp_code}-{i}"

                        invoice_items_data.append({
                            'inventory_id': None,
                            'custom_name': custom_name,
                            'item_code': custom_code,
                            'quantity': qty,
                            'unit_price': unit_price,
                            'item_total': item_total
                        })
                    else:
                        inventory_item = db_session.query(Inventory).get(int(item_id))
                        if not inventory_item:
                            flash(f'Item not found', 'error')
                            return redirect(url_for('add_invoice'))

                        qty = int(quantities[i])
                        if inventory_item.quantity < qty:
                            flash(f'Insufficient stock for {inventory_item.name}. Available: {inventory_item.quantity}', 'error')
                            return redirect(url_for('add_invoice'))

                        unit_price = float(unit_prices[i])
                        item_total = qty * unit_price
                        calculated_total += item_total

                        invoice_items_data.append({
                            'inventory_id': int(item_id),
                            'inventory_item': inventory_item,
                            'item_code': inventory_item.specifications or "INV-ITM",
                            'quantity': qty,
                            'unit_price': unit_price,
                            'cost_price': inventory_item.cost_price,
                            'item_total': item_total
                        })

            customer_identification = request.form['customer_identification']
            customer = db_session.query(Customer).filter_by(identification_number=customer_identification).first()
            if not customer:
                flash(f'Customer not found', 'error')
                return redirect(url_for('add_invoice'))

            activity_type_id = request.form.get('activity_type_id')
            if activity_type_id == '':
                activity_type_id = None
            else:
                activity_type_id = int(activity_type_id)

            invoice = Invoice(
                customer_id=customer.identification_number,
                activity_type_id=activity_type_id,
                total_amount=calculated_total,
                balance_due=calculated_total,
                status=InvoiceStatus.DRAFT,
                due_date=datetime.now() # Default immediate
            )
            db_session.add(invoice)
            db_session.flush()
            
            # Set custom sequence-aware invoice number
            invoice.invoice_number = generate_document_number(customer, Invoice)

            for item_data in invoice_items_data:
                inv_item = InvoiceItem(
                    invoice_id=invoice.id,
                    inventory_id=item_data['inventory_id'],
                    item_code=item_data['item_code'],
                    description=item_data.get('custom_name') or item_data['inventory_item'].name,
                    quantity=item_data['quantity'],
                    unit_price=item_data['unit_price'],
                    cost_price=item_data.get('cost_price', 0.0),
                    amount=item_data['item_total']
                )
                db_session.add(inv_item)

                if item_data['inventory_id']:
                    # Deduct Stock
                    item_data['inventory_item'].quantity -= item_data['quantity']
                    
                    stock_transaction = StockTransaction(
                        inventory_id=item_data['inventory_id'],
                        transaction_type=TransactionType.STOCK_OUT,
                        quantity=-item_data['quantity'],
                        unit_price=item_data['unit_price'],
                        total_value=-item_data['item_total'],
                        reference_id=invoice.id,
                        reference_type='invoice',
                        customer_name=f"{customer.name} {customer.surname or ''}",
                        notes=f'Sold via Invoice #{invoice.id}'
                    )
                    db_session.add(stock_transaction)

            db_session.commit()
            flash('Invoice created successfully!', 'success')
            return redirect(url_for('invoices'))

        except Exception as e:
            db_session.rollback()
            flash(f'Error creating invoice: {str(e)}', 'error')
            return redirect(url_for('add_invoice'))

    customers = db_session.query(Customer).all()
    inventory_items = db_session.query(Inventory).filter(Inventory.quantity > 0).all()
    activity_types = db_session.query(ActivityType).filter_by(is_active=True).all()
    return render_template('add_invoice.html', 
                         customers=customers, 
                         inventory_items=inventory_items, 
                         activity_types=activity_types)

@app.route('/invoices/edit/<int:invoice_id>', methods=['GET', 'POST'])
def edit_invoice(invoice_id):
    """Edit existing invoice and manage stock"""
    invoice_obj = db_session.query(Invoice).get(invoice_id)
    if not invoice_obj:
        flash('Invoice not found', 'error')
        return redirect(url_for('invoices'))

    if request.method == 'POST':
        from models import TransactionType, StockChangeReason, StockTransaction
        try:
            # 1. Process items
            item_ids = request.form.getlist('item_id[]')
            quantities = request.form.getlist('quantity[]')
            unit_prices = request.form.getlist('unit_price[]')
            custom_item_names = request.form.getlist('custom_item_name[]')

            calculated_total = 0
            invoice_items_data = []

            # 2. Revert OLD stock
            db_items = db_session.query(InvoiceItem).filter_by(invoice_id=invoice_id).all()
            for db_item in db_items:
                if db_item.inventory_id:
                    inv_item = db_session.query(Inventory).get(db_item.inventory_id)
                    if inv_item:
                        inv_item.quantity += db_item.quantity
                        # Add a compensation transaction
                        transaction = StockTransaction(
                            inventory_id=inv_item.id,
                            transaction_type=TransactionType.STOCK_IN,
                            quantity=db_item.quantity,
                            reason=StockChangeReason.RESTOCK,
                            notes=f"Reverting for invoice #{invoice_id} edit",
                            reference_id=invoice_id,
                            reference_type="INVOICE_EDIT_REVERT"
                        )
                        db_session.add(transaction)

            # 3. Process NEW items
            for i, item_id in enumerate(item_ids):
                if item_id:
                    qty = int(quantities[i])
                    unit_price = float(unit_prices[i])
                    item_total = qty * unit_price
                    calculated_total += item_total

                    if item_id == 'custom':
                        custom_name = custom_item_names[i] if i < len(custom_item_names) else ''
                        timestamp_code = datetime.now().strftime('%Y%m%d%H%M%S')
                        custom_code = f"CUST-INV-EDT-{timestamp_code}-{i}"
                        invoice_items_data.append({
                            'inventory_id': None,
                            'custom_name': custom_name,
                            'item_code': custom_code,
                            'quantity': qty,
                            'unit_price': unit_price,
                            'item_total': item_total
                        })
                    else:
                        inv_id = int(item_id)
                        inv_item = db_session.query(Inventory).get(inv_id)
                        if inv_item:
                            inv_item.quantity -= qty
                            transaction = StockTransaction(
                                inventory_id=inv_item.id,
                                transaction_type=TransactionType.STOCK_OUT,
                                quantity=-qty,
                                unit_price=unit_price,
                                total_value=-item_total,
                                reference_id=invoice_id,
                                reference_type="INVOICE_EDIT_DEDUCT",
                                customer_name=f"{invoice_obj.customer.name} {invoice_obj.customer.surname or ''}",
                                notes=f"Updating invoice #{invoice_id}"
                            )
                            db_session.add(transaction)

                            invoice_items_data.append({
                                'inventory_id': inv_id,
                                'inventory_item': inv_item,
                                'item_code': inv_item.specifications or "INV-ITM",
                                'quantity': qty,
                                'unit_price': unit_price,
                                'item_total': item_total
                            })

            # 4. Update Invoice
            activity_type_id = request.form.get('activity_type_id')
            if activity_type_id == '':
                invoice_obj.activity_type_id = None
            else:
                invoice_obj.activity_type_id = int(activity_type_id)
            
            invoice_obj.customer_id = request.form['customer_identification']
            old_total = invoice_obj.total_amount
            new_total = calculated_total
            paid_amount = old_total - invoice_obj.balance_due
            invoice_obj.total_amount = new_total
            invoice_obj.balance_due = max(0.0, new_total - paid_amount)
            
            from models import InvoiceStatus
            if invoice_obj.balance_due <= 0 and paid_amount > 0:
                invoice_obj.status = InvoiceStatus.PAID
            elif invoice_obj.balance_due > 0 and paid_amount > 0:
                invoice_obj.status = InvoiceStatus.PARTIAL
            elif invoice_obj.balance_due == new_total:
                invoice_obj.status = InvoiceStatus.DRAFT

            # 5. Recreate Items
            db_session.query(InvoiceItem).filter_by(invoice_id=invoice_id).delete()
            for item in invoice_items_data:
                new_item = InvoiceItem(
                    invoice_id=invoice_id,
                    inventory_id=item['inventory_id'],
                    item_code=item['item_code'],
                    description=item.get('custom_name') or item['inventory_item'].name,
                    quantity=item['quantity'],
                    unit_price=item['unit_price'],
                    amount=item['item_total']
                )
                db_session.add(new_item)

            db_session.commit()
            flash('Invoice updated successfully!', 'success')
            return redirect(url_for('invoices'))

        except Exception as e:
            db_session.rollback()
            flash(f'Error updating invoice: {str(e)}', 'error')
            return redirect(url_for('edit_invoice', invoice_id=invoice_id))

    customers = db_session.query(Customer).all()
    inventory_items = db_session.query(Inventory).all()
    activity_types = db_session.query(ActivityType).filter_by(is_active=True).all()
    return render_template('edit_invoice.html', invoice=invoice_obj, customers=customers, inventory_items=inventory_items, activity_types=activity_types)

@app.route('/quotations/<int:quotation_id>/convert', methods=['POST'])
def convert_to_invoice(quotation_id):
    """Convert quotation to invoice"""
    try:
        quotation_obj = db_session.query(quotation).get(quotation_id)
        if not quotation_obj:
            flash('Quotation not found', 'error')
            return redirect(url_for('quotations'))

        # Check stock availability first
        for item in quotation_obj.items:
            if item.inventory_id:
                if item.inventory.quantity < item.quantity:
                    flash(f'Insufficient stock for {item.inventory.name} to convert quotation. Available: {item.inventory.quantity}, Required: {item.quantity}', 'error')
                    return redirect(url_for('quotations'))

        invoice = Invoice(
            customer_id=quotation_obj.customer_id,
            quotation_id=quotation_obj.id,
            total_amount=quotation_obj.total_amount,
            balance_due=quotation_obj.total_amount,
            status=InvoiceStatus.DRAFT,
            due_date=datetime.now()
        )
        db_session.add(invoice)
        db_session.flush()
        
        # Inherit the quotation number if possible, or generate new invoice-specific sequence
        # Check if the quotation_number is already used as an invoice_number to avoid unique constraint violation
        if quotation_obj.quotation_number:
            existing = db_session.query(Invoice).filter_by(invoice_number=quotation_obj.quotation_number).first()
            if existing:
                # Invoice number already exists, generate a new one instead
                invoice.invoice_number = generate_document_number(quotation_obj.customer, Invoice)
            else:
                invoice.invoice_number = quotation_obj.quotation_number
        else:
            invoice.invoice_number = generate_document_number(quotation_obj.customer, Invoice)

        for q_item in quotation_obj.items:
            # Generate code if missing (for legacy items)
            code = q_item.item_code
            if not code:
                if q_item.inventory_id:
                    code = q_item.inventory.specifications or "INV-ITM"
                else:
                    code = f"CUST-LEGACY-{q_item.id}"

            inv_item = InvoiceItem(
                invoice_id=invoice.id,
                inventory_id=q_item.inventory_id,
                item_code=code,
                description=q_item.description or (q_item.inventory.name if q_item.inventory else "Item"),
                quantity=q_item.quantity,
                unit_price=q_item.unit_price,
                amount=q_item.quantity * q_item.unit_price
            )
            db_session.add(inv_item)

            if q_item.inventory_id:
                # Deduct Stock
                q_item.inventory.quantity -= q_item.quantity
                
                stock_transaction = StockTransaction(
                    inventory_id=q_item.inventory_id,
                    transaction_type=TransactionType.STOCK_OUT,
                    quantity=-q_item.quantity,
                    unit_price=q_item.unit_price,
                    total_value=-(q_item.quantity * q_item.unit_price),
                    reference_id=invoice.id,
                    reference_type='invoice',
                    customer_name=f"{quotation_obj.customer.name} {quotation_obj.customer.surname or ''}",
                    notes=f'Converted from Quotation #{quotation_obj.id} to Invoice #{invoice.id}'
                )
                db_session.add(stock_transaction)

        quotation_obj.status = 'PROCESSED' # Or some status indicating it's done
        db_session.commit()
        flash(f'Successfully converted Quotation #{quotation_id} to Invoice #{invoice.id}', 'success')
        return redirect(url_for('view_invoice', invoice_id=invoice.id))

    except Exception as e:
        db_session.rollback()
        flash(f'Error converting quotation: {str(e)}', 'error')
        return redirect(url_for('quotations'))

@app.route('/invoice/<int:invoice_id>')
def view_invoice(invoice_id):
    """View an invoice as an HTML page"""
    invoice = db_session.query(Invoice).get(invoice_id)
    if not invoice:
        # Check if we should render 404
        from flask import abort
        abort(404)
    
    invoice_items = invoice.items
    total_quantity = sum(item.quantity for item in invoice_items)

    return render_template('view_invoice.html', invoice=invoice, invoice_items=invoice_items, total_quantity=total_quantity)

@app.route('/invoice/<int:invoice_id>/pdf')
def generate_invoice_pdf(invoice_id):
    """Generate PDF invoice"""
    invoice = db_session.query(Invoice).get(invoice_id)
    if not invoice:
        from flask import abort
        abort(404)
    
    invoice_items = invoice.items

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, topMargin=0.5*inch, bottomMargin=0.5*inch, leftMargin=0.5*inch, rightMargin=0.5*inch)
    styles = getSampleStyleSheet()
    story = []

    # Logo and Header (Same as Quotation)
    logo_path = os.path.join(app.root_path, 'static', 'images', 'logo.png')
    logo = Image(logo_path, width=1.2*inch, height=1.2*inch, kind='proportional')

    company_name_style = ParagraphStyle(
        'company_name_style',
        parent=styles['h1'],
        fontSize=22,
        textColor=colors.red,
        alignment=0,
        leading=26
    )

    contact_info_style = ParagraphStyle(
        'contact_info_style',
        parent=styles['Normal'],
        fontSize=9,
        leading=11
    )

    address_style = ParagraphStyle(
        'address_style',
        parent=styles['Normal'],
        fontSize=9,
        leading=11,
        alignment=2
    )

    header_text = """
    <b>+263 774 040 059</b><br/>
    <b>+263 717 039 984</b><br/>
    <b>giebeeengineering@gmail.com</b>
    """
    address_text = """
    <b>108 Central Avenue</b><br/>
    <b>Room 8, 1st Floor</b><br/>
    <b>Harare, Zimbabwe</b>
    """

    header_table_data = [
        [logo, Paragraph('<b>GieBee Engineering (Pvt) Ltd</b>', company_name_style), ''],
        ['', Paragraph(header_text, contact_info_style), Paragraph(address_text, address_style)]
    ]

    header_table = Table(header_table_data, colWidths=[1.3*inch, 3.5*inch, 2.7*inch])
    header_table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('ALIGN', (0, 0), (0, -1), 'LEFT'),
        ('SPAN', (0, 0), (0, 1)),
        ('SPAN', (1, 0), (2, 0)),
        ('ALIGN', (2, 1), (2, 1), 'RIGHT'),
    ]))

    story.append(header_table)
    story.append(Spacer(1, 0.1*inch))
    story.append(HRFlowable(width="100%", thickness=1.5, color=colors.red))
    story.append(Spacer(1, 0.2*inch))

    # Invoice Title
    title_style = ParagraphStyle(
        'invoice_style',
        parent=styles['h2'],
        fontSize=16,
        alignment=0,
        spaceAfter=8
    )
    story.append(Paragraph('Tax Invoice', title_style))
    story.append(Paragraph(f'INV-{invoice.id:05d}', styles['Normal']))
    story.append(Spacer(1, 0.2*inch))

    # Customer Name and Date
    customer_date_style = ParagraphStyle(
        'customer_date_style',
        parent=styles['Normal'],
        fontSize=12,
        alignment=0,
        spaceAfter=10
    )
    story.append(Paragraph(f"<b>Customer:</b> {invoice.customer.name} {invoice.customer.surname or ''}", customer_date_style))
    story.append(Paragraph(f"<b>Date:</b> {invoice.date_created.strftime('%d-%m-%Y')}", customer_date_style))
    story.append(Paragraph(f"<b>Status:</b> {invoice.status.value}", customer_date_style))
    story.append(Spacer(1, 0.2*inch))

    # Items Table
    items_data = [['Sr', 'Item Code', 'Description', 'Quantity', 'Price', 'Total Amount']]
    
    for i, item in enumerate(invoice_items):
        item_code = item.item_code or "N/A"
        item_text = item.description 
        
        # If description is just the code or empty, try to get inventory name
        if not item_text or item_text == item_code:
            if item.inventory_id:
                inventory = db_session.query(Inventory).get(item.inventory_id)
                if inventory:
                    item_text = inventory.name
        
        items_data.append([
            str(i + 1),
            Paragraph(item_code, styles['Normal']),
            Paragraph(item_text or "N/A", styles['Normal']),
            str(item.quantity),
            f"${item.unit_price:,.2f}",
            f"${item.amount:,.2f}"
        ])

    items_table = Table(items_data, colWidths=[0.4*inch, 1.2*inch, 2.9*inch, 0.7*inch, 1*inch, 1.3*inch])
    items_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.black),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('ALIGN', (3, 0), (-1, -1), 'RIGHT'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('TOPPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.whitesmoke),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('LEFTPADDING', (0, 0), (-1, -1), 6),
        ('RIGHTPADDING', (0, 0), (-1, -1), 6),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
    ]))
    story.append(items_table)
    story.append(Spacer(1, 0.2*inch))

    # Total
    total_data = [
        ['', '', '', '', 'Total:', f"${invoice.total_amount:,.2f}"],
        ['', '', '', '', 'Paid:', f"${invoice.paid_amount:,.2f}"],
        ['', '', '', '', 'Balance:', f"${invoice.balance_due:,.2f}"]
    ]
    total_table = Table(total_data, colWidths=[0.4*inch, 1.2*inch, 2.9*inch, 0.7*inch, 1*inch, 1.3*inch])
    total_table.setStyle(TableStyle([
        ('ALIGN', (4, 0), (-1, -1), 'RIGHT'),
        ('FONTNAME', (4, 0), (-1, -1), 'Helvetica-Bold'),
        ('LINEABOVE', (4, 2), (-1, 2), 1, colors.black), # Line above Balance
    ]))
    story.append(total_table)
    story.append(Spacer(1, 0.4*inch))

    # Banking Details
    banking_details_style = ParagraphStyle(
        'banking_details_style',
        parent=styles['Normal'],
        spaceBefore=20,
        fontSize=10
    )
    story.append(Paragraph('<b>Banking Details</b>', banking_details_style))
    banking_info = """
    Giebee Engineering Pvt Ltd<br/>
    Bank Transfer: ZB Bank<br/>
    FCA: 411800483226405<br/>
    Branch: Chisipite<br/>
    """
    story.append(Paragraph(banking_info, styles['Normal']))

    doc.build(story)
    buffer.seek(0)

    # Sanitize filename
    safe_name = "".join([c for c in f"{invoice.customer.name} {invoice.customer.surname or ''}" if c.isalpha() or c.isdigit() or c==' ']).rstrip().replace(" ", "_")
    filename = f'Invoice_{invoice.id}_{safe_name}.pdf'

    return send_file(buffer, as_attachment=True, download_name=filename, mimetype='application/pdf')


@app.route('/payments')
def payments():
    """List all payments"""
    payments = db_session.query(Payment).order_by(Payment.payment_date.desc()).all()
    return render_template('payments.html', payments=payments)

@app.route('/invoice/<int:invoice_id>/add_payment', methods=['GET', 'POST'])
def add_payment(invoice_id):
    """Add payment to an invoice"""
    invoice = db_session.query(Invoice).get(invoice_id)
    if not invoice:
        flash('Invoice not found', 'error')
        return redirect(url_for('invoices'))

    if request.method == 'POST':

        try:
            amount = float(request.form['amount'])
            payment_method = request.form['payment_method']
            payer_name = request.form.get('payer_name', '')
            reference = request.form.get('reference', '')
            notes = request.form.get('notes', '')

            # Generate Transaction ID
            import random
            import string
            suffix = ''.join(random.choices(string.ascii_uppercase + string.digits, k=4))
            transaction_id = f"TX-{datetime.now().strftime('%Y%m%d')}-{suffix}"

            if amount > invoice.balance_due:
                flash(f'Payment amount (${amount}) cannot exceed balance due (${invoice.balance_due})', 'error')
                return redirect(url_for('add_payment', invoice_id=invoice_id))

            # Create Payment Record
            from models import PaymentType, InvoiceStatus
            payment = Payment(
                invoice_id=invoice.id,
                amount=amount,
                payment_method=PaymentType(payment_method),
                payer_name=payer_name,
                transaction_id=transaction_id,
                reference_number=reference,
                notes=notes,
                payment_date=datetime.now()
            )
            db_session.add(payment)

            # Update Invoice Stats
            invoice.paid_amount += amount
            invoice.balance_due -= amount
            
            if invoice.balance_due <= 0:
                invoice.status = InvoiceStatus.PAID
            else:
                invoice.status = InvoiceStatus.PARTIAL
            
            # Create Financial Record (Income)
            from models import FinancialType
            fin_record = FinancialRecord(
                type=FinancialType.INCOME,
                category="Sales",
                description=f"Payment for Invoice #{invoice.id}",
                amount=amount,
                date=datetime.now(),
                reference_id=invoice.id,
                notes=f"Payer: {payer_name} | Method: {payment_method} | Ref: {reference}"
            )
            db_session.add(fin_record)

            db_session.commit()
            flash('Payment recorded successfully!', 'success')
            return redirect(url_for('view_invoice', invoice_id=invoice.id))

        except Exception as e:
            db_session.rollback()
            flash(f'Error recording payment: {str(e)}', 'error')
            return redirect(url_for('add_payment', invoice_id=invoice_id))

    return render_template('add_payment.html', invoice=invoice)


@app.route('/payment/<int:payment_id>/pdf')
def generate_payment_pdf(payment_id):
    """Generate PDF receipt for payment"""
    payment = db_session.query(Payment).get(payment_id)
    if not payment:
        from flask import abort
        abort(404)
    
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, topMargin=0.5*inch, bottomMargin=0.5*inch, leftMargin=0.5*inch, rightMargin=0.5*inch)
    styles = getSampleStyleSheet()
    story = []

    # Logo and Header (Same as Invoice)
    logo_path = os.path.join(app.root_path, 'static', 'images', 'logo.png')
    logo = Image(logo_path, width=1.2*inch, height=1.2*inch, kind='proportional')

    company_name_style = ParagraphStyle(
        'company_name_style',
        parent=styles['h1'],
        fontSize=22,
        textColor=colors.red,
        alignment=0,
        leading=26
    )

    contact_info_style = ParagraphStyle(
        'contact_info_style',
        parent=styles['Normal'],
        fontSize=9,
        leading=11
    )

    address_style = ParagraphStyle(
        'address_style',
        parent=styles['Normal'],
        fontSize=9,
        leading=11,
        alignment=2
    )

    header_text = """
    <b>+263 774 040 059</b><br/>
    <b>+263 717 039 984</b><br/>
    <b>giebeeengineering@gmail.com</b>
    """
    address_text = """
    <b>108 Central Avenue</b><br/>
    <b>Room 8, 1st Floor</b><br/>
    <b>Harare, Zimbabwe</b>
    """

    header_table_data = [
        [logo, Paragraph('<b>GieBee Engineering (Pvt) Ltd</b>', company_name_style), ''],
        ['', Paragraph(header_text, contact_info_style), Paragraph(address_text, address_style)]
    ]

    header_table = Table(header_table_data, colWidths=[1.3*inch, 3.5*inch, 2.7*inch])
    header_table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('ALIGN', (0, 0), (0, -1), 'LEFT'),
        ('SPAN', (0, 0), (0, 1)),
        ('SPAN', (1, 0), (2, 0)),
        ('ALIGN', (2, 1), (2, 1), 'RIGHT'),
    ]))

    story.append(header_table)
    story.append(Spacer(1, 0.1*inch))
    story.append(HRFlowable(width="100%", thickness=1.5, color=colors.red))
    story.append(Spacer(1, 0.2*inch))

    # Receipt Title
    title_style = ParagraphStyle(
        'receipt_style',
        parent=styles['h2'],
        fontSize=16,
        alignment=0,
        spaceAfter=8
    )
    story.append(Paragraph('Payment Receipt', title_style))
    story.append(Paragraph(f'RCPT-{payment.id:05d}', styles['Normal']))
    story.append(Spacer(1, 0.2*inch))

    # Payment Details
    details_style = ParagraphStyle(
        'details_style',
        parent=styles['Normal'],
        fontSize=12,
        alignment=0,
        spaceAfter=10,
        leading=16
    )
    
    invoice = payment.invoice
    customer = invoice.customer

    story.append(Paragraph(f"<b>Received From:</b> {customer.name} {customer.surname or ''}", details_style))
    story.append(Paragraph(f"<b>Transaction ID:</b> {payment.transaction_id or 'N/A'}", details_style))
    story.append(Paragraph(f"<b>Date:</b> {payment.payment_date.strftime('%d-%m-%Y')}", details_style))
    story.append(Paragraph(f"<b>Payment Method:</b> {payment.payment_method.value}", details_style))
    if payment.reference_number:
        story.append(Paragraph(f"<b>Reference:</b> {payment.reference_number}", details_style))
    
    story.append(Spacer(1, 0.2*inch))
    
    story.append(Paragraph(f"<b>Payment For:</b> Invoice #{invoice.id}", details_style))
    
    if payment.notes:
        story.append(Paragraph(f"<b>Notes:</b> {payment.notes}", details_style))
    
    story.append(Spacer(1, 0.2*inch))

    # Amount Box
    amount_data = [
        ['Amount Received', f"${payment.amount:,.2f}"]
    ]
    amount_table = Table(amount_data, colWidths=[2*inch, 2*inch])
    amount_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.lightgrey),
        ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
        ('ALIGN', (0, 0), (0, 0), 'LEFT'),
        ('ALIGN', (1, 0), (1, 0), 'RIGHT'),
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 14),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 12),
        ('TOPPADDING', (0, 0), (-1, -1), 12),
        ('BOX', (0, 0), (-1, -1), 1, colors.black),
    ]))
    story.append(amount_table)

    story.append(Spacer(1, 0.4*inch))
    story.append(Paragraph("Thank you for your business!", styles['Normal']))

    doc.build(story)
    buffer.seek(0)

    # Sanitize filename
    safe_name = "".join([c for c in f"{customer.name} {customer.surname or ''}" if c.isalpha() or c.isdigit() or c==' ']).rstrip().replace(" ", "_")
    filename = f'Payment_{payment.id}_{safe_name}.pdf'

    return send_file(buffer, as_attachment=True, download_name=filename, mimetype='application/pdf')


# Auto-migration helper
def check_db_schema():
    """Checks for missing columns and adds them if necessary (Simple Migration)"""
    from sqlalchemy import text
    from database import engine
    try:
        # Check for payer_name in payments
        with engine.connect() as conn:
            try:
                conn.execute(text("ALTER TABLE payments ADD COLUMN payer_name VARCHAR(100)"))
                conn.commit()
                print("Added column 'payer_name' to 'payments'")
            except Exception:
                pass
            
            # Check for quotation_id in invoices
            try:
                conn.execute(text("ALTER TABLE invoices ADD COLUMN quotation_id INTEGER REFERENCES quotations(id)"))
                conn.commit()
                print("Added column 'quotation_id' to 'invoices'")
            except Exception:
                pass
    except Exception as e:
        print(f"Schema check warning: {e}")

@app.before_request
def startup_check():
    if not hasattr(app, 'schema_checked'):
        init_db()
        check_db_schema()
        app.schema_checked = True

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5002)
