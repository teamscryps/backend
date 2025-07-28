from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    # Application Settings
    PROJECT_NAME: str = "FastAPI Backend Application"
    DEBUG: bool = True
    
    # Database Configuration
    DATABASE_URL: str = "postgresql://postgres:1234@localhost:5432/scryps_db"
    
    # JWT Settings
    SECRET_KEY: str = "your-super-secret-key-change-this-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    
    # Email Settings (for OTP delivery)
    SMTP_HOST: str = "smtp.gmail.com"
    SMTP_PORT: int = 587
    SMTP_USERNAME: str = "your-email@gmail.com"
    SMTP_PASSWORD: str = "your-app-password"
    
    # OTP Settings
    OTP_EXPIRE_MINUTES: int = 5
    
    # Redis Settings (if needed for caching)
    REDIS_URL: str = "redis://localhost:6379"
    
    # API Settings
    API_V1_STR: str = "/api/v1"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

settings = Settings() 