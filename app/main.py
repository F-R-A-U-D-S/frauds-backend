from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routes import auth, model
from app.db.session import Base, engine

Base.metadata.create_all(bind=engine)

app = FastAPI(title="Capstone Backend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/auth", tags=["auth"])
app.include_router(model.router, prefix="/model", tags=["model"])

@app.get("/")
def root():
    return {"status": "F.R.A.U.D.S backend running"}