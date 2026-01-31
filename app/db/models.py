from sqlalchemy import Column, String, DateTime, Boolean, Integer
import uuid
from datetime import datetime
from typing import Optional

from app.db.base_class import Base

# user model for authentication
class User(Base):
    __tablename__ = "users"
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    employee_number = Column(Integer, unique=True, nullable=False)
    name = Column(String, nullable=False)
    username = Column(String, unique=True, nullable=False)
    password_hash = Column(String, nullable=False)
    title = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)
    is_admin = Column(Boolean, nullable=False, default=False)
    email = Column(String, unique=True, nullable=True) # Added email field

class ExportToken(Base):
    __tablename__ = "export_tokens"
    token = Column(String, primary_key=True, index=True)
    user_id = Column(String, nullable=False) 
    file_path = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime, nullable=False)
    is_used = Column(Boolean, default=False)

from sqlmodel import SQLModel

class UserBase(SQLModel):
    name: str 
    username: str 
    email: Optional[str] = None # Added email field
    title: Optional[str] = None


class UserPublic(UserBase):
    employee_number: int
    id: str
    is_admin: bool
    created_at: datetime



class UserCreate(UserBase):
    employee_number: int
    password_hash: str


class UserUpdate(SQLModel):
    name: Optional[str] = None
    username: Optional[str] = None
    email: Optional[str] = None # Added email field
    password_hash: Optional[str] = None
    title: Optional[str] = None
    is_admin: Optional[bool] = None