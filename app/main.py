from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from app.routes import auth, report, predict, upload, schema
from app.db.base_class import Base
from app.db.session import engine
from app.core.security import get_current_user


Base.metadata.create_all(bind=engine)

app = FastAPI(title="Capstone Backend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",  
        "http://127.0.0.1:5173",
        "http://localhost:5174",  
        "http://127.0.0.1:5174"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(report.router)
app.include_router(auth.router)
app.include_router(predict.router)
app.include_router(upload.router)
app.include_router(schema.router)


@app.get("/")
def root():
    return {"status": "F.R.A.U.D.S backend running"}

@app.get("/secure")
def secure_route(user = Depends(get_current_user)):
    return {"message": "ok", "user": user["username"]}

@app.options("/{rest_of_path:path}")
async def preflight(rest_of_path: str):
    return {}