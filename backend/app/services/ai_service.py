import abc
import json
import asyncio
from typing import Optional
import httpx
from pydantic import ValidationError

from app.config import settings
from app.schemas import AIAnalysisResult, AICategoryEnum, AIPriorityEnum

# Shared, lazily-created httpx.AsyncClient so OpenRouter/local adapters reuse a
# single connection pool instead of opening a new one per request.
_http_client: Optional[httpx.AsyncClient] = None


def get_http_client() -> httpx.AsyncClient:
    global _http_client
    if _http_client is None:
        _http_client = httpx.AsyncClient(timeout=45.0)
    return _http_client


# Fallback returned when a provider responds but the payload is empty, not
# valid JSON, or missing the fields AIAnalysisResult requires — surfaced as a
# FAILED item (see WorkItemService.process_ai_analysis) rather than silently
# faking a category/priority the model never actually produced.
MALFORMED_RESPONSE_MESSAGE = "AI Analysis unavailable (malformed response received)."


def _build_analysis_messages(title: str, description: str) -> list[dict]:
    prompt = f"""
    Analyze the following work item and respond ONLY with a JSON object.
    JSON schema requirements:
    {{
        "category": "DOCUMENT_REQUEST" | "TECHNICAL_ISSUE" | "ACCOUNT_INQUIRY" | "BILLING_DISPUTE" | "GENERAL",
        "priority": "LOW" | "MEDIUM" | "HIGH" | "CRITICAL",
        "summary": "Brief 1-2 sentence summary of the issue",
        "recommendedAction": "Clear action step for the operations agent"
    }}

    Work Item Title: {title}
    Work Item Description: {description}
    """
    return [
        {"role": "system", "content": "You are an AI assistant that extracts structured JSON work intake summaries."},
        {"role": "user", "content": prompt},
    ]


class BaseLLMService(abc.ABC):
    """Abstract interface for LLM Provider Adapters."""

    @abc.abstractmethod
    async def analyze_work_item(self, title: str, description: str) -> AIAnalysisResult:
        """
        Analyzes work item details and returns structured result.
        Must raise Exception on failure (timeouts, parsing error, API failures).
        """
        pass


class MockLLMService(BaseLLMService):
    """Mock implementation for testing & offline development."""

    def __init__(self, simulate_failure: bool = False, delay_seconds: float = 1.0):
        self.simulate_failure = simulate_failure
        self.delay_seconds = delay_seconds

    async def analyze_work_item(self, title: str, description: str) -> AIAnalysisResult:
        # Simulate network latency
        if self.delay_seconds > 0:
            await asyncio.sleep(self.delay_seconds)

        # Simulate provider failure or timeout scenario
        if self.simulate_failure or "FAIL_LLM" in title.upper():
            raise RuntimeError("Mock LLM Provider failure: Service unavailable or timeout.")

        # Return mock structured response matching required output schema
        return AIAnalysisResult(
            category=AICategoryEnum.DOCUMENT_REQUEST,
            priority=AIPriorityEnum.HIGH,
            summary=f"Automated summary for '{title}': Missing required information in request.",
            recommendedAction="Request missing documentation or context directly from applicant."
        )


class GroqLLMService(BaseLLMService):
    """Real LLM Service using Groq API with structured JSON parsing."""

    def __init__(self):
        if not settings.GROQ_API_KEY:
            raise ValueError("GROQ_API_KEY is not configured in settings.")
        
        from groq import AsyncGroq
        self.client = AsyncGroq(api_key=settings.GROQ_API_KEY)

    async def analyze_work_item(self, title: str, description: str) -> AIAnalysisResult:
        try:
            response = await asyncio.wait_for(
                self.client.chat.completions.create(
                    model="llama-3.3-70b-versatile",
                    messages=_build_analysis_messages(title, description),
                    response_format={"type": "json_object"},
                    temperature=0.1,
                ),
                timeout=10.0  # 10-second hard execution timeout
            )

            raw_content = response.choices[0].message.content
            parsed_json = json.loads(raw_content)

            # Validate response structure strictly via Pydantic
            return AIAnalysisResult(**parsed_json)

        except asyncio.TimeoutError:
            raise RuntimeError("LLM Service call timed out after 10 seconds.")
        except (json.JSONDecodeError, ValidationError) as e:
            raise ValueError(f"LLM produced malformed or invalid schema output: {str(e)}")
        except Exception as e:
            raise RuntimeError(f"LLM Provider API error: {str(e)}")


