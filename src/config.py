"""Configuration, read once from the environment."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover - dotenv is in requirements.txt
    def load_dotenv(*_args, **_kwargs):
        return False

ROOT = Path(__file__).resolve().parent.parent

# The 22 intent classes, fixed by the dataset. Order is stable so that the
# prompt text is stable, which keeps the response cache usable across runs.
INTENT_CLASSES: tuple[str, ...] = (
    "account_access",
    "api_key_issue",
    "api_usage_question",
    "authentication_failure",
    "billing_query",
    "compliance_request",
    "configuration_help",
    "data_export",
    "data_residency",
    "database_issue",
    "deployment_failure",
    "feature_request",
    "integration_help",
    "onboarding",
    "performance_degradation",
    "quota_or_overage",
    "rate_limit",
    "rollback_request",
    "security_incident",
    "sso_configuration",
    "unclear_request",
    "webhook_issue",
)

URGENCY_LEVELS: tuple[str, ...] = ("high", "medium", "low")

# Classes the dataset marks must_not_auto_respond on every occurrence. These are
# a hard escalation rule rather than a threshold, because a confident classifier
# is exactly the condition under which a threshold would let one through.
NEVER_AUTO_RESPOND: frozenset[str] = frozenset(
    {"compliance_request", "feature_request", "security_incident", "unclear_request"}
)

CHANNELS: tuple[str, ...] = ("email", "chat", "docs_comment", "forum")


def _as_path(value: str) -> Path:
    p = Path(value.replace("sqlite:///", ""))
    return p if p.is_absolute() else (ROOT / p).resolve()


@dataclass(frozen=True)
class Config:
    provider: str = "groq"
    api_key: str = ""
    model_name: str = "qwen/qwen3.8-27b"

    retrieval_backend: str = "lexical"
    embedding_model: str = "all-MiniLM-L6-v2"
    chroma_path: Path = field(default_factory=lambda: ROOT / "storage" / "chroma")

    database_path: Path = field(default_factory=lambda: ROOT / "storage" / "decisions.db")
    cache_path: Path = field(default_factory=lambda: ROOT / "storage" / "llm_cache.sqlite")
    corpus_path: Path = field(default_factory=lambda: ROOT / "data" / "documentation.json")

    log_level: str = "INFO"
    confidence_threshold: float = 0.75
    retrieval_top_k: int = 3
    retrieval_min_score: float = 0.45
    tokens_per_minute: int = 8000
    request_timeout_s: float = 60.0
    max_attempts: int = 4
    # The longest this will wait out a provider throttle before giving up on a
    # ticket and escalating it. A support system does not hold a customer for
    # eight minutes because a free tier said so; it hands the ticket to a
    # person. This also bounds the run, which the gate depends on.
    max_throttle_wait_s: float = 90.0

    kill_switch_path: Path = field(default_factory=lambda: ROOT / "storage" / "KILL_SWITCH")

    @property
    def has_credentials(self) -> bool:
        # The placeholder shipped in .env.example counts as absent. Someone who
        # copies the file and forgets the key otherwise gets a 401 on every
        # ticket of an 80 ticket run, which reads as a broken key rather than
        # as a missing one and costs a run to work out.
        return bool(self.api_key) and self.api_key.strip() != "your_key_here"


def load_config(env_file: str | os.PathLike[str] | None = None) -> Config:
    """Read configuration from .env plus the process environment."""
    load_dotenv(env_file or (ROOT / ".env"), override=False)

    provider = os.getenv("LLM_PROVIDER", "groq").strip().lower()
    key_var = "OPENROUTER_API_KEY" if provider == "openrouter" else "GROQ_API_KEY"

    return Config(
        provider=provider,
        api_key=os.getenv(key_var, "").strip(),
        model_name=os.getenv("MODEL_NAME", "qwen/qwen3.8-27b").strip(),
        retrieval_backend=os.getenv("RETRIEVAL_BACKEND", "lexical").strip().lower(),
        embedding_model=os.getenv("EMBEDDING_MODEL", "all-MiniLM-L6-v2").strip(),
        chroma_path=_as_path(os.getenv("CHROMA_PATH", "./storage/chroma")),
        database_path=_as_path(os.getenv("DATABASE_URL", "sqlite:///./storage/decisions.db")),
        cache_path=_as_path(os.getenv("CACHE_PATH", "./storage/llm_cache.sqlite")),
        log_level=os.getenv("LOG_LEVEL", "INFO").strip().upper(),
        confidence_threshold=float(os.getenv("CONFIDENCE_THRESHOLD", "0.75")),
        retrieval_top_k=int(os.getenv("RETRIEVAL_TOP_K", "3")),
        retrieval_min_score=float(os.getenv("RETRIEVAL_MIN_SCORE", "0.45")),
        tokens_per_minute=int(os.getenv("TOKENS_PER_MINUTE", "8000")),
        request_timeout_s=float(os.getenv("REQUEST_TIMEOUT_S", "60")),
        max_attempts=int(os.getenv("MAX_ATTEMPTS", "4")),
        max_throttle_wait_s=float(os.getenv("MAX_THROTTLE_WAIT_S", "90")),
        kill_switch_path=_as_path(os.getenv("KILL_SWITCH_PATH", "./storage/KILL_SWITCH")),
    )
