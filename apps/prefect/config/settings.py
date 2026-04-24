"""
Environment configuration module for Prefect deployment.

Provides Pydantic models for managing configuration across local and production
environments. Configuration is loaded from environment variables with sensible
defaults for local development.

Requirements: 8.1, 8.2, 8.3, 8.4
"""

import os
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field, model_validator


class Environment(str, Enum):
    """Supported deployment environments."""
    LOCAL = "local"
    PRODUCTION = "production"


class PrefectConfig(BaseModel):
    """Prefect server configuration."""
    api_url: str = Field(description="Prefect API URL")
    ui_url: str = Field(description="Prefect UI URL")


class DatabaseConfig(BaseModel):
    """PostgreSQL database configuration."""
    host: str = Field(default="postgres", description="Database host")
    port: int = Field(default=5432, description="Database port")
    name: str = Field(default="prefect", description="Database name")
    user: str = Field(default="prefect", description="Database user")
    password: str = Field(default="", description="Database password from env")

    @property
    def connection_url(self) -> str:
        """Generate PostgreSQL connection URL."""
        return f"postgresql+asyncpg://{self.user}:{self.password}@{self.host}:{self.port}/{self.name}"


class EnvironmentConfig(BaseModel):
    """
    Main environment configuration model.
    
    Supports both local and production environments with appropriate defaults.
    Sensitive values are loaded from environment variables.
    """
    environment: Environment = Field(
        default=Environment.LOCAL,
        description="Current deployment environment"
    )
    prefect: PrefectConfig = Field(description="Prefect server configuration")
    database: DatabaseConfig = Field(description="Database configuration")
    domain: Optional[str] = Field(
        default=None,
        description="Domain name for production deployment"
    )

    @model_validator(mode="before")
    @classmethod
    def set_defaults_by_environment(cls, data: dict) -> dict:
        """Set default values based on environment if not explicitly provided."""
        if isinstance(data, dict):
            env = data.get("environment", Environment.LOCAL)
            if isinstance(env, str):
                env = Environment(env)
            
            # Set prefect defaults if not provided
            if "prefect" not in data:
                if env == Environment.LOCAL:
                    data["prefect"] = {
                        "api_url": "http://localhost:4200/api",
                        "ui_url": "http://localhost:4200"
                    }
                else:
                    domain = data.get("domain", "prefect.raniendu.dev")
                    data["prefect"] = {
                        "api_url": f"https://{domain}/api",
                        "ui_url": f"https://{domain}"
                    }
            
            # Set database defaults if not provided
            if "database" not in data:
                data["database"] = {
                    "host": "postgres" if env == Environment.LOCAL else "localhost",
                    "port": 5432,
                    "name": "prefect",
                    "user": "prefect",
                    "password": os.environ.get("POSTGRES_PASSWORD", "prefect_local")
                }
        
        return data

    def to_env_vars(self) -> dict[str, str]:
        """Export configuration as environment variables dict."""
        return {
            "PREFECT_API_URL": self.prefect.api_url,
            "PREFECT_UI_URL": self.prefect.ui_url,
            "PREFECT_API_DATABASE_CONNECTION_URL": self.database.connection_url,
        }


def detect_environment() -> Environment:
    """
    Detect the current environment from environment variables.
    
    Checks ENVIRONMENT or PREFECT_ENVIRONMENT variables.
    Defaults to LOCAL if not set.
    """
    env_value = os.environ.get("ENVIRONMENT") or os.environ.get("PREFECT_ENVIRONMENT")
    
    if env_value:
        env_value = env_value.lower()
        if env_value in ("production", "prod"):
            return Environment.PRODUCTION
    
    return Environment.LOCAL


def get_config(
    environment: Optional[Environment] = None,
    domain: Optional[str] = None,
) -> EnvironmentConfig:
    """
    Load configuration for the specified or detected environment.
    
    Args:
        environment: Override environment detection. If None, auto-detects.
        domain: Domain name for production. Defaults to prefect.raniendu.dev.
    
    Returns:
        EnvironmentConfig with appropriate settings for the environment.
    
    Requirements: 8.1, 8.2, 8.3, 8.4
    """
    if environment is None:
        environment = detect_environment()
    
    # Load sensitive values from environment
    postgres_password = os.environ.get("POSTGRES_PASSWORD", "prefect_local")
    
    # Set domain for production
    if environment == Environment.PRODUCTION:
        domain = domain or os.environ.get("PREFECT_DOMAIN", "prefect.raniendu.dev")
    
    config_data = {
        "environment": environment,
        "domain": domain,
        "database": {
            "password": postgres_password,
        }
    }
    
    return EnvironmentConfig(**config_data)
