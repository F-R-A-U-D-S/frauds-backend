from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from routes import auth, report
from db.base_class import Base
from db.session import engine
from app.routes import auth
from app.core.security import get_current_user

Base.metadata.drop_all(bind=engine)  # Drops existing tables
Base.metadata.create_all(bind=engine)

app = FastAPI(title="Capstone Backend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(report.router)
app.include_router(auth.router)


@app.get("/")
def root():
    return {"status": "F.R.A.U.D.S backend running"}

@app.get("/secure")
def secure_route(user = Depends(get_current_user)):
    return {"message": "ok", "user": user["username"]}