from pydantic import Field, MySQLDsn, BaseModel, RedisDsn
from pydantic_settings import BaseSettings, SettingsConfigDict


class Database(BaseModel):
    url: MySQLDsn = Field(alias="URL")
    pool_size: int = Field(10, alias="POOL_SIZE")
    max_overflow: int = Field(20, alias="MAX_OVERFLOW")
    pool_timeout: int = Field(30, alias="POOL_TIMEOUT")


class Redis(BaseModel):
    url: RedisDsn = Field(alias="URL")


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        case_sensitive=True,
        env_nested_delimiter="_",
        env_file='.env',
        env_file_encoding='utf-8'
    )

    database: Database = Field(alias="DATABASE")
    redis: Redis = Field(alias="REDIS")
    debug: bool = Field(False, alias="DEBUG")


settings = Settings()
