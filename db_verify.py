from sqlalchemy import create_engine, MetaData, Table, select

engine = create_engine('sqlite:///instance/database.db')
metadata = MetaData()

def verify():
    with engine.connect() as conn:
        try:
            customers = Table('customers', metadata, autoload_with=engine)
            suppliers = Table('suppliers', metadata, autoload_with=engine)
            
            print("--- Customers ---")
            s = select(customers).limit(3)
            results = conn.execute(s).fetchall()
            for row in results:
                print(row)
                
            print("--- Suppliers ---")
            s = select(suppliers).limit(3)
            results = conn.execute(s).fetchall()
            for row in results:
                print(row)
        except Exception as e:
            print(f"Error: {e}")

if __name__ == "__main__":
    verify()
