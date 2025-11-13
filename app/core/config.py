from pydantic import BaseSettings

class Settings(BaseSettings):
    PROJECT_NAME: str = "F.R.A.U.D.S Backend"
    DATABASE_URL: str
    AWS_REGION: str
    S3_BUCKET: str
    KMS_KEY_ID: str
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    
    class Config:
        env_file = ".env"

settings = Settings()