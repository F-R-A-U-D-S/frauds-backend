from pydantic import BaseModel
from sqlmodel import SQLModel
from datetime import datetime



class PredictRequest(BaseModel):
    # result_key: str
    input_key: str

class UserBase(SQLModel):
    name: str
    username: str
    email: str | None = None
    title: str | None = None

class UserCreate(UserBase):
    employee_number: int
    password: str     # ✔ FIXED

class UserLogin(SQLModel):
    username: str
    password: str

class UserPublic(UserBase):
    employee_number: int
    id: str
    is_admin: bool
    created_at: datetime

class UserUpdate(UserBase):
    name: str | None = None
    username: str | None = None
    email: str | None = None
    password: str | None = None
    title: str | None = None
    is_admin: bool | None = None
