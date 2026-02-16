from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")
    openai_key:str = Field(..., alias="OPENAI_KEY") 
    model_name : str = Field(..., alias='MODEL_NAME')
    duckdb_path: str = Field(..., alias="DUCKDB_PATH")
    rate_per_distance: float = Field(..., alias="RATE_PER_DISTANCE")
