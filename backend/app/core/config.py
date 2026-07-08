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
    # Comma-separated models to try, in order, if gemini_model hits a
    # quota/rate-limit error — each Gemini model has its own separate
    # free-tier quota bucket, so falling back actually buys more headroom
    # rather than hitting the same wall.
    gemini_fallback_models: str = "gemini-2.5-flash,gemini-2.0-flash"

    # Search
    tavily_api_key: str | None = None

    # Tracing (§7.1)
    langfuse_public_key: str | None = None
    langfuse_secret_key: str | None = None
    langfuse_host: str | None = None

    # Gates (§4.4, §6)
    ats_pass_threshold: float = 70.0

    # Optional durable checkpoint store for the LangGraph Manager Agent —
    # when set, the Human Approval Gate's paused state survives process
    # restarts instead of living only in memory. When unset, the graph
    # falls back to an in-memory checkpointer (fine for local/demo use).
    # Tables are created in database_schema, not "public", so this can
    # safely point at a database shared with an unrelated app.
    database_url: str | None = None
    database_schema: str = "jobpilot"

    # Local, private data store — resumes and personal data are never sent
    # to third parties beyond the LLM/search providers required for the
    # current step (§6.4).
    jobpilot_data_dir: str = ".jobpilot_data"

    # Application Agent auto-submit allow-list (§4.6, §6.3)
    auto_submit_allowlist: str = ""

    api_host: str = "0.0.0.0"
    api_port: int = 8000

    # Admin dashboard — HTTP Basic Auth. Override via env in any real
    # deployment; these are dev-only defaults.
    admin_username: str = "admin"
    admin_password: str = "123456"

    @property
    def data_dir(self) -> Path:
        p = Path(self.jobpilot_data_dir)
        p.mkdir(parents=True, exist_ok=True)
        return p

    @property
    def gemini_model_candidates(self) -> list[str]:
        fallbacks = [m.strip() for m in self.gemini_fallback_models.split(",") if m.strip()]
        # Primary first, then fallbacks, de-duplicated while preserving order.
        seen: set[str] = set()
        ordered = [self.gemini_model, *fallbacks]
        return [m for m in ordered if not (m in seen or seen.add(m))]

    @property
    def allowlist_hosts(self) -> set[str]:
        return {h.strip().lower() for h in self.auto_submit_allowlist.split(",") if h.strip()}

    @property
    def checkpoint_dsn(self) -> str | None:
        """``database_url`` with a ``search_path`` pinned to
        ``database_schema`` — every LangGraph checkpoint table this app
        creates or touches lives in that schema, never in ``public``,
        so this can safely point at a database another app also uses."""
        if not self.database_url:
            return None
        sep = "&" if "?" in self.database_url else "?"
        return f"{self.database_url}{sep}options=-csearch_path%3D{self.database_schema}"


@lru_cache
def get_settings() -> Settings:
    return Settings()
