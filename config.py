
from pydantic_settings import BaseSettings, SettingsConfigDict
from cryptography.fernet import Fernet

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

    ENCRYPTION_KEY: str = Fernet.generate_key().decode()

    LOG_LEVEL: str = "INFO"
    # Primary broker webhook secret: MUST be set via environment in non-debug environments.
    BROKER_WEBHOOK_SECRET: str | None = None
    # Comma-separated list of previous secrets still accepted for signature verification (facilitates rotation)
    BROKER_WEBHOOK_ADDITIONAL_SECRETS: str | None = None

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    def _post_init(self):
        # Enforce secret presence in non-debug contexts
        if not self.DEBUG:
            if not self.BROKER_WEBHOOK_SECRET:
                raise ValueError("BROKER_WEBHOOK_SECRET must be set in environment for non-debug mode")
        # Warn (raise) if an obviously default placeholder is used outside debug
        if (self.BROKER_WEBHOOK_SECRET and self.BROKER_WEBHOOK_SECRET.lower() in {"change-me", "changeme", "default", "secret"}) and not self.DEBUG:
            raise ValueError("Insecure BROKER_WEBHOOK_SECRET value detected; change it")

settings = Settings()
settings._post_init()
