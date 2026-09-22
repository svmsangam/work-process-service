from pydantic_settings import BaseSettings
from typing import Literal

class Settings(BaseSettings):
    PROJECT_NAME: str = "AI-Assisted Work Intake System"
    DATABASE_URL: str = "postgresql://postgres:postgres@localhost:5432/work_intake"

    # LLM Settings
    # NOTE: defaults to "mock" (not "openrouter") so the app and test suite run
    # out of the box without API credentials or network access. Set AI_PROVIDER
    # in .env to switch to a real provider.
    AI_PROVIDER: Literal["mock", "groq", "gemini", "openrouter", "local"] = "mock"
    GROQ_API_KEY: str | None = None
    GEMINI_API_KEY: str | None = None

    # OpenRouter settings
    OPENROUTER_API_KEY: str = ""
    OPENROUTER_BASE_URL: str = "https://openrouter.ai/api/v1"
    OPENROUTER_MODEL: str = "nex-agi/nex-n2.5-pro:free"
    YOUR_SITE_URL: str = "http://localhost:5173"
    YOUR_SITE_NAME: str = "WorkProcessAnalysis"

    # Local (e.g. Ollama) OpenAI-compatible endpoint settings
    LOCAL_AI_BASE_URL: str = "http://localhost:11434/v1"
    LOCAL_AI_MODEL: str = "llama3"

    class Config:
        env_file = ".env"

settings = Settings()