import json
import os
import sqlite3
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv
import httpx
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(BASE_DIR, ".env"))


class LLMAdapterError(Exception):
    pass


@dataclass
class ChatMessage:
    role: str
    content: str


@dataclass
class LLMResponse:
    content: str
    provider: str
    model: str
    raw_response: Optional[Dict[str, Any]] = None


def get_sqlite_db_path() -> str:
    database_url = os.getenv("DATABASE_URL", "sqlite:///./bookcase.db")
    prefix = "sqlite:///"
    if database_url.startswith(prefix):
        path = database_url[len(prefix):]
        if not path:
            return os.path.join(BASE_DIR, "bookcase.db")
        if os.path.isabs(path):
            return path
        return os.path.join(BASE_DIR, path)
    database_path = os.getenv("DATABASE_PATH", "bookcase.db")
    if os.path.isabs(database_path):
        return database_path
    return os.path.join(BASE_DIR, database_path)


def persist_usage(provider: str, model: str, raw_response: Optional[Dict[str, Any]]) -> None:
    if not raw_response:
        return

    usage_metadata = raw_response.get("usage_metadata") or {}
    response_metadata = raw_response.get("response_metadata") or {}
    token_usage = response_metadata.get("token_usage") or {}

    input_tokens = usage_metadata.get("input_tokens")
    output_tokens = usage_metadata.get("output_tokens")
    total_tokens = usage_metadata.get("total_tokens")

    if input_tokens is None:
        input_tokens = token_usage.get("prompt_tokens", 0)
    if output_tokens is None:
        output_tokens = token_usage.get("completion_tokens", 0)
    if total_tokens is None:
        total_tokens = token_usage.get("total_tokens", (input_tokens or 0) + (output_tokens or 0))

    reasoning_tokens = (
        ((usage_metadata.get("output_token_details") or {}).get("reasoning"))
        or ((token_usage.get("completion_tokens_details") or {}).get("reasoning_tokens"))
        or 0
    )

    db_path = get_sqlite_db_path()
    try:
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                '''
                INSERT INTO llm_usage_logs
                (provider, model, input_tokens, output_tokens, total_tokens, reasoning_tokens, raw_response_json)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ''',
                (
                    provider,
                    model,
                    int(input_tokens or 0),
                    int(output_tokens or 0),
                    int(total_tokens or 0),
                    int(reasoning_tokens or 0),
                    json.dumps(raw_response, ensure_ascii=False),
                ),
            )
            conn.commit()
    except Exception as exc:
        print(f"[WARNING] Failed to persist LLM usage: {exc}")


class BaseLLMProvider:
    def chat(self, messages: List[ChatMessage], response_format: Optional[Dict[str, Any]] = None) -> LLMResponse:
        raise NotImplementedError


class OpenAICompatibleProvider(BaseLLMProvider):
    def __init__(
        self,
        base_url: str,
        api_key: str,
        model: str,
        timeout: int = 120,
        connect_timeout: int = 10,
        max_retries: int = 2,
    ):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = timeout
        self.connect_timeout = connect_timeout
        self.max_retries = max_retries
        self.http_client = httpx.Client(
            timeout=httpx.Timeout(timeout=self.timeout, connect=self.connect_timeout)
        )
        self.client = ChatOpenAI(
            model=self.model,
            api_key=api_key,
            base_url=self.base_url,
            timeout=self.timeout,
            max_retries=self.max_retries,
            http_client=self.http_client,
        )

    def chat(self, messages: List[ChatMessage], response_format: Optional[Dict[str, Any]] = None) -> LLMResponse:
        lc_messages = []
        for message in messages:
            if message.role == "system":
                lc_messages.append(SystemMessage(content=message.content))
            else:
                lc_messages.append(HumanMessage(content=message.content))

        extra_body: Dict[str, Any] = {}
        if response_format:
            extra_body["response_format"] = response_format

        try:
            response = self.client.invoke(lc_messages, extra_body=extra_body or None)
        except httpx.ReadTimeout as exc:
            raise LLMAdapterError(
                f"LLM request timed out after {self.timeout}s read timeout. "
                f"Try increasing LLM_TIMEOUT or reducing the requested output length."
            ) from exc
        except Exception as exc:
            status_code = getattr(exc, "status_code", None)
            if status_code and 400 <= status_code < 500:
                raise LLMAdapterError(f"LLM request failed with status {status_code}") from exc
            raise LLMAdapterError("LLM request failed after retries") from exc

        content = response.content
        if isinstance(content, list):
            content = "".join(
                block.get("text", "") if isinstance(block, dict) else str(block)
                for block in content
            )

        if not content:
            raise LLMAdapterError("LLM provider returned empty content")

        llm_response = LLMResponse(
            content=str(content),
            provider="dashscope_compatible" if "dashscope.aliyuncs.com" in self.base_url else "openai_compatible",
            model=self.model,
            raw_response={
                "response_metadata": getattr(response, "response_metadata", None),
                "usage_metadata": getattr(response, "usage_metadata", None),
            },
        )
        print(
            "[INFO] LLM response: "
            + json.dumps(
                {
                    "provider": llm_response.provider,
                    "model": llm_response.model,
                    "raw_response": llm_response.raw_response,
                    "content": llm_response.content,
                },
                ensure_ascii=False,
            )
        )
        persist_usage(llm_response.provider, llm_response.model, llm_response.raw_response)
        return llm_response


class LLMAdapter:
    def __init__(self, provider_name: Optional[str] = None):
        self.provider_name = provider_name or os.getenv("LLM_PROVIDER", "dashscope_compatible")
        self.provider = self._build_provider()

    def _build_provider(self) -> BaseLLMProvider:
        if self.provider_name in {"openai_compatible", "dashscope_compatible"}:
            default_base_url = "https://dashscope.aliyuncs.com/compatible-mode/v1"
            default_model = "qwen3.6-plus"
            base_url = os.getenv("LLM_BASE_URL", default_base_url)
            api_key = os.getenv("LLM_API_KEY")
            model = os.getenv("LLM_MODEL", default_model)
            timeout = int(os.getenv("LLM_TIMEOUT", "120"))
            connect_timeout = int(os.getenv("LLM_CONNECT_TIMEOUT", "10"))
            max_retries = int(os.getenv("LLM_MAX_RETRIES", "2"))

            if not api_key:
                raise LLMAdapterError(
                    "LLM_API_KEY is required for the configured LLM provider"
                )

            return OpenAICompatibleProvider(
                base_url=base_url,
                api_key=api_key,
                model=model,
                timeout=timeout,
                connect_timeout=connect_timeout,
                max_retries=max_retries,
            )

        raise LLMAdapterError(f"Unsupported LLM provider: {self.provider_name}")

    def chat(self, messages: List[ChatMessage], response_format: Optional[Dict[str, Any]] = None) -> LLMResponse:
        return self.provider.chat(messages=messages, response_format=response_format)
