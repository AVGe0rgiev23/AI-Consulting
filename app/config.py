import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = Path(os.environ.get("LEADGENIUS_DATA", BASE_DIR / "data"))
DATA_DIR.mkdir(parents=True, exist_ok=True)

DB_PATH = Path(os.environ.get("LEADGENIUS_DB", DATA_DIR / "leadgenius.db"))
EXPORT_DIR = DATA_DIR / "exports"
EXPORT_DIR.mkdir(parents=True, exist_ok=True)

SECRET_KEY = os.environ.get("LEADGENIUS_SECRET", "dev-insecure-change-me")
SESSION_COOKIE = "lg_session"

SEARCH_API_KEY = os.environ.get("SEARCH_API_KEY", "")

PROVIDER_KEY_VARS = {
    "groq": "GROQ_API_KEY",
    "gemini": "GEMINI_API_KEY",
    "openrouter": "OPENROUTER_API_KEY",
    "anthropic": "ANTHROPIC_API_KEY",
}

PROVIDER_PRIORITY = ["groq", "gemini", "openrouter", "anthropic"]

OPENAI_COMPAT_BASES = {
    "groq": "https://api.groq.com/openai/v1",
    "gemini": "https://generativelanguage.googleapis.com/v1beta/openai",
    "openrouter": "https://openrouter.ai/api/v1",
}

PROVIDER_MODELS = {
    "groq": ("llama-3.1-8b-instant", "llama-3.3-70b-versatile"),
    "gemini": ("gemini-2.5-flash-lite", "gemini-2.5-flash"),
    "openrouter": ("meta-llama/llama-3.3-70b-instruct:free", "deepseek/deepseek-chat-v3-0324:free"),
    "anthropic": ("claude-haiku-4-5-20251001", "claude-sonnet-5"),
}


def pick_provider(env=None):
    env = os.environ if env is None else env
    forced = env.get("LEADGENIUS_LLM_PROVIDER", "").strip().lower()
    if forced in PROVIDER_KEY_VARS:
        return forced
    for name in PROVIDER_PRIORITY:
        if env.get(PROVIDER_KEY_VARS[name], ""):
            return name
    return "anthropic"


LLM_PROVIDER = pick_provider()
LLM_API_KEY = os.environ.get(PROVIDER_KEY_VARS[LLM_PROVIDER], "")

MODEL_FAST = os.environ.get("LEADGENIUS_MODEL_FAST", PROVIDER_MODELS[LLM_PROVIDER][0])
MODEL_SMART = os.environ.get("LEADGENIUS_MODEL_SMART", PROVIDER_MODELS[LLM_PROVIDER][1])

USE_LLM_STUB = not LLM_API_KEY
USE_FETCH_STUB = os.environ.get("LEADGENIUS_FETCH_STUB", "1") == "1"
USE_SENDER_STUB = os.environ.get("LEADGENIUS_SENDER_STUB", "1") == "1"

INSTANTLY_API_BASE = "https://api.instantly.ai/api/v2"
SMARTLEAD_API_BASE = "https://server.smartlead.ai/api/v1"

STRIPE_SECRET_KEY = os.environ.get("STRIPE_SECRET_KEY", "")
STRIPE_WEBHOOK_SECRET = os.environ.get("STRIPE_WEBHOOK_SECRET", "")
USE_BILLING_STUB = not STRIPE_SECRET_KEY
APP_BASE_URL = os.environ.get("LEADGENIUS_BASE_URL", "http://127.0.0.1:8000")

STARTING_CREDITS = int(os.environ.get("LEADGENIUS_STARTING_CREDITS", "25"))
PLAN_SEATS = {"trial": 1, "starter": 1, "professional": 3, "agency": 10, "enterprise": 999}
PLAN_LEAD_CAPS = {"trial": 25, "starter": 500, "professional": 2000, "agency": 10000,
                  "enterprise": 100000}
RESEARCH_COST = 1
CRAWL_MAX_PAGES = 15
DOMAIN_CACHE_DAYS = 7
SEARCH_CACHE_DAYS = int(os.environ.get("LEADGENIUS_SEARCH_CACHE_DAYS", "3"))

