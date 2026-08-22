from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


load_dotenv()


@dataclass(frozen=True)
class Settings:
    root_dir: Path
    llm_provider: str
    ollama_base_url: str
    ollama_model: str
    azure_openai_endpoint: str
    azure_openai_api_key: str
    azure_openai_api_version: str
    azure_openai_deployment: str
    max_kb_results: int
    postgres_dsn: str
    app_name: str
    show_trace: bool


def get_settings() -> Settings:
    root_dir = Path(__file__).resolve().parent.parent
    postgres_dsn = os.getenv(
        "POSTGRES_DSN",
        "postgresql://postgres:postgres@localhost:5432/it_support",
    )

    return Settings(
        root_dir=root_dir,
        llm_provider=os.getenv("LLM_PROVIDER", "ollama").strip().lower(),
        ollama_base_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"),
        ollama_model=os.getenv("OLLAMA_MODEL", "gemma4:latest"),
        azure_openai_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT", ""),
        azure_openai_api_key=os.getenv("AZURE_OPENAI_API_KEY", ""),
        azure_openai_api_version=os.getenv("AZURE_OPENAI_API_VERSION", "2024-10-21"),
        azure_openai_deployment=os.getenv("AZURE_OPENAI_DEPLOYMENT", ""),
        max_kb_results=max(1, int(os.getenv("MAX_KB_RESULTS", "3"))),
        postgres_dsn=postgres_dsn,
        app_name=os.getenv("APP_NAME", "AI IT Support Assistant"),
        show_trace=os.getenv("SHOW_TRACE", "true").lower() == "true",
    )
