from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware

from app.routes import auth, report, predict, upload, schema, user_router
from app.db.base_class import Base
from app.db.session import engine
from app.core.security import get_current_user

# DB tables
Base.metadata.create_all(bind=engine)

# Load environment variables from dotenv
from dotenv import load_dotenv
load_dotenv()

# Create app
app = FastAPI(title="F.R.A.U.D.S Backend API")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],   # allow all origins (frontend dev safe)
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["Content-Disposition"],
)

# Routers
app.include_router(report.router)
app.include_router(auth.router)
app.include_router(predict.router)
app.include_router(upload.router)
app.include_router(schema.router)
app.include_router(user_router.router)
from app.routes import export
app.include_router(export.router)
from app.routes import admin_stats
app.include_router(admin_stats.router)

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
