from pydantic_settings import BaseSettings
from typing import Optional
import os


class Settings(BaseSettings):
    """Application settings with environment variable support"""
    
    # Application settings
    app_name: str = "Rick & Morty API"
    app_version: str = "1.0.0"
    debug: bool = False
    
    # API settings
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    api_workers: int = 1
    
    # External API settings
    rick_morty_api_url: str = "https://rickandmortyapi.com/api"
    external_api_timeout: int = 10
    external_api_max_retries: int = 3
    external_api_backoff_delay: float = 1.0
    
    # Database settings
    database_url: Optional[str] = None
    database_host: str = "localhost"
    database_port: int = 5432
    database_name: str = "rickmorty"
    database_user: str = "postgres"
    database_password: str = "password"
    
    # Database connection pool settings
    db_pool_size: int = 20
    db_max_overflow: int = 30
    db_pool_timeout: int = 30
    db_pool_recycle: int = 3600
    db_pool_pre_ping: bool = True
    db_echo: bool = False
    db_echo_pool: bool = False
    
    # Redis settings
    redis_url: Optional[str] = None
    redis_host: str = "localhost"
    redis_port: int = 6379
    redis_password: Optional[str] = None
    redis_db: int = 0
    
    # Cache settings
    cache_ttl: int = 3600  # 1 hour (L2 default)
    cache_l1_ttl: int = 120  # 2 minutes (L1 TTL)
    cache_l2_ttl: int = 600  # 10 minutes (L2 TTL)
    cache_l1_max_size: int = 500  # L1 max entries
    cache_l1_max_value_size: int = 1024 * 1024  # 1MB max value size for L1
    cache_max_size: int = 1000  # Legacy setting
    cache_jitter_percent: int = 10  # 10% jitter for TTL
    cache_max_refresh_concurrency: int = 5  # Max concurrent refreshes
    
    # Rate limiting
    rate_limit_requests: int = 100
    rate_limit_window: int = 60  # seconds
    
    # Monitoring
    enable_metrics: bool = True
    metrics_port: int = 9090
    enable_tracing: bool = True
    jaeger_endpoint: Optional[str] = None
    
    # Health check settings
    health_check_timeout: int = 5
    
    # Admin authentication
    admin_api_key: str = ""
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False
    
    @property
    def database_url_computed(self) -> str:
        """Compute database URL from components if not provided directly"""
        if self.database_url:
            return self.database_url
        return f"postgresql+asyncpg://{self.database_user}:{self.database_password}@{self.database_host}:{self.database_port}/{self.database_name}"
    
    @property
    def redis_url_computed(self) -> str:
        """Compute Redis URL from components if not provided directly"""
        if self.redis_url:
            return self.redis_url
        
        auth = f":{self.redis_password}@" if self.redis_password else ""
        return f"redis://{auth}{self.redis_host}:{self.redis_port}/{self.redis_db}"


# Global settings instance
settings = Settings()
