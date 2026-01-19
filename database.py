import os
from datetime import datetime
from sqlalchemy import create_engine
from sqlalchemy.orm import scoped_session, sessionmaker
from sqlalchemy.ext.declarative import declarative_base

# Use DATABASE_URL from environment, default to SQLite for local development
database_url = os.environ.get('DATABASE_URL')
if database_url and database_url.startswith("postgres://"):
    database_url = database_url.replace("postgres://", "postgresql://", 1)

database_url = database_url or 'sqlite:///instance/database.db'

# Ensure the directory exists for SQLite database (only for local development)
if database_url.startswith('sqlite:///'):
    db_path = database_url.replace('sqlite:///', '')
    db_dir = os.path.dirname(db_path)
    if db_dir and not os.path.exists(db_dir):
        os.makedirs(db_dir)
    
    # Create an automatic backup of the SQLite database if it exists
    if os.path.exists(db_path):
        import shutil
        backup_dir = os.path.join(os.getcwd(), 'backups')
        if not os.path.exists(backup_dir):
            os.makedirs(backup_dir)
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_path = os.path.join(backup_dir, f"backup_{timestamp}_{os.path.basename(db_path)}")
        try:
            shutil.copy2(db_path, backup_path)
            # Keep only last 5 backups
            backups = sorted([os.path.join(backup_dir, f) for f in os.listdir(backup_dir) if f.startswith('backup_')], key=os.path.getmtime)
            while len(backups) > 5:
                os.remove(backups.pop(0))
            print(f"Database backed up successfully to {backup_path}")
        except Exception as e:
            print(f"Failed to create database backup: {e}")

# Configure engine with connection pooling for production
engine = create_engine(database_url, pool_pre_ping=True, pool_recycle=300)
db_session = scoped_session(sessionmaker(autocommit=False,
                                         autoflush=False,
                                         bind=engine))
Base = declarative_base()
Base.query = db_session.query_property()

def init_db():
    import models
    Base.metadata.create_all(bind=engine)
