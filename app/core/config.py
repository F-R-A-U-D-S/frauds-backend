from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    PROJECT_NAME: str = "F.R.A.U.D.S Backend"
    DATABASE_URL: str = "sqlite:///./database.db"
    AWS_REGION: str = "us-east-1"
    S3_BUCKET: str = "my-app-bucket"
    KMS_KEY_ID: str = "my-kms-key-id"
    SECRET_KEY: str = "your-secret-key"
    ALGORITHM: str = "HS256"
    
    class Config:
        env_file = ".env"

settings = Settings()