from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, ForeignKey, Boolean, Enum
from sqlalchemy.orm import relationship
from database import Base
import enum
from datetime import datetime

class PaymentType(enum.Enum):
    CASH = "CASH"
    ECOCASH = "ECOCASH"
    SWIPE = "SWIPE"
    TRANSFER = "TRANSFER"
    CREDIT = "CREDIT"

class Currency(enum.Enum):
    USD = "USD"
    ZWL = "ZWL"
    RAND = "RAND"

class StockChangeReason(enum.Enum):
    SOLD_TO_CUSTOMER = "SOLD_TO_CUSTOMER"
    INSTALLED_TO_CLIENT = "INSTALLED_TO_CLIENT"
    DAMAGED = "DAMAGED"
    RETURNED = "RETURNED"
    ADJUSTMENT = "ADJUSTMENT"

class ExpenseCategory(enum.Enum):
    FUEL = "Fuel"
    CAR_MAINTENANCE = "Car Maintenance"
    RENT = "Rent"
    SOLAR_MAINTENANCE = "Solar Maintenance"
    SERVICES = "Services"
    EMPLOYEE_PAYMENTS = "Employee Payments"
    UTILITIES = "Utilities"
    EQUIPMENT = "Equipment Purchase"
    OTHER = "Other Expenses"

class ActivityStatusEnum(enum.Enum):
    SCHEDULED = "SCHEDULED"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"

class quotationstatus(enum.Enum):
    PENDING = "PENDING"
    PAID = "PAID"
    OVERDUE = "OVERDUE"
    CANCELLED = "CANCELLED"

class InvoiceStatus(enum.Enum):
    DRAFT = "DRAFT"
    SENT = "SENT"
    PARTIAL = "PARTIAL"
    PAID = "PAID"
    OVERDUE = "OVERDUE"
    CANCELLED = "CANCELLED"

class TransactionType(enum.Enum):
    STOCK_IN = "STOCK_IN"
    STOCK_OUT = "STOCK_OUT"
    ADJUSTMENT = "ADJUSTMENT"

class FinancialType(enum.Enum):
    INCOME = "INCOME"
    EXPENSE = "EXPENSE"

class JourneyStatus(enum.Enum):
    PLANNED = "PLANNED"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"

class FuelType(enum.Enum):
    PETROL = "PETROL"
    DIESEL = "DIESEL"
    LPG = "LPG"
    ELECTRIC = "ELECTRIC"

class VehicleType(enum.Enum):
    CAR = "CAR"
    TRUCK = "TRUCK"
    VAN = "VAN"
    MOTORCYCLE = "MOTORCYCLE"

class LocationCategory(enum.Enum):
    CUSTOMER = "CUSTOMER"
    SUPPLIER = "SUPPLIER"
    SERVICE = "SERVICE"
    OFFICE = "OFFICE"
    OTHER = "OTHER"

class Supplier(Base):
    __tablename__ = 'suppliers'
    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False)
    contact_person = Column(String(100))
    phone = Column(String(20))
    email = Column(String(100))
    address = Column(String(200))
    payment_terms = Column(String(50))
    currency = Column(Enum(Currency), default=Currency.USD)
    notes = Column(String(500))
    date_created = Column(DateTime, default=datetime.utcnow)

class Customer(Base):
    __tablename__ = 'customers'
    identification_number = Column(String(50), primary_key=True)
    name = Column(String(100), nullable=False)
    surname = Column(String(100))
    citizenship = Column(String(50))
    address = Column(String(200))
    phone = Column(String(20))
    email = Column(String(100))
    date_created = Column(DateTime, default=datetime.utcnow)

class Inventory(Base):
    __tablename__ = 'inventory'
    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False)
    brand = Column(String(50))
    category = Column(String(50))
    specifications = Column(String(500))
    quantity = Column(Integer, default=0)
    unit_price = Column(Float, default=0.0)
    cost_price = Column(Float, default=0.0)
    supplier_id = Column(Integer, ForeignKey('suppliers.id'))
    supplier = relationship('Supplier')
    minimum_stock_level = Column(Integer, default=5)
    notes = Column(String(500))
    date_created = Column(DateTime, default=datetime.utcnow)
    date_updated = Column(DateTime, onupdate=datetime.utcnow)

class ActivityType(Base):
    __tablename__ = 'activity_types'
    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False)
    description = Column(String(500))
    is_active = Column(Boolean, default=True)
    date_created = Column(DateTime, default=datetime.utcnow)

