import os
from pathlib import Path

from dotenv import load_dotenv

BACKEND_DIR = Path(__file__).resolve().parent.parent
REPO_ROOT = BACKEND_DIR.parent
DATA_DIR = BACKEND_DIR / "data"

load_dotenv(REPO_ROOT / ".env")

DATA_DIR.mkdir(parents=True, exist_ok=True)

DOSSIER_PATH = DATA_DIR / "dossier.json"
CHECKPOINT_PATH = DATA_DIR / "checkpoints.sqlite"
TOKEN_LOG_PATH = DATA_DIR / "token_log.jsonl"


def read_text(name, default=""):
    return (os.getenv(name) or default).strip()


def read_number(name, default):
    try:
        return int(read_text(name) or default)
    except ValueError:
        return default


def read_flag(name, default=False):
    value = read_text(name).lower()
    if not value:
        return default
    return value in {"1", "true", "yes", "on"}


OPENAI_API_KEY = read_text("OPENAI_API_KEY")
OPENAI_MODEL = read_text("OPENAI_MODEL", "gpt-5.6-luna")

OPENROUTER_API_KEY = read_text("OPENROUTER_API_KEY")
OPENROUTER_MODEL = read_text("OPENROUTER_MODEL", "openai/gpt-4o-mini")
OPENROUTER_BASE_URL = read_text("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")

TAVILY_API_KEY = read_text("TAVILY_API_KEY")

MODEL_TEMPERATURE = read_text("MODEL_TEMPERATURE", "0")
SEARCH_DEPTH = read_text("SEARCH_DEPTH", "advanced")

LANGSMITH_TRACING = read_flag("LANGSMITH_TRACING", False)
LANGSMITH_API_KEY = read_text("LANGSMITH_API_KEY")
LANGSMITH_PROJECT = read_text("LANGSMITH_PROJECT", "dossier")
LANGSMITH_ENDPOINT = read_text("LANGSMITH_ENDPOINT", "https://api.smith.langchain.com")

DJANGO_SECRET_KEY = read_text("DJANGO_SECRET_KEY", "dossier-local-dev-only")
DJANGO_DEBUG = read_flag("DJANGO_DEBUG", True)

MAX_RESEARCH_ITERATIONS = read_number("MAX_RESEARCH_ITERATIONS", 5)
RESEARCH_AGENT_MAX_STEPS = read_number("RESEARCH_AGENT_MAX_STEPS", 12)
RETRIEVAL_TOP_K = read_number("RETRIEVAL_TOP_K", 8)
SEARCH_RESULTS_PER_QUERY = read_number("SEARCH_RESULTS_PER_QUERY", 5)
FETCH_PAGE_MAX_CHARS = read_number("FETCH_PAGE_MAX_CHARS", 12000)

FRONTEND_ORIGINS = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
]

OPENAI_CONFIGURED = bool(OPENAI_API_KEY)
OPENROUTER_CONFIGURED = bool(OPENROUTER_API_KEY)
SEARCH_CONFIGURED = bool(TAVILY_API_KEY)


TRACING_CONFIGURED = LANGSMITH_TRACING and bool(LANGSMITH_API_KEY)


def apply_tracing_environment():
    if not TRACING_CONFIGURED:
        os.environ["LANGSMITH_TRACING"] = "false"
        return False
    os.environ["LANGSMITH_TRACING"] = "true"
    os.environ["LANGSMITH_API_KEY"] = LANGSMITH_API_KEY
    os.environ["LANGSMITH_PROJECT"] = LANGSMITH_PROJECT
    os.environ["LANGSMITH_ENDPOINT"] = LANGSMITH_ENDPOINT
    return True


TRACING_ENABLED = apply_tracing_environment()


def active_provider():
    if OPENAI_CONFIGURED:
        return "openai"
    if OPENROUTER_CONFIGURED:
        return "openrouter"
    return "none"


def active_model():
    if OPENAI_CONFIGURED:
        return OPENAI_MODEL
    if OPENROUTER_CONFIGURED:
        return OPENROUTER_MODEL
    return "none"