class OpenRouterLLMService(BaseLLMService):
    """Real LLM Service using OpenRouter's OpenAI-compatible chat completions API."""

    def __init__(self):
        if not settings.OPENROUTER_API_KEY:
            raise ValueError("OPENROUTER_API_KEY is not configured in settings.")
        self.client = get_http_client()

    async def analyze_work_item(self, title: str, description: str) -> AIAnalysisResult:
        headers = {
            "Authorization": f"Bearer {settings.OPENROUTER_API_KEY}",
            "HTTP-Referer": settings.YOUR_SITE_URL,
            "X-Title": settings.YOUR_SITE_NAME,
        }
        body = {
            "model": settings.OPENROUTER_MODEL,
            "messages": _build_analysis_messages(title, description),
            "response_format": {"type": "json_object"},
            "temperature": 0.1,
        }

        try:
            response = await self.client.post(
                f"{settings.OPENROUTER_BASE_URL}/chat/completions",
                headers=headers,
                json=body,
                timeout=30.0,  # free-tier OpenRouter models can be slow; give them real headroom
            )
            response.raise_for_status()

            raw_content = response.json()["choices"][0]["message"]["content"]
            if not raw_content or not raw_content.strip():
                raise ValueError(MALFORMED_RESPONSE_MESSAGE)
            parsed_json = json.loads(raw_content)

            # Validate response structure strictly via Pydantic
            return AIAnalysisResult(**parsed_json)

        except httpx.TimeoutException:
            raise RuntimeError("AI Analysis failed: OpenRouter request timed out after 30 seconds.")
        except httpx.HTTPStatusError as e:
            raise RuntimeError(f"AI Analysis failed: OpenRouter API error {e.response.status_code}.")
        except (json.JSONDecodeError, ValidationError, KeyError, IndexError, TypeError):
            raise ValueError(MALFORMED_RESPONSE_MESSAGE)
        except ValueError:
            raise
        except Exception as e:
            raise RuntimeError(f"AI Analysis failed: OpenRouter provider error: {str(e)}")


class LocalLLMService(BaseLLMService):
    """LLM Service for a local OpenAI-compatible endpoint (e.g. Ollama)."""

    def __init__(self):
        self.client = get_http_client()

    async def analyze_work_item(self, title: str, description: str) -> AIAnalysisResult:
        body = {
            "model": settings.LOCAL_AI_MODEL,
            "messages": _build_analysis_messages(title, description),
            "response_format": {"type": "json_object"},
            "temperature": 0.1,
        }

        try:
            response = await self.client.post(
                f"{settings.LOCAL_AI_BASE_URL}/chat/completions",
                json=body,
                timeout=45.0,  # local models can be slower than hosted APIs
            )
            response.raise_for_status()

            raw_content = response.json()["choices"][0]["message"]["content"]
            if not raw_content or not raw_content.strip():
                raise ValueError(MALFORMED_RESPONSE_MESSAGE)
            parsed_json = json.loads(raw_content)

            # Validate response structure strictly via Pydantic
            return AIAnalysisResult(**parsed_json)

        except httpx.TimeoutException:
            raise RuntimeError("AI Analysis failed: local AI endpoint request timed out after 45 seconds.")
        except httpx.HTTPStatusError as e:
            raise RuntimeError(f"AI Analysis failed: local AI endpoint error {e.response.status_code}.")
        except (json.JSONDecodeError, ValidationError, KeyError, IndexError, TypeError):
            raise ValueError(MALFORMED_RESPONSE_MESSAGE)
        except ValueError:
            raise
        except Exception as e:
            raise RuntimeError(f"AI Analysis failed: local AI endpoint error: {str(e)}")


def get_ai_service() -> BaseLLMService:
    """Dependency Provider / Factory method for AI LLM Service."""
    if settings.AI_PROVIDER == "groq":
        return GroqLLMService()
    if settings.AI_PROVIDER == "openrouter":
        return OpenRouterLLMService()
    if settings.AI_PROVIDER == "local":
        return LocalLLMService()
    return MockLLMService()