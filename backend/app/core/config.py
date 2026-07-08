from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # LLM providers — pluggable, matches production pattern of not
    # single-sourcing model risk (§8).
    openai_api_key: str | None = None
    gemini_api_key: str | None = None
    llm_provider: str = "openai"  # "openai" | "gemini"
    openai_model: str = "gpt-4o-mini"
    gemini_model: str = "gemini-1.5-flash"

    # Search
    tavily_api_key: str | None = None

    # Tracing (§7.1)
    langfuse_public_key: str | None = None
    langfuse_secret_key: str | None = None
    langfuse_host: str | None = None

    # Gates (§4.4, §6)
    ats_pass_threshold: float = 70.0

    # Local, private data store — resumes and personal data are never sent
    # to third parties beyond the LLM/search providers required for the
    # current step (§6.4).
    jobpilot_data_dir: str = ".jobpilot_data"

    # Application Agent auto-submit allow-list (§4.6, §6.3)
    auto_submit_allowlist: str = ""

    api_host: str = "0.0.0.0"
    api_port: int = 8000

    @property
    def data_dir(self) -> Path:
        p = Path(self.jobpilot_data_dir)
        p.mkdir(parents=True, exist_ok=True)
        return p

    @property
    def allowlist_hosts(self) -> set[str]:
        return {h.strip().lower() for h in self.auto_submit_allowlist.split(",") if h.strip()}


@lru_cache
def get_settings() -> Settings:
    return Settings()