class Activity(Base):
    __tablename__ = 'activities'
    id = Column(Integer, primary_key=True)
    customer_id = Column(String(50), ForeignKey('customers.identification_number'))
    customer = relationship('Customer')
    activity_type_id = Column(Integer, ForeignKey('activity_types.id'))
    activity_type = relationship('ActivityType')
    description = Column(String(500))
    status = Column(Enum(ActivityStatusEnum), default=ActivityStatusEnum.SCHEDULED)
    date = Column(DateTime, default=datetime.utcnow)
    completed_date = Column(DateTime)
    technician = Column(String(100))
    equipment_used = Column(String(200))
    labor_hours = Column(Float)
    labor_cost = Column(Float)
    material_cost = Column(Float)
    total_cost = Column(Float)
    currency = Column(Enum(Currency), default=Currency.USD)
    notes = Column(String(500))
    date_created = Column(DateTime, default=datetime.utcnow)

class quotation(Base):
    __tablename__ = 'quotations'
    id = Column(Integer, primary_key=True)
    customer_id = Column(String(50), ForeignKey('customers.identification_number'))
    customer = relationship('Customer')
    total_amount = Column(Float, nullable=False)
    tax_amount = Column(Float, default=0.0)
    discount_amount = Column(Float, default=0.0)
    status = Column(String(50), default='PENDING')
    due_date = Column(DateTime)
    paid_date = Column(DateTime)
    notes = Column(String(500))
    date_created = Column(DateTime, default=datetime.utcnow)

class quotationItem(Base):
    __tablename__ = 'quotation_items'
    id = Column(Integer, primary_key=True)
    quotation_id = Column(Integer, ForeignKey('quotations.id'))
    quotation = relationship('quotation', backref='items')
    inventory_id = Column(Integer, ForeignKey('inventory.id'))
    inventory = relationship('Inventory')
    quantity = Column(Integer, nullable=False)
    unit_price = Column(Float, nullable=False)
    description = Column(String(200))
    item_code = Column(String(50))  # For custom item codes or inventory reference

class StockTransaction(Base):
    __tablename__ = 'stock_transactions'
    id = Column(Integer, primary_key=True)
    inventory_id = Column(Integer, ForeignKey('inventory.id'))
    inventory = relationship('Inventory')
    transaction_type = Column(Enum(TransactionType), nullable=False)
    quantity = Column(Integer, nullable=False)
    unit_price = Column(Float)
    total_value = Column(Float)
    currency = Column(Enum(Currency), default=Currency.USD)
    reason = Column(Enum(StockChangeReason))
    reference_id = Column(Integer)
    reference_type = Column(String(50))
    customer_name = Column(String(100))
    notes = Column(String(500))
    created_by = Column(String(100))
    date_created = Column(DateTime, default=datetime.utcnow)

class FinancialRecord(Base):
    __tablename__ = 'financial_records'
    id = Column(Integer, primary_key=True)
    type = Column(Enum(FinancialType), nullable=False)
    category = Column(String(100))
    description = Column(String(500))
    amount = Column(Float, nullable=False)
    date = Column(DateTime, default=datetime.utcnow)
    receipt_number = Column(String(50))
    vendor_supplier = Column(String(100))
    reference_id = Column(Integer)
    notes = Column(String(500))
    date_created = Column(DateTime, default=datetime.utcnow)

class FinancialCategory(Base):
    __tablename__ = 'financial_categories'
    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False)
    type = Column(Enum(FinancialType), nullable=False)
    description = Column(String(500))
    is_active = Column(Boolean, default=True)
    date_created = Column(DateTime, default=datetime.utcnow)

class CustomField(Base):
    __tablename__ = 'custom_fields'
    id = Column(Integer, primary_key=True)
    entity_type = Column(String(50), nullable=False)
    entity_id = Column(Integer, nullable=False)
    field_name = Column(String(100), nullable=False)
    field_value = Column(String(500))
    field_type = Column(String(50), default='text')
    date_created = Column(DateTime, default=datetime.utcnow)

class FuelRecord(Base):
    __tablename__ = 'fuel_records'
    id = Column(Integer, primary_key=True)
    journey_id = Column(Integer, ForeignKey('journey_records.id'))
    journey = relationship('JourneyRecord')
    vehicle_id = Column(String(50))
    fuel_type = Column(Enum(FuelType))
    quantity_liters = Column(Float)
    price_per_liter = Column(Float)
    total_cost = Column(Float)
    fuel_station = Column(String(100))
    date = Column(DateTime, default=datetime.utcnow)
    notes = Column(String(500))
    date_created = Column(DateTime, default=datetime.utcnow)

