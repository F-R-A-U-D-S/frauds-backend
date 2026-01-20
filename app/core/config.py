from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    PROJECT_NAME: str = "F.R.A.U.D.S Backend"
    DATABASE_URL: str = "sqlite:///./database.db"
    AWS_REGION: str = "us-east-1"
    S3_BUCKET: str = "capstone-secure-uploads"
    KMS_KEY_ID: str = "arn:aws:kms:us-east-1:132121094135:key/b151ad6a-5680-4372-9e2c-9edc2962f653"
    SECRET_KEY: str = "secret-key"
    ALGORITHM: str = "HS256"
    
    class Config:
        env_file = ".env"

settings = Settings()