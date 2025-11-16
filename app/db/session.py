from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

DATABASE_URL = "sqlite:///./database.db"

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)

Base = declarative_base()


def get_db():
	"""Dependency generator that yields a SQLAlchemy Session and ensures it's closed."""
	db = SessionLocal()
	try:
		yield db
	finally:
		db.close()