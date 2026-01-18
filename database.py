import os
from sqlalchemy import create_engine
from sqlalchemy.orm import scoped_session, sessionmaker
from sqlalchemy.ext.declarative import declarative_base


# Use DATABASE_URL from environment, default to SQLite for local development
# For PostgreSQL (recommended for deployment), set DATABASE_URL to: postgresql://user:password@host:port/database
# For MySQL, set DATABASE_URL to: mysql+pymysql://user:password@host:port/database
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

# Configure engine with connection pooling for production
engine = create_engine(database_url, pool_pre_ping=True, pool_recycle=300)
db_session = scoped_session(sessionmaker(autocommit=False,
                                         autoflush=False,
                                         bind=engine))
Base = declarative_base()
Base.query = db_session.query_property()

def init_db():
    # import all modules here that might define models so that
    # they will be registered properly on the metadata.  Otherwise
    # you will have to import them first before calling init_db()
    import models
    Base.metadata.create_all(bind=engine)