class MileageRecord(Base):
    __tablename__ = 'mileage_records'
    id = Column(Integer, primary_key=True)
    journey_id = Column(Integer, ForeignKey('journey_records.id'))
    journey = relationship('JourneyRecord')
    vehicle_id = Column(String(50))
    start_location = Column(String(100))
    end_location = Column(String(100))
    distance_km = Column(Float)
    start_odometer = Column(Float)
    end_odometer = Column(Float)
    date = Column(DateTime, default=datetime.utcnow)
    notes = Column(String(500))
    date_created = Column(DateTime, default=datetime.utcnow)

class JourneyRecord(Base):
    __tablename__ = 'journey_records'
    id = Column(Integer, primary_key=True)
    activity_id = Column(Integer, ForeignKey('activities.id'))
    activity = relationship('Activity')
    vehicle_id = Column(String(50))
    driver = Column(String(100))
    start_location = Column(String(100))
    end_location = Column(String(100))
    start_time = Column(DateTime, default=datetime.utcnow)
    end_time = Column(DateTime)
    purpose = Column(String(200))
    status = Column(String(20), default="PLANNED")
    total_distance = Column(Float, default=0.0)
    total_fuel_cost = Column(Float, default=0.0)
    notes = Column(String(500))
    date_created = Column(DateTime, default=datetime.utcnow)

class Location(Base):
    __tablename__ = 'locations'
    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False)
    address = Column(String(200))
    latitude = Column(Float)
    longitude = Column(Float)
    category = Column(Enum(LocationCategory), default=LocationCategory.OTHER)
    visit_frequency = Column(Integer, default=0)
    last_visit = Column(DateTime)
    notes = Column(String(500))
    date_created = Column(DateTime, default=datetime.utcnow)

class Pricing(Base):
    __tablename__ = 'pricing'
    id = Column(Integer, primary_key=True)
    item_type = Column(String(50), nullable=False)
    item_name = Column(String(100), nullable=False)
    price = Column(Float, nullable=False)
    unit = Column(String(20))
    effective_date = Column(DateTime, default=datetime.utcnow)
    expiry_date = Column(DateTime)
    notes = Column(String(500))
    date_created = Column(DateTime, default=datetime.utcnow)

class Invoice(Base):
    __tablename__ = 'invoices'
    id = Column(Integer, primary_key=True)
    customer_id = Column(String(50), ForeignKey('customers.identification_number'))
    customer = relationship('Customer')
    activity_type_id = Column(Integer, ForeignKey('activity_types.id'), nullable=True)
    activity_type = relationship('ActivityType')
    quotation_id = Column(Integer, ForeignKey('quotations.id'), nullable=True)
    quotation = relationship('quotation')
    total_amount = Column(Float, nullable=False)
    paid_amount = Column(Float, default=0.0)
    balance_due = Column(Float, nullable=False)
    status = Column(Enum(InvoiceStatus), default=InvoiceStatus.DRAFT)
    due_date = Column(DateTime)
    notes = Column(String(500))
    date_created = Column(DateTime, default=datetime.utcnow)

class InvoiceItem(Base):
    __tablename__ = 'invoice_items'
    id = Column(Integer, primary_key=True)
    invoice_id = Column(Integer, ForeignKey('invoices.id'))
    invoice = relationship('Invoice', backref='items')
    inventory_id = Column(Integer, ForeignKey('inventory.id'), nullable=True)
    inventory = relationship('Inventory')
    item_code = Column(String(50))
    description = Column(String(200))
    quantity = Column(Integer, nullable=False)
    unit_price = Column(Float, nullable=False)
    cost_price = Column(Float, default=0.0)
    amount = Column(Float, nullable=False)

class Payment(Base):
    __tablename__ = 'payments'
    id = Column(Integer, primary_key=True)
    invoice_id = Column(Integer, ForeignKey('invoices.id'))
    invoice = relationship('Invoice', backref='payments')
    amount = Column(Float, nullable=False)
    payment_date = Column(DateTime, default=datetime.utcnow)

    payment_method = Column(Enum(PaymentType), default=PaymentType.CASH)
    payer_name = Column(String(100), nullable=True)  # New field for person who paid
    reference_number = Column(String(100))
    notes = Column(String(500))
    date_created = Column(DateTime, default=datetime.utcnow)
