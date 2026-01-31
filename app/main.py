from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from app.routes import auth, report, predict, upload, schema, user_router
from app.db.base_class import Base
from app.db.session import engine, SessionLocal
from app.core.security import get_current_user, hash_password
from app.db.models import User

# DB tables
Base.metadata.create_all(bind=engine)

# Load environment variables from dotenv
from dotenv import load_dotenv
load_dotenv()

# Lifespan event handler for startup tasks, in this case user instantiation
@asynccontextmanager
async def lifespan(app: FastAPI):
    # STARTUP: seed default demo users
    db = SessionLocal()

    default_users = [
        {
            "employee_number": 1001,
            "name": "Test User",
            "username": "testuser",
            "email": "testuser@example.com",
            "password_hash": hash_password("test123"),
            "title": "Tester",
            "is_admin": False,
        },
        {
            "employee_number": 1002,
            "name": "Admin User",
            "username": "admin",
            "email": "admin@example.com",
            "password_hash": hash_password("admin123"),
            "title": "Administrator",
            "is_admin": True,
        },
    ]

    for user_data in default_users:
        existing = db.query(User).filter(User.username == user_data["username"]).first()
        if not existing:
            db.add(User(**user_data))

    db.commit()
    db.close()

    # Hand over control to the application
    yield


# Create app with lifespan 
app = FastAPI(
    title="F.R.A.U.D.S Backend API",
    lifespan=lifespan
)


# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],   # allow all origins (frontend dev safe)
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Routers
app.include_router(report.router)
app.include_router(auth.router)
app.include_router(predict.router)
app.include_router(upload.router)
app.include_router(schema.router)
app.include_router(user_router.router)


# Basic endpoints
@app.get("/")
def root():
    return {"status": "F.R.A.U.D.S backend running"}

@app.get("/secure")
def secure_route(user=Depends(get_current_user)):
    return {"message": "ok", "user": user["username"]}

@app.options("/{rest_of_path:path}")
async def preflight(rest_of_path: str):
    return {}
