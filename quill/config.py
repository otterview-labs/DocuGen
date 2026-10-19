from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="QUILL_", env_file=".env", extra="ignore")

    data_dir: Path = Path("data")
    api_key: str = ""
    knowledge_url: str = "http://127.0.0.1:8006"
    knowledge_token: str = ""
    llm_base_url: str = "https://api.openai.com/v1"
    llm_api_key: str = ""
    llm_model: str = ""
    llm_reasoning_effort: str = ""
    llm_timeout: float = Field(120, gt=0, le=600)
    llm_max_tokens: int = Field(4096, ge=128, le=32768)
    max_upload_mb: int = Field(20, ge=1, le=100)
    frontend_dir: Path = Path(__file__).resolve().parent.parent / "frontend" / "dist"
