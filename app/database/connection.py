from sqlalchemy import create_engine
from dotenv import load_dotenv
from sqlalchemy.orm import sessionmaker
import os

load_dotenv()

DATABASE_URL = os.getenv('DATABASE_URL')

# pool_pre_ping: a pooled connection that MySQL closed (restart, wait_timeout) is replaced instead of failing
# the next request with "MySQL server has gone away"; pool_recycle stays below MySQL's default 8 h wait_timeout.
engine = create_engine(DATABASE_URL, pool_pre_ping=True, pool_recycle=3600)

SessionLocal = sessionmaker(
    bind=engine,
    autocommit=False,
    autoflush=False
)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()