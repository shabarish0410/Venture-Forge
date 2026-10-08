from pathlib import Path
import json
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import SecretStr, Field
from typing import Literal
from pydantic import model_validator
from urllib.parse import urlsplit
from .model_config import ModelProfile

ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ROOT / ".env", extra="ignore", hide_input_in_errors=True)
    database_url: str
    app_origin: str = "http://127.0.0.1:3000"
    app_env: Literal["development", "production"] = "development"
    cookie_secure: bool = False
    session_hours: int = Field(default=12, ge=1, le=168)
    bootstrap_email: str = "founder@ventureforge.local"
    bootstrap_password: str = ""
    google_client_id: str = ""
    google_client_secret: SecretStr = SecretStr("")
    github_client_id: str = ""
    github_client_secret: SecretStr = SecretStr("")
    research_allowed_hosts: list[str] = Field(default_factory=list, max_length=50)
    research_search_api_key: SecretStr = SecretStr("")
    model_router_policy: Literal["hybrid", "disabled"] = "hybrid"
    model_profiles: list[ModelProfile] = Field(default_factory=list, max_length=30)
    model_profiles_file: str | None = None
    model_max_context_bytes: int = Field(default=500000, ge=1024, le=2000000)
    model_provider: Literal["disabled", "openai", "anthropic", "gemini", "ollama"] = "disabled"
    model_id: str = ""
    openai_api_key: SecretStr = SecretStr("")
    anthropic_api_key: SecretStr = SecretStr("")
    gemini_api_key: SecretStr = SecretStr("")
    ollama_url: str = "http://127.0.0.1:11434"
    model_input_inr_per_million: float = Field(default=0, ge=0, allow_inf_nan=False)
    model_output_inr_per_million: float = Field(default=0, ge=0, allow_inf_nan=False)

    @model_validator(mode="after")
    def unique_model_profiles(self):
        origin = urlsplit(self.app_origin)
        if origin.scheme not in {"http", "https"} or not origin.hostname or origin.username or origin.password or origin.path not in {"", "/"} or origin.query or origin.fragment:
            raise ValueError("APP_ORIGIN must be an HTTP(S) origin without credentials, query or fragment")
        if origin.scheme == "http" and origin.hostname not in {"127.0.0.1", "localhost", "::1", "testserver"}:
            raise ValueError("APP_ORIGIN requires HTTPS outside local development")
        self.app_origin = self.app_origin.rstrip("/")
        if (self.app_env == "production" or origin.hostname not in {"127.0.0.1", "localhost", "::1", "testserver"}) and (origin.scheme != "https" or not self.cookie_secure):
            raise ValueError("Production authentication requires an HTTPS APP_ORIGIN and COOKIE_SECURE=true")
        if self.model_profiles_file:
            if self.model_profiles: raise ValueError("Use MODEL_PROFILES or MODEL_PROFILES_FILE, not both")
            source = Path(self.model_profiles_file)
            if not source.is_absolute(): source = ROOT / source
            try:
                if source.stat().st_size > 100000: raise ValueError("Profile configuration is too large")
                data = json.loads(source.read_text(encoding="utf-8"))
                if not isinstance(data, list) or len(data) > 30: raise ValueError("Invalid profile collection")
                self.model_profiles = [ModelProfile.model_validate(p) for p in data]
            except Exception:
                raise ValueError("Invalid model profile file; check its path and declared capabilities") from None
        if len({p.name for p in self.model_profiles}) != len(self.model_profiles):
            raise ValueError("Model profile names must be unique")
        return self
