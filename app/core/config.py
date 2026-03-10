from pydantic import Field, MySQLDsn, BaseModel
from pydantic_settings import BaseSettings, SettingsConfigDict


class Database(BaseModel):
    url: MySQLDsn = Field(alias="DATABASE_URL")
    pool_size: int = Field(10, alias="DB_POOL_SIZE")
    max_overflow: int = Field(20, alias="DB_MAX_OVERFLOW")
    pool_timeout: int = Field(30, alias="DB_POOL_TIMEOUT")


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_nested_delimiter="_")

    database: Database
    debug: bool = Field(False, alias="DEBUG")


settings = Settings()
