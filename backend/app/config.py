"""Application configuration loaded from environment variables."""

from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "SakhiSetu"
    environment: str = "development"
    log_level: str = "INFO"

    # Database & Redis
    database_url: str = "postgresql+psycopg://sakhisetu:sakhisetu@localhost:5432/sakhisetu"
    redis_url: str = "redis://localhost:6379/0"

    # Security & Encryption
    sakhi_encryption_key: str = "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA="
    sakhi_jwt_secret: str = "dev-secret-change-in-production"
    sakhi_blind_index_salt: str = "dev-blind-index-salt"

    # Lyzr ADK
    lyzr_api_key: str = ""
    lyzr_environment: str = "local"
    lyzr_model: str = "gpt-4o-mini"

    # Bhashini & Fallback Speech
    bhashini_user_id: str = ""
    bhashini_api_key: str = ""
    bhashini_pipeline_url: str = "https://dhruva-api.bhashini.gov.in/services/inference/pipeline"
    sarvam_api_key: str = ""

    # Messaging & Voice Providers
    whatsapp_provider: str = "sandbox"  # sandbox | gupshup | karix
    gupshup_api_key: str = ""
    gupshup_source_number: str = ""
    gupshup_app_name: str = "SakhiSetu"

    voice_provider: str = "sandbox"  # sandbox | exotel
    exotel_account_sid: str = ""
    exotel_api_key: str = ""
    exotel_api_token: str = ""
    exotel_caller_id: str = ""

    # Media storage path
    media_storage_dir: str = "./media_store"

    # Cost metering unit rates (INR)
    cost_per_llm_1k_tokens_inr: float = 0.05
    cost_per_asr_min_bhashini_inr: float = 0.00
    cost_per_asr_min_fallback_inr: float = 0.80
    cost_per_voice_min_exotel_inr: float = 0.45
    cost_per_whatsapp_msg_inr: float = 0.12


@lru_cache
def get_settings() -> Settings:
    return Settings()
