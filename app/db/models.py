from sqlalchemy import Column, String, DateTime, Boolean, Integer
import uuid
from datetime import datetime

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

from sqlmodel import SQLModel

class UserBase(SQLModel):
    name: str 
    username: str 
    title: str 


class UserPublic(UserBase):
    employee_number: int
    id: str
    is_admin: bool
    created_at: datetime



class UserCreate(UserBase):
    employee_number: int
    password_hash: str


class UserUpdate(UserBase):
    name: str | None = None
    username: str | None = None
    password_hash: str | None = None
    title: str | None = None
    is_admin: bool | None = None