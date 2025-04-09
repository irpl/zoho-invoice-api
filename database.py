from sqlalchemy import create_engine, Column, String, DateTime
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime, timezone
import os

# Create SQLite database (you can change this to your preferred database)
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./zoho_tokens.db")
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class ZohoToken(Base):
    __tablename__ = "zoho_tokens"

    id = Column(String, primary_key=True, default="zoho_refresh_token")
    refresh_token = Column(String, nullable=False)
    access_token = Column(String)
    access_token_expiry = Column(DateTime)
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def init_db():
    Base.metadata.create_all(bind=engine)

def set_initial_refresh_token(db, refresh_token: str):
    """Set the initial refresh token in the database"""
    token = db.query(ZohoToken).first()
    if token:
        token.refresh_token = refresh_token
    else:
        token = ZohoToken(refresh_token=refresh_token)
        db.add(token)
    db.commit()
    return token

def get_refresh_token(db):
    """Get the refresh token, or raise an exception if not set"""
    token = db.query(ZohoToken).first()
    if not token or not token.refresh_token:
        raise Exception("No refresh token found in database. Please set the initial refresh token using set_initial_refresh_token()")
    return token.refresh_token

def update_access_token(db, access_token, expiry):
    token = db.query(ZohoToken).first()
    if not token:
        raise Exception("No refresh token found in database")
    token.access_token = access_token
    token.access_token_expiry = expiry
    db.commit()
    return token 