from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    PROJECT_NAME: str = "F.R.A.U.D.S Backend"
    DATABASE_URL: str = "sqlite:///./database.db"
    AWS_REGION: str = "us-east-1"
    S3_BUCKET: str = "capstone-secure-uploads"
    KMS_KEY_ID: str = "arn:aws:kms:us-east-1:132121094135:key/b151ad6a-5680-4372-9e2c-9edc2962f653"

    AWS_ACCESS_KEY_ID: str | None = None
    AWS_SECRET_ACCESS_KEY: str | None = None
    AWS_SESSION_TOKEN: str | None = None  # optional, only if we are using temp creds in the future

    SECRET_KEY: str = "secret-key"
    ALGORITHM: str = "HS256"

    # Email Settings
    SMTP_SERVER: str | None = None
    SMTP_PORT: int = 587
    SMTP_USER: str | None = None
    SMTP_PASSWORD: str | None = None
    EMAILS_FROM_EMAIL: str | None = "noreply@frauds.com"

    class Config:
        env_file = ".env"

settings = Settings()