CRAWL_TIME_BUDGET_SECONDS = float(os.environ.get("LEADGENIUS_CRAWL_BUDGET_S", "25"))
CRAWL_DELAY_SECONDS = float(os.environ.get("LEADGENIUS_CRAWL_DELAY_S", "1.0"))
CRAWL_MAX_DELAY_SECONDS = 5.0
CRAWL_RETRIES = 2
CRAWL_MAX_PAGE_BYTES = 1_500_000
CRAWL_CONTACT_URL = os.environ.get("LEADGENIUS_CONTACT_URL", f"{APP_BASE_URL}/bot")
CRAWL_USER_AGENT = f"LeadGeniusBot/1.0 (+{CRAWL_CONTACT_URL})"

DAILY_BUDGET_USD = float(os.environ.get("LEADGENIUS_DAILY_BUDGET_USD", "5.0"))
REQUEST_MAX_USD = float(os.environ.get("LEADGENIUS_REQUEST_MAX_USD", "0.10"))
DAILY_LLM_CALL_CAP = int(os.environ.get("LEADGENIUS_DAILY_LLM_CALLS", "1000"))
SEARCH_COST_USD = float(os.environ.get("LEADGENIUS_SEARCH_COST_USD", "0.01"))
LLM_MAX_INPUT_CHARS = int(os.environ.get("LEADGENIUS_LLM_MAX_INPUT_CHARS", "24000"))
LLM_MAX_OUTPUT_TOKENS = 1500

PROVIDER_PRICES_PER_M = {
    "groq": (0.0, 0.0),
    "gemini": (0.0, 0.0),
    "openrouter": (0.0, 0.0),
    "anthropic": (3.0, 15.0),
}
LLM_PRICE_IN_PER_M = float(
    os.environ.get("LEADGENIUS_PRICE_IN_PER_M", PROVIDER_PRICES_PER_M[LLM_PROVIDER][0])
)
LLM_PRICE_OUT_PER_M = float(
    os.environ.get("LEADGENIUS_PRICE_OUT_PER_M", PROVIDER_PRICES_PER_M[LLM_PROVIDER][1])
)

QUALITY_FLOOR = int(os.environ.get("LEADGENIUS_QUALITY_FLOOR", "40"))
APPROVAL_SCORE_FLOOR = int(os.environ.get("LEADGENIUS_APPROVAL_FLOOR", "40"))
STALE_SIGNAL_DAYS = int(os.environ.get("LEADGENIUS_STALE_SIGNAL_DAYS", "365"))

RATE_WINDOW_SECONDS = int(os.environ.get("LEADGENIUS_RATE_WINDOW_S", "600"))
UPLOADS_PER_WINDOW = int(os.environ.get("LEADGENIUS_UPLOADS_PER_WINDOW", "10"))
RESEARCH_RUNS_PER_WINDOW = int(os.environ.get("LEADGENIUS_RESEARCH_PER_WINDOW", "5"))
API_REQUESTS_PER_WINDOW = int(os.environ.get("LEADGENIUS_API_PER_WINDOW", "120"))

STALE_JOB_MINUTES = int(os.environ.get("LEADGENIUS_STALE_JOB_MINUTES", "15"))
MAX_JOB_ATTEMPTS = int(os.environ.get("LEADGENIUS_MAX_JOB_ATTEMPTS", "3"))
CONFIDENCE_HIGH = 70

BANNED_PHRASES = [
    "i came across your",
    "i came across you",
    "hope this email finds you",
    "hope you're doing well",
    "hope you are doing well",
    "i noticed you",
    "i noticed that you",
    "your amazing website",
    "amazing website",
    "revolutionize",
    "supercharge",
    "unleash",
    "game-changer",
    "game changer",
    "cutting-edge",
    "synergy",
    "circle back",
    "touch base",
    "i wanted to reach out",
    "i hope this message finds you",
    "to whom it may concern",
    "dear sir or madam",
    "we are excited to",
    "loved your recent post",
]
