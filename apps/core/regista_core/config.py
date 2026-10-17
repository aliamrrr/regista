"""Runtime settings, read from the environment and the repo-root ``.env`` file.

Every field maps to the upper-case variable of the same name in ``.env.example``; a test keeps
the two in sync. Defaults run the whole stack offline (golden rule 6): memory bus, template
LLM mode, no speech, local JSON store.
"""

from functools import lru_cache
from typing import Annotated, Literal

from pydantic import BaseModel, Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

BusMode = Literal["memory", "eventhubs"]
LlmMode = Literal["template", "cache", "live"]
TtsMode = Literal["off", "cache", "live"]
StoreMode = Literal["local", "cosmos"]
LogLevel = Literal["CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG"]


class RuntimeModes(BaseModel):
    """The switches that decide whether REGISTA runs offline or against Azure."""

    bus: BusMode
    llm_mode: LlmMode
    tts_mode: TtsMode
    store: StoreMode


class Settings(BaseSettings):
    """All runtime configuration for regista-core."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_ignore_empty=True,  # `KEY=` in .env means "unset", not an empty string
        extra="ignore",  # the shared .env also carries VITE_* keys for the web app
    )

    # runtime modes
    bus: BusMode = "memory"
    llm_mode: LlmMode = "template"
    tts_mode: TtsMode = "off"
    store: StoreMode = "local"
    demo_access_code: SecretStr | None = None
    daily_llm_budget_usd: float = Field(default=5.0, ge=0)
    log_level: LogLevel = "INFO"

    # Microsoft Foundry (models)
    foundry_project_endpoint: str | None = None
    azure_openai_endpoint: str | None = None
    model_fast: str = "gpt-5-mini"
    model_smart: str = "gpt-5-mini"
    azure_openai_api_key: SecretStr | None = None

    # Event Hubs
    eventhubs_fqdn: str | None = None
    eventhub_events: str = "events"
    eventhub_tracking: str = "tracking"
    checkpoint_blob_url: str | None = None

    # Cosmos DB
    cosmos_endpoint: str | None = None
    cosmos_database: str = "regista"

    # Azure AI Speech
    speech_region: str = "swedencentral"
    speech_key: SecretStr | None = None
    voice_en: str = "en-GB-RyanNeural"
    voice_fr: str = "fr-FR-HenriNeural"
    voice_es: str = "es-ES-AlvaroNeural"
    voice_ar: str = "ar-MA-JamalNeural"

    # Azure AI Content Safety
    content_safety_endpoint: str | None = None
    content_safety_key: SecretStr | None = None

    # Observability
    applicationinsights_connection_string: SecretStr | None = None
    otel_service_name: str = "regista-core"

    # Managed identity (Azure only)
    azure_client_id: str | None = None

    # Web origins allowed to call the API (comma-separated in the environment)
    cors_origins: Annotated[list[str], NoDecode] = ["http://localhost:5173"]

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _split_origins(cls, value: object) -> object:
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value

    def runtime_modes(self) -> RuntimeModes:
        """Return the bus / LLM / TTS / store modes this process runs with."""
        return RuntimeModes(
            bus=self.bus, llm_mode=self.llm_mode, tts_mode=self.tts_mode, store=self.store
        )


@lru_cache
def get_settings() -> Settings:
    """Return the process-wide settings, loaded once from the environment and ``.env``."""
    return Settings()